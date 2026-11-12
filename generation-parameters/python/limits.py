"""
Part 3: max tokens and stop sequences cut the output; they don't shape it.

Uses temperature 0 so every run gives the same replies, and shows:
  1. num_predict (max tokens) on the interface prompt: the JSON contract breaks.
  2. num_predict on a free-text reply: the answer stops mid-sentence.
  3. A stop sequence of "}": generation stops there, and the "}" itself is not returned.

    python limits.py
    python limits.py --model qwen2.5:3b
"""
import argparse
import json
import os
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", help="Ollama model (overrides OLLAMA_CHAT_MODEL)")
    args = parser.parse_args()
    if args.model:
        os.environ["OLLAMA_CHAT_MODEL"] = args.model

    from checks import parse_contract
    from ollama import chat, model_name, unload
    from prompts import interface, just_ask

    documents = json.loads((DATA / "help_center.json").read_text())["documents"]
    context = [(d, documents[d]) for d in ["export"]]
    question = "Where do I export my data?"
    unload()
    print(f"Model: {model_name()} | temperature 0 | question: \"{question}\"\n")

    def run(messages, **options):
        response = chat(messages, {"temperature": 0, "seed": 1, **options})
        return response["message"]["content"], response.get("done_reason"), response.get("eval_count")

    print("1. Max tokens (num_predict) with the interface prompt's JSON contract")
    for limit in (300, 30, 10):
        reply, reason, tokens = run(interface(question, context), num_predict=limit)
        contract, _ = parse_contract(reply)
        print(f"   num_predict {limit:>3}: done_reason={reason!r}, {tokens} tokens, usable JSON: {'yes' if contract else 'NO'}")
        print(f"      {reply!r}")

    print("\n2. Max tokens on a free-text reply (just_ask prompt)")
    for limit in (300, 40):
        reply, reason, tokens = run(just_ask(question, context), num_predict=limit)
        print(f"   num_predict {limit:>3}: done_reason={reason!r}, {tokens} tokens, ends with: {reply[-60:]!r}")

    print("\n3. Stop sequence \"}\" with the interface prompt")
    reply, reason, tokens = run(interface(question, context), num_predict=300, stop=["}"])
    contract, _ = parse_contract(reply)
    print(f"   done_reason={reason!r}, {tokens} tokens, usable JSON: {'yes' if contract else 'NO'}")
    print(f"      {reply!r}")


if __name__ == "__main__":
    main()
