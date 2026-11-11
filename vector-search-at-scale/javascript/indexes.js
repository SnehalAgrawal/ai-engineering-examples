/**
 * Part 2: an approximate index (HNSW) trades a little recall for a lot of speed.
 *
 * Runs on REAL embeddings (from embed_words.js or ../python/embed_words.py).
 * Uses hnswlib-node, community-maintained Node.js bindings for hnswlib (a reference
 * HNSW implementation). IVF is not covered here: hnswlib only implements HNSW.
 * See ../python/indexes.py for the IVF comparison.
 *
 * recall@10 compares HNSW with exact search on the same data: "did the index find
 * the true nearest neighbours?", not "are the results relevant to a person?".
 */
import hnswlib from "hnswlib-node";
import { exactTopK, fmt, K, loadRealEmbeddings, recallAtK, row, searchOneAtATime, splitQueries } from "./common.js";

const { HierarchicalNSW } = hnswlib;
const { corpus, queries, n, numQueries, dims } = splitQueries(loadRealEmbeddings());
console.log(`Real embeddings: ${n.toLocaleString()} vectors x ${dims} dims | ${numQueries} held-out queries | k=${K} | Node.js ${process.version}\n`);

// Exact search: the ground truth (and its latency).
const exact = searchOneAtATime(numQueries, (i) => exactTopK(corpus, dims, row(queries, dims, i)));
console.log(`Exact (plain JS)  recall@10 1.000 | median ${fmt(exact.medianMs).padStart(7)} ms | p95 ${fmt(exact.p95Ms).padStart(7)} ms\n`);

// HNSW. hnswlib-node builds single-threaded, so this takes a few minutes.
const index = new HierarchicalNSW("ip", dims);
index.initIndex(n, 32, 64, 100); // maxElements, M, efConstruction, seed
let start = performance.now();
for (let i = 0; i < n; i++) index.addPoint(Array.from(row(corpus, dims, i)), i);
console.log(`HNSW (M=32, efConstruction=64): built in ${((performance.now() - start) / 1000).toFixed(1)} s (single-threaded)`);

const queryArrays = Array.from({ length: numQueries }, (_, i) => Array.from(row(queries, dims, i)));
for (const ef of [16, 32, 64, 128, 256]) {
  index.setEf(ef);
  const result = searchOneAtATime(numQueries, (i) => index.searchKnn(queryArrays[i], K).neighbors);
  console.log(`  efSearch ${String(ef).padStart(3)}    recall@10 ${fmt(recallAtK(result.ids, exact.ids))} | median ${fmt(result.medianMs).padStart(7)} ms | p95 ${fmt(result.p95Ms).padStart(7)} ms`);
}
