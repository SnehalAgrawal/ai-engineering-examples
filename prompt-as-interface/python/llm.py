"""Chat provider: a local Ollama model (default) or OpenAI."""
import os

import requests
from dotenv import load_dotenv

# Load configuration from a local .env file if one exists.
load_dotenv()


def provider() -> str:
    return os.environ.get("LLM_PROVIDER", "ollama").lower()


def model_name() -> str:
    if provider() == "openai":
        return os.environ.get("OPENAI_CHAT_MODEL", "")
    return os.environ.get("OLLAMA_CHAT_MODEL", "llama3.2:3b")


def reset() -> None:
    """Unloads the Ollama model (keep_alive 0), so the next request starts fresh."""
    if provider() == "ollama":
        base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        response = requests.post(
            f"{base_url}/api/generate",
            json={"model": model_name(), "keep_alive": 0},
            timeout=60,
        )
        response.raise_for_status()


def chat(messages: list[dict], seed: int, max_tokens: int = 300) -> str:
    """
    Sends one chat request and returns the reply text.

    Sampling settings are left at the model's defaults. Only the seed is set, so a
    run can be repeated, and the reply length is capped to keep the suite fast.
    """
    if provider() == "ollama":
        base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        response = requests.post(
            f"{base_url}/api/chat",
            json={
                "model": model_name(),
                "messages": messages,
                "stream": False,
                "options": {"seed": seed, "num_predict": max_tokens},
            },
            timeout=300,
        )
        response.raise_for_status()
        return response.json()["message"]["content"]

    if provider() == "openai":
        from openai import OpenAI

        if not os.environ.get("OPENAI_API_KEY"):
            raise SystemExit("Set OPENAI_API_KEY to use the OpenAI provider.")
        if not model_name():
            raise SystemExit("Set OPENAI_CHAT_MODEL to a chat model your account can use.")
        client = OpenAI()
        response = client.chat.completions.create(
            model=model_name(),
            messages=messages,
            seed=seed,
            max_completion_tokens=max_tokens,
        )
        return response.choices[0].message.content or ""

    raise ValueError(f"Unsupported LLM provider: {provider()}")
