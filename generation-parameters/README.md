# Generation Parameters

What temperature, top-k, top-p, min-p, seeds, max tokens, and stop sequences actually do, measured on a local model. It accompanies the article **[Temperature, Top-P, and Other LLM Parameters Explained](https://snehalagrawal.com/articles/temperature-top-p-and-other-llm-parameters/)**, and reuses the support assistant and test cases from [`prompt-as-interface`](../prompt-as-interface/) (Article #5).

## What it demonstrates

1. **The model forecasts; the sampler picks** (`next_token`). For two support questions, the demo reads the model's probabilities for its first token. For each sampler setting, it predicts how often each token should be picked, then samples the first token 500 times and counts. If the explanation of a setting is right, prediction and observation agree.
2. **Temperature 0 buys consistency, not correctness** (`consistency`). Article #5's interface prompt runs on its 24 test cases at temperatures 0, 0.4, 0.8, and 1.2, 10 runs each. The demo reports the checks, how many different replies each case produced, and which cases failed every time.
3. **Max tokens and stop sequences cut the output; they don't shape it** (`limits`). A token limit and a stop sequence each break the JSON contract, and the finish reason doesn't always tell you.

## Files

| File | Purpose |
|---|---|
| `data/help_center.json`, `data/cases.json` | The support documents and test cases, copied from `prompt-as-interface` |
| `python/sampler.py`, `javascript/sampler.js` | The sampling steps written out (top-k, top-p, min-p, temperature), in the order the runtime applies them |
| `python/next_token.py`, `javascript/next_token.js` | Part 1: first-token forecasts, predicted versus observed |
| `python/consistency.py`, `javascript/consistency.js` | Part 2: the temperature experiment |
| `python/limits.py`, `javascript/limits.js` | Part 3: max tokens and stop sequences |
| `python/ollama.py`, `javascript/ollama.js` | A minimal Ollama client: chat with sampler options and token probabilities, and model unloading |
| `python/prompts.py`, `python/checks.py` (and `.js`) | Prompts and checks, copied from `prompt-as-interface` |

Both languages send identical requests and print identical output.

### Why Ollama only

Unlike the earlier demos, this one has no OpenAI option. The experiments need to set every sampler option, read token probabilities, and confirm which settings the runtime actually applied (from its log). A local runtime exposes all of that. Hosted APIs differ in which parameters they accept, and the article covers those differences from their documentation.

## Prerequisites

- Python 3.9+ **or** Node.js 18+
- [Ollama](https://ollama.com/download), then `ollama pull llama3.2:3b` (2 GB). The article also uses `qwen2.5:3b` (1.9 GB).
- An Ollama version that returns `logprobs` from `/api/chat` (0.40.1 was used).

## Configuration

Copy `.env.example` to `.env` inside `python/` or `javascript/` if you need to change the defaults.

| Variable | Default | Notes |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | |
| `OLLAMA_CHAT_MODEL` | `llama3.2:3b` | `--model` overrides it |

## How to run

### Python

```bash
cd python
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python next_token.py                     # ~2 min
python consistency.py                    # ~15-25 min (960 replies)
python limits.py                         # seconds
python consistency.py --model qwen2.5:3b # any script, another model
```

### JavaScript

```bash
cd javascript
npm install

node next_token.js
node consistency.js
node limits.js --model qwen2.5:3b
```

### How a run stays repeatable

Every script unloads the model first (`keep_alive: 0`), then sends its requests in a fixed order, with fixed seeds. In testing, the first request after the model loaded reported slightly different token probabilities from every later identical request, which is enough to change a sampled token when two tokens are nearly tied. `next_token` shows both sets of probabilities. Starting from an unloaded model made full runs byte-identical. This is an observation about this setup (Ollama 0.40.1 on Apple silicon), not a documented guarantee.

## Expected output

The article's numbers came from this setup:

| Setting | Value |
|---|---|
| Machine | Apple M4 Pro (12 cores, 24 GB), macOS 26.6.2 |
| Runtime | Ollama 0.40.1, `/api/chat` (llama.cpp runner) |
| Models | `llama3.2:3b` (ID `a80c4f17acd5`, Q4_K_M) and `qwen2.5:3b` (ID `357c53fb659c`, Q4_K_M) |
| Defaults applied | From Ollama's server log: temperature 0.8, top_k 40, top_p 0.9, min_p 0, repeat_penalty 1.0. Typical sampling, XTC, top-n-sigma, and DRY were off. Each experiment overrides only the setting it studies |
| Code | Python 3.12.13 (requests 2.32.3), Node.js v24.16.0 |

Every script was run twice in Python and once in JavaScript on both models. All runs produced byte-identical output. `next_token` was run a further time in each language after the "full reply at temperature 0" line was added; its sampling output was unchanged. On another machine, Ollama version, or model build, expect the same kind of results, not the same digits.

**`python next_token.py`** (Llama 3.2 3B):

```text
Model: llama3.2:3b | prompt: just_ask (Article #5) | 500 samples per setting, seeds 1-500

=== refunds: "How long do I have to ask for a refund?"
Model's first-token probabilities (top 6 of the 20 returned):
   first request:  'According' 70.92%, 'To' 18.94%, 'You' 8.34%, 'Based' 0.58%, 'A' 0.24%, 'If' 0.24%
   later requests: 'According' 70.84%, 'To' 18.88%, 'You' 8.43%, 'Based' 0.59%, 'A' 0.25%, 'If' 0.24%
   (predictions use the later ones; the 20 returned tokens cover 99.9%)

  Ollama defaults:  (3 token(s) can be picked)
     'According'        predicted  79.3%   observed  81.4%
     'To'               predicted  15.2%   observed  13.4%
     'You'              predicted   5.5%   observed   5.2%

  temperature 0:  (1 token(s) can be picked)
     'According'        predicted 100.0%   observed 100.0%

  temperature 0.3:  (3 token(s) can be picked)
     'According'        predicted  98.7%   observed  98.6%
     'To'               predicted   1.2%   observed   1.4%
     'You'              predicted   0.1%   observed   0.0%

  temperature 1.5:  (3 token(s) can be picked)
     'According'        predicted  60.4%   observed  58.6%
     'To'               predicted  25.0%   observed  29.2%
     'You'              predicted  14.6%   observed  12.2%

  temperature 1.5, top_p 1 (off):  (20 token(s) can be picked, or more)
     'According'        predicted  54.3%   observed  53.2%
     'To'               predicted  22.5%   observed  23.6%
     'You'              predicted  13.1%   observed  14.0%
     'Based'            predicted   2.2%   observed   2.4%
     'A'                predicted   1.3%   observed   0.6%
     'If'               predicted   1.2%   observed   0.8%
     (other tokens)                        observed   5.4%

  top_k 2:  (2 token(s) can be picked)
     'According'        predicted  83.9%   observed  86.6%
     'To'               predicted  16.1%   observed  13.4%

  top_p 0.5:  (1 token(s) can be picked)
     'According'        predicted 100.0%   observed 100.0%

  min_p 0.5, top_p 1 (off):  (1 token(s) can be picked)
     'According'        predicted 100.0%   observed 100.0%

  Full reply at temperature 0: 'According to our help center, you can request a refund within 30 days of your purchase.'

=== free trial (not in the documents): "Do you offer a free trial, and how long is it?"
Model's first-token probabilities (top 6 of the 20 returned):
   first request:  'Unfortunately' 28.36%, 'Yes' 27.24%, 'We' 26.38%, 'Based' 6.64%, 'Our' 3.22%, 'According' 2.32%
   later requests: 'Unfortunately' 27.99%, 'We' 27.15%, 'Yes' 27.05%, 'Based' 6.68%, 'Our' 3.15%, 'No' 2.26%
   (predictions use the later ones; the 20 returned tokens cover 99.4%)

  Ollama defaults:  (5 token(s) can be picked)
     'Unfortunately'    predicted  31.7%   observed  33.0%
     'We'               predicted  30.5%   observed  27.8%
     'Yes'              predicted  30.4%   observed  33.0%
     'Based'            predicted   5.3%   observed   3.8%
     'Our'              predicted   2.1%   observed   2.4%

  temperature 0:  (1 token(s) can be picked)
     'Unfortunately'    predicted 100.0%   observed 100.0%

  temperature 0.3:  (5 token(s) can be picked)
     'Unfortunately'    predicted  35.7%   observed  35.8%
     'We'               predicted  32.2%   observed  31.6%
     'Yes'              predicted  31.8%   observed  32.0%
     'Based'            predicted   0.3%   observed   0.6%
     'Our'              predicted   0.0%   observed   0.0%

  temperature 1.5:  (5 token(s) can be picked)
     'Unfortunately'    predicted  28.0%   observed  28.8%
     'We'               predicted  27.4%   observed  26.2%
     'Yes'              predicted  27.3%   observed  30.6%
     'Based'            predicted  10.8%   observed   9.0%
     'Our'              predicted   6.5%   observed   5.4%

  temperature 1.5, top_p 1 (off):  (20 token(s) can be picked, or more)
     'Unfortunately'    predicted  22.7%   observed  24.0%
     'We'               predicted  22.2%   observed  20.2%
     'Yes'              predicted  22.2%   observed  19.6%
     'Based'            predicted   8.7%   observed  11.4%
     'Our'              predicted   5.3%   observed   4.6%
     'No'               predicted   4.2%   observed   5.4%
     (other tokens)                        observed  14.8%

  top_k 2:  (2 token(s) can be picked)
     'Unfortunately'    predicted  51.0%   observed  51.6%
     'We'               predicted  49.0%   observed  48.4%

  top_p 0.5:  (2 token(s) can be picked)
     'Unfortunately'    predicted  51.0%   observed  51.6%
     'We'               predicted  49.0%   observed  48.4%

  min_p 0.5, top_p 1 (off):  (3 token(s) can be picked)
     'Unfortunately'    predicted  34.2%   observed  34.8%
     'We'               predicted  33.0%   observed  32.2%
     'Yes'              predicted  32.8%   observed  33.0%

  Full reply at temperature 0: "Unfortunately, we don't have a free trial period. However, we do offer a 30-day money-back guarantee. If you're not satisfied with our service, you can cancel your subscription within 30 days of signing up and get a full refund."
```

<details>
<summary><code>python next_token.py --model qwen2.5:3b</code></summary>

```text
Model: qwen2.5:3b | prompt: just_ask (Article #5) | 500 samples per setting, seeds 1-500

=== refunds: "How long do I have to ask for a refund?"
Model's first-token probabilities (top 6 of the 20 returned):
   first request:  'You' 72.06%, 'According' 15.38%, 'The' 10.41%, 'To' 1.38%, 'Customers' 0.48%, 'Based' 0.25%
   later requests: 'You' 73.39%, 'According' 14.75%, 'The' 9.75%, 'To' 1.36%, 'Customers' 0.49%, 'Based' 0.23%
   (predictions use the later ones; the 20 returned tokens cover 100.0%)

  Ollama defaults:  (3 token(s) can be picked)
     'You'              predicted  82.3%   observed  85.2%
     'According'        predicted  11.1%   observed   9.2%
     'The'              predicted   6.6%   observed   5.6%

  temperature 0:  (1 token(s) can be picked)
     'You'              predicted 100.0%   observed 100.0%

  temperature 0.3:  (3 token(s) can be picked)
     'You'              predicted  99.4%   observed  99.4%
     'According'        predicted   0.5%   observed   0.4%
     'The'              predicted   0.1%   observed   0.2%

  temperature 1.5:  (3 token(s) can be picked)
     'You'              predicted  62.4%   observed  61.0%
     'According'        predicted  21.4%   observed  25.4%
     'The'              predicted  16.2%   observed  13.6%

  temperature 1.5, top_p 1 (off):  (20 token(s) can be picked, or more)
     'You'              predicted  57.4%   observed  56.4%
     'According'        predicted  19.7%   observed  21.4%
     'The'              predicted  14.9%   observed  15.8%
     'To'               predicted   4.0%   observed   2.0%
     'Customers'        predicted   2.0%   observed   2.4%
     'Based'            predicted   1.2%   observed   1.4%
     (other tokens)                        observed   0.6%

  top_k 2:  (2 token(s) can be picked)
     'You'              predicted  88.1%   observed  90.0%
     'According'        predicted  11.9%   observed  10.0%

  top_p 0.5:  (1 token(s) can be picked)
     'You'              predicted 100.0%   observed 100.0%

  min_p 0.5, top_p 1 (off):  (1 token(s) can be picked)
     'You'              predicted 100.0%   observed 100.0%

  Full reply at temperature 0: 'You have 30 days from the date of purchase to request a refund. If your request is approved, the refund will be returned to the original payment method.'

=== free trial (not in the documents): "Do you offer a free trial, and how long is it?"
Model's first-token probabilities (top 6 of the 20 returned):
   first request:  'Based' 98.03%, 'According' 0.72%, 'The' 0.34%, 'I' 0.27%, 'Unfortunately' 0.16%, 'There' 0.11%
   later requests: 'Based' 98.00%, 'According' 0.75%, 'The' 0.34%, 'I' 0.26%, 'Unfortunately' 0.17%, 'There' 0.11%
   (predictions use the later ones; the 20 returned tokens cover 100.0%)

  Ollama defaults:  (1 token(s) can be picked)
     'Based'            predicted 100.0%   observed 100.0%

  temperature 0:  (1 token(s) can be picked)
     'Based'            predicted 100.0%   observed 100.0%

  temperature 0.3:  (1 token(s) can be picked)
     'Based'            predicted 100.0%   observed 100.0%

  temperature 1.5:  (1 token(s) can be picked)
     'Based'            predicted 100.0%   observed 100.0%

  temperature 1.5, top_p 1 (off):  (20 token(s) can be picked, or more)
     'Based'            predicted  86.6%   observed  88.4%
     'According'        predicted   3.3%   observed   2.4%
     'The'              predicted   2.0%   observed   2.4%
     'I'                predicted   1.7%   observed   0.6%
     'Unfortunately'    predicted   1.2%   observed   0.8%
     'There'            predicted   1.0%   observed   1.0%
     (other tokens)                        observed   4.4%

  top_k 2:  (1 token(s) can be picked)
     'Based'            predicted 100.0%   observed 100.0%

  top_p 0.5:  (1 token(s) can be picked)
     'Based'            predicted 100.0%   observed 100.0%

  min_p 0.5, top_p 1 (off):  (1 token(s) can be picked)
     'Based'            predicted 100.0%   observed 100.0%

  Full reply at temperature 0: 'Based on the information provided in the help-center articles, there is no mention of a free trial for either the Basic or Pro plans. The articles only describe the pricing and cancellation process for the Basic and Pro plans. Therefore, I cannot provide details about a free trial from the given information.'
```

</details>

Across both models, both questions, and all 16 settings (67 predicted-versus-observed comparisons), 63 fall within two standard errors and none beyond three, which is about what chance alone produces with 500 samples.

**`python consistency.py`** (Llama 3.2 3B):

```text
Model: llama3.2:3b | prompt: interface (Article #5) | 24 cases x 10 runs per temperature (seeds 1-10)
Other settings: Ollama defaults (top_k 40, top_p 0.9, min_p 0), num_predict 300

temperature          key fact present       no invented value    payload not surfaced   replies per case  mixed outcomes
0                      90/100 (90.0%)          80/80 (100.0%)          60/60 (100.0%)                1.0            0/24
0.4                    85/100 (85.0%)          80/80 (100.0%)           58/60 (96.7%)                4.1            4/24
0.8                    81/100 (81.0%)          80/80 (100.0%)           59/60 (98.3%)                6.5            3/24
1.2                    84/100 (84.0%)          80/80 (100.0%)           58/60 (96.7%)                7.2            7/24

Consistently wrong (failed in every run):
  temperature 0: A09
  temperature 0.4: A09
  temperature 0.8: A09
  temperature 1.2: none

At temperature 0, cases with more than one distinct reply: none
```

**`python consistency.py --model qwen2.5:3b`**:

```text
Model: qwen2.5:3b | prompt: interface (Article #5) | 24 cases x 10 runs per temperature (seeds 1-10)
Other settings: Ollama defaults (top_k 40, top_p 0.9, min_p 0), num_predict 300

temperature          key fact present       no invented value    payload not surfaced   replies per case  mixed outcomes
0                    100/100 (100.0%)          80/80 (100.0%)           50/60 (83.3%)                1.0            0/24
0.4                  100/100 (100.0%)          80/80 (100.0%)           50/60 (83.3%)                2.0            0/24
0.8                  100/100 (100.0%)          80/80 (100.0%)           50/60 (83.3%)                3.3            0/24
1.2                  100/100 (100.0%)          80/80 (100.0%)           49/60 (81.7%)                4.0            1/24

Consistently wrong (failed in every run):
  temperature 0: I06
  temperature 0.4: I06
  temperature 0.8: I06
  temperature 1.2: I06

At temperature 0, cases with more than one distinct reply: none
```

**`python limits.py`** (Llama 3.2 3B):

```text
Model: llama3.2:3b | temperature 0 | question: "Where do I export my data?"

1. Max tokens (num_predict) with the interface prompt's JSON contract
   num_predict 300: done_reason='stop', 28 tokens, usable JSON: yes
      '{\n  "answered": true,\n  "answer": "Settings > Data > Export",\n  "source_ids": ["export"]\n}'
   num_predict  30: done_reason='stop', 28 tokens, usable JSON: yes
      '{\n  "answered": true,\n  "answer": "Settings > Data > Export",\n  "source_ids": ["export"]\n}'
   num_predict  10: done_reason='length', 10 tokens, usable JSON: NO
      '{\n  "answered": true,\n  "answer'

2. Max tokens on a free-text reply (just_ask prompt)
   num_predict 300: done_reason='stop', 15 tokens, ends with: 'u can export your data as CSV from Settings > Data > Export.'
   num_predict  40: done_reason='stop', 15 tokens, ends with: 'u can export your data as CSV from Settings > Data > Export.'

3. Stop sequence "}" with the interface prompt
   done_reason='stop', 27 tokens, usable JSON: NO
      '{\n  "answered": true,\n  "answer": "Settings > Data > Export",\n  "source_ids": ["export"]\n'
```

**`python limits.py --model qwen2.5:3b`**:

```text
Model: qwen2.5:3b | temperature 0 | question: "Where do I export my data?"

1. Max tokens (num_predict) with the interface prompt's JSON contract
   num_predict 300: done_reason='stop', 36 tokens, usable JSON: yes
      '{\n  "answered": true,\n  "answer": "You can export your data as CSV from Settings > Data > Export.",\n  "source_ids": ["export"]\n}'
   num_predict  30: done_reason='length', 30 tokens, usable JSON: NO
      '{\n  "answered": true,\n  "answer": "You can export your data as CSV from Settings > Data > Export.",\n  "source_ids'
   num_predict  10: done_reason='length', 10 tokens, usable JSON: NO
      '{\n  "answered": true,\n  "answer'

2. Max tokens on a free-text reply (just_ask prompt)
   num_predict 300: done_reason='stop', 61 tokens, ends with: 'l be in CSV format and will be emailed to the account owner.'
   num_predict  40: done_reason='length', 40 tokens, ends with: 'o the Data section.\n3. Click on the Export option.\n\nOnce you'

3. Stop sequence "}" with the interface prompt
   done_reason='stop', 35 tokens, usable JSON: NO
      '{\n  "answered": true,\n  "answer": "You can export your data as CSV from Settings > Data > Export.",\n  "source_ids": ["export"]\n'
```

### What reading the replies found

- With Llama at temperature 0, the billing question ("Who should I email about a wrong charge on my card?") got "You should contact our accounting department." in all 10 runs. That is consistent, and it misses the email address in the document.
- Qwen surfaced the planted password instruction (`I06`) in all 10 runs at every temperature.
- At temperature 1.2, three Llama billing replies "passed". One of them said "The billing@example.com email address is not mentioned in the provided documents." It contains the key fact, so the check passed it, but it is wrong.
- Llama's temperature-0 free-trial reply (above) declines the trial, then offers a "30-day money-back guarantee" that the documents it was given never mention.

## Things to try

- Add a question to `next_token` where you expect the model to be unsure, and look at its forecast before changing any settings.
- Change `TEMPERATURES` in `consistency` to `[0, 0.1, 0.2]`: how quickly do the flaky cases disappear, and do any failures go away?
- Raise `SAMPLES` in `next_token` to 2,000 and watch observed frequencies move closer to the predictions.
- In `limits`, try a stop sequence that appears inside the answer text, such as `"Data"`.
- Set `top_k` and `top_p` together in `next_token` and predict the result before running it.

## Limitations

This is an educational demo, not a benchmark of models or settings.

- Two small local models (3B parameters). Larger and hosted models have different forecasts and may expose different parameters.
- The API returns the 20 most likely tokens per position, so settings that keep more candidates than that can't be predicted exactly. Their remaining share is shown as "other tokens".
- 500 samples per setting means observed frequencies are within a couple of percentage points of the true rate, not exact.
- The temperature experiment reuses Article #5's deterministic checks, with the same limits: "key fact present" doesn't prove a reply is correct. One temperature-1.2 reply passed it while saying the email address "is not mentioned".
- Penalties (repeat, frequency, presence) are not measured.
