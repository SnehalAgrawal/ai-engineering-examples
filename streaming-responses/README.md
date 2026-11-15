# Streaming Responses

What streaming changes for the person waiting for an LLM's reply, measured from the model to the user's screen. It accompanies the article **[Streaming LLM Responses: Why and How](https://snehalagrawal.com/articles/streaming-llm-responses-why-and-how/)** (Article #19).

The demo is the support assistant from Article #18: it drafts a reply to a customer email from retrieved documentation. Here the reply is streamed through a small app server to a client, sometimes through a proxy:

```text
client ──► [proxy] ──► app server ──► Ollama (llama3.2:3b)
           exp. 2      server-sent events, one event per chunk
```

| Experiment | Question |
|---|---|
| 1. What the user waits for | When do the first words appear, compared with the complete reply? |
| 2. Where streams get stuck | What does a buffering proxy between the app server and the client do to that? |
| 3. When the user leaves | If the client disconnects, does the model keep generating? |
| 4. Streaming and checks | Article #18's value check needs the whole reply. What happens when it runs before, after, or sentence by sentence? |

The model is a small local one, and the replies are short (17 to 218 tokens). The results describe this setup, not what a hosted model or longer replies would do.

## What was frozen before the runs

1. **Inputs and settings were frozen before any code**, in commit c7a4401: Article #18's documents, emails, and labels, copied unchanged (see [data/README.md](data/README.md)); the drafting prompt; and [data/settings.json](data/settings.json), which defines every experiment, measurement, and output. No setting was tuned on these runs.
2. **Step 0, run once before the experiments, checked how to read Ollama's log.** Experiment 3 relies on that reading. It runs two emails to completion and two cancelled after 20 chunks.
   - For completed requests, the log's count is one below Ollama's `eval_count`, within the frozen tolerance.
   - For cancelled requests, the "processing task", "cancel task", and release lines matched one task.
3. **Each language ran all 280 requests once,** Python first, then JavaScript. Each mode or policy is a separate block, which starts with the model unloaded and an unmeasured warm-up request.

### Implementation notes

These are not changes to the frozen settings:

- **Ollama may be shared with other work, which would distort the timings.** The runner waits until no other program has been connected to Ollama for 60 seconds before its first call. Before each later block, it waits again only if one has connected since. It records any overlap per request; none occurred.
- **The app server also writes its own record of each request,** because a client that disconnects never receives the final event.
- **Experiment 3's check of the ignore mode compares with `eval_count - 1`,** the offset step 0 measured.
- **A failed write is defined the same way in both languages,** with a different mechanism:
  - in JavaScript, a write that Node reports an error for;
  - in Python, a write that raises.
- **Character counts are in code points** in both languages.

## Results

Unless marked otherwise, timings below are from the Python run. Counts and outcomes matched between Python and JavaScript; selected JavaScript timings are shown alongside the Python figures. Timings are in seconds, given as "median (minimum to maximum)", and vary from run to run.

### Parity

- **Counts and outcomes:** the aggregate counts and outcome summaries of the two reports match line for line.
- **Excerpts:** identical.
- **Replies:** for every request that ran to completion, the generated reply is identical across all modes and both languages, for all 40 emails.
- **Values that depend on timing differ:** the cancellation token estimates (experiment 3), and the number of events the app server received after a disconnect.

### 1. What the user waits for

Within each streamed request, the first words appeared **0.75 s (0.21 to 3.32) before the reply was complete**. That is 20% (11% to 63%) of the total wait: time the user had something to read while generation continued. These runs don't establish whether streaming changes the total generation time (see the confounded comparison below). The first words reached the client at most 1.2 ms after the model's first token (JavaScript: 2.5 ms).

Most of the wait came before the first token, while the model read the prompt:

| Emails | Prompt tokens | Output tokens | First words | Complete |
|---|---|---|---|---|
| 1 question (e01–e14) | 1,334 | 45 | 1.83 (1.70 to 2.35) | 2.32 (1.91 to 5.23) |
| 2 questions (e15–e30) | 2,424 | 70 | 3.46 (3.26 to 4.04) | 4.28 (3.88 to 5.15) |
| 3 questions (e31–e40) | 3,474 | 96 | 5.24 (4.80 to 5.61) | 6.41 (5.52 to 7.47) |

(Token counts are medians.) More questions bring more excerpts, so question count and prompt length move together here; the table doesn't separate them.

**The comparison between the non-streaming and streaming blocks is confounded.**
- The observed medians: non-streaming complete in 3.74 s; streaming complete in 4.23 s (JavaScript: 3.74 and 4.38).
- These don't show that either mode is faster. The two blocks ran minutes apart, and Ollama's own prefill time for the *same prompt* was slower in the streaming block for 37 of 40 emails (median +407 ms), in both runs. It was faster for the same three emails, e38–e40.
- The first block began at 1.06 ms per prompt token in Python and 1.18 in JavaScript; the streaming block that followed began at 1.28 and 1.52.
- This is consistent with an effect of block order, possibly the machine slowing under sustained load. Temperature and clock speed were not measured, so the cause is unknown.
- One JavaScript outlier stays in the data: e37's prefill in the streaming block took 11.0 s longer, and its first words came after 16.3 s. Nothing else was connected to Ollama, and the cause is unknown.

### 2. Where streams get stuck (e01–e20)

| Proxy | Model's first token to first visible text | Writes per reply (median, range) | Replies delivered in one write |
|---|---|---|---|
| pass-through | 0.00 | 50 (17 to 218) | 0 of 20 |
| buffer-all | 0.57 (0.19 to 3.02) | 1 | 20 of 20 |
| buffer-4096 | 0.59 (0.19 to 0.83) | 1 (1 to 4) | 15 of 20 |

- **Buffer-all:** the app server streamed every reply, but the client saw nothing until the reply was complete, and then all of it at once.
- **Buffer-4096:** 15 of the 20 replies fit in one 4,096-byte block, so for them the fixed-size buffer behaved exactly like buffering everything. That is a property of these short replies, not of all streaming. The longest reply, e11 (12,938 bytes of events), arrived in 4 bursts: first words at 2.51 s, complete at 5.00 s.

### 3. When the user leaves (e01–e10)

The client closed the connection after 20 text events. e08's whole reply is 17 tokens, so its client never reached 20 events and never disconnected; it is not a cancellation trial. That leaves 9 disconnects per mode. The app server noticed each one at its first failed write, 0.022 s later (JavaScript: 0.012 s).

| App server | Text events it received after the disconnect | Tokens the model generated (Ollama's log) |
|---|---|---|
| ignore | 6 to 43 | the whole reply, in each of the 9 disconnects |
| cancel | 0 | 23 in each of the 9 disconnects (JavaScript: 22) |

With "ignore", the model wrote every reply to the end for a user who had gone. With "cancel", it stopped 2 to 3 tokens after the 20 the client had received. Closing the client's connection didn't cancel anything by itself: only the app server closing its own connection to Ollama did.

### 4. Streaming and checks

One email of 40 failed the value check: e27, whose reply invents "99.9% per month" uptime.

| Policy | e27 | Model's first token to first visible text, all 40 emails |
|---|---|---|
| check-whole | nothing shown | 0.79 (0.22 to 2.84) |
| stream-then-check | the whole reply shown, then retracted; the false value was on screen for 0.52 s (JavaScript: 0.62 s) | 0.00 |
| sentence-gate | "Hi Priya Nair," shown, the rest withheld | 0.08 (0.03 to 0.66) |

One flagged email shows how each policy behaves, not how often the check catches errors. The policies' first-text medians across separate blocks share experiment 1's confound; the delays in the table are measured within each request.

## Files

| File | Purpose |
|---|---|
| `data/` | Frozen inputs, `settings.json`, and `prompts.json` ([data/README.md](data/README.md)) |
| `app_server.*` | Drafts a reply and passes it on, streamed or not, under one of the four policies; cancels or ignores a disconnect |
| `proxy.*` | Pass-through, buffer-all, or buffer-4096 between the client and the app server |
| `client.*` | Sends a request and records when each event arrives, decoding UTF-8 and framing events across arbitrary reads |
| `check.*` | Article #18's value check, and the sentence splitter |
| `ollama.*` | Ollama calls: embeddings, chat with and without streaming, unload, and who else is connected |
| `ollama_log.*` | Reads the task, prompt tokens, cancellation, and release count from Ollama's server log |
| `retrieval.*`, `chunkers.*`, `search.*`, `tokens.*` | Retrieval as in Article #18 |
| `run.*` | Runs the experiments and saves every request |
| `report.*` | Prints the report from a saved run: counts and outcomes first, then timings |
| `python/step0.py` | Step 0, the check of the log reading (Python only) |

## Prerequisites

- Python 3.10+ **or** Node.js 18+ (tested with Python 3.12.13 and Node.js 24.16.0)
- [Ollama](https://ollama.com/download) 0.40.16, with `llama3.2:3b` and `nomic-embed-text`
- `lsof` (macOS and Linux), to see whether another program is using Ollama
- The Llama 3.2 tokenizer in `data/tokenizer.json`, used for the retrieval budgets: see [rag-engineering/04-chunking: Get the tokenizer](https://github.com/SnehalAgrawal/rag-engineering/tree/main/04-chunking#get-the-tokenizer)
- For experiment 3, read access to Ollama's server log (`~/.ollama/logs/server.log` by default; set `OLLAMA_SERVER_LOG` otherwise). The log format is that of Ollama 0.40.16; check it with `step0.py` before relying on another version.

## How to run

```bash
cd python
pip install -r requirements.txt
python step0.py          # about a minute: checks the log reading
python run.py            # about 20 minutes: all four experiments, into runs/python/main
python report.py
```

```bash
cd javascript
npm install
node run.js              # into runs/javascript/main
node report.js
```

`run.py --out smoke --emails e01,e02 --experiments 1,4` runs a subset. Runs are saved under `runs/` and aren't committed. Expect the same shape of results, not the same timings: they depend on the machine, its load, and the power source.

## Setup used for the published numbers

| | |
|---|---|
| Machine | Apple M4 Pro (24 GB), macOS 26.6.2, on mains power |
| Ollama | 0.40.16; `/api/chat` with and without streaming; `/api/embed` |
| Chat model | `llama3.2:3b`, ID `a80c4f17acd5` (Q4_K_M), temperature 0, seed 1, `num_ctx` 8192, at most 700 output tokens |
| Retrieval | as in Article #18: structure-headings chunks, RRF of `nomic-embed-text` (ID `0a109f422b47`) and BM25, 1,000 tokens per question and 3,000 per email |
| Transport | server-sent events from the app server, one event per Ollama chunk, written and flushed at once; HTTP on 127.0.0.1 |
| Runtimes | Python 3.12.13 (standard library HTTP server and client), Node.js 24.16.0 (`node:http`) |
| Date | 2026-11-15 |
