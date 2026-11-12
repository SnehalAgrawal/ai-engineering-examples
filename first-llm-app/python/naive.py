"""
The model as the whole product: the user's text goes straight to the model,
and the model's reply goes straight back. No context, no checks.
"""
from llm import chat


def answer(text: str, url: str | None = None) -> str:
    return chat([{"role": "user", "content": text}], url=url)["content"]
