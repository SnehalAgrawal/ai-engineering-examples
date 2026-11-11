"""
Part 2: approximate indexes trade a little recall for a lot of speed.

Runs on REAL embeddings (from embed_words.py). 500 items are held out as queries.
For each index, recall@10 is measured against exact search on the same data:
it answers "did the index find the true nearest neighbours?", not "are the results
relevant to a human?" (that needs labeled queries; see Article #3).
"""
import time

import faiss

from common import K, load_real_embeddings, recall_at_k, search_one_at_a_time, split_queries


def size_mb(index):
    return faiss.serialize_index(index).nbytes / 1e6


def main():
    corpus, queries = split_queries(load_real_embeddings())
    n, d = corpus.shape
    print(f"Real embeddings: {n:,} vectors x {d} dims | {len(queries)} held-out queries | k={K} | FAISS {faiss.__version__}\n")

    faiss.omp_set_num_threads(1)
    flat = faiss.IndexFlatIP(d)
    flat.add(corpus)
    exact_ids, med, p95 = search_one_at_a_time(flat, queries)
    print(f"Exact (Flat)      recall@10 1.000 | median {med:6.3f} ms | p95 {p95:6.3f} ms | {size_mb(flat):5.0f} MB\n")

    # HNSW: a layered graph you walk from far-away "hubs" toward the query's neighbourhood.
    faiss.omp_set_num_threads(0)
    hnsw = faiss.IndexHNSWFlat(d, 32, faiss.METRIC_INNER_PRODUCT)
    hnsw.hnsw.efConstruction = 64
    start = time.perf_counter()
    hnsw.add(corpus)
    print(f"HNSW (M=32, efConstruction=64): built in {time.perf_counter() - start:.1f} s, {size_mb(hnsw):.0f} MB")
    faiss.omp_set_num_threads(1)
    for ef in (16, 32, 64, 128, 256):
        hnsw.hnsw.efSearch = ef
        ids, med, p95 = search_one_at_a_time(hnsw, queries)
        print(f"  efSearch {ef:>3}    recall@10 {recall_at_k(ids, exact_ids):.3f} | median {med:6.3f} ms | p95 {p95:6.3f} ms")
    print()

    # IVF: cluster the vectors into "sections", then search only the nearest few sections.
    faiss.omp_set_num_threads(0)
    nlist = 1024
    ivf = faiss.IndexIVFFlat(faiss.IndexFlatIP(d), d, nlist, faiss.METRIC_INNER_PRODUCT)
    start = time.perf_counter()
    ivf.train(corpus)
    ivf.add(corpus)
    print(f"IVF (nlist={nlist}): trained and built in {time.perf_counter() - start:.1f} s, {size_mb(ivf):.0f} MB")
    faiss.omp_set_num_threads(1)
    for nprobe in (1, 4, 16, 64):
        ivf.nprobe = nprobe
        ids, med, p95 = search_one_at_a_time(ivf, queries)
        print(f"  nprobe {nprobe:>3}      recall@10 {recall_at_k(ids, exact_ids):.3f} | median {med:6.3f} ms | p95 {p95:6.3f} ms")


if __name__ == "__main__":
    main()
