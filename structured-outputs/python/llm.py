"""
Chat provider: Groq (default, free tier) or a local Ollama model.

Both are called with plain HTTP, and both support the three output modes the
demo compares:
  None    free text (whatever the prompt asks for)
  "json"  JSON mode: any syntactically valid JSON
  dict    a JSON schema the output is constrained to
"""
import os
import time

import requests
from dotenv import load_dotenv

load_dotenv()

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


def provider() -> str:
    return os.environ.get("LLM_PROVIDER", "groq").lower()


def model_name() -> str:
    if provider() == "groq":
        return os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b")
    return os.environ.get("OLLAMA_CHAT_MODEL", "llama3.2:1b")


def chat(messages: list[dict], seed: int, max_tokens: int, output=None) -> dict:
    """
    Sends one request. Returns the reply text, why generation stopped, the
    tokens used, and (for Groq) the backend fingerprint.
    """
    if provider() == "groq":
        return _groq(messages, seed, max_tokens, output)
    if provider() == "ollama":
        return _ollama(messages, seed, max_tokens, output)
    raise ValueError(f"Unsupported LLM provider: {provider()}")


def reset() -> None:
    """Ollama: unload the model so runs start from the same state and free memory afterwards."""
    if provider() == "ollama":
        base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        requests.post(f"{base_url}/api/generate", json={"model": model_name(), "keep_alive": 0}, timeout=60).raise_for_status()


def _groq(messages, seed, max_tokens, output):
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        raise SystemExit("Set GROQ_API_KEY in python/.env (create a free key at https://console.groq.com).")
    body = {"model": model_name(), "messages": messages, "seed": seed, "max_completion_tokens": max_tokens}
    if output == "json":
        body["response_format"] = {"type": "json_object"}
    elif isinstance(output, dict):
        body["response_format"] = {"type": "json_schema", "json_schema": {"name": "support_reply", "strict": True, "schema": output}}

    for attempt in range(8):
        response = requests.post(GROQ_URL, json=body, headers={"Authorization": f"Bearer {key}"}, timeout=120)
        if response.status_code == 429:
            # Free-tier rate limit: wait as long as Groq asks, then retry.
            wait = float(response.headers.get("retry-after", 10))
            time.sleep(min(max(wait, 1.0), 120))
            continue
        if response.status_code >= 400:
            # Keep API errors (for example a rejected generation) as results instead of crashing the run.
            return {"content": "", "finish_reason": f"error {response.status_code}", "tokens": 0,
                    "fingerprint": None, "error": response.text[:300]}
        data = response.json()
        choice = data["choices"][0]
        return {
            "content": choice["message"].get("content") or "",
            "finish_reason": choice.get("finish_reason"),
            "tokens": data.get("usage", {}).get("total_tokens", 0),
            "fingerprint": data.get("system_fingerprint"),
            "error": None,
        }
    raise SystemExit("Still rate-limited after several retries. Try again later or lower RUNS.")


def _ollama(messages, seed, max_tokens, output):
    base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    body = {"model": model_name(), "messages": messages, "stream": False,
            "options": {"seed": seed, "num_predict": max_tokens}}
    if output is not None:
        body["format"] = output
    response = requests.post(f"{base_url}/api/chat", json=body, timeout=300)
    response.raise_for_status()
    data = response.json()
    return {"content": data["message"]["content"], "finish_reason": data.get("done_reason"),
            "tokens": data.get("prompt_eval_count", 0) + data.get("eval_count", 0), "fingerprint": None, "error": None}
