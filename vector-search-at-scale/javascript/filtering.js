/**
 * Part 3: the filtering trap (the JavaScript twin of python/filtering.py).
 *
 * Each vector gets one of 20 tenant labels at random (5% each). Every query must
 * only return its own tenant's items. Strategies compared on REAL embeddings:
 *   1. Exact search on the tenant's items only   -> ground truth
 *   2. Post-filter: HNSW top-10, then drop other tenants
 *   3. Over-fetch: HNSW top-200, then filter, keep 10
 *   4. Filter during search: hnswlib's filter callback, at efSearch 64 and 256
 */
import hnswlib from "hnswlib-node";
import { exactTopK, fmt, K, loadRealEmbeddings, recallAtK, row, searchOneAtATime, seededRandom, SEED, splitQueries } from "./common.js";

const { HierarchicalNSW } = hnswlib;
const NUM_TENANTS = 20;
const OVERFETCH = 200;

const { corpus, queries, n, numQueries, dims } = splitQueries(loadRealEmbeddings());
const random = seededRandom(SEED);
const tenantOf = Int32Array.from({ length: n }, () => Math.floor(random() * NUM_TENANTS));
const queryTenant = Int32Array.from({ length: numQueries }, () => Math.floor(random() * NUM_TENANTS));
const idsByTenant = Array.from({ length: NUM_TENANTS }, () => []);
tenantOf.forEach((t, id) => idsByTenant[t].push(id));
console.log(`${n.toLocaleString()} real embeddings, ${NUM_TENANTS} tenants (~${Math.round(n / NUM_TENANTS).toLocaleString()} items each), k=${K}\n`);

const index = new HierarchicalNSW("ip", dims);
index.initIndex(n, 32, 64, 100);
for (let i = 0; i < n; i++) index.addPoint(Array.from(row(corpus, dims, i)), i);
const queryArrays = Array.from({ length: numQueries }, (_, i) => Array.from(row(queries, dims, i)));

const truth = [], post = [], over = [], during = [], duringWide = [];
for (let i = 0; i < numQueries; i++) {
  const t = queryTenant[i];
  const allowed = (label) => tenantOf[label] === t;
  truth.push(exactTopK(corpus, dims, row(queries, dims, i), K, idsByTenant[t]));

  index.setEf(64);
  post.push(index.searchKnn(queryArrays[i], K).neighbors.filter(allowed));
  over.push(index.searchKnn(queryArrays[i], OVERFETCH).neighbors.filter(allowed).slice(0, K));
  during.push(index.searchKnn(queryArrays[i], K, allowed).neighbors);
  index.setEf(256);
  duringWide.push(index.searchKnn(queryArrays[i], K, allowed).neighbors);
}

function report(name, results) {
  const counts = results.map((r) => r.length);
  const avg = counts.reduce((a, b) => a + b, 0) / counts.length;
  const empty = (counts.filter((c) => c === 0).length / counts.length) * 100;
  console.log(`  ${name.padEnd(32)} avg results ${fmt(avg, 2).padStart(5)}/${K} | queries with 0 results ${fmt(empty, 1).padStart(5)}% | recall@10 ${fmt(recallAtK(results, truth))}`);
}
report("Post-filter (top-10, then filter)", post);
report(`Over-fetch (top-${OVERFETCH}, then filter)`, over);
report("Filter during search (ef=64)", during);
report("Filter during search (ef=256)", duringWide);

// Latency on 100 queries: unfiltered vs filtering during search at both budgets.
const sample = 100;
index.setEf(64);
const plain = searchOneAtATime(sample, (i) => index.searchKnn(queryArrays[i], K).neighbors);
const filtered = {};
for (const ef of [64, 256]) {
  index.setEf(ef);
  filtered[ef] = searchOneAtATime(sample, (i) => index.searchKnn(queryArrays[i], K, (label) => tenantOf[label] === queryTenant[i]).neighbors);
}
console.log(`\n  Median latency: unfiltered (ef=64) ${fmt(plain.medianMs)} ms | filtered ef=64 ${fmt(filtered[64].medianMs)} ms | filtered ef=256 ${fmt(filtered[256].medianMs)} ms`);
