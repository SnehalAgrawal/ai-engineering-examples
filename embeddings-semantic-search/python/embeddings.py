import os
from openai import OpenAI
import requests

def create_embedding(text: str) -> list[float]:
    """
    Creates an embedding for the given text using the configured provider.
    """
    provider = os.environ.get("EMBEDDING_PROVIDER", "openai").lower()
    
    if provider == "openai":
        client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        model = os.environ.get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
        
        response = client.embeddings.create(
            input=[text], 
            model=model
        )
        return response.data[0].embedding

    elif provider == "ollama":
        base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        model = os.environ.get("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text")
        
        response = requests.post(
            f"{base_url}/api/embeddings",
            json={"model": model, "prompt": text}
        )
        response.raise_for_status()
        return response.json()["embedding"]
    
    else:
        raise ValueError(f"Unsupported embedding provider: {provider}")
