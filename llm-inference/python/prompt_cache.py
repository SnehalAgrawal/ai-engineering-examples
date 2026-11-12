"""
Prompt caching: when a request starts with the same tokens as an earlier one,
the server can reuse the work it already did for that prefix.

  python prompt_cache.py
  python prompt_cache.py --model llama3.2:1b

The same long document is sent four times, with the question in different
places. Every sequence starts from an unloaded model; it runs --reps times
and the table shows medians.
"""
import argparse
import json

from ollama_client import document, generate, median, model_name, unload, version

parser = argparse.ArgumentParser()
parser.add_argument("--model")
parser.add_argument("--reps", type=int, default=3)
args = parser.parse_args()
model = args.model or model_name()

DOC = document(80)
Q1 = "Which section explains how to cancel a subscription? Answer with the section number only."
Q2 = "Which section explains how to export data? Answer with the section number only."
STEPS = [
    ("1. document, question 1", f"{DOC}\n\n{Q1}"),
    ("2. same document, question 2", f"{DOC}\n\n{Q2}"),
    ("3. question 2, then the document", f"{Q2}\n\n{DOC}"),
    ("4. document, question 1 again", f"{DOC}\n\n{Q1}"),
]

results = {label: [] for label, _ in STEPS}
for rep in range(args.reps):
    unload(model)
    generate("Hello", num_predict=1, model=model)  # load the model first, so loading isn't measured
    for label, prompt in STEPS:
        results[label].append(generate(prompt, num_predict=8, model=model))
unload(model)

print(f"Model: {model} | Ollama {version()} | temperature 0 | {args.reps} sequences, medians\n")
print(f"{'request':<36}{'input tokens':>13}{'reused':>9}{'computed':>10}{'prefill':>11}{'first token':>13}")
for label, runs in results.items():
    get = lambda key: median([r[key] for r in runs])
    print(f"{label:<36}{get('input_tokens'):>13.0f}{get('cached_tokens'):>9.0f}"
          f"{get('input_tokens') - get('cached_tokens'):>10.0f}{get('prefill_s') * 1000:>8.0f} ms{get('ttft_s') * 1000:>10.0f} ms")
print("\nreused: input tokens Ollama read from its cache (prompt_eval_cached_count).")
out = f"results-cache-{model.replace(':', '_')}.json"
with open(out, "w") as f:
    json.dump({"model": model, "runs": results}, f, indent=1)
print(f"Every run was saved to {out}.")
