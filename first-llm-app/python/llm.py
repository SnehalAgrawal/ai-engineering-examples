"""
The model call: the only part of the application that talks to the model.

Every failure on the way (server down, timeout, HTTP error, a response that
isn't the expected JSON) becomes one exception type, LLMError, so the rest of
the application has a single thing to handle.
"""
import os

import requests
from dotenv import load_dotenv

load_dotenv()


class LLMError(Exception):
    pass


def model_name() -> str:
    return os.environ.get("OLLAMA_CHAT_MODEL", "llama3.2:3b")


def base_url() -> str:
    return os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")


def chat(messages: list[dict], *, schema: dict | None = None, max_tokens: int = 300,
         timeout: float = 60, url: str | None = None) -> dict:
    body = {
        "model": model_name(),
        "messages": messages,
        "stream": False,
        "options": {"temperature": 0, "seed": 1, "num_predict": max_tokens},
    }
    if schema is not None:
        body["format"] = schema  # Ollama constrains the output to this JSON schema
    try:
        response = requests.post(f"{url or base_url()}/api/chat", json=body, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException as error:
        raise LLMError(type(error).__name__) from error
    try:
        data = response.json()
        content = data["message"]["content"]
        if not isinstance(content, str):
            raise TypeError("content is not a string")
    except (ValueError, KeyError, TypeError) as error:
        raise LLMError("InvalidResponse") from error
    return {
        "content": content,
        "prompt_tokens": data.get("prompt_eval_count", 0),
        "output_tokens": data.get("eval_count", 0),
        "done_reason": data.get("done_reason"),
    }


def unload() -> None:
    """Unload the model, so runs start from the same state and memory is freed afterwards."""
    requests.post(f"{base_url()}/api/generate", json={"model": model_name(), "keep_alive": 0}, timeout=60).raise_for_status()
