"""
Predicts the KV cache size from the model's shape, then compares the
prediction with what Ollama allocates (from Ollama's server log).

  python kv_cache.py
  python kv_cache.py --model llama3.2:1b --ctx 2048 4096 8192

For every token in the context, every layer stores one key vector and one
value vector per KV head:

  bytes per token = layers x KV heads x (key size + value size) x bytes per value

Ollama's default cache type is f16: 2 bytes per value.
"""
import argparse
import os
import re
from pathlib import Path

from ollama_client import generate, model_name, model_size_bytes, show, unload, version

parser = argparse.ArgumentParser()
parser.add_argument("--model")
parser.add_argument("--ctx", type=int, nargs="+", default=[4096, 8192])
args = parser.parse_args()
model = args.model or model_name()
log_path = Path(os.path.expanduser(os.environ.get("OLLAMA_LOG", "~/.ollama/logs/server.log")))

info = show(model)["model_info"]
arch = info["general.architecture"]
layers = info[f"{arch}.block_count"]
kv_heads = info[f"{arch}.attention.head_count_kv"]
head_size = info[f"{arch}.embedding_length"] // info[f"{arch}.attention.head_count"]
key_size = info.get(f"{arch}.attention.key_length", head_size)
value_size = info.get(f"{arch}.attention.value_length", head_size)
per_token = layers * kv_heads * (key_size + value_size) * 2
MiB = 2**20

print(f"Model: {model} | Ollama {version()} | weights on disk: {model_size_bytes(model) / 1e9:.2f} GB")
print(f"Shape: {layers} layers, {kv_heads} KV heads, key size {key_size}, value size {value_size}")
print(f"Per token: {layers} x {kv_heads} x ({key_size} + {value_size}) x 2 bytes = {per_token:,} bytes ({per_token / 1024:.0f} KiB)\n")
print(f"{'context':>8}{'predicted':>14}{'Ollama log':>14}")

for ctx in args.ctx:
    predicted = per_token * ctx / MiB
    unload(model)
    start = log_path.stat().st_size if log_path.exists() else None
    generate("Hi", num_predict=1, model=model, num_ctx=ctx)  # loads the model with this context size
    logged = "n/a"
    if start is not None:
        with log_path.open() as f:
            f.seek(start)
            sizes = re.findall(r"llama_kv_cache: size =\s*([\d.]+) MiB \(\s*(\d+) cells", f.read())
        if sizes:
            logged = f"{float(sizes[-1][0]):.2f} MiB"
    print(f"{ctx:>8}{predicted:>10.2f} MiB{logged:>14}")
unload(model)

if not log_path.exists():
    print(f"\nNo server log at {log_path}; set OLLAMA_LOG to compare with what Ollama allocated.")
