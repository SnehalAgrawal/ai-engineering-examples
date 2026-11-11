/**
 * Part 1: exact search ("compare against everything") gets slower as the corpus grows.
 *
 * The cost depends only on how many vectors there are and how long they are, not on
 * what they mean, so random vectors are fine here. Plain JavaScript, no library:
 * this is exactly the loop from Article #3, at larger sizes.
 */
import { exactTopK, fmt, NUM_QUERIES, row, searchOneAtATime, seededRandom } from "./common.js";

const DIMENSIONS = 768;
const SIZES = [10_000, 50_000, 250_000];

function randomMatrix(rows, random) {
  const m = new Float32Array(rows * DIMENSIONS);
  for (let i = 0; i < m.length; i++) m[i] = random() * 2 - 1;
  return m;
}

const random = seededRandom(0);
const queries = randomMatrix(NUM_QUERIES, random);
console.log(`Exact search, ${DIMENSIONS} dimensions, ${NUM_QUERIES} queries, one at a time (Node.js ${process.version})\n`);

for (const n of SIZES) {
  const corpus = randomMatrix(n, random);
  const { medianMs, p95Ms } = searchOneAtATime(NUM_QUERIES, (i) => exactTopK(corpus, DIMENSIONS, row(queries, DIMENSIONS, i)));
  const mb = (corpus.byteLength / 1e6).toFixed(0).padStart(6);
  console.log(`  ${n.toLocaleString().padStart(9)} vectors (${mb} MB) | median ${fmt(medianMs, 2).padStart(6)} ms | p95 ${fmt(p95Ms, 2).padStart(6)} ms per query`);
}
