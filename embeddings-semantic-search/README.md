# Embeddings and Semantic Search

A small, runnable example of semantic search with text embeddings. It accompanies the article **[Embeddings Explained: The Building Block Behind Semantic Search](https://snehalagrawal.com/articles/embeddings-explained/)**.

The demo puts keyword search and embedding-based search side by side over the same five help-center documents, so you can see both where embeddings help and where they mislead.

## What it demonstrates

1. **Keyword search fails on vocabulary mismatch.** "How do I get my money back?" shares no keywords with "Customers can request a refund within 30 days of purchase."
2. **Embeddings retrieve by meaning.** The same query, embedded with the same model as the documents, ranks the refund document first.
3. **Similarity is not correctness.** Try `"How do I start a subscription?"`. The top result is the document about *cancelling* a subscription, with a high score.
4. **Scores are relative, not absolute.** Unrelated documents still get non-trivial scores, and an off-topic query still returns a ranked list.

## Flow

```text
Index time:  documents ──► embedding model ──► document vectors (kept in memory)
Query time:  query     ──► same model      ──► query vector
             query vector vs. every document vector ──► cosine similarity ──► ranked results
```

The same logic is implemented in Python and JavaScript.

| File | Purpose |
|---|---|
| `python/embeddings.py`, `javascript/embeddings.js` | Calls the embedding provider (OpenAI or Ollama), batched |
| `python/search.py`, `javascript/search.js` | Documents, keyword baseline, cosine similarity, ranking |

## Prerequisites

- Python 3.9+ **or** Node.js 18+
- One embedding provider:
  - **OpenAI**: an API key, or
  - **Ollama** (local, no API key): [install Ollama](https://ollama.com/download), then run `ollama pull nomic-embed-text`

## Configuration

Copy `.env.example` to `.env` inside `python/` or `javascript/` and edit it. Both implementations load `.env` automatically. Plain environment variables work too.

| Variable | Default | Notes |
|---|---|---|
| `EMBEDDING_PROVIDER` | `openai` | `openai` or `ollama` |
| `OPENAI_API_KEY` | none | Required for OpenAI |
| `OPENAI_EMBEDDING_MODEL` | `text-embedding-3-small` | |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | |
| `OLLAMA_EMBEDDING_MODEL` | `nomic-embed-text` | |
| `QUERY_PREFIX` / `DOCUMENT_PREFIX` | empty | Task prefixes for models trained with them (e.g. nomic-embed-text uses `search_query: ` and `search_document: `) |

Never commit your `.env` file. The repository `.gitignore` excludes it.

## How to run

### Python

```bash
cd python
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then edit it
python search.py
```

### JavaScript

```bash
cd javascript
npm install
cp .env.example .env   # then edit it
node search.js
```

### Your own queries

Pass one or more queries as arguments:

```bash
python search.py "How do I start a subscription?" "Can I get a refund after 45 days?"
node search.js "What is the weather in Paris?"
```

## Expected output

Exact scores depend on the model, the provider, and whether you use task prefixes. The scores quoted in the article were produced with this setup:

| Setting | Value |
|---|---|
| Ollama version | 0.40.1 (`ollama --version`) |
| Endpoint | `POST /api/embed` (returns unit-length vectors) |
| Model tag | `nomic-embed-text:latest` |
| Ollama model ID | `0a109f422b47` (shown by `ollama list`; full config digest `sha256:0a109f422b47e3a30ba2b10eca18548e944e8a23073ee3f3e947efcf3c45e59f`) |
| Weights digest | `sha256:970aa74c0a90ef7482477cf803618e776e173c007bf957f635f1015bfcfef0e6` (the blob named in `ollama show --modelfile nomic-embed-text`) |
| Model details | `nomic-bert` architecture, 137M parameters, F16, context length 2,048 tokens |
| Dimensions | 768 |
| Prefixes | Run 1: none (the demo default). Run 2: `QUERY_PREFIX="search_query: "`, `DOCUMENT_PREFIX="search_document: "` |
| Similarity | Cosine, printed to 4 decimal places |

`latest` is a moving tag, not a version. Before comparing your numbers with the article, check that `ollama list` shows ID `0a109f422b47` for `nomic-embed-text` and that `ollama show --modelfile nomic-embed-text` points at the weights digest above. If either differs, expect different digits but the same overall pattern.

To reproduce the article's numbers (Python shown; `node search.js` takes the same arguments and printed identical output):

```bash
export EMBEDDING_PROVIDER=ollama
QUERIES=("How do I get my money back?" "I want to stop paying for this every month" \
  "I can't log in to my account" "How do I start a subscription?" \
  "Can I get a refund after 45 days?" "refund" "What is the weather in Paris?" \
  "Wie bekomme ich mein Geld zurück?")

# Default: no prefixes
python search.py "${QUERIES[@]}"

# With nomic-embed-text's task prefixes
QUERY_PREFIX="search_query: " DOCUMENT_PREFIX="search_document: " python search.py "${QUERIES[@]}"
```

With that setup and no prefixes, the first query produced:

```text
Query: How do I get my money back?

Keyword search (shared words):
  No document shares a meaningful keyword with the query.

Semantic search (cosine similarity):
  0.5839 | Customers can request a refund within 30 days of purchase.
  0.5608 | To cancel your subscription, go to Settings > Billing > Cancel.
  0.5463 | Billing issues can be resolved by contacting our accounting department.
  0.5341 | If you forgot your password, click 'Forgot Password' on the login page.
  0.4138 | Our support team is available 24/7 via live chat.
```

The refund document wins, but notice how small the margin is. That is part of the lesson.

Notes from running it:

- Repeated runs, and the Python and JavaScript versions, produced identical scores in this setup.
- `/api/embed` returned unit-length vectors. Ollama's older `/api/embeddings` endpoint returned unnormalized vectors (length ≈ 22) from the same model, so this demo uses `/api/embed`.
- `/api/embed` silently truncates input longer than the model's context (2,048 tokens for this build) unless you pass `"truncate": false`. The demo documents are short, so this doesn't affect them.

## Things to try

- `"How do I start a subscription?"`: there is no such document. What comes back first, and with what score?
- `"Can I get a refund after 45 days?"`: retrieval finds the right document, but does that document say "yes"?
- `"What is the weather in Paris?"`: a completely off-topic query still returns a ranked list.
- A query in another language: compare an English-focused model with a multilingual one.
- Set `QUERY_PREFIX` / `DOCUMENT_PREFIX` for `nomic-embed-text` and see how the scores shift.
- Switch providers: scores from different models are not comparable with each other.

## Limitations

This is an educational demo, not a production search system.

- Similarity is computed by comparing the query with every document in memory. That is fine for five documents and does not scale. Vector indexes and vector databases address this (the next article in the series).
- The keyword baseline is a naive shared-word count, not a real ranking function such as BM25.
- There is no relevance threshold, no metadata filtering, no hybrid search, and no reranking.
- `cosine_similarity` raises an error on mismatched dimensions or zero vectors rather than returning a misleading score.
- Document embeddings are recomputed on every run instead of being stored.
