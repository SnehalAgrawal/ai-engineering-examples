"""Minimal Ollama client: chat with explicit sampler options, and model unloading."""
import os

import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")


def model_name() -> str:
    return os.environ.get("OLLAMA_CHAT_MODEL", "llama3.2:3b")


def chat(messages: list[dict], options: dict, top_logprobs: int = 0) -> dict:
    """
    Sends one chat request and returns Ollama's full JSON response.

    `options` are sampler settings (temperature, top_k, top_p, min_p, seed,
    num_predict, stop). Anything not set falls back to Ollama's defaults.
    With top_logprobs > 0, the response also carries the model's probability
    for the most likely tokens at each position.
    """
    body = {"model": model_name(), "messages": messages, "stream": False, "options": options}
    if top_logprobs:
        body["logprobs"] = True
        body["top_logprobs"] = top_logprobs
    response = requests.post(f"{BASE_URL}/api/chat", json=body, timeout=300)
    response.raise_for_status()
    return response.json()


def unload() -> None:
    """
    Unloads the model (keep_alive 0) so every run starts from the same state.
    In testing, a reply could change with the same seed depending on what the
    loaded model had processed before; starting fresh makes runs repeatable.
    """
    response = requests.post(f"{BASE_URL}/api/generate", json={"model": model_name(), "keep_alive": 0}, timeout=60)
    response.raise_for_status()
