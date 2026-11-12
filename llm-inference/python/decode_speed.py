"""
Why a smaller model generates faster, and what a cold start costs.

  python decode_speed.py
  python decode_speed.py --bandwidth-gbs 273      # your machine's memory bandwidth

To generate each token, the model reads (roughly) all of its weights from
memory once. So memory bandwidth divided by the size of the weights gives a
rough upper bound on decode speed. Pass your machine's memory bandwidth to
print that bound next to the measured speed.
"""
import argparse
import json

from ollama_client import QUESTION, generate, median, model_size_bytes, unload, version

parser = argparse.ArgumentParser()
parser.add_argument("--models", nargs="+", default=["llama3.2:1b", "llama3.2:3b"])
parser.add_argument("--reps", type=int, default=3)
parser.add_argument("--bandwidth-gbs", type=float, help="memory bandwidth in GB/s, to print the upper bound")
args = parser.parse_args()

print(f"Ollama {version()} | temperature 0 | 128 output tokens | {args.reps} warm runs per model, medians\n")
header = f"{'model':<14}{'weights':>9}{'cold load':>11}{'cold first token':>18}{'warm first token':>18}{'decode speed':>15}"
if args.bandwidth_gbs:
    header += f"{'upper bound':>14}{'of bound':>10}"
print(header)

saved = {}
for model in args.models:
    unload(model)
    cold = generate("Hello", num_predict=1, model=model)
    warm = [generate(f"Request {r}.\n{QUESTION}", num_predict=128, model=model) for r in range(1, args.reps + 1)]
    unload(model)
    size = model_size_bytes(model)
    speed = median([r["output_tokens"] / r["decode_s"] for r in warm])
    row = (f"{model:<14}{size / 1e9:>6.2f} GB{cold['load_s']:>9.2f} s{cold['ttft_s'] * 1000:>15.0f} ms"
           f"{median([r['ttft_s'] for r in warm]) * 1000:>15.0f} ms{speed:>9.1f} tok/s")
    if args.bandwidth_gbs:
        bound = args.bandwidth_gbs * 1e9 / size
        row += f"{bound:>8.0f} tok/s{speed / bound:>9.0%}"
    print(row)
    saved[model] = {"weights_bytes": size, "cold": cold, "warm": warm}

print("\ncold: the first request after the model was unloaded, including loading it into memory.")
print("upper bound: memory bandwidth / weights size, if every token reads all the weights once.")
with open("results-decode.json", "w") as f:
    json.dump(saved, f, indent=1)
print("Every run was saved to results-decode.json.")
