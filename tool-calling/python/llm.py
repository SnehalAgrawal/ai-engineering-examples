"""
Chat provider with tool calling: a local Ollama model (default) or Groq's free tier.

Both are called with plain HTTP. The two APIs shape tool calls slightly
differently, so every reply is normalised to the same form:

  {"content": str, "tool_calls": [{"id", "name", "arguments"}], "finish_reason",
   "tokens", "fingerprint", "error", "message"}

"arguments" is always the raw JSON text the model produced. "message" is the
assistant message to append to the conversation before sending tool results.
"""
import json
import os
import time

import requests
from dotenv import load_dotenv

load_dotenv()

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


def provider() -> str:
    return os.environ.get("LLM_PROVIDER", "ollama").lower()


def model_name() -> str:
    if provider() == "groq":
        return os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b")
    return os.environ.get("OLLAMA_CHAT_MODEL", "llama3.2:3b")


def chat(messages: list[dict], tools: list[dict], seed: int, max_tokens: int) -> dict:
    if provider() == "groq":
        return _groq(messages, tools, seed, max_tokens)
    if provider() == "ollama":
        return _ollama(messages, tools, seed, max_tokens)
    raise ValueError(f"Unsupported LLM provider: {provider()}")


def tool_message(call: dict, content: str) -> dict:
    """The message that returns one tool result to the model."""
    if provider() == "groq":
        return {"role": "tool", "tool_call_id": call["id"], "name": call["name"], "content": content}
    return {"role": "tool", "tool_name": call["name"], "content": content}


def reset() -> None:
    """Ollama: unload the model so runs start from the same state and memory is freed afterwards."""
    if provider() == "ollama":
        base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        requests.post(f"{base_url}/api/generate", json={"model": model_name(), "keep_alive": 0}, timeout=60).raise_for_status()


def _groq(messages, tools, seed, max_tokens):
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        raise SystemExit("Set GROQ_API_KEY in python/.env (create a free key at https://console.groq.com).")
    body = {"model": model_name(), "messages": messages, "tools": tools, "tool_choice": "auto",
            "seed": seed, "max_completion_tokens": max_tokens}
    for _ in range(8):
        response = requests.post(GROQ_URL, json=body, headers={"Authorization": f"Bearer {key}"}, timeout=120)
        if response.status_code == 429:
            # Free-tier rate limit: wait as long as Groq asks, then retry.
            time.sleep(min(max(float(response.headers.get("retry-after", 10)), 1.0), 120))
            continue
        if response.status_code >= 400:
            # Keep API errors (for example a malformed tool call Groq rejected) as results.
            return {"content": "", "tool_calls": [], "finish_reason": f"error {response.status_code}",
                    "tokens": 0, "fingerprint": None, "error": response.text[:500], "message": None}
        data = response.json()
        choice = data["choices"][0]
        raw_calls = choice["message"].get("tool_calls") or []
        calls = [{"id": c["id"], "name": c["function"]["name"], "arguments": c["function"]["arguments"]} for c in raw_calls]
        content = choice["message"].get("content") or ""
        message = {"role": "assistant", "content": content}
        if raw_calls:
            message["tool_calls"] = raw_calls
        return {"content": content, "tool_calls": calls, "finish_reason": choice.get("finish_reason"),
                "tokens": data.get("usage", {}).get("total_tokens", 0),
                "fingerprint": data.get("system_fingerprint"), "error": None, "message": message}
    raise SystemExit("Still rate-limited after several retries. Try again later or lower the number of runs.")


def _ollama(messages, tools, seed, max_tokens):
    base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    body = {"model": model_name(), "messages": messages, "tools": tools, "stream": False,
            "options": {"seed": seed, "num_predict": max_tokens}}
    response = requests.post(f"{base_url}/api/chat", json=body, timeout=300)
    response.raise_for_status()
    data = response.json()
    raw_calls = data["message"].get("tool_calls") or []
    # Ollama returns arguments as an object; keep the JSON text so both providers look the same.
    calls = [{"id": c.get("id", f"call_{i}"), "name": c["function"]["name"],
              "arguments": json.dumps(c["function"].get("arguments", {}))} for i, c in enumerate(raw_calls)]
    content = data["message"].get("content") or ""
    message = {"role": "assistant", "content": content}
    if raw_calls:
        message["tool_calls"] = raw_calls
    return {"content": content, "tool_calls": calls, "finish_reason": data.get("done_reason"),
            "tokens": data.get("prompt_eval_count", 0) + data.get("eval_count", 0),
            "fingerprint": None, "error": None, "message": message}
