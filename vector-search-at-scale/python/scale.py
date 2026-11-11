"""
Part 1: exact search ("compare against everything") gets slower as the corpus grows.

Exact search cost depends only on how many vectors there are and how long they are,
not on what they mean, so random vectors are fine here. 768 dimensions matches
nomic-embed-text, the model used in Article #3 and in embed_words.py.
"""
import faiss
import numpy as np

from common import NUM_QUERIES, search_one_at_a_time

DIMENSIONS = 768
SIZES = (10_000, 50_000, 250_000)


def main():
    faiss.omp_set_num_threads(1)  # one query, one thread: like a single request
    rng = np.random.default_rng(0)
    queries = rng.standard_normal((NUM_QUERIES, DIMENSIONS)).astype("float32")
    print(f"Exact search, {DIMENSIONS} dimensions, {NUM_QUERIES} queries, one at a time (FAISS {faiss.__version__})\n")
    for n in SIZES:
        corpus = rng.standard_normal((n, DIMENSIONS)).astype("float32")
        index = faiss.IndexFlatIP(DIMENSIONS)
        index.add(corpus)
        _, median, p95 = search_one_at_a_time(index, queries)
        print(f"  {n:>9,} vectors ({corpus.nbytes / 1e6:6.0f} MB) | median {median:6.2f} ms | p95 {p95:6.2f} ms per query")


if __name__ == "__main__":
    main()
