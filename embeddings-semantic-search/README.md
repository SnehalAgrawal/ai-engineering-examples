# Embeddings and Semantic Search Demo

This repository provides a minimal, reproducible implementation of semantic search using text embeddings. It accompanies **Article #3: Embeddings Explained** on [snehalagrawal.com](https://snehalagrawal.com).

## Conceptual Flow

The demo demonstrates the core pipeline of semantic search:
`Text` $\rightarrow$ `Embedding Model` $\rightarrow$ `Vector` $\rightarrow$ `Similarity Calculation` $\rightarrow$ `Ranking`.

Unlike keyword search, semantic search finds documents that are conceptually related to the query, even if they share no common words.

## Implementations

The same logic is implemented in both Python and JavaScript to demonstrate that embeddings are a language-agnostic data concept.

### Python
- `embeddings.py`: Handles the interaction with the embedding provider.
- `search.py`: Implements the document collection, embedding generation, and cosine similarity ranking.

### JavaScript
- `embeddings.js`: Handles the interaction with the embedding provider.
- `search.js`: Implements the document collection, embedding generation, and cosine similarity ranking.

## Prerequisites

- **Python 3.9+**
- **Node.js 18+**
- An API key from **OpenAI** OR a local **Ollama** instance running.

## Configuration

Both implementations use environment variables for configuration. Copy `.env.example` to `.env` and fill in your details.

### OpenAI (Cloud)
- `EMBEDDING_PROVIDER=openai`
- `OPENAI_API_KEY=your_api_key`
- `OPENAI_EMBEDDING_MODEL=text-embedding-3-small`

### Ollama (Local)
- `EMBEDDING_PROVIDER=ollama`
- `OLLAMA_BASE_URL=http://localhost:11434`
- `OLLAMA_EMBEDDING_MODEL=nomic-embed-text`

## How to Run

### Python
```bash
cd python
pip install -r requirements.txt
# Set environment variables or use a .env file
python search.py
```

### JavaScript
```bash
cd javascript
npm install
# Set environment variables or use a .env file
node search.js
```

## Expected Output

When searching for `"How do I get my money back?"`, the system should rank the document `"Customers can request a refund within 30 days of purchase."` as the top result, despite the lack of keyword overlap.

## Limitations

This is a teaching demo. For production systems, do not calculate similarity in-memory. Use a **Vector Database** (see Article #4) to handle indexing, storage, and efficient retrieval of millions of vectors.
