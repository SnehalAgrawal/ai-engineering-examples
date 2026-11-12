// Chat provider: a local Ollama model (default) or OpenAI.
import "dotenv/config";

export function provider() {
  return (process.env.LLM_PROVIDER || "ollama").toLowerCase();
}

export function modelName() {
  if (provider() === "openai") return process.env.OPENAI_CHAT_MODEL || "";
  return process.env.OLLAMA_CHAT_MODEL || "llama3.2:3b";
}

/** Unloads the Ollama model (keep_alive 0), so the next request starts fresh. */
export async function reset() {
  if (provider() !== "ollama") return;
  const baseUrl = process.env.OLLAMA_BASE_URL || "http://localhost:11434";
  const response = await fetch(`${baseUrl}/api/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ model: modelName(), keep_alive: 0 }),
  });
  if (!response.ok) throw new Error(`Ollama unload failed: ${response.status} ${await response.text()}`);
}

/**
 * Sends one chat request and returns the reply text.
 *
 * Sampling settings are left at the model's defaults. Only the seed is set, so a
 * run can be repeated, and the reply length is capped to keep the suite fast.
 */
export async function chat(messages, seed, maxTokens = 300) {
  if (provider() === "ollama") {
    const baseUrl = process.env.OLLAMA_BASE_URL || "http://localhost:11434";
    const response = await fetch(`${baseUrl}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        model: modelName(),
        messages,
        stream: false,
        options: { seed, num_predict: maxTokens },
      }),
    });
    if (!response.ok) throw new Error(`Ollama request failed: ${response.status} ${await response.text()}`);
    const data = await response.json();
    return data.message.content;
  }

  if (provider() === "openai") {
    if (!process.env.OPENAI_API_KEY) throw new Error("Set OPENAI_API_KEY to use the OpenAI provider.");
    if (!modelName()) throw new Error("Set OPENAI_CHAT_MODEL to a chat model your account can use.");
    const { default: OpenAI } = await import("openai");
    const client = new OpenAI();
    const response = await client.chat.completions.create({
      model: modelName(),
      messages,
      seed,
      max_completion_tokens: maxTokens,
    });
    return response.choices[0].message.content || "";
  }

  throw new Error(`Unsupported LLM provider: ${provider()}`);
}
