"""
Runs one conversation and prints every step: what the model asked for, what
the application did with it, and the final reply.

  python walkthrough.py R1                     # case id from data/cases.json
  python walkthrough.py I1 --prompt basic      # the prompt without rules
  python walkthrough.py --question "Please refund INV-1002"
"""
import argparse
import json
import os

parser = argparse.ArgumentParser()
parser.add_argument("case", nargs="?", default="R1")
parser.add_argument("--question")
parser.add_argument("--prompt", choices=["basic", "contract"], default="contract")
parser.add_argument("--seed", type=int, default=1)
parser.add_argument("--model")
args = parser.parse_args()
if args.model:
    os.environ["GROQ_MODEL" if os.environ.get("LLM_PROVIDER", "ollama") == "groq" else "OLLAMA_CHAT_MODEL"] = args.model

from agent import run_conversation  # noqa: E402
from llm import model_name, provider, reset  # noqa: E402
from tools import DATA  # noqa: E402

prompts = json.loads((DATA / "prompts.json").read_text())
cases = {c["id"]: c for c in json.loads((DATA / "cases.json").read_text())["cases"]}
question = args.question or cases[args.case]["question"]


def show(kind, event):
    if kind == "model":
        if event["error"]:
            print(f"\nMODEL  error: {event['error']}")
        elif event["tool_calls"]:
            for call in event["tool_calls"]:
                print(f"\nMODEL  asks to call {call['name']} with arguments {call['arguments']}")
            if event["content"].strip():
                print(f"       (and wrote: {event['content'].strip()!r})")
        else:
            print(f"\nMODEL  final reply (finish reason: {event['finish_reason']}):\n{event['content'].strip()}")
    else:
        status = "executed" if event["executed"] else "NOT executed"
        print(f"APP    {event['tool']}: {status}")
        print(f"       result sent back: {json.dumps(event['result'], ensure_ascii=False)}")


reset()
print(f"Model: {model_name()} ({provider()}) | prompt: {args.prompt} | seed {args.seed}")
print(f"\nCUSTOMER  {question}")
result = run_conversation(prompts[args.prompt], question, args.seed, on_event=show)
reset()
if result["step_limit"]:
    print("\n(stopped: step limit reached without a final reply)")
print(f"\n{result['steps']} model call(s), {result['tokens']:,} tokens")
