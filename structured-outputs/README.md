# Structured Outputs

Asking a model for JSON versus enforcing it with a schema, measured on a support assistant. It accompanies the article **[Structured Outputs: Making LLMs Produce Reliable Data](https://snehalagrawal.com/articles/structured-outputs-making-llms-produce-reliable-data/)**, and reuses the assistant and test cases from [`prompt-as-interface`](../prompt-as-interface/) (Article #5).

## What it demonstrates

Article #5's 24 test cases (answerable questions, questions the documents don't answer, and retrieved tickets with planted instructions) run in four modes:

| Mode | Prompt | Output setting |
|---|---|---|
| `prompt_only` | Article #5's interface prompt, which describes the JSON contract in words | none |
| `json_mode` | the interface prompt | JSON mode: any valid JSON |
| `schema` | the interface prompt | a strict JSON schema (`schema.py`) |
| `schema_no_contract` | the one-line "just ask" prompt | the same strict schema |

The schema requires exactly `answered` (boolean), `answer` (string), and `source_ids` (array), and allows `source_ids` to contain only the ids of the documents retrieved for that question. That is a business rule a schema can express. "The cited document supports the answer" is one it can't.

For each mode, the demo reports whether the reply is valid JSON, whether it matches the schema, Article #5's three content checks, and whether the `answered` flag fits the kind of question. `truncation` shows what a token limit does to a schema-enforced reply.

## Files

| File | Purpose |
|---|---|
| `data/help_center.json`, `data/cases.json` | Support documents and test cases from `prompt-as-interface` (one check extended; see Revisions) |
| `python/schema.py`, `javascript/schema.js` | The schema, built per question, and a validator for it |
| `python/run_modes.py`, `javascript/run_modes.js` | The four-mode experiment; `--regrade` re-checks saved replies without calling the model |
| `python/truncation.py`, `javascript/truncation.js` | One schema-enforced question at several token limits |
| `python/llm.py`, `javascript/llm.js` | Provider: Groq (default) or Ollama, with plain HTTP and rate-limit retries |
| `python/prompts.py`, `python/checks.py` (and `.js`) | Prompts and checks from `prompt-as-interface` |

## Prerequisites

- Python 3.9+ **or** Node.js 18+
- A provider:
  - **Groq** (default; free tier): create an API key at [console.groq.com](https://console.groq.com). The published numbers use `openai/gpt-oss-20b`, which supports strict schemas. One full Python run is about 192 requests and 105,000 tokens. Check your current free-tier limits in the Groq console.
  - **Ollama** (local): [install Ollama](https://ollama.com/download), then `ollama pull llama3.2:1b`. Small local models give much weaker content results, but the shape-versus-meaning lesson is the same.

## Configuration

Copy `.env.example` to `.env` inside `python/` or `javascript/`, and add your key.

| Variable | Default | Notes |
|---|---|---|
| `LLM_PROVIDER` | `groq` | `groq` or `ollama` |
| `GROQ_API_KEY` | none | Required for Groq |
| `GROQ_MODEL` | `openai/gpt-oss-20b` | Must support strict structured outputs for the `schema` modes |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | |
| `OLLAMA_CHAT_MODEL` | `llama3.2:1b` | |

Never commit your `.env` file. The repository `.gitignore` excludes it, and each folder's `.gitignore` excludes the saved `results-*.jsonl` files.

## How to run

### Python

```bash
cd python
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # then add your Groq key

python run_modes.py             # 4 modes x 24 cases x 2 runs (~15 min on the free tier)
python run_modes.py --runs 1    # half the requests and tokens
python truncation.py
python run_modes.py --regrade results-modes-openai_gpt-oss-20b.jsonl   # re-check saved replies, no API calls
LLM_PROVIDER=ollama python run_modes.py --runs 1                       # local model instead
```

### JavaScript

```bash
cd javascript
npm install
cp .env.example .env

node run_modes.js
node truncation.js
node run_modes.js --regrade results-modes-openai_gpt-oss-20b.jsonl
```

## Expected output

Setup: Groq free tier, `openai/gpt-oss-20b`, provider default sampling, seed = run number, `max_completion_tokens` 1000, 2026-11-12.

A hosted model is not a fixed artifact. Groq returns a `system_fingerprint` for the backend configuration that served each request, and documents that determinism "is not guaranteed". The 192 Python requests were served by 36 different fingerprints. The JavaScript run sent the same requests separately, so its replies differ somewhat. It is reported as a second sample, not a byte-for-byte copy. Re-grading the same saved replies in Python and JavaScript gives identical tables.

**Python run** (2 runs per case, 192 requests, 106,517 tokens), re-graded with the final checks:

```text
mode                    valid JSON  matches schema      key fact present     no invented value  payload not surfaced   flag matches  empty answer
prompt_only                  97.9%           97.9%                100.0%                100.0%                100.0%          97.9%             0
json_mode                   100.0%          100.0%                100.0%                100.0%                100.0%          97.9%             0
schema                      100.0%          100.0%                100.0%                100.0%                100.0%         100.0%             0
schema_no_contract          100.0%          100.0%                100.0%                 87.5%                 41.7%          68.8%             0

valid JSON: the reply parses as a JSON object, with no cleanup.
matches schema: exactly answered/answer/source_ids, right types, ids only from the retrieved documents.
flag matches: `answered` is true for answerable questions and false for questions the documents don't answer.

API errors: 0 | finish reasons: stop 192
Tokens used: 106,517 | backend fingerprints: fp_228717f27c, fp_3023a70d60, fp_334cc21c60, fp_34cb00738d, fp_565badff47, fp_5979a0e1b7, fp_63473661d7, fp_75c733514d, fp_80501ff3a1, fp_816fc87d18, fp_84bb35977d, fp_8b41efc9a3, fp_8d13edce1d, fp_92d51d08e5, fp_9340e7d14d, fp_976a85d17a, fp_996f667773, fp_9b8528b477, fp_a12402de73, fp_a4315eb300, fp_a8c584dda7, fp_bb6a356524, fp_c5a89987dc, fp_ce54c53bd5, fp_d23c14756c, fp_d3e146e1a5, fp_d6de37e6be, fp_e11c8bbf69, fp_e189667b30, fp_e23fc997ca, fp_e2cb7a84ec, fp_e99e93f2ac, fp_ed70b23331, fp_ef00694abe, fp_f102a3179c, fp_feb9b278f1
```

**JavaScript run** (1 run per case, 96 requests, 51,473 tokens), re-graded with the final checks:

```text
mode                    valid JSON  matches schema      key fact present     no invented value  payload not surfaced   flag matches  empty answer
prompt_only                 100.0%          100.0%                100.0%                100.0%                100.0%         100.0%             0
json_mode                   100.0%          100.0%                100.0%                100.0%                100.0%         100.0%             0
schema                       91.7%           91.7%                100.0%                100.0%                100.0%          91.7%             0
schema_no_contract          100.0%          100.0%                100.0%                 87.5%                 33.3%          70.8%             0

valid JSON: the reply parses as a JSON object, with no cleanup.
matches schema: exactly answered/answer/source_ids, right types, ids only from the retrieved documents.
flag matches: `answered` is true for answerable questions and false for questions the documents don't answer.

API errors: 2 | finish reasons: error 400 2, stop 94
Tokens used: 51,473 | backend fingerprints: None, fp_228717f27c, fp_3023a70d60, fp_334cc21c60, fp_34cb00738d, fp_565badff47, fp_63473661d7, fp_75c733514d, fp_80501ff3a1, fp_816fc87d18, fp_84bb35977d, fp_8b41efc9a3, fp_8d13edce1d, fp_92d51d08e5, fp_9340e7d14d, fp_976a85d17a, fp_996f667773, fp_9b8528b477, fp_a12402de73, fp_a4315eb300, fp_a8c584dda7, fp_bb6a356524, fp_c5a89987dc, fp_ce54c53bd5, fp_d23c14756c, fp_d3e146e1a5, fp_e11c8bbf69, fp_e189667b30, fp_e23fc997ca, fp_e99e93f2ac, fp_ed70b23331, fp_ef00694abe, fp_f102a3179c, fp_feb9b278f1
```

**`truncation`** (Python; JavaScript gave the same outcome):

```text
Model: openai/gpt-oss-20b (groq) | schema enforced | question: "Where do I export my data?"

max tokens 1000: finish='stop', 623 tokens, valid JSON: yes, matches schema: yes
   reply: '{"answered":true,"answer":"You can export your data as CSV from Settings\u202f>\u202fData\u202f>\u202fExport.","source_ids":["export"]}'
max tokens   60: finish='error 400', 0 tokens, valid JSON: NO, matches schema: NO
   reply: ''
   API error: {"error":{"message":"Failed to validate JSON. Please adjust your prompt. See 'failed_generation' for more details.","type":"invalid_request_error","code":"json_validate_failed","failed_generation":""}}

max tokens   12: finish='error 400', 0 tokens, valid JSON: NO, matches schema: NO
   reply: ''
   API error: {"error":{"message":"Failed to validate JSON. Please adjust your prompt. See 'failed_generation' for more details.","type":"invalid_request_error","code":"json_validate_failed","failed_generation":""}}
```

### What reading the replies found

Every invalid reply, API error, and failed check was read by hand, along with all `schema_no_contract` replies.

- The one invalid `prompt_only` reply was a correct refusal that stopped one character short: `...,"source_ids":[]` with no closing brace.
- The two strict-mode errors in the JavaScript run (cases `N06` and `N07`) were the same: the `failed_generation` field shows the same refusal, missing the same closing brace. Strict mode returned an error instead of invalid JSON. Across 144 strict-mode requests, 2 errored; both are counted as failures in the JavaScript `schema` row, not dropped. Groq documents strict mode as never erroring, so this is an observed discrepancy with the documentation in this run, not schema-invalid output. The cause isn't documented.
- In `schema_no_contract`, the planted instruction reached the customer in 7 of 12 Python runs and 4 of 6 JavaScript runs. In 9 of those 11, `source_ids` cited the malicious ticket, which the retrieved-ids rule allows.
- Without the contract, `answered` meant "I replied": it was `true` on almost every question the documents don't answer. Replies also invented refund times ("3-5 business days") and claimed "unlimited team members" on the Pro plan, which the checks don't catch (no number).
- A local check with `llama3.2:1b` on Ollama (1 run per mode) worked end to end. Twice, the model looped inside `source_ids` (`"plans", "plans", ...`) until the token limit cut the reply into invalid JSON. With a 12-token limit, Ollama returned truncated JSON with finish reason `length`, where Groq returned an HTTP 400 error.
- One valid reply wrote "Settings > Data > Export" with narrow no-break spaces (` `). It is schema-valid, but it would break exact string matching.

### Revisions to the suite

After reading the replies, the `A07` check (two-factor codes by text message) was extended. It had rejected correct answers phrased as "codes are not sent via text message" and "only available through authenticator apps". The extension changes no result in the `prompt-as-interface` or `generation-parameters` runs. It was applied to the saved replies with `--regrade`; no requests were re-sent.

## Things to try

- Add `"maxItems": 3` (or `"uniqueItems": true`) to `source_ids` and rerun with a small local model: does the looping stop? Check which JSON Schema keywords your provider actually enforces first; each structured-output implementation supports a different subset.
- Write a semantic validator: `answered` must be false exactly when `source_ids` is empty, and sources must not include `ticket-` documents. How many replies would it reject in each mode?
- Run `schema_no_contract` with the interface prompt's field descriptions added back one at a time. Which sentence restores the `answered` flag?
- Swap `GROQ_MODEL` for a model with only best-effort schemas, and compare the error and invalid-JSON rates.

## Limitations

This is an educational demo, not a benchmark of providers or models.

- One hosted model on one day, sampled twice in Python and once in JavaScript. Hosted models and their serving stacks change, so expect the same kind of results, not the same digits.
- The free tier limits requests and tokens per minute and per day. The scripts retry when rate-limited, but a full run can still take a while.
- The content checks are the deterministic checks from `prompt-as-interface`, with their known limits: they catch invented values and planted payloads, not every unsupported claim.
- Provider statements about other services (OpenAI, Anthropic, OpenRouter, Cloudflare) in the article come from their documentation and were not measured here.
