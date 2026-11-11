# ai-engineering-examples

Small, focused, runnable examples for the AI fundamentals articles on [snehalagrawal.com](https://snehalagrawal.com).

Each directory is self-contained, with its own README, setup instructions, and `.env.example`. These are educational demos, not production code.

| Example | What it shows | Article |
|---|---|---|
| [`embeddings-semantic-search/`](embeddings-semantic-search/) | Keyword search vs. embedding-based semantic search, cosine similarity, and where similarity misleads (Python and JavaScript) | [Embeddings Explained](https://snehalagrawal.com/articles/embeddings-explained/) |

## Conventions

- Examples support a cloud provider and a local option (Ollama) where practical.
- Configuration goes through environment variables. Never commit a `.env` file.
