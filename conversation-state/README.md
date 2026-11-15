# Conversation State

What an application sends a model in a long conversation, and what the model can still answer. It accompanies the article **[Managing Conversation State in AI Applications](https://snehalagrawal.com/articles/managing-conversation-state-in-ai-applications/)** (Article #20).

The model keeps nothing between calls: every request carries whatever the application decides to send. This demo compares those decisions on twelve scripted support chats, 20 turns each, at Fernwick Goods, a fictional online homeware shop. After turn 20, six probe questions ask for facts from the chat: an order number that was corrected, the issue, the current status, and three details such as a date, a colour, or a house number.

| Experiment | Question |
|---|---|
| 1. The model is stateless | What does the model answer with no history, and with all of it? How does the request grow turn by turn, and how much of it is actually recomputed? |
| 2. Past the window | What happens when the full history doesn't fit the context window (`num_ctx` 2048)? |
| 3. Strategies | Within a 1,920-token limit, which facts survive: the last N turns, a token budget, a running summary plus recent turns, or a structured case record plus recent turns? What does keeping a summary or a record cost? |

The scope is one conversation. What an application carries between separate conversations is Article #26's subject.

The model is a small local one (`llama3.2:3b`), and each chat is 2,612 to 2,880 tokens with the system prompt. The results describe this setup, not what a larger model or a hosted service would do.

## What was frozen before the runs

1. **The conversations, facts, probes, and settings were frozen before any code**, in commit 2eebbea (see [data/README.md](data/README.md)). Every message, the assistant's included, is scripted, so every strategy builds its context from the same transcript. Fact positions are computed by the data check, not declared.
2. **Step 0 checked the instruments on Ollama 0.40.16 before any experiment.**
   - The application's token count, which renders the model's chat template, equals Ollama's `prompt_eval_count`, including for text outside ASCII.
   - `prompt_eval_count` is the whole prompt even when Ollama reuses a cached prefix; only its server log shows how many tokens were actually evaluated. Experiment 1c records both (a settings amendment, approved before any experiment).
   - A request larger than the window is accepted without an error or a warning: Ollama drops whole messages from the start and keeps the system prompt.
3. **The prompts were developed on the four dev conversations only** (c01 to c04), in three rounds, and frozen by a rule set in advance (`data/prompts.json` records every version and why it changed). N for the `last_n` strategy, 13 turns, was computed from the dev conversations with the frozen prompts (`data/derived.json`). Commit 1d4baa1.
4. **The eight test conversations (c05 to c12) were not used for prompt development, for choosing any setting, or in any model call before the final run.** Without calling the model, they were read by the data check and by the check that Python and JavaScript build identical requests. Results are reported for test; dev results separately.

### Implementation notes

These are not changes to the frozen settings:

- **What the model saw, not only what was sent.** When Ollama evaluates fewer tokens than the application sent (experiment 2), the runner finds the one ending of the conversation whose count equals Ollama's and checks each fact against it. It also reads the server log for a context shift during the answer (`slot context shift`, with the tokens discarded) and the `truncated` flag, for the request's own task.
- **Every maintenance request is checked before it is sent**: a summary request must leave room for its 300-token output, an extraction request for its 120 tokens. An oversized request stops the run, because Ollama would drop messages from it silently.
- **Ollama may be shared with other work.** The runner waits until no other program has been connected to Ollama for 60 seconds before its first call, and again before a block if one has connected since. Overlap is recorded per request.
- **Hand labels are keyed by conversation, probe, and the answer's SHA-256**, because the same text (such as "I don't have that information.") can answer different probes.
- **Python and JavaScript produce the same requests, records, and report**; timings differ. JSON inserted into a prompt is written as Python writes it (`", "` and `": "`), and the report rounds as Python does.

## Results

Added after the run.

## Files

| File | Purpose |
|---|---|
| `data/` | Frozen conversations, settings, prompts, and the derived N ([data/README.md](data/README.md)) |
| `check_data.*` | Checks the frozen inputs and their hashes, and prints where each fact sits; `--derive` computes N |
| `tokens.*`, `chat_template.*` | Llama 3.2 token counts of a request rendered as the model's chat template renders it |
| `context.*` | What each strategy sends, and the summary and case-record update requests |
| `ollama.*` | Ollama calls, unloading, and who else is connected |
| `ollama_log.*` | Reads a request's task from Ollama's server log: tokens evaluated, context shifts, the truncated flag |
| `run.*` | Runs the experiments and saves every model call |
| `report.*` | Prints the report from a saved run: counts and outcomes first, then timings |
| `python/step0.py` | Step 0, the checks of the instruments (Python only) |
| `python/dev.py` | Prompt development on the dev conversations (Python only) |
| `python/label.py` | The hand-labelling worklist from a saved run, and a check of `data/hand_labels.json` (Python only) |

## Prerequisites

- Python 3.10+ **or** Node.js 18+ (tested with Python 3.12.13 and Node.js 24.16.0)
- [Ollama](https://ollama.com/download) 0.40.16, with `llama3.2:3b`
- `lsof` (macOS and Linux), to see whether another program is using Ollama
- The Llama 3.2 tokenizer in `data/tokenizer.json`: see [rag-engineering/04-chunking: Get the tokenizer](https://github.com/SnehalAgrawal/rag-engineering/tree/main/04-chunking#get-the-tokenizer)
- Read access to Ollama's server log (`~/.ollama/logs/server.log` by default; set `OLLAMA_SERVER_LOG` otherwise), for experiments 1c and 2. The log format is that of Ollama 0.40.16; check it with `step0.py` before relying on another version.
- Optional environment variables: `OLLAMA_BASE_URL` (default `http://localhost:11434`), `OLLAMA_CHAT_MODEL` (default `llama3.2:3b`), `TOKENIZER_PATH`

## How to run

```bash
cd python
pip install -r requirements.txt
python check_data.py     # checks the frozen inputs
python step0.py          # about two minutes: checks the token counts and Ollama's handling of long requests
python run.py            # all three experiments, into runs/python/main
python report.py
python label.py          # the hand-labelling worklist
```

```bash
cd javascript
npm install
node check_data.js
node run.js              # into runs/javascript/main
node report.js
```

`run.py --smoke --out smoke --conversations c01` runs every block on one dev conversation. Runs are saved under `runs/` and aren't committed. Expect the same counts and outcomes, not the same timings: they depend on the machine and its load.

## Setup used for the published numbers

| | |
|---|---|
| Machine | Apple M4 Pro (24 GB), macOS 26.6.2 |
| Ollama | 0.40.16; `/api/chat` without streaming |
| Model | `llama3.2:3b`, ID `a80c4f17acd5` (Q4_K_M), temperature 0, seed 1 |
| Windows | `num_ctx` 8192 (full history, growth) and 2048 (past the window, strategies, maintenance); 1,920-token prompt limit |
| Runtimes | Python 3.12.13 (standard library HTTP client), Node.js 24.16.0 (`node:http`) |
| Date | added with the results |
