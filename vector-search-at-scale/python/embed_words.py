"""
Build a REAL embedding corpus by embedding a word list.

Why real embeddings: approximate indexes behave very differently on synthetic data
depending on how it is generated (tidy clusters make them look perfect; uniform noise
makes them look hopeless). Recall numbers only mean something on real embeddings.

Default input: /usr/share/dict/words (present on macOS; on Linux install a words
package such as `wamerican`, or pass any text file with one item per line).
The embedding provider comes from .env (see .env.example), exactly as in the
embeddings-semantic-search demo. Ollama is recommended: it is local and free.

Output: embeddings.npy (float32, unit-length) and items.txt, cached so the
benchmarks can rerun without re-embedding. Both are git-ignored.

Usage:
  python embed_words.py                    # all words
  python embed_words.py --limit 100000     # first N items (faster / cheaper)
  python embed_words.py --input my.txt
"""
import argparse
import time

import numpy as np

from embeddings import create_embeddings  # same provider switch as Article #3's demo

BATCH = 256
RETRIES = 5


def embed_with_retry(texts):
    """Embed one batch, retrying transient failures (local model servers do restart under load)."""
    for attempt in range(1, RETRIES + 1):
        try:
            return create_embeddings(texts)
        except Exception as error:  # network errors, HTTP 5xx/4xx from a restarting server
            if attempt == RETRIES:
                raise
            wait = 2 ** attempt
            print(f"  batch failed ({error}); retry {attempt}/{RETRIES - 1} in {wait}s", flush=True)
            time.sleep(wait)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="/usr/share/dict/words")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    with open(args.input, encoding="utf-8", errors="ignore") as f:
        items = list(dict.fromkeys(line.strip() for line in f if line.strip()))  # dedupe, keep order
    if args.limit:
        items = items[: args.limit]
    print(f"Embedding {len(items):,} items (batch {BATCH})...", flush=True)

    vectors, start = [], time.perf_counter()
    for i in range(0, len(items), BATCH):
        vectors.extend(embed_with_retry(items[i : i + BATCH]))
        if (i // BATCH) % 50 == 0:
            done = min(i + BATCH, len(items))
            print(f"  {done:,}/{len(items):,}  ({done / (time.perf_counter() - start):,.0f} items/s)", flush=True)

    matrix = np.asarray(vectors, dtype="float32")
    matrix /= np.linalg.norm(matrix, axis=1, keepdims=True)  # make dot product == cosine
    np.save("embeddings.npy", matrix)
    with open("items.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(items))
    print(f"Saved embeddings.npy {matrix.shape} in {time.perf_counter() - start:.0f}s", flush=True)


if __name__ == "__main__":
    main()
