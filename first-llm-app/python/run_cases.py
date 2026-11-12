"""
Sends the same ten inputs to the naive version and to the application, and
shows what the customer would see from each.

  python run_cases.py
  python run_cases.py --model qwen2.5:3b

The model-down case points both versions at an address where no model server
is listening.
"""
import argparse
import json
import os

parser = argparse.ArgumentParser()
parser.add_argument("--model")
args = parser.parse_args()
if args.model:
    os.environ["OLLAMA_CHAT_MODEL"] = args.model

import re  # noqa: E402
from pathlib import Path  # noqa: E402

import naive  # noqa: E402
from app import DOCUMENTS, handle, unsupported_values  # noqa: E402
from llm import chat, model_name, unload  # noqa: E402

DATA = Path(__file__).resolve().parent.parent / "data"
CASES = json.loads((DATA / "cases.json").read_text())["cases"]
UNREACHABLE = "http://127.0.0.1:9"  # nothing listens here


def passes(check, text):
    return check is None or any(re.search(p, text, re.IGNORECASE) for p in check["patterns"])


def short(text: str, width: int = 150) -> str:
    text = " ".join(text.split())
    return text if len(text) <= width else text[: width - 1] + "…"


unload()
print(f"Model: {model_name()} | temperature 0, seed 1 | {len(CASES)} inputs, each sent to both versions\n")
records = []
for case in CASES:
    url = UNREACHABLE if case.get("fault") == "unavailable" else None
    try:
        naive_shown = naive.answer(case["input"], url=url)
        naive_error = None
    except Exception as error:  # the naive version has no error handling: this is what reaches the user
        naive_shown, naive_error = f"(unhandled {type(error).__name__}: the request fails with a server error)", type(error).__name__
    result = handle(case["input"], url=url)
    records.append({"case": case["id"], "kind": case["kind"], "naive": naive_shown, "naive_error": naive_error,
                    "app": result["message"], "app_status": result["status"], "app_sources": result["sources"],
                    "app_model_output": result["model_output"], "log": result["log"]})
unload()

all_docs = list(DOCUMENTS.values())
for r, case in zip(records, CASES):
    print(f"[{r['case']}]  input: {short(case['input'], 90)!r} ({len(case['input']):,} characters)")
    print(f"  naive: {short(r['naive'])}")
    print(f"  app:   {r['app_status']} {r['log']['outcome']}: {short(r['app'])}" + (f"  sources: {r['app_sources']}" if r["app_sources"] else ""))
    notes = []
    if case.get("check"):
        notes.append(f"key fact: naive {'yes' if passes(case['check'], r['naive']) else 'NO'}, app {'yes' if passes(case['check'], r['app']) else 'NO'}")
    invented_naive = unsupported_values(r["naive"], all_docs) if not r["naive_error"] else []
    invented_app = unsupported_values(r["app"], all_docs)
    if invented_naive or invented_app:
        notes.append(f"values not in the help center: naive {invented_naive}, app {invented_app}")
    if r["log"]["prompt_tokens"] is not None:
        notes.append(f"app prompt tokens: {r['log']['prompt_tokens']:,}")
    if notes:
        print("  " + " | ".join(notes))
    print()

oversized = next(c for c in CASES if c["kind"] == "oversized")
probe = chat([{"role": "user", "content": oversized["input"]}], max_tokens=1)
unload()
print(f"The oversized input as the naive version sends it: the model server processed {probe['prompt_tokens']:,} prompt tokens "
      f"and returned no error ({len(oversized['input']):,} characters sent).")

print("\nApplication log (one record per request; request ids and latencies differ on every run):")
for r in records:
    print("  " + json.dumps(r["log"]))
with open(f"results-cases-{model_name().replace(':', '_')}.jsonl", "w") as f:
    for r in records:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
