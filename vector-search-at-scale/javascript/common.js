// Shared helpers for the demo scripts (the JavaScript twin of python/common.py).
import { existsSync } from "node:fs";
import { readNpy } from "./npy.js";

export const K = 10;
export const NUM_QUERIES = 500;
export const SEED = 42;

/** Small deterministic random number generator (mulberry32), so runs are repeatable. */
export function seededRandom(seed = SEED) {
  let state = seed >>> 0;
  return () => {
    state = (state + 0x6d2b79f5) >>> 0;
    let t = state;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Load the cached real embeddings (run embed_words.js first). */
export function loadRealEmbeddings(path = "embeddings.npy") {
  if (!existsSync(path)) {
    console.error("embeddings.npy not found. Run `node embed_words.js` first (or copy it from ../python/).");
    process.exit(1);
  }
  return readNpy(path);
}

/** Hold out random rows as queries so they are not in the searched corpus. */
export function splitQueries({ data, rows, cols }, numQueries = NUM_QUERIES, seed = SEED) {
  const random = seededRandom(seed);
  const order = Array.from({ length: rows }, (_, i) => i);
  for (let i = rows - 1; i > 0; i--) {
    const j = Math.floor(random() * (i + 1));
    [order[i], order[j]] = [order[j], order[i]];
  }
  const pick = (ids) => {
    const out = new Float32Array(ids.length * cols);
    ids.forEach((id, r) => out.set(data.subarray(id * cols, (id + 1) * cols), r * cols));
    return out;
  };
  const queryIds = order.slice(0, numQueries);
  const corpusIds = order.slice(numQueries);
  return {
    corpus: pick(corpusIds),
    queries: pick(queryIds),
    n: corpusIds.length,
    numQueries,
    dims: cols,
  };
}

/** Row `i` of a row-major matrix, as a view (no copy). */
export const row = (matrix, dims, i) => matrix.subarray(i * dims, (i + 1) * dims);

/**
 * Exact top-k by inner product: compares the query with every candidate row.
 * `candidates` is an optional list of row ids to restrict the search to (for filtering).
 */
export function exactTopK(corpus, dims, query, k = K, candidates = null) {
  const best = []; // [{ id, score }], kept sorted by score, descending
  const total = candidates ? candidates.length : corpus.length / dims;
  for (let c = 0; c < total; c++) {
    const id = candidates ? candidates[c] : c;
    let score = 0;
    const offset = id * dims;
    for (let j = 0; j < dims; j++) score += corpus[offset + j] * query[j];
    if (best.length < k || score > best[best.length - 1].score) {
      let pos = best.length;
      while (pos > 0 && best[pos - 1].score < score) pos--;
      best.splice(pos, 0, { id, score });
      if (best.length > k) best.pop();
    }
  }
  return best.map((b) => b.id);
}

/** Run `searchFn(queryIndex)` once per query; return { ids, medianMs, p95Ms }. */
export function searchOneAtATime(numQueries, searchFn) {
  const ids = [];
  const timings = [];
  for (let i = 0; i < numQueries; i++) {
    const start = performance.now();
    ids.push(searchFn(i));
    timings.push(performance.now() - start);
  }
  timings.sort((a, b) => a - b);
  const pct = (p) => timings[Math.min(timings.length - 1, Math.floor(p * timings.length))];
  return { ids, medianMs: pct(0.5), p95Ms: pct(0.95) };
}

/** Share of the exact top-k that the approximate search also found. */
export function recallAtK(approxIds, exactIds) {
  let total = 0;
  let counted = 0;
  approxIds.forEach((approx, i) => {
    const exact = new Set(exactIds[i]);
    if (exact.size === 0) return;
    total += approx.filter((id) => exact.has(id)).length / exact.size;
    counted++;
  });
  return total / counted;
}

export const fmt = (x, digits = 3) => x.toFixed(digits);
