# LLM Inference

Where the time and memory go when a local model answers a request: prefill, decode, the KV cache, prompt caching, and model size. It accompanies the article **[How LLM Inference Works](https://snehalagrawal.com/articles/how-llm-inference-works/)**.

## What it demonstrates

| Script | Question it answers |
|---|---|
| `kv_cache` | How much memory does the KV cache need? Predicts it from the model's shape, then compares with what Ollama actually allocates (read from Ollama's server log). |
| `latency` | Where does the time go? Grows the prompt with a fixed answer length, then grows the answer with a fixed prompt. |
| `prompt_cache` | What does reusing a prompt prefix save, and what breaks it? Sends the same long document four times with the question in different places. |
| `decode_speed` | Why does a smaller model generate faster, and what does a cold start cost? Compares two model sizes against a memory-bandwidth upper bound. |

Every measurement comes from Ollama's own timing fields (`prompt_eval_count`, `prompt_eval_cached_count`, `prompt_eval_duration`, `eval_count`, `eval_duration`, `load_duration`), plus time to first token measured by the client from a streamed response. The scripts run at temperature 0, repeat each setting three times, and print medians.

## Files

| File | Purpose |
|---|---|
| `data/paragraphs.json` | Help-center paragraphs, repeated and numbered to build documents of a chosen length |
| `python/ollama_client.py`, `javascript/ollama_client.js` | Streams one request and returns Ollama's timings plus time to first token |
| `python/kv_cache.py`, `javascript/kv_cache.js` | KV cache prediction versus Ollama's allocation |
| `python/latency.py`, `javascript/latency.js` | Prompt length and answer length versus time |
| `python/prompt_cache.py`, `javascript/prompt_cache.js` | Prefix reuse |
| `python/decode_speed.py`, `javascript/decode_speed.js` | Model size, decode speed, and cold starts |

## Prerequisites

