# Vector Search at Scale

A runnable look at what changes when semantic search grows from a handful of documents to hundreds of thousands. It accompanies the article **[Vector Databases Explained: What Problem Are They Solving?](https://snehalagrawal.com/articles/vector-databases-explained/)**, and picks up where the [`embeddings-semantic-search`](../embeddings-semantic-search/) demo (Article #3) left off.

That demo compared a query with every document. This one measures why that stops scaling, what an index does instead, and the filtering trap that catches many real systems.

## What it demonstrates

1. **Exact search cost grows with the corpus.** Comparing the query against every vector gets linearly slower as you add vectors (`scale.py`).
2. **Approximate indexes trade a little recall for a lot of speed.** HNSW and IVF answer in a fraction of the time, at a measurable cost in accuracy, which you control with a search budget (`indexes.py`).
3. **Filters break naive approximate search.** "Only this customer's documents" can return almost nothing if you filter after searching. Filtering during the search fixes it, at a cost (`filtering.py`).

## Flow

```text
embed_words.py   word list ──► embedding model ──► embeddings.npy (cached, ~236k x 768)
scale.py         random vectors ──► exact search at 10k / 50k / 250k ──► latency per query
indexes.py       embeddings.npy ──► Flat (exact) | HNSW | IVF ──► recall@10 vs latency
filtering.py     embeddings.npy + 20 tenant labels ──► post-filter | over-fetch | filter during search
```

Why both random and real vectors? The cost of *exact* search depends only on how many vectors there are and how long they are, so random vectors measure it accurately (`scale.py`). Approximate search depends on the *shape* of the data: on synthetic data, the same index can look nearly perfect or nearly useless depending on how the data was generated. So recall is measured on **real embeddings** (`indexes.py`, `filtering.py`).

## Files

| File | Purpose |
|---|---|
| `python/embeddings.py` | Embedding provider (OpenAI or Ollama). Identical to the Article #3 demo |
| `python/embed_words.py` | Embeds a word list with retries; caches `embeddings.npy` and `items.txt` |
| `python/scale.py` | Exact search latency at growing corpus sizes |
| `python/indexes.py` | Exact vs HNSW vs IVF: recall@10, latency, build time, size |
| `python/filtering.py` | Per-tenant filtering: post-filter vs over-fetch vs filter during search |
| `python/common.py` | Shared helpers: loading, query hold-out, timing, recall@k |
| `javascript/embeddings.js` | Embedding provider (OpenAI or Ollama). Identical to the Article #3 demo |
| `javascript/embed_words.js` | Same as the Python version; writes the same `embeddings.npy` format |
| `javascript/scale.js` | Exact search latency, in plain JavaScript |
| `javascript/indexes.js` | Exact vs HNSW: recall@10 and latency |
| `javascript/filtering.js` | The same filtering comparison as the Python version |
| `javascript/common.js`, `javascript/npy.js` | Shared helpers, and a small reader/writer for NumPy's `.npy` format |

### Python and JavaScript are not identical

The article's numbers come from the **Python** version, which uses [FAISS](https://github.com/facebookresearch/faiss). FAISS has official Python and C++ bindings, but not JavaScript. The **JavaScript** version uses [`hnswlib-node`](https://github.com/yoshoku/hnswlib-node), community-maintained Node.js bindings for [hnswlib](https://github.com/nmslib/hnswlib), and plain JavaScript loops for exact search. So:

- It covers exact search, HNSW, and filtering, but **not IVF**, because hnswlib only implements HNSW.
- Its numbers differ from the article's: different library, different query sample, and single-threaded index builds. The patterns are the same.
- Both versions read and write the same `embeddings.npy` file, so you only need to embed once. Copy it between `python/` and `javascript/`.

## Prerequisites

- Python 3.9+ **or** Node.js 18+
- About 3 GB of free memory for the index experiments
- An embedding provider, used only by `embed_words.py` / `embed_words.js`:
  - **Ollama** (recommended: local and free): [install Ollama](https://ollama.com/download), then `ollama pull nomic-embed-text`
  - **OpenAI**: an API key. Embedding the full word list costs money, so consider `--limit`
- A word list. macOS includes `/usr/share/dict/words` (Webster's Second International; its README notes that the 1934 copyright has lapsed). On Linux, install a words package such as `wamerican`, or pass any text file with one item per line.

## Configuration

Copy `.env.example` to `.env` inside `python/` or `javascript/`. Settings load automatically.

| Variable | Default | Notes |
|---|---|---|
| `EMBEDDING_PROVIDER` | `ollama` in `.env.example` | `ollama` or `openai` |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | |
| `OLLAMA_EMBEDDING_MODEL` | `nomic-embed-text` | |
| `OPENAI_API_KEY` | none | Required for OpenAI |
| `OPENAI_EMBEDDING_MODEL` | `text-embedding-3-small` | |

Never commit your `.env` file. The repository `.gitignore` excludes it, and each folder's `.gitignore` excludes the generated `embeddings.npy` and `items.txt`.

## How to run

### Python

```bash
cd python
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # then edit it

python embed_words.py           # one-time: builds embeddings.npy (~17 min for 236k words locally)
python scale.py                 # ~10 s
python indexes.py               # ~1 min
python filtering.py             # ~1 min
```

### JavaScript

```bash
cd javascript
npm install
cp .env.example .env            # then edit it

node embed_words.js             # one-time; or copy embeddings.npy from ../python/
node scale.js                   # ~1.5 min (plain JavaScript loops)
node indexes.js                 # several minutes: exact baseline + single-threaded HNSW build
node filtering.js               # several minutes
```

`scale.py` / `scale.js` do not need `embeddings.npy` and can run first. For a faster first try, use `python embed_words.py --limit 50000`. The index and filtering numbers will differ from the article's, but the patterns hold.

## Expected output

The article's numbers came from this setup:

| Setting | Value |
|---|---|
| Machine | Apple M4 Pro (12 cores, 24 GB), macOS 26.6.2 |
| Python / libraries | Python 3.12.13, faiss-cpu 1.16.0, numpy 2.5.4 |
| Embeddings | Ollama 0.40.1, `nomic-embed-text:latest` (ID `0a109f422b47`), 768 dimensions |
| Corpus | `/usr/share/dict/words`, 235,976 items; 500 held out as queries (seed 42) |
| Search | One query at a time, one thread, k = 10 |
| HNSW | M = 32, efConstruction = 64 |
| IVF | nlist = 1024, trained on the 235,476 indexed vectors (the 500 held-out queries are not used for training) |

Latency depends heavily on hardware. Recall is primarily determined by the dataset, the query set, how the index was built, and the search parameters, so the same settings can give very different recall on a different corpus. Each script was run twice: recall was identical and latency stayed within about 3%.

**`scale.py`**: exact search grows linearly with corpus size.

```text
     10,000 vectors (    31 MB) | median   0.39 ms | p95   0.42 ms per query
     50,000 vectors (   154 MB) | median   1.99 ms | p95   2.05 ms per query
    250,000 vectors (   768 MB) | median  10.16 ms | p95  10.46 ms per query
```

**`indexes.py`**: on real embeddings.

```text
Exact (Flat)      recall@10 1.000 | median  9.587 ms | p95  9.786 ms |   723 MB

HNSW (M=32, efConstruction=64): built in 43.1 s, 787 MB
  efSearch  16    recall@10 0.909 | median  0.063 ms | p95  0.101 ms
  efSearch  32    recall@10 0.945 | median  0.099 ms | p95  0.145 ms
  efSearch  64    recall@10 0.962 | median  0.169 ms | p95  0.237 ms
  efSearch 128    recall@10 0.971 | median  0.310 ms | p95  0.432 ms
  efSearch 256    recall@10 0.986 | median  0.584 ms | p95  0.811 ms

IVF (nlist=1024): trained and built in 2.8 s, 728 MB
  nprobe   1      recall@10 0.616 | median  0.059 ms | p95  0.075 ms
  nprobe   4      recall@10 0.801 | median  0.092 ms | p95  0.122 ms
  nprobe  16      recall@10 0.882 | median  0.227 ms | p95  0.280 ms
  nprobe  64      recall@10 0.935 | median  0.756 ms | p95  0.855 ms
```

**`filtering.py`**: 20 tenants, about 5% of the data each.

```text
  Post-filter (top-10, then filter) avg results  0.51/10 | queries with 0 results  61.0% | recall@10 0.051
  Over-fetch (top-200, then filter) avg results  8.70/10 | queries with 0 results   0.0% | recall@10 0.761
  Filter during search (ef=64)     avg results 10.00/10 | queries with 0 results   0.0% | recall@10 0.787
  Filter during search (ef=256)    avg results 10.00/10 | queries with 0 results   0.0% | recall@10 0.948

  Median latency: unfiltered (ef=64) 0.179 ms | filtered ef=64 0.175 ms | filtered ef=256 0.633 ms
```

### JavaScript

Same machine and the same `embeddings.npy`, with Node.js v24.16.0 and `hnswlib-node` 3.0.0. The 500 query words differ from the Python run: both use seed 42, but NumPy and the JavaScript helper are different random generators, which pick different queries and tenant labels. Each script was run twice: recall was identical and latency stayed within about 3%.

**`scale.js`**: the same linear growth. Plain JavaScript loops are about 12–14× slower than FAISS's optimized native code, which is why libraries matter even for exact search.

```text
     10,000 vectors (    31 MB) | median   4.75 ms | p95   4.96 ms per query
     50,000 vectors (   154 MB) | median  24.06 ms | p95  25.12 ms per query
    250,000 vectors (   768 MB) | median 140.65 ms | p95 144.99 ms per query
```

**`indexes.js`**: HNSW recall closely matches FAISS with the same `M` and `efConstruction`, on a different query sample. Per-query latency is 2.3–3.2× FAISS's on this machine, depending on `efSearch`. The build runs on one thread, against FAISS's 12.

```text
Exact (plain JS)  recall@10 1.000 | median 118.441 ms | p95 126.094 ms

HNSW (M=32, efConstruction=64): built in 137.9 s (single-threaded)
  efSearch  16    recall@10 0.893 | median   0.199 ms | p95   0.297 ms
  efSearch  32    recall@10 0.927 | median   0.281 ms | p95   0.403 ms
  efSearch  64    recall@10 0.955 | median   0.435 ms | p95   0.654 ms
  efSearch 128    recall@10 0.973 | median   0.735 ms | p95   1.129 ms
  efSearch 256    recall@10 0.980 | median   1.315 ms | p95   1.985 ms
```

**`filtering.js`**: post-filtering fails the same way. Filtering during search behaves differently from FAISS.

```text
  Post-filter (top-10, then filter) avg results  0.51/10 | queries with 0 results  57.2% | recall@10 0.051
  Over-fetch (top-200, then filter) avg results  8.74/10 | queries with 0 results   0.0% | recall@10 0.844
  Filter during search (ef=64)     avg results 10.00/10 | queries with 0 results   0.0% | recall@10 0.987
  Filter during search (ef=256)    avg results 10.00/10 | queries with 0 results   0.0% | recall@10 0.996

  Median latency: unfiltered (ef=64) 0.443 ms | filtered ef=64 6.256 ms | filtered ef=256 20.877 ms
```

The two libraries make opposite trade-offs when filtering during search:

| | Recall@10 (ef=64) | Median latency (ef=64) |
|---|---|---|
| FAISS (Python) | 0.787 | 0.175 ms, about the same as unfiltered |
| hnswlib (JavaScript) | 0.987 | 6.256 ms, about 14× unfiltered |

FAISS keeps its latency and loses recall. hnswlib keeps exploring until it has found enough matching results, so it keeps its recall and spends the time instead. A separate measurement on the first 100 queries showed where the time goes:

- hnswlib checked the filter about **2,817 times per query** with the tenant filter, against **183** with a filter that allows everything.
- Calling a JavaScript filter function adds little on its own: 0.466 ms with the allow-everything filter, against 0.435 ms with no filter.

So the extra time comes from extra graph exploration, not from JavaScript. Filtered-search behavior depends on the implementation: measure the one you use, with your real filter selectivity.

Note on recall: here, recall@10 means "did the index find the same 10 neighbours that exact search finds?" It measures the index, not whether the results are relevant to a person. Relevance needs labeled queries (see Article #3).

## Things to try

- Change `efSearch` or `nprobe` and watch the recall and latency trade-off move.
- Change `M` or `efConstruction` in `indexes.py`: higher values build slower and use more memory, but give a better graph.
- Change `NUM_TENANTS` in `filtering.py`. With 2 tenants (50% of the data each), post-filtering mostly works. With 100 tenants (1% each), it almost never does.
- Run `embed_words.py --limit 20000` and rerun `indexes.py`: on a small corpus, exact search is already fast enough.
- Replace the word list with your own documents (`--input your_file.txt`) and measure on your data.

## Limitations

This is an educational benchmark, not a product comparison.

- Single words are short inputs. Real document chunks produce different embeddings, so measure on your own data before choosing settings.
- Queries run one at a time on one thread. A production server handles many queries concurrently, with different overheads.
- FAISS and hnswlib are index libraries, not databases. They can save an index to a file, but they do not manage durable storage, concurrent updates, replication, or access control, and FAISS's HNSW index cannot remove individual vectors. Those are the things a vector database adds. See the article.
- Tenant labels are assigned at random. Real filters are often correlated with content, which changes how each strategy behaves.
