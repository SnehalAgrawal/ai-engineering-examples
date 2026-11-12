// Minimal Ollama client: chat with explicit sampler options, and model unloading.
// Same behavior as ../python/ollama.py.
import "dotenv/config";

const BASE_URL = process.env.OLLAMA_BASE_URL || "http://localhost:11434";

export function modelName() {
  return process.env.OLLAMA_CHAT_MODEL || "llama3.2:3b";
}

/**
 * Sends one chat request and returns Ollama's full JSON response.
 *
 * `options` are sampler settings (temperature, top_k, top_p, min_p, seed,
 * num_predict, stop). Anything not set falls back to Ollama's defaults.
 * With topLogprobs > 0, the response also carries the model's probability
 * for the most likely tokens at each position.
 */
export async function chat(messages, options, topLogprobs = 0) {
  const body = { model: modelName(), messages, stream: false, options };
  if (topLogprobs) {
    body.logprobs = true;
    body.top_logprobs = topLogprobs;
  }
  const response = await fetch(`${BASE_URL}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw new Error(`Ollama request failed: ${response.status} ${await response.text()}`);
  return response.json();
}

/**
 * Unloads the model (keep_alive 0) so every run starts from the same state.
 * In testing, a reply could change with the same seed depending on what the
 * loaded model had processed before; starting fresh makes runs repeatable.
 */
export async function unload() {
  const response = await fetch(`${BASE_URL}/api/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ model: modelName(), keep_alive: 0 }),
  });
  if (!response.ok) throw new Error(`Ollama unload failed: ${response.status} ${await response.text()}`);
}
