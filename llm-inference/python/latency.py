"""
Where the time goes in one request: prefill (reading the prompt) and decode
(generating the answer, one token at a time).

  python latency.py
  python latency.py --model llama3.2:1b

Part 1 grows the prompt and keeps the answer at 32 tokens.
Part 2 keeps the prompt short and grows the answer.

Each request starts with a unique line, so no request can reuse the cached
prompt of the one before. Every setting runs --reps times; the tables show
medians.
"""
import argparse
import json
import platform
import subprocess

from ollama_client import QUESTION, document, generate, median, model_name, unload, version

parser = argparse.ArgumentParser()
parser.add_argument("--model")
parser.add_argument("--reps", type=int, default=3)
args = parser.parse_args()
model = args.model or model_name()
SECTIONS = [8, 16, 32, 64, 100]
OUTPUT_TOKENS = [16, 64, 256]


def power_source() -> str:
    if platform.system() != "Darwin":
        return "unknown"
    out = subprocess.run(["pmset", "-g", "batt"], capture_output=True, text=True).stdout
    return "battery" if "Battery Power" in out else "AC power" if "AC Power" in out else "unknown"


unload(model)
warm = generate("Hello", num_predict=1, model=model)  # loads the model; not part of the measurements
print(f"Model: {model} | Ollama {version()} | {platform.machine()} | power: {power_source()} | "
      f"temperature 0 | {args.reps} runs per setting, medians")
print(f"Model load before the runs: {warm['load_s']:.2f} s\n")

part1 = {n: [] for n in SECTIONS}
part2 = {n: [] for n in OUTPUT_TOKENS}
for rep in range(1, args.reps + 1):
    for n in SECTIONS:
        prompt = f"Request {rep}-{n}.\n{document(n)}\n\n{QUESTION}"
        part1[n].append(generate(prompt, num_predict=32, model=model))
    for n in OUTPUT_TOKENS:
        prompt = f"Request {rep}-out{n}.\n{QUESTION}"
        part2[n].append(generate(prompt, num_predict=n, model=model))
unload(model)


def m(runs, key):
    return median([r[key] for r in runs])


print("1. Longer prompt, same 32-token answer")
print(f"{'input tokens':>13}{'processed':>11}{'prefill':>11}{'prefill speed':>16}{'first token':>13}{'decode speed':>15}")
for n, runs in part1.items():
    processed = m(runs, "input_tokens") - m(runs, "cached_tokens")
    print(f"{m(runs, 'input_tokens'):>13.0f}{processed:>11.0f}{m(runs, 'prefill_s') * 1000:>8.0f} ms"
          f"{median([(r['input_tokens'] - r['cached_tokens']) / r['prefill_s'] for r in runs]):>10.0f} tok/s"
          f"{m(runs, 'ttft_s') * 1000:>10.0f} ms"
          f"{median([r['output_tokens'] / r['decode_s'] for r in runs]):>9.1f} tok/s")

print("\n2. Same short prompt, longer answer")
print(f"{'output tokens':>14}{'first token':>13}{'decode':>11}{'total':>11}{'decode speed':>15}")
for n, runs in part2.items():
    print(f"{m(runs, 'output_tokens'):>14.0f}{m(runs, 'ttft_s') * 1000:>10.0f} ms{m(runs, 'decode_s'):>9.2f} s"
          f"{m(runs, 'total_s'):>9.2f} s{median([r['output_tokens'] / r['decode_s'] for r in runs]):>9.1f} tok/s")

print("\nprocessed: input tokens actually computed (input tokens minus tokens reused from Ollama's cache).")
print("first token: time from sending the request to receiving the first generated text, measured by this script.")
out = f"results-latency-{model.replace(':', '_')}.json"
with open(out, "w") as f:
    json.dump({"model": model, "part1": part1, "part2": part2}, f, indent=1)
print(f"Every run was saved to {out}.")
