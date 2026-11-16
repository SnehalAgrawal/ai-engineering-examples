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

Each language ran all 952 model calls once, Python first, then JavaScript, from commit febfa22 with prompts `v4-frozen`. There were no errors, and no other program was connected to Ollama during any request. An earlier Python attempt was stopped from outside after 334 calls; it is kept (`runs/python/main-stopped-at-334`, not committed) and not used.

### Parity

All 952 records match between the languages outside timings: every answer's SHA-256, every token count, what was sent and what the model saw, the ending Ollama kept, every context shift, and every tokens-evaluated figure. All 48 summary updates and all 240 case-record updates match too. The two reports' counts and outcomes match line for line.

### How answers were graded

- **Mechanical grade first.** Each answer is matched against the accepted forms of the fact's current and stale values.
- **Then 310 answers were read by hand**, as the settings require: every answer not graded correct, every status answer, and 10 sampled correct answers per block. They are labelled in [data/hand_labels.json](data/hand_labels.json). The final grade is the hand label where an answer was read, and otherwise the mechanical "correct".
- **Labels:**
  - correct;
  - stale: gives an earlier value as the current one;
  - both: gives the current and an earlier value without saying which is current;
  - not stated: says it doesn't know;
  - wrong: another value from what the model was sent, including a case record or a summary;
  - invented: a value found in neither the conversation nor what the model saw.
- **Status answers:** an answer that says the case is closed or resolved is correct only where the conversation says so.
- **The sample of mechanically correct answers found one false positive.** One answer said "super king" about the cover being sent back, not the one being sent.
- **Two limits of the instruments:**
  - In four conditions where the model never saw it, the answer to c06's "How big across was the mirror?" was still the right value, "60 cm". That was a guess, not memory: a common mirror size.
  - The check of whether a value was in the context matches accepted forms only. Three summary answers had the value as a paraphrase that the check can't see.

The tables below give the final grades on the 48 test probes (8 conversations × 6). Fact positions are the dataset's classes: early (last mentioned in turns 1 to 5), middle (6 to 15), and late (16 to 20).

### 1. The model is stateless

| Test, 48 probes | Correct | Stale | Both | Not stated | Wrong | Invented |
|---|---|---|---|---|---|---|
| No history | 0 | 0 | 0 | 48 | 0 | 0 |
| Full history (`num_ctx` 8192) | 43 | 2 | 1 | 1 | 1 | 0 |

- **What was sent:** the full-history request grows from 167 to 189 tokens at turn 1 to 2,542 to 2,796 at turn 20. Over 20 turns a conversation sends 28,740 to 30,526 tokens in all, which is 10.6 to 11.4 times its last request. These are counted for all 12 conversations, without model calls.
- **What was recomputed:** on the 8 test conversations, Ollama's log shows how many tokens it actually evaluated for each request. All 160 requests had a matching log line.
  - The median is 9% of the request (4% to 91%). At turn 20 it was 112 to 133 of 2,672 to 2,796 tokens; the rest was reused from Ollama's prompt cache.
  - Ollama's `prompt_eval_count` reports the whole request either way. It equalled the application's count in all 160.

These measure Ollama 0.40.16 on these requests, sent one after another. They aren't a general saving from prompt caching.

### 2. Past the window (`num_ctx` 2048)

- **Sent:** 2,632 to 2,908 tokens, and every request was accepted (HTTP 200) with no error and no warning.
- **Cut before the answer:** Ollama's `prompt_eval_count` was 1,951 to 2,047. For all 72 requests, exactly one ending of the conversation has that count, starting at turn 5 to 7. So Ollama dropped the earliest turns and kept the system prompt.
- **Effect on answers:**
  - For the 16 probes whose value had been sent but not seen, 1 answer was correct, and that one was the "60 cm" guess.
  - Where the value was seen, 42 of 56 were correct.
- **Cut during the answer:** the prompt left 1 to 97 tokens of room (median 46.5). In 22 of 72 answers, Ollama's log records a context shift that discarded 1,021 tokens, with `truncated = 1`. This comes from the log line for the request's own task, not from a difference in token counts. 12 of those 22 answers were still correct.

| Test, 48 probes | Correct | Stale | Both | Not stated | Wrong | Invented |
|---|---|---|---|---|---|---|
| Full history at `num_ctx` 2048 | 28 | 3 | 0 | 6 | 8 | 3 |

### 3. Strategies (`num_ctx` 2048, prompt limit 1,920)

| Test, 48 probes | Prompt tokens (median) | Correct | Stale | Both | Not stated | Wrong | Invented |
|---|---|---|---|---|---|---|---|
| Full history at 8192 (reference) | 2,808 | 43 | 2 | 1 | 1 | 1 | 0 |
| `last_n`, 13 turns | 1,802 | 28 | 1 | 0 | 12 | 6 | 1 |
| `token_budget` | 1,894 | 30 | 1 | 0 | 5 | 8 | 4 |
| Summary + last 4 turns | 919 | 33 | 2 | 0 | 7 | 3 | 3 |
| Case record + last 4 turns | 662 | 18 | 0 | 0 | 15 | 12 | 3 |

| Correct, by fact position | Early (of 11) | Middle (of 20) | Late (of 17) |
|---|---|---|---|
| Full history at 8192 | 11 | 19 | 13 |
| `last_n` | 1 | 15 | 12 |
| `token_budget` | 1 | 16 | 13 |
| Summary + last 4 turns | 9 | 14 | 10 |
| Case record + last 4 turns | 4 | 4 | 10 |

- **Windows:** `last_n` and `token_budget` kept the last 13 to 15 turns, so facts stated early were gone. No `last_n` request went over the limit (1,731 to 1,888 tokens).
- **Summaries:** they kept most early facts at about half the tokens, but they were lossy.
  - 29 of 48 updates reached the 300-token cap and were cut off, including 9 of 12 final summaries.
  - On test, 27 of 48 facts have their current value in the final summary, 8 of them alongside a stale value. 12 facts reached the input of a summary call but are missing from the final summary.
- **Case records:** they were the cheapest per answer, and errors in them were repeated as fact.
  - The final status was "resolved" in 10 of 12 conversations.
  - On test, the final record had the right order number in 7 of 8; c05's record has one that appears nowhere in the conversation. It had the right issue in 5 of 8, and the right status in 2 of 8.
  - The record holds only the order number, issue, and status. On the 24 test facts outside it, the answers were not stated 14, correct 6 (from the last 4 turns), wrong 2, invented 2.
- **Dev (24 probes):** full history 22, `last_n` 13, `token_budget` 16, summary 16, record 13. The full history leads here too, but the summary only ties the token budget, and the record ties `last_n`.

| Maintenance | Summary | Case record |
|---|---|---|
| Calls per conversation | 4 | 20 |
| Input tokens per conversation (median) | 3,609 | 12,591 |
| Output tokens per conversation (median) | 1,086 | 502 |
| Time per conversation (median; Python, JavaScript) | 23.9 s, 20.2 s | 10.1 s, 9.7 s |

Timings vary from run to run. One `last_n` request in the Python run took 23.6 s to evaluate its prompt, against at most 2.5 s for the others in the block (2.8 s in JavaScript), with no other program connected; the cause is unknown. It doesn't change the medians.

These results describe one small model on eight test conversations. They don't show that one strategy is better in general.

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
| Date | 2026-11-16 |
