// The model call: the only part of the application that talks to the model.
// Same behaviour as ../python/llm.py. Every failure on the way (server down, timeout,
// HTTP error, a response that isn't the expected JSON) becomes one error type,
// LLMError, so the rest of the application has a single thing to handle.
import "dotenv/config";

export class LLMError extends Error {}

export const modelName = () => process.env.OLLAMA_CHAT_MODEL || "llama3.2:3b";
export const baseUrl = () => process.env.OLLAMA_BASE_URL || "http://localhost:11434";

export async function chat(messages, { schema = null, maxTokens = 300, timeout = 60, url = null } = {}) {
  const body = {
    model: modelName(),
    messages,
    stream: false,
    options: { temperature: 0, seed: 1, num_predict: maxTokens },
  };
  if (schema !== null) body.format = schema; // Ollama constrains the output to this JSON schema
  let response;
  try {
    response = await fetch(`${url || baseUrl()}/api/chat`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
      signal: AbortSignal.timeout(timeout * 1000),
    });
  } catch (error) {
    throw new LLMError(error.name === "TimeoutError" ? "Timeout" : "ConnectionError");
  }
  if (!response.ok) throw new LLMError(`HTTPError ${response.status}`);
  let data, content;
  try {
    data = await response.json();
    content = data.message.content;
    if (typeof content !== "string") throw new TypeError();
  } catch {
    throw new LLMError("InvalidResponse");
  }
  return {
    content,
    prompt_tokens: data.prompt_eval_count ?? 0,
    output_tokens: data.eval_count ?? 0,
    done_reason: data.done_reason ?? null,
  };
}

// Unload the model, so runs start from the same state and memory is freed afterwards.
export async function unload() {
  const response = await fetch(`${baseUrl()}/api/generate`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ model: modelName(), keep_alive: 0 }),
  });
  if (!response.ok) throw new Error(`Ollama returned ${response.status}`);
}
