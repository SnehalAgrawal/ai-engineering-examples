import "dotenv/config"; // Load configuration from a local .env file if one exists.
import OpenAI from "openai";

/**
 * Creates one embedding per input text using the configured provider.
 *
 * Texts are sent in a single batched request. Embedding one text per request
 * works too, but batching is how you would normally index many documents.
 */
export async function createEmbeddings(texts) {
  const provider = (process.env.EMBEDDING_PROVIDER || "openai").toLowerCase();

  if (provider === "openai") {
    const openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });
    const model = process.env.OPENAI_EMBEDDING_MODEL || "text-embedding-3-small";

    const response = await openai.embeddings.create({
      model,
      input: texts,
      encoding_format: "float",
    });

    // The API returns one item per input, each carrying its input index.
    return [...response.data]
      .sort((a, b) => a.index - b.index)
      .map((item) => item.embedding);
  }

  if (provider === "ollama") {
    const baseUrl = process.env.OLLAMA_BASE_URL || "http://localhost:11434";
    const model = process.env.OLLAMA_EMBEDDING_MODEL || "nomic-embed-text";

    const response = await fetch(`${baseUrl}/api/embed`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model, input: texts }),
    });

    if (!response.ok) {
      throw new Error(`Ollama request failed: ${response.status} ${await response.text()}`);
    }

    const data = await response.json();
    return data.embeddings;
  }

  throw new Error(`Unsupported embedding provider: ${provider}`);
}

/** Convenience wrapper for embedding a single text. */
export async function createEmbedding(text) {
  const [embedding] = await createEmbeddings([text]);
  return embedding;
}
