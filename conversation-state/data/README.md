# Inputs

Twelve scripted support conversations and the settings for every experiment, frozen before any code or model run.

- **The conversations** (`conversations/c01.json` to `c12.json`) are chats between a customer and the support assistant of Fernwick Goods, a fictional online homeware shop. Every message, the assistant's included, is written in advance, so each strategy builds its context from the same transcript.
- **Each conversation** has 20 turns. Its 6 facts are an order number, an issue, a status, and three others, such as a date, a colour, or an amount. Each fact has accepted forms for its current value and for any earlier (stale) value. The 6 probes each ask for one fact's current value, after turn 20.
- **The split is by whole conversation.** c01 to c04 are dev, used to develop the prompts. c05 to c12 are test, used for nothing until the final run.
- **Fact positions are computed, not declared.** The data check finds the last turn that mentions each value (see `settings.json`, `inputs.position` and `inputs.matching`).
- **`settings.json`** defines the strategies, the context limits, the grading, the experiments, and the run plan.

| File | SHA-256 |
|---|---|
| settings.json | `8658f7b5853a8f83dbc0235de896d2dac567c0b0215acfa875660bb1f60c2995` |
| conversations/c01.json | `335a06a60330f232ef92ced55e323d1390c929b4d9c8cf24aedcbb983f7a61f5` |
| conversations/c02.json | `00fd36963fce41545b152d56ad199f54c606286c7d941b5ce63dfa9d5ab9ac8a` |
| conversations/c03.json | `7c0b935f98d3be15953f977d2b5f78bf91ac678c8b13538846726c2b94fe6112` |
| conversations/c04.json | `c81fa4d8c0dc81c21e42f321f3a73d75503f445e89a52db111b04f0839ced2e1` |
| conversations/c05.json | `345d4383543b67a8caa207ba4d35bec4cefcd5ad8efc22ff942266a42758eeaf` |
| conversations/c06.json | `5a685987ef86b1d7e9a10557f910e24a7ca3a042c794af698c12c31b9f112aa3` |
| conversations/c07.json | `0f2c2b0bf16022b302b35411b3d565eafc6866e4696a5265c5bd83d9d0b769f3` |
| conversations/c08.json | `1f5dabfc5bbe970111781d788b1e3dc3dc545515951a5026fe29837439e3de64` |
| conversations/c09.json | `bac9041313c8def781c34691e24be98480c2e6e5e4bd0314166280291dbcafcf` |
| conversations/c10.json | `baf763bf392491ebd4868481b28d95c8bc7cb7853f735e7d99638236f5edc0dd` |
| conversations/c11.json | `4b72db04fcba8e1079f5cb7bf7c5098b56c8a18b26cb060a38b1402bd4836254` |
| conversations/c12.json | `6f717e4a4622765d3b4692b8f3ff0baf927abac5bd4ca29fc0757e7a9a49677a` |

`settings.json` was amended after step 0, with approval, before any experiment: experiment 1c also records the tokens Ollama actually evaluated (from its server log), and experiment 2 records the answer length and the step 0 finding (see `experiments.1_the_model_is_stateless.c_growth` and `experiments.2_past_the_window`). At the prompt freeze it was clarified (approval pending) with the num_ctx and size check of the summary and extraction calls (`model.summary`, `model.extraction`). The hash above is the amended file's; the original is in commit 2eebbea.

Added later, not part of this freeze:
- `prompts.json`: the system, summary, and extraction prompts, developed on the dev conversations;
- `derived.json`: N for the `last_n` strategy, computed from the dev conversations after the prompts are frozen and step 0 has confirmed the token counts;
- `hand_labels.json`: hand labels, written after the final run.

`tokenizer.json` (the Llama 3.2 tokenizer, for token counts) isn't committed; see the demo README.
