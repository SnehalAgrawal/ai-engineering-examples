"""
Part 1: what the sampler settings do to the model's next-token choice.

For two support-assistant questions, it asks the model for the probabilities of
its first token, then, for each setting:
  - predicts how often each token should be picked (sampler.py), and
  - samples the first token SAMPLES times with different seeds and counts.

If the explanation of a setting is right, prediction and observation agree,
within the noise you expect from a finite number of samples.

    python next_token.py
    python next_token.py --model qwen2.5:3b
"""
import argparse
import json
import math
import os
from collections import Counter
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
SAMPLES = 500
TOP = 20  # how many token probabilities to ask for

SETTINGS = [
    ("Ollama defaults", {}),
    ("temperature 0", {"temperature": 0}),
    ("temperature 0.3", {"temperature": 0.3}),
    ("temperature 1.5", {"temperature": 1.5}),
    ("temperature 1.5, top_p 1 (off)", {"temperature": 1.5, "top_p": 1.0}),
    ("top_k 2", {"top_k": 2}),
    ("top_p 0.5", {"top_p": 0.5}),
    ("min_p 0.5, top_p 1 (off)", {"min_p": 0.5, "top_p": 1.0}),
]

QUESTIONS = [
    ("refunds", "How long do I have to ask for a refund?", ["refunds", "cancel"]),
    ("free trial (not in the documents)", "Do you offer a free trial, and how long is it?", ["plans", "cancel"]),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", help="Ollama model (overrides OLLAMA_CHAT_MODEL)")
    args = parser.parse_args()
    if args.model:
        os.environ["OLLAMA_CHAT_MODEL"] = args.model

    from ollama import chat, model_name, unload
    from prompts import just_ask
    from sampler import DEFAULTS, predict

    documents = json.loads((DATA / "help_center.json").read_text())["documents"]
    unload()
    print(f"Model: {model_name()} | prompt: just_ask (Article #5) | {SAMPLES} samples per setting, seeds 1-{SAMPLES}\n")

    for label, question, context in QUESTIONS:
        messages = just_ask(question, [(d, documents[d]) for d in context])

        # The model's probabilities for its first token. They don't depend on the
        # sampler settings: they are what the settings then work on.
        # Asked twice: in testing, the first request after the model loaded gave
        # slightly different probabilities from every later identical request, and
        # the samples below are drawn under the later ("warm") conditions.
        # Called right away, within this iteration, so it always sees this question's messages.
        def first_token_probabilities():
            first = chat(messages, {"num_predict": 1, "seed": 0}, top_logprobs=TOP)["logprobs"][0]["top_logprobs"]  # noqa: B023
            return [(t["token"], math.exp(t["logprob"])) for t in first]

        cold = first_token_probabilities()
        probabilities = first_token_probabilities()
        covered = sum(p for _, p in probabilities)
        print(f"=== {label}: \"{question}\"")
        print("Model's first-token probabilities (top 6 of the 20 returned):")
        print("   first request:  " + ", ".join(f"{token!r} {p:.2%}" for token, p in cold[:6]))
        print("   later requests: " + ", ".join(f"{token!r} {p:.2%}" for token, p in probabilities[:6]))
        print(f"   (predictions use the later ones; the 20 returned tokens cover {covered:.1%})")

        for name, overrides in SETTINGS:
            settings = {**DEFAULTS, **overrides}
            predicted = predict(probabilities, **settings)
            picks = Counter(
                chat(messages, {**overrides, "num_predict": 1, "seed": seed})["message"]["content"]
                for seed in range(1, SAMPLES + 1)
            )
            shown = sorted(set(predicted) | set(picks), key=lambda t: (-predicted.get(t, 0), -picks.get(t, 0), t))
            print(f"\n  {name}:  ({len(predicted)} token(s) can be picked{'' if len(predicted) < TOP else ', or more'})")
            for token in shown[:6]:
                p = f"{predicted[token]:6.1%}" if token in predicted else "     -"
                print(f"     {token!r:18} predicted {p}   observed {picks.get(token, 0) / SAMPLES:6.1%}")
            rest = sum(picks[t] for t in shown[6:])
            if rest:
                print(f"     {'(other tokens)':18} {'':16}   observed {rest / SAMPLES:6.1%}")

        # The whole reply that temperature 0 produces (always the most likely token).
        greedy = chat(messages, {"temperature": 0, "seed": 1, "num_predict": 300})["message"]["content"]
        print(f"\n  Full reply at temperature 0: {greedy!r}")
        print()


if __name__ == "__main__":
    main()
