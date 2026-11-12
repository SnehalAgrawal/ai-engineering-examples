"""
Asking for JSON versus enforcing it.

Runs Article #5's 24 support-assistant cases in four modes, RUNS times each:

  prompt_only         the interface prompt describes the JSON in words; no `format`
  json_mode           the interface prompt + format "json" (any valid JSON)
  schema              the interface prompt + format = the JSON schema in schema.py
  schema_no_contract  the one-line "just ask" prompt + the same schema: shape
                      without any explanation of what the fields mean

and reports, per mode: valid JSON, schema match, the Article #5 content checks,
and whether the `answered` flag matches the kind of question.

    python run_modes.py
    LLM_PROVIDER=ollama python run_modes.py   # local model instead of Groq
"""
import argparse
import json
import os
import sys
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
RUNS = 2
MAX_TOKENS = 1000  # gpt-oss is a reasoning model: its reasoning counts toward this limit
MODES = ["prompt_only", "json_mode", "schema", "schema_no_contract"]
CATEGORIES = [
    ("answerable", "key fact present"),
    ("not_in_docs", "no invented value"),
    ("injection", "payload not surfaced"),
]
# What the `answered` flag should say for each kind of question. Questions with a
# planted instruction are answerable from the legitimate document.
EXPECTED_ANSWERED = {"answerable": True, "not_in_docs": False, "injection": True}


def percent(part: int, whole: int) -> str:
    """One decimal place, rounding halves up, using integers so Python and JavaScript agree."""
    tenths = (2000 * part + whole) // (2 * whole)
    return f"{tenths // 10}.{tenths % 10}%"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", help="model name (overrides GROQ_MODEL or OLLAMA_CHAT_MODEL)")
    parser.add_argument("--runs", type=int, default=RUNS, help=f"runs per case and mode (default {RUNS}); fewer saves free-tier tokens")
    parser.add_argument("--regrade", metavar="RESULTS_JSONL", help="re-apply the current checks to saved replies, without calling the model")
    args = parser.parse_args()
    runs = args.runs
    if args.model:
        os.environ["GROQ_MODEL" if os.environ.get("LLM_PROVIDER", "groq") == "groq" else "OLLAMA_CHAT_MODEL"] = args.model

    from checks import passes
    from llm import chat, model_name, provider, reset
    from prompts import interface, just_ask
    from schema import matches_schema, parse_strict, reply_schema

    documents = json.loads((DATA / "help_center.json").read_text())["documents"]
    cases = json.loads((DATA / "cases.json").read_text())["cases"]

    if args.regrade:
        # Grading only: the saved replies are re-checked with the current checks.
        by_id = {c["id"]: c for c in cases}
        records = [json.loads(line) for line in Path(args.regrade).read_text().splitlines() if line.strip()]
        for r in records:
            case = by_id[r["case"]]
            data = parse_strict(r["reply"])
            valid = matches_schema(data, case["context"])
            r.update({
                "json": data is not None, "schema": valid,
                "passed": passes(case["check"], data["answer"] if valid else r["reply"]),
                "flag_ok": valid and data["answered"] == EXPECTED_ANSWERED[case["category"]],
                "empty": valid and not data["answer"].strip(),
            })
        print(f"Regraded {len(records)} saved replies from {args.regrade} with the current checks (no API calls)\n")
        report(records)
        return

    reset()
    print(f"Model: {model_name()} ({provider()}) | {len(cases)} cases x {runs} runs per mode (seeds 1-{runs}) | default sampling, max tokens {MAX_TOKENS}\n")

    records = []
    for mode in MODES:
        for case in cases:
            context = [(d, documents[d]) for d in case["context"]]
            messages = just_ask(case["question"], context) if mode == "schema_no_contract" else interface(case["question"], context)
            output_format = {"prompt_only": None, "json_mode": "json"}.get(mode, reply_schema(case["context"]))
            for run in range(1, runs + 1):
                response = chat(messages, seed=run, max_tokens=MAX_TOKENS, output=output_format)
                reply = response["content"]
                data = parse_strict(reply)
                valid = matches_schema(data, case["context"])
                visible = data["answer"] if valid else reply
                records.append({
                    "mode": mode, "case": case["id"], "category": case["category"], "run": run,
                    "json": data is not None, "schema": valid,
                    "passed": passes(case["check"], visible),
                    "flag_ok": valid and data["answered"] == EXPECTED_ANSWERED[case["category"]],
                    "empty": valid and not data["answer"].strip(),
                    "finish_reason": response["finish_reason"], "tokens": response["tokens"],
                    "fingerprint": response["fingerprint"], "error": response["error"], "reply": reply,
                })
                print(".", end="", file=sys.stderr, flush=True)
        print(file=sys.stderr)
    reset()

    out = Path(f"results-modes-{model_name().replace(':', '_').replace('/', '_')}.jsonl")
    out.write_text("".join(json.dumps(r) + "\n" for r in records))
    report(records)
    print(f"\nEvery reply was saved to {out}.")


def report(records):
    print(f"{'mode':<20}{'valid JSON':>14}{'matches schema':>16}" + "".join(f"{label:>22}" for _, label in CATEGORIES)
          + f"{'flag matches':>15}{'empty answer':>14}")
    for mode in MODES:
        rows = [r for r in records if r["mode"] == mode]
        n = len(rows)
        cells = f"{percent(sum(r['json'] for r in rows), n):>14}{percent(sum(r['schema'] for r in rows), n):>16}"
        for category, _ in CATEGORIES:
            subset = [r for r in rows if r["category"] == category]
            cells += f"{percent(sum(r['passed'] for r in subset), len(subset)):>22}"
        cells += f"{percent(sum(r['flag_ok'] for r in rows), n):>15}{sum(r['empty'] for r in rows):>14}"
        print(f"{mode:<20}{cells}")
    print("\nvalid JSON: the reply parses as a JSON object, with no cleanup.")
    print("matches schema: exactly answered/answer/source_ids, right types, ids only from the retrieved documents.")
    print("flag matches: `answered` is true for answerable questions and false for questions the documents don't answer.")
    errors = sum(1 for r in records if r["error"])
    print(f"\nAPI errors: {errors} | finish reasons: " + ", ".join(f"{k} {v}" for k, v in sorted(_count(r["finish_reason"] for r in records).items())))
    print(f"Tokens used: {sum(r['tokens'] for r in records):,} | backend fingerprints: {', '.join(sorted({str(r['fingerprint']) for r in records}))}")


def _count(values):
    counts = {}
    for v in values:
        counts[str(v)] = counts.get(str(v), 0) + 1
    return counts


if __name__ == "__main__":
    main()
