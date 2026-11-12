"""
A small Ollama client that measures one request.

Ollama reports its own timings in every final response (all in nanoseconds):
  load_duration          loading the model into memory
  prompt_eval_count      input tokens in the prompt
  prompt_eval_cached_count  input tokens reused from the cache
  prompt_eval_duration   processing the uncached input tokens (prefill)
  eval_count             output tokens generated
  eval_duration          generating them (decode)

The client adds one timing of its own: time to first token, measured from
sending the request to receiving the first piece of generated text.
"""
import json
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
DATA = Path(__file__).resolve().parent.parent / "data"
PARAGRAPHS = json.loads((DATA / "paragraphs.json").read_text())["paragraphs"]
QUESTION = "Write the numbers from 1 to 1000, separated by commas."


def model_name() -> str:
    return os.environ.get("OLLAMA_CHAT_MODEL", "llama3.2:3b")


def document(sections: int, offset: int = 0) -> str:
    """A document of numbered sections built from the help-center paragraphs.
    A different offset gives a different document of the same length."""
    return "\n".join(f"Section {i + 1}. {PARAGRAPHS[(i + offset) % len(PARAGRAPHS)]}" for i in range(sections))


def generate(prompt: str, num_predict: int, model: str | None = None, num_ctx: int | None = None) -> dict:
    """Streams one request at temperature 0 and returns Ollama's timings plus time to first token (seconds)."""
    options = {"temperature": 0, "num_predict": num_predict}
    if num_ctx:
        options["num_ctx"] = num_ctx
    body = {"model": model or model_name(), "prompt": prompt, "stream": True, "options": options}
    start = time.perf_counter()
    first_token = None
    final = None
    with requests.post(f"{BASE_URL}/api/generate", json=body, stream=True, timeout=600) as response:
        response.raise_for_status()
        for line in response.iter_lines():
            if not line:
                continue
            chunk = json.loads(line)
            if first_token is None and chunk.get("response"):
                first_token = time.perf_counter() - start
            if chunk.get("done"):
                final = chunk
    total = time.perf_counter() - start
    ns = 1e9
    return {
        "input_tokens": final["prompt_eval_count"],
        "cached_tokens": final.get("prompt_eval_cached_count", 0),
        "output_tokens": final["eval_count"],
        "load_s": final.get("load_duration", 0) / ns,
        "prefill_s": final["prompt_eval_duration"] / ns,
        "decode_s": final["eval_duration"] / ns,
        "ttft_s": first_token,
        "total_s": total,
        "done_reason": final.get("done_reason"),
    }


def unload(model: str | None = None) -> None:
    requests.post(f"{BASE_URL}/api/generate", json={"model": model or model_name(), "keep_alive": 0}, timeout=60).raise_for_status()


def show(model: str | None = None) -> dict:
    response = requests.post(f"{BASE_URL}/api/show", json={"model": model or model_name()}, timeout=60)
    response.raise_for_status()
    return response.json()


def model_size_bytes(model: str | None = None) -> int:
    """Size of the model's weights on disk, from Ollama's model list."""
    name = model or model_name()
    tags = requests.get(f"{BASE_URL}/api/tags", timeout=60).json()["models"]
    return next(m["size"] for m in tags if m["name"] == name)


def version() -> str:
    return requests.get(f"{BASE_URL}/api/version", timeout=60).json()["version"]


def median(values: list[float]) -> float:
    ordered = sorted(values)
    middle = len(ordered) // 2
    return ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2
