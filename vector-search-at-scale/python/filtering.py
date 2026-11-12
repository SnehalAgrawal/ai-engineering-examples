"""
Part 3: the filtering trap.

Real systems rarely search "everything". They search "this customer's documents",
"documents this user may see", or "articles in English". Here each vector gets one of
20 tenant labels at random (5% each), and every query must only return its tenant's items.

Compares four strategies on REAL embeddings:
  1. Exact search on the tenant's items only   -> ground truth
  2. Post-filter: ANN top-10, then drop other tenants
  3. Over-fetch: ANN top-200, then filter, keep 10
  4. Filter during search: the index only considers allowed ids
     (at the default search budget, efSearch=64, and at a larger one, efSearch=256)
"""
import time

import faiss
import numpy as np

from common import SEED, K, load_real_embeddings, recall_at_k, search_one_at_a_time, split_queries

NUM_TENANTS = 20
OVERFETCH = 200


def main():
    corpus, queries = split_queries(load_real_embeddings())
    n, d = corpus.shape
    rng = np.random.default_rng(SEED)
    tenant_of = rng.integers(0, NUM_TENANTS, size=n)
    query_tenant = rng.integers(0, NUM_TENANTS, size=len(queries))
    print(f"{n:,} real embeddings, {NUM_TENANTS} tenants (~{n // NUM_TENANTS:,} items each), k={K}\n")

    faiss.omp_set_num_threads(0)
    hnsw = faiss.IndexHNSWFlat(d, 32, faiss.METRIC_INNER_PRODUCT)
    hnsw.hnsw.efConstruction = 64
    hnsw.add(corpus)
    hnsw.hnsw.efSearch = 64
    faiss.omp_set_num_threads(1)

    truth, post, over, during, during_wide = [], [], [], [], []
    for q, t in zip(queries, query_tenant):
        allowed = np.flatnonzero(tenant_of == t).astype("int64")
        q1 = q.reshape(1, -1)

        # 1. Ground truth: exact search over this tenant's items.
        scores = corpus[allowed] @ q
        truth.append(allowed[np.argsort(-scores)[:K]])

        # 2. Post-filter: ask for 10, then throw away other tenants' results.
        _, ids = hnsw.search(q1, K)
        post.append([i for i in ids[0] if i >= 0 and tenant_of[i] == t])

        # 3. Over-fetch: ask for 200, filter, keep the best 10.
        _, ids = hnsw.search(q1, OVERFETCH)
        over.append([i for i in ids[0] if i >= 0 and tenant_of[i] == t][:K])

        # 4. Filter during search, at two search budgets.
        selector = faiss.IDSelectorBatch(allowed)
        _, ids = hnsw.search(q1, K, params=faiss.SearchParametersHNSW(sel=selector, efSearch=64))
        during.append([i for i in ids[0] if i >= 0])
        _, ids = hnsw.search(q1, K, params=faiss.SearchParametersHNSW(sel=selector, efSearch=256))
        during_wide.append([i for i in ids[0] if i >= 0])

    def report(name, results):
        counts = [len(r) for r in results]
        padded = [list(r) + [-1] * (K - len(r)) for r in results]
        print(f"  {name:<32} avg results {np.mean(counts):5.2f}/{K} | "
              f"queries with 0 results {np.mean([c == 0 for c in counts]) * 100:5.1f}% | "
              f"recall@10 {recall_at_k(padded, truth):.3f}")

    report("Post-filter (top-10, then filter)", post)
    report(f"Over-fetch (top-{OVERFETCH}, then filter)", over)
    report("Filter during search (ef=64)", during)
    report("Filter during search (ef=256)", during_wide)

    # Latency: unfiltered search vs filtering during search at both budgets.
    sample_queries = queries[:100]
    sample_tenants = query_tenant[:100]
    _, med_plain, _ = search_one_at_a_time(hnsw, sample_queries)
    medians = {}
    for ef in (64, 256):
        timings = []
        for q, t in zip(sample_queries, sample_tenants):
            allowed = np.flatnonzero(tenant_of == t).astype("int64")
            params = faiss.SearchParametersHNSW(sel=faiss.IDSelectorBatch(allowed), efSearch=ef)
            start = time.perf_counter()
            hnsw.search(q.reshape(1, -1), K, params=params)
            timings.append((time.perf_counter() - start) * 1000)
        medians[ef] = float(np.median(timings))
    print(f"\n  Median latency: unfiltered (ef=64) {med_plain:.3f} ms | "
          f"filtered ef=64 {medians[64]:.3f} ms | filtered ef=256 {medians[256]:.3f} ms")

if __name__ == "__main__":
    main()