- Python 3.10+ **or** Node.js 18+
- [Ollama](https://ollama.com/download), with `ollama pull llama3.2:3b` and `ollama pull llama3.2:1b` (about 2.0 GB and 1.3 GB)

Each script runs for under a minute on an Apple M4 Pro and unloads the model when it finishes. Timings depend on your hardware, power source, and what else is running.

## Configuration

Copy `.env.example` to `.env` inside `python/` or `javascript/` if you need to change a default.

| Variable | Default | Notes |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | |
| `OLLAMA_CHAT_MODEL` | `llama3.2:3b` | |
| `OLLAMA_LOG` | `~/.ollama/logs/server.log` | The macOS default. `kv_cache` reads it to compare its prediction with Ollama's allocation; on other systems, point it at your server log or skip the comparison. |

## How to run

### Python

```bash
cd python
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python kv_cache.py
python kv_cache.py --model llama3.2:1b --ctx 4096
python latency.py
python prompt_cache.py
python decode_speed.py --bandwidth-gbs 273      # use your machine's memory bandwidth
```

### JavaScript

```bash
cd javascript
npm install

node kv_cache.js
node latency.js
node prompt_cache.js
node decode_speed.js --bandwidth-gbs 273
```

## Expected output

Setup: Ollama 0.40.16 on an Apple M4 Pro (24 GB, 273 GB/s memory bandwidth per Apple's specification), on battery power with Low Power Mode off; `llama3.2:3b` (`a80c4f17acd5`, Q4_K_M) and `llama3.2:1b` (`baf6a787fdff`, Q8_0); Ollama's default context of 4,096 tokens and f16 KV cache; temperature 0; 2026-11-12.

Timings are not repeatable to the digit. The tables below are the Python run. The JavaScript run, made right after it, produced the same token counts and KV cache sizes, and timings within about 15% (listed after each table). Expect the same shapes on your machine, not the same numbers.

**`kv_cache`** (`llama3.2:3b`, then `llama3.2:1b`):

```text
Model: llama3.2:3b | Ollama 0.40.16 | weights on disk: 2.02 GB
Shape: 28 layers, 8 KV heads, key size 128, value size 128
Per token: 28 x 8 x (128 + 128) x 2 bytes = 114,688 bytes (112 KiB)

 context     predicted    Ollama log
    4096    448.00 MiB    448.00 MiB
    8192    896.00 MiB    896.00 MiB
```

```text
Model: llama3.2:1b | Ollama 0.40.16 | weights on disk: 1.32 GB
Shape: 16 layers, 8 KV heads, key size 64, value size 64
Per token: 16 x 8 x (64 + 64) x 2 bytes = 32,768 bytes (32 KiB)

 context     predicted    Ollama log
    4096    128.00 MiB    128.00 MiB
```

The prediction matches Ollama's allocation exactly, because both are the same arithmetic: Ollama's log line reads:

```text
llama_kv_cache: size =  448.00 MiB (  4096 cells,  28 layers,  1/1 seqs), K (f16):  224.00 MiB, V (f16):  224.00 MiB
```

**`latency`** (`llama3.2:3b`):

```text
Model: llama3.2:3b | Ollama 0.40.16 | arm64 | power: battery | temperature 0 | 3 runs per setting, medians
Model load before the runs: 0.81 s

1. Longer prompt, same 32-token answer
 input tokens  processed    prefill   prefill speed  first token   decode speed
          256        234     293 ms       800 tok/s       300 ms     85.1 tok/s
          466        442     519 ms       851 tok/s       529 ms     88.9 tok/s
          886        862     992 ms       869 tok/s      1005 ms     83.6 tok/s
         1726       1702    2049 ms       831 tok/s      2071 ms     87.2 tok/s
         2668       2644    3377 ms       783 tok/s      3402 ms     77.4 tok/s

2. Same short prompt, longer answer
 output tokens  first token     decode      total   decode speed
            16        83 ms     0.16 s     0.24 s     98.9 tok/s
            64        50 ms     0.72 s     0.77 s     89.3 tok/s
           256        54 ms     2.90 s     2.95 s     88.2 tok/s

processed: input tokens actually computed (input tokens minus tokens reused from Ollama's cache).
first token: time from sending the request to receiving the first generated text, measured by this script.
```

JavaScript run: prefill 780 to 842 tokens/s, first token 306 ms to 3,393 ms over the same prompt sizes; decode 84 to 98 tokens/s.

**`prompt_cache`** (`llama3.2:3b`):

```text
Model: llama3.2:3b | Ollama 0.40.16 | temperature 0 | 3 sequences, medians

request                              input tokens   reused  computed    prefill  first token
1. document, question 1                      2141       20      2121    2761 ms      2770 ms
2. same document, question 2                 2140     2125        15      37 ms        45 ms
3. question 2, then the document             2140       20      2120    2722 ms      2743 ms
4. document, question 1 again                2141     2125        16      40 ms        88 ms

reused: input tokens Ollama read from its cache (prompt_eval_cached_count).
```

JavaScript run: the same token counts; first token 2,867 ms, 49 ms, 3,151 ms, and 149 ms.

**`decode_speed --bandwidth-gbs 273`**:

```text
Ollama 0.40.16 | temperature 0 | 128 output tokens | 3 warm runs per model, medians

model           weights  cold load  cold first token  warm first token   decode speed   upper bound  of bound
llama3.2:1b     1.32 GB     1.06 s           1106 ms             24 ms    145.5 tok/s     207 tok/s      70%
llama3.2:3b     2.02 GB     0.78 s            833 ms             53 ms     86.7 tok/s     135 tok/s      64%

cold: the first request after the model was unloaded, including loading it into memory.
upper bound: memory bandwidth / weights size, if every token reads all the weights once.
```

JavaScript run: 146.3 and 90.5 tokens/s (71% and 67% of the bound); cold loads of 1.05 s and 1.53 s.

### What reading the results found

- **Prefill is about nine to ten times faster per token than decode.** `llama3.2:3b` read prompts at roughly 780 to 870 tokens/s and generated at roughly 84 to 99 tokens/s (lower at the longest prompt). Prefill processes all prompt tokens together; decode produces one token at a time.
- **Time to first token tracks the prompt; total time tracks the answer.** First token grew from about 0.3 s to 3.4 s as the prompt grew from 256 to 2,668 tokens. With a short prompt it stayed between 50 and 85 ms while the answer grew, and total time grew with the answer: 0.24 s for 16 tokens, 2.95 s for 256.
- **Decode speed may drop slightly with a long context**, as attention reads a longer cache. At 2,668 input tokens, decode was the slowest of the five sizes in two of three runs (76.0, 77.4, and 84.9 tokens/s), but the difference is close to run-to-run variation at these lengths.
- **Prefix reuse is exact-prefix only.** The same document with a new question reused 2,125 of 2,140 input tokens, and first token fell from 2.8 s to 45 ms. Putting the question before the document reused only the 20-token chat header. In step 4, the document prefix was still reusable after a different request in between: this version of Ollama kept more than the most recent prompt.
- **Decode speed follows model size.** The 1B model generated 145 to 164 tokens/s and the 3B model 87 to 97 tokens/s across three runs, at 64% to 79% of the memory-bandwidth bound. The "upper bound" column is an idealized single-request weight-read ceiling, not a prediction: it assumes every token reads all the weights once at the full theoretical bandwidth, and ignores KV cache reads and runtime overhead.
- **Cold starts vary.** Loading `llama3.2:3b` took between 0.53 s and 1.53 s across runs, depending on whether its file was already in the operating system's file cache. Loading `llama3.2:1b` took about 1.05 s each time.

## Things to try

- Run `latency.py` plugged in and on battery. What changes?
- Set `OLLAMA_KV_CACHE_TYPE=q8_0` (with flash attention enabled) and rerun `kv_cache.py`. Does the allocation halve?
- Run `kv_cache.py --ctx 32768` and compare the KV cache with the weights.
- Add a system prompt to `prompt_cache.py` that includes the current time. What happens to reuse?

## Limitations

This is an educational demo, not a benchmark.

- One machine, two small models, one runtime. Hosted providers batch many users' requests together on data-center hardware, so their numbers, and some of their trade-offs, differ.
- Each setting ran three times. Timings vary with temperature, power source, and background load.
- The bandwidth bound uses the size of the model file, which includes parts that aren't read for every token.
