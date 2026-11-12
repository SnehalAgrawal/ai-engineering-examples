# ai-engineering-examples

Small, focused, runnable examples for the AI fundamentals articles on [snehalagrawal.com](https://snehalagrawal.com).

Each directory is self-contained, with its own README, setup instructions, and `.env.example`. These are educational demos, not production code.

| Example | What it shows | Article |
|---|---|---|
| [`embeddings-semantic-search/`](embeddings-semantic-search/) | Keyword search vs. embedding-based semantic search, cosine similarity, and where similarity misleads (Python and JavaScript) | [Embeddings Explained](https://snehalagrawal.com/articles/embeddings-explained/) |
| [`vector-search-at-scale/`](vector-search-at-scale/) | Why exact search stops scaling, HNSW and IVF recall vs. latency on real embeddings, and the metadata-filtering trap (Python and JavaScript) | [Vector Databases Explained](https://snehalagrawal.com/articles/vector-databases-explained/) |
| [`prompt-as-interface/`](prompt-as-interface/) | Testing a prompt like an interface: three prompts, 24 test cases (answerable, not in the documents, planted instructions), two local models (Python and JavaScript) | [Prompt Engineering: Beyond Writing Better Prompts](https://snehalagrawal.com/articles/prompt-engineering-beyond-better-prompts/) |
| [`generation-parameters/`](generation-parameters/) | Temperature, top-k, top-p, min-p, seeds, max tokens and stop sequences, measured: predicted vs observed token choices, and a temperature experiment on the support assistant (Python and JavaScript) | [Temperature, Top-P, and Other LLM Parameters Explained](https://snehalagrawal.com/articles/temperature-top-p-and-other-llm-parameters/) |

## Conventions

- Examples support a cloud provider and a local option (Ollama) where practical.
- Configuration goes through environment variables. Never commit a `.env` file.
