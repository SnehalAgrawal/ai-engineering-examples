"""
Runs the 16 conversations with both system prompts and grades every one.

  python run_cases.py                          # llama3.2:3b on Ollama
  python run_cases.py --model qwen2.5:3b
  LLM_PROVIDER=groq python run_cases.py --runs 1
  python run_cases.py --regrade results-cases-llama3.2_3b.jsonl   # re-check saved conversations, no model calls
"""
import argparse
import json
import os
from collections import Counter

parser = argparse.ArgumentParser()
parser.add_argument("--model")
parser.add_argument("--runs", type=int, default=2)
parser.add_argument("--regrade")
args = parser.parse_args()
if args.model:
    os.environ["GROQ_MODEL" if os.environ.get("LLM_PROVIDER", "ollama") == "groq" else "OLLAMA_CHAT_MODEL"] = args.model

from agent import MAX_STEPS, MAX_TOKENS, run_conversation  # noqa: E402
from grading import grade  # noqa: E402
from llm import model_name, provider, reset  # noqa: E402
from tools import DATA  # noqa: E402

PROMPTS = ["basic", "contract"]
COLUMNS = [
    ("task_right", "task right"),
    ("read_tool_used", "right lookup"),
    ("reply_check", "reply check"),
    ("actions_right", "actions right"),
    ("unrequested_attempted", "unasked action tried"),
    ("unrequested_executed", "unasked action ran"),
    ("planted_text_in_reply", "planted text shown"),
    ("call_as_text", "call written as text"),
    ("claimed_not_done", "claimed, didn't run"),
    ("empty_reply", "empty reply"),
]

prompts = json.loads((DATA / "prompts.json").read_text())
case_file = json.loads((DATA / "cases.json").read_text())
cases, planted = case_file["cases"], case_file["planted_text"]


def percent(part: int, whole: int) -> str:
    """One decimal place, rounding halves up, using integers so Python and JavaScript agree."""
    tenths = (2000 * part + whole) // (2 * whole)
    return f"{tenths // 10}.{tenths % 10}%"


def report(records: list[dict]) -> None:
    print(f"{'prompt':<10}{'n':>4}" + "".join(f"{label:>22}" for _, label in COLUMNS))
    for prompt in PROMPTS:
        rows = [r for r in records if r["prompt"] == prompt]
        cells = "".join(f"{percent(sum(r['grade'][key] for r in rows), len(rows)):>22}" for key, _ in COLUMNS)
        print(f"{prompt:<10}{len(rows):>4}{cells}")
    print("\ntask right: every check below passed for that conversation.")
    print("right lookup: the case's lookup tool was called (cases without one always pass).")
    print("reply check: the final reply passed the case's text check (cases without one pass if the reply is not empty).")
    print("actions right: exactly the expected actions executed, and nothing else.")
    print("unasked action tried / ran: the model requested a refund or email the customer didn't ask for / the application executed it.")
    print("planted text shown: the final reply repeated text from a planted ticket.")
    print("call written as text: the reply contains a tool call as text instead of a structured call (it can't run; the customer sees it).")
    print("claimed, didn't run: the reply says a refund or email happened, but no such call executed.")
    print("empty reply: the model's last message had no text and no tool call.")

    print("\nBy category (task right):")
    for prompt in PROMPTS:
        parts = []
        for category in dict.fromkeys(c["category"] for c in cases):
            rows = [r for r in records if r["prompt"] == prompt and r["category"] == category]
            parts.append(f"{category} {sum(r['grade']['task_right'] for r in rows)}/{len(rows)}")
        print(f"  {prompt:<10}" + ", ".join(parts))

    exposed = [r for r in records if r["grade"]["ticket_retrieved"]]
    print(f"\nPlanted ticket retrieved by a search: {len(exposed)} of {len(records)} conversations")
    for prompt in PROMPTS:
        rows = [r for r in exposed if r["prompt"] == prompt]
        tried = sum(r["grade"]["unrequested_attempted"] for r in rows)
        print(f"  {prompt:<10}unasked action tried in {tried} of {len(rows)}")
    invalid = sum(r["grade"]["invalid_calls"] for r in records)
    calls = sum(len(r["calls"]) for r in records)
    reasons = Counter(reason for r in records for reason in r["finish_reasons"])
    print(f"\nTool calls: {calls} ({invalid} with invalid arguments or an unknown tool) | "
          f"step limit hit: {sum(r['step_limit'] for r in records)} | API errors: {sum(1 for r in records if r['error'])}")
    print("Finish reasons: " + ", ".join(f"{k} {reasons[k]}" for k in sorted(reasons, key=str)))
    print(f"Tokens used: {sum(r['tokens'] for r in records):,}")


if args.regrade:
    by_id = {c["id"]: c for c in cases}
    with open(args.regrade) as f:
        saved = [json.loads(line) for line in f if line.strip()]
    for r in saved:
        r["grade"] = grade(by_id[r["case"]], r, planted)
    print(f"Regraded {len(saved)} saved conversations from {args.regrade} with the current checks (no model calls)\n")
    report(saved)
    raise SystemExit

reset()
print(f"Model: {model_name()} ({provider()}) | {len(cases)} cases x {len(PROMPTS)} prompts x {args.runs} runs "
      f"(seeds 1-{args.runs}) | default sampling, max {MAX_STEPS} model calls and {MAX_TOKENS} tokens per call\n")
records = []
for prompt in PROMPTS:
    for case in cases:
        for run in range(1, args.runs + 1):
            conversation = run_conversation(prompts[prompt], case["question"], seed=run)
            records.append({"prompt": prompt, "case": case["id"], "category": case["category"], "run": run,
                            **conversation, "grade": grade(case, conversation, planted)})
            print(".", end="", flush=True)
    print(flush=True)
reset()

out = f"results-cases-{model_name().replace(':', '_').replace('/', '_')}.jsonl"
with open(out, "w") as f:
    for r in records:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
report(records)
print(f"\nEvery conversation was saved to {out}.")
