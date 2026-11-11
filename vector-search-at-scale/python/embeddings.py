import os

import requests
from dotenv import load_dotenv
from openai import OpenAI

# Load configuration from a local .env file if one exists.
load_dotenv()


def create_embeddings(texts: list[str]) -> list[list[float]]:
    """
    Creates one embedding per input text using the configured provider.

    Texts are sent in a single batched request. Embedding one text per request
    works too, but batching is how you would normally index many documents.
    """
    provider = os.environ.get("EMBEDDING_PROVIDER", "openai").lower()

    if provider == "openai":
        client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        model = os.environ.get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

        response = client.embeddings.create(input=texts, model=model)
        # The API returns one item per input, each carrying its input index.
        ordered = sorted(response.data, key=lambda item: item.index)
        return [item.embedding for item in ordered]

    if provider == "ollama":
        base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        model = os.environ.get("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text")

        response = requests.post(
            f"{base_url}/api/embed",
            json={"model": model, "input": texts},
            timeout=120,
        )
        response.raise_for_status()
        return response.json()["embeddings"]

    raise ValueError(f"Unsupported embedding provider: {provider}")


def create_embedding(text: str) -> list[float]:
    """Convenience wrapper for embedding a single text."""
    return create_embeddings([text])[0]
