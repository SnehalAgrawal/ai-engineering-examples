"""
A schema constrains which tokens can come next. It can't make the model finish.

Asks one question with the schema enforced, at several max-tokens limits, and
shows how generation ended and whether the reply is still valid JSON. With a
reasoning model (like gpt-oss on Groq), the limit also covers its reasoning,
so a small limit can run out before any JSON is written.

    python truncation.py
    LLM_PROVIDER=ollama python truncation.py
"""
import json
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"


def main():
    from llm import chat, model_name, provider, reset
    from prompts import interface
    from schema import matches_schema, parse_strict, reply_schema

    documents = json.loads((DATA / "help_center.json").read_text())["documents"]
    question, context_ids = "Where do I export my data?", ["export"]
    messages = interface(question, [(d, documents[d]) for d in context_ids])
    reset()
    print(f"Model: {model_name()} ({provider()}) | schema enforced | question: \"{question}\"\n")
    for limit in (1000, 60, 12):
        response = chat(messages, seed=1, max_tokens=limit, output=reply_schema(context_ids))
        reply = response["content"]
        data = parse_strict(reply)
        print(f"max tokens {limit:>4}: finish={response['finish_reason']!r}, {response['tokens']} tokens, "
              f"valid JSON: {'yes' if data is not None else 'NO'}, matches schema: {'yes' if matches_schema(data, context_ids) else 'NO'}")
        print(f"   reply: {reply!r}")
        if response["error"]:
            print(f"   API error: {response['error']}")
    reset()


if __name__ == "__main__":
    main()
