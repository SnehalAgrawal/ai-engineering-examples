"""Shared helpers for the demo scripts."""
import time

import numpy as np

K = 10
NUM_QUERIES = 500
SEED = 42


def load_real_embeddings(path="embeddings.npy"):
    """Load the cached real embeddings (run embed_words.py first)."""
    try:
        matrix = np.load(path)
    except FileNotFoundError:
        raise SystemExit("embeddings.npy not found. Run `python embed_words.py` first.")
    return matrix


def split_queries(matrix, num_queries=NUM_QUERIES, seed=SEED):
    """Hold out random rows as queries so they are not in the searched corpus."""
    rng = np.random.default_rng(seed)
    order = rng.permutation(len(matrix))
    queries = matrix[order[:num_queries]]
    corpus = matrix[order[num_queries:]]
    return np.ascontiguousarray(corpus), np.ascontiguousarray(queries)


def search_one_at_a_time(index, queries, k=K, params=None):
    """Search queries one by one (like individual requests). Returns ids, median ms, p95 ms."""
    ids, timings = [], []
    for q in queries:
        start = time.perf_counter()
        if params is None:
            _, found = index.search(q.reshape(1, -1), k)
        else:
            _, found = index.search(q.reshape(1, -1), k, params=params)
        timings.append((time.perf_counter() - start) * 1000)
        ids.append(found[0])
    return np.array(ids), float(np.median(timings)), float(np.percentile(timings, 95))


def recall_at_k(approx_ids, exact_ids):
    """Share of the exact top-k that the approximate search also found (ignores -1 padding)."""
    scores = []
    for approx, exact in zip(approx_ids, exact_ids):
        exact_set = {i for i in exact if i >= 0}
        if exact_set:
            scores.append(len({i for i in approx if i >= 0} & exact_set) / len(exact_set))
    return float(np.mean(scores))
