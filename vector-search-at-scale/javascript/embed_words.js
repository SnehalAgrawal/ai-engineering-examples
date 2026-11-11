/**
 * Build a REAL embedding corpus by embedding a word list (the JavaScript twin of
 * python/embed_words.py). Writes embeddings.npy and items.txt in the same format,
 * so either language can use the file the other one produced.
 *
 * Usage:
 *   node embed_words.js                    # all words
 *   node embed_words.js --limit 100000     # first N items (faster / cheaper)
 *   node embed_words.js --input my.txt
 */
import { readFileSync, writeFileSync } from "node:fs";
import { createEmbeddings } from "./embeddings.js"; // same provider switch as Article #3's demo
import { writeNpy } from "./npy.js";

const BATCH = 256;
const RETRIES = 5;

function argument(name, fallback) {
  const i = process.argv.indexOf(name);
  return i === -1 ? fallback : process.argv[i + 1];
}

async function embedWithRetry(texts) {
  // Local model servers occasionally restart under load; retry with backoff.
  for (let attempt = 1; attempt <= RETRIES; attempt++) {
    try {
      return await createEmbeddings(texts);
    } catch (error) {
      if (attempt === RETRIES) throw error;
      const wait = 2 ** attempt;
      console.log(`  batch failed (${error.message}); retry ${attempt}/${RETRIES - 1} in ${wait}s`);
      await new Promise((resolve) => setTimeout(resolve, wait * 1000));
    }
  }
}

async function main() {
  const input = argument("--input", "/usr/share/dict/words");
  const limit = Number(argument("--limit", 0));
  let items = [...new Set(readFileSync(input, "utf8").split("\n").map((l) => l.trim()).filter(Boolean))];
  if (limit) items = items.slice(0, limit);
  console.log(`Embedding ${items.length.toLocaleString()} items (batch ${BATCH})...`);

  const start = performance.now();
  let matrix = null;
  let dims = 0;
  for (let i = 0; i < items.length; i += BATCH) {
    const vectors = await embedWithRetry(items.slice(i, i + BATCH));
    if (!matrix) {
      dims = vectors[0].length;
      matrix = new Float32Array(items.length * dims);
    }
    vectors.forEach((vector, j) => {
      const norm = Math.hypot(...vector); // normalize so dot product == cosine
      matrix.set(vector.map((x) => x / norm), (i + j) * dims);
    });
    if ((i / BATCH) % 50 === 0) {
      const done = Math.min(i + BATCH, items.length);
      const rate = done / ((performance.now() - start) / 1000);
      console.log(`  ${done.toLocaleString()}/${items.length.toLocaleString()}  (${Math.round(rate)} items/s)`);
    }
  }

  writeNpy("embeddings.npy", matrix, items.length, dims);
  writeFileSync("items.txt", items.join("\n"));
  console.log(`Saved embeddings.npy (${items.length}, ${dims}) in ${Math.round((performance.now() - start) / 1000)}s`);
}

main().catch((error) => {
  console.error("Error:", error.message);
  process.exit(1);
});
