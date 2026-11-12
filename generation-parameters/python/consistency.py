"""
Part 2: does a lower temperature make the assistant right, or only consistent?

Runs Article #5's interface prompt on its 24 test cases at several
temperatures, RUNS times each (seed = run number), and reports per temperature:
  - the same three checks as Article #5,
  - how many different replies each case produced, and
  - which cases failed in every run ("consistently wrong").

    python consistency.py
    python consistency.py --model qwen2.5:3b
"""
import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
TEMPERATURES = [0, 0.4, 0.8, 1.2]
RUNS = 10
CATEGORIES = [
    ("answerable", "key fact present"),
    ("not_in_docs", "no invented value"),
    ("injection", "payload not surfaced"),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", help="Ollama model (overrides OLLAMA_CHAT_MODEL)")
    args = parser.parse_args()
    if args.model:
        os.environ["OLLAMA_CHAT_MODEL"] = args.model

    from checks import parse_contract, passes
    from ollama import chat, model_name, unload
    from prompts import interface

    documents = json.loads((DATA / "help_center.json").read_text())["documents"]
    cases = json.loads((DATA / "cases.json").read_text())["cases"]
    unload()
    print(f"Model: {model_name()} | prompt: interface (Article #5) | {len(cases)} cases x {RUNS} runs per temperature (seeds 1-{RUNS})")
    print("Other settings: Ollama defaults (top_k 40, top_p 0.9, min_p 0), num_predict 300\n")

    records = []
    for temperature in TEMPERATURES:
        for case in cases:
            messages = interface(case["question"], [(d, documents[d]) for d in case["context"]])
            for run in range(1, RUNS + 1):
                reply = chat(messages, {"temperature": temperature, "seed": run, "num_predict": 300})["message"]["content"]
                contract, _ = parse_contract(reply)
                visible = contract["answer"] if contract else reply
                records.append({
                    "temperature": temperature, "case": case["id"], "category": case["category"], "run": run,
                    "passed": passes(case["check"], visible), "reply": reply,
                })
                print(".", end="", file=sys.stderr, flush=True)
        print(file=sys.stderr)

    out = Path(f"results-consistency-{model_name().replace(':', '_').replace('/', '_')}.jsonl")
    out.write_text("".join(json.dumps(r) + "\n" for r in records))
    report(records)
    print(f"\nEvery reply was saved to {out}.")


def percent(part: int, whole: int) -> str:
    """One decimal place, rounding halves up, using integers so Python and JavaScript agree."""
    tenths = (2000 * part + whole) // (2 * whole)
    return f"{tenths // 10}.{tenths % 10}%"


def report(records):
    print(f"{'temperature':<13}" + "".join(f"{label:>24}" for _, label in CATEGORIES)
          + f"{'replies per case':>19}{'mixed outcomes':>16}")
    for temperature in TEMPERATURES:
        rows = [r for r in records if r["temperature"] == temperature]
        cells = ""
        for category, _ in CATEGORIES:
            subset = [r for r in rows if r["category"] == category]
            passed = sum(r["passed"] for r in subset)
            cells += f"{f'{passed}/{len(subset)} ({percent(passed, len(subset))})':>24}"
        replies, outcomes = defaultdict(set), defaultdict(set)
        for r in rows:
            replies[r["case"]].add(r["reply"])
            outcomes[r["case"]].add(r["passed"])
        distinct = sum(len(v) for v in replies.values()) / len(replies)
        mixed = sum(len(v) > 1 for v in outcomes.values())
        print(f"{temperature:<13}{cells}{distinct:>19.1f}{f'{mixed}/{len(outcomes)}':>16}")

    print("\nConsistently wrong (failed in every run):")
    for temperature in TEMPERATURES:
        rows = [r for r in records if r["temperature"] == temperature]
        always = sorted({r["case"] for r in rows} - {r["case"] for r in rows if r["passed"]})
        print(f"  temperature {temperature}: {', '.join(always) if always else 'none'}")

    zero = [r for r in records if r["temperature"] == 0]
    varied = sorted({c for c in {r["case"] for r in zero} if len({r["reply"] for r in zero if r["case"] == c}) > 1})
    print(f"\nAt temperature 0, cases with more than one distinct reply: {', '.join(varied) if varied else 'none'}")


if __name__ == "__main__":
    main()
