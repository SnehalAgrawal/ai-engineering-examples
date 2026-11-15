# Inputs

Everything in this folder except `settings.json` and `prompts.json` is copied unchanged from [`production-ai-patterns/01-reliable-llm-pipeline/data`](https://github.com/SnehalAgrawal/production-ai-patterns/tree/main/01-reliable-llm-pipeline/data), where it was frozen in commit 08bf05c for Article #18.

| File | SHA-256 |
|---|---|
| documents/admin-guide.md | `7c1a52a88e50491804781b050e982e34b07bf9f93593675a340f8521cb9c47b3` |
| documents/api-reference.md | `1cff46f15a5d64d551cd1d1c236235792844214c50fba68cb0b49b03c874aa39` |
| documents/billing-guide.md | `1ad6b1a83f3ebcd9cbf4b8772e013b9113213309e47074a6ed090519e1e4328a` |
| documents/data-processing-policy.md | `405a982c49ef6d7e267de04352b3a81661f1fec310e83765de4ef5255c36a230` |
| documents/release-notes.md | `77ee5458d3c57753cc0d6a8dc35ea140f405d6518350ac82a81e7a687527c25b` |
| labels.json | `28aafdbff5afc5c1f0138a9280c4af7c0ecea9f282f731b27a9e9a8222d1d12e` |
| emails/e01.txt to e40.txt, concatenated in order | `7e2592e2f5e19e6d852718713fcd3ec088f59b12f4699b13b0e45fe5d8624fba` |

- **The emails** are the inputs: each one is retrieved for, drafted, and streamed.
- **The labels** are used only for their labelled questions (`asks`), which serve as retrieval queries, so the only model call per email is the draft. Nothing here scores replies against the labels.
- **There is no development/test split.** No prompt or setting is chosen from these runs.
- **The documents** are the knowledge base the excerpts come from.

`settings.json` and `prompts.json` were written for this demo before any run. The prompt is Article #18's drafting prompt (v3); only its last sentence changed, which now asks for plain text instead of JSON.
