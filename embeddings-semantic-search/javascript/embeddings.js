import OpenAI from "openai";
import axios from "axios";

export async function createEmbedding(text) {
  const provider = (process.env.EMBEDDING_PROVIDER || "openai").toLowerCase();

  if (provider === "openai") {
    const openai = new OpenAI({
      apiKey: process.env.OPENAI_API_KEY,
    });
    const model = process.env.OPENAI_EMBEDDING_MODEL || "text-embedding-3-small";

    const response = await openai.embeddings.create({
      model: model,
      input: text,
      encoding_format: "float",
    });

    return response.data[0].embedding;
  } else if (provider === "ollama") {
    const baseUrl = process.env.OLLAMA_BASE_URL || "http://localhost:11434";
    const model = process.env.OLLAMA_EMBEDDING_MODEL || "nomic-embed-text";

    const response = await axios.post(`${baseUrl}/api/embeddings`, {
      model: model,
      prompt: text,
    });

    return response.data.embedding;
  } else {
    throw new Error(`Unsupported embedding provider: ${provider}`);
  }
}
