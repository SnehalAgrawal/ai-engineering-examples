"""
Runs every test case against every prompt variant, several times, and reports
how often each variant behaved correctly.

    python run_suite.py                      # all variants, 5 runs each
    python run_suite.py --model qwen2.5:7b   # another Ollama model
    python run_suite.py --case I04 --runs 1  # print the raw replies for one case
"""
import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
CATEGORIES = [
    ("answerable", "key fact present"),
    ("not_in_docs", "no invented value detected"),
    ("injection", "planted payload not surfaced"),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", help="Ollama model to use (overrides OLLAMA_CHAT_MODEL)")
    parser.add_argument("--runs", type=int, default=5, help="runs per case; run r uses seed r")
    parser.add_argument("--case", help="only run this case id and print the replies")
    args = parser.parse_args()
    if args.model:
        os.environ["OLLAMA_CHAT_MODEL"] = args.model

    # Imported after --model is applied, so the provider sees the override.
    from checks import parse_contract, passes
    from llm import chat, model_name, provider, reset
    from prompts import VARIANTS

    documents = json.loads((DATA / "help_center.json").read_text())["documents"]
    cases = json.loads((DATA / "cases.json").read_text())["cases"]
    if args.case:
        cases = [c for c in cases if c["id"] == args.case]
        if not cases:
            raise SystemExit(f"No case with id {args.case}")

    print(f"Model: {model_name()} ({provider()}) | {len(cases)} cases x {args.runs} runs (seeds 1-{args.runs}) | default sampling settings\n")

    # Start every suite run from the same state. With Ollama, a reply could change
    # with the same seed depending on what the loaded model had processed before,
    # so the model is unloaded first. A full run is then repeatable.
    reset()

    records = []
    for variant, build in VARIANTS.items():
        for case in cases:
            context = [(doc_id, documents[doc_id]) for doc_id in case["context"]]
            for run in range(1, args.runs + 1):
                reply = chat(build(case["question"], context), seed=run)
                contract, how = parse_contract(reply) if variant == "interface" else (None, None)
                visible = contract["answer"] if contract else reply
                records.append({
                    "variant": variant, "case": case["id"], "category": case["category"], "run": run,
                    "passed": passes(case["check"], visible), "contract": how,
                    "answered": contract["answered"] if contract else None,
                    "sources_ok": set(contract["source_ids"]) <= set(case["context"]) if contract else None,
                    "no_sources": contract["source_ids"] == [] if contract else None,
                    "reply": reply,
                })
                if args.case:
                    print(f"--- {variant} | run {run} | {'PASS' if records[-1]['passed'] else 'FAIL'}\n{reply}\n")
                else:
                    print(".", end="", file=sys.stderr, flush=True)
    print(file=sys.stderr)
    if args.case:
        return

    out = Path(f"results-{model_name().replace(':', '_').replace('/', '_')}.jsonl")
    out.write_text("".join(json.dumps(r) + "\n" for r in records))
    report(records)
    print(f"\nEvery reply was saved to {out}. Read the failures before trusting a score.")


def report(records):
    def count(rows):
        passed = sum(r["passed"] for r in rows)
        return f"{passed:>3}/{len(rows):<3} ({100 * passed / len(rows):5.1f}%)"

    header = "".join(f"{label:>30}" for _, label in CATEGORIES)
    print(f"{'':16}{header}")
    for variant in dict.fromkeys(r["variant"] for r in records):
        rows = [r for r in records if r["variant"] == variant]
        cells = "".join(f"{count([r for r in rows if r['category'] == cat]):>30}" for cat, _ in CATEGORIES)
        print(f"{variant:16}{cells}")

    iface = [r for r in records if r["variant"] == "interface"]
    if iface:
        usable = [r for r in iface if r["contract"]]
        fenced = sum(r["contract"] == "fenced" for r in iface)
        declined = [r for r in usable if r["category"] == "not_in_docs"]
        not_in_docs = [r for r in iface if r["category"] == "not_in_docs"]
        print("\nInterface contract:")
        print(f"  usable JSON reply                     {len(usable):>3}/{len(iface)} ({fenced} wrapped in a Markdown code fence)")
        print(f"  \"answered\": false on not-in-docs      {sum(r['answered'] is False for r in declined):>3}/{len(not_in_docs)}")
        print(f"  source_ids all from retrieved docs    {sum(r['sources_ok'] for r in usable):>3}/{len(usable)}")
        not_answered = [r for r in usable if r["answered"] is False]
        print(f"  \"answered\": false with no source_ids  {sum(r['no_sources'] for r in not_answered):>3}/{len(not_answered)}")

    outcomes = defaultdict(set)
    for r in records:
        outcomes[(r["variant"], r["case"])].add(r["passed"])
    flaky = defaultdict(int)
    for (variant, _), seen in outcomes.items():
        flaky[variant] += len(seen) > 1
    print("\nCases with different outcomes across runs: " + " | ".join(f"{v} {n}" for v, n in flaky.items()))


if __name__ == "__main__":
    main()
