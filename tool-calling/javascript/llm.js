// Chat provider with tool calling: a local Ollama model (default) or Groq's free tier.
// Same behaviour as ../python/llm.py. Every reply is normalised to:
//   { content, toolCalls: [{ id, name, arguments }], finishReason, tokens, fingerprint, error, message }
// "arguments" is always the raw JSON text the model produced.
import "dotenv/config";
import { pyDumps } from "./pyjson.js";

const GROQ_URL = "https://api.groq.com/openai/v1/chat/completions";

export const provider = () => (process.env.LLM_PROVIDER || "ollama").toLowerCase();

export function modelName() {
  if (provider() === "groq") return process.env.GROQ_MODEL || "openai/gpt-oss-20b";
  return process.env.OLLAMA_CHAT_MODEL || "llama3.2:3b";
}

export async function chat(messages, tools, seed, maxTokens) {
  if (provider() === "groq") return groq(messages, tools, seed, maxTokens);
  if (provider() === "ollama") return ollama(messages, tools, seed, maxTokens);
  throw new Error(`Unsupported LLM provider: ${provider()}`);
}

// The message that returns one tool result to the model.
export function toolMessage(call, content) {
  if (provider() === "groq") return { role: "tool", tool_call_id: call.id, name: call.name, content };
  return { role: "tool", tool_name: call.name, content };
}

// Ollama: unload the model so runs start from the same state and memory is freed afterwards.
export async function reset() {
  if (provider() !== "ollama") return;
  const baseUrl = process.env.OLLAMA_BASE_URL || "http://localhost:11434";
  const response = await fetch(`${baseUrl}/api/generate`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ model: modelName(), keep_alive: 0 }),
  });
  if (!response.ok) throw new Error(`Ollama returned ${response.status}`);
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function groq(messages, tools, seed, maxTokens) {
  const key = process.env.GROQ_API_KEY;
  if (!key) throw new Error("Set GROQ_API_KEY in javascript/.env (create a free key at https://console.groq.com).");
  const body = { model: modelName(), messages, tools, tool_choice: "auto", seed, max_completion_tokens: maxTokens };
  for (let attempt = 0; attempt < 8; attempt++) {
    const response = await fetch(GROQ_URL, {
      method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${key}` },
      body: JSON.stringify(body),
    });
    if (response.status === 429) {
      // Free-tier rate limit: wait as long as Groq asks, then retry.
      const wait = Number(response.headers.get("retry-after") || 10);
      await sleep(Math.min(Math.max(wait, 1), 120) * 1000);
      continue;
    }
    if (response.status >= 400) {
      // Keep API errors (for example a malformed tool call Groq rejected) as results.
      return { content: "", toolCalls: [], finishReason: `error ${response.status}`, tokens: 0, fingerprint: null,
        error: (await response.text()).slice(0, 500), message: null };
    }
    const data = await response.json();
    const choice = data.choices[0];
    const rawCalls = choice.message.tool_calls || [];
    const content = choice.message.content || "";
    const message = { role: "assistant", content };
    if (rawCalls.length) message.tool_calls = rawCalls;
    return {
      content, message, finishReason: choice.finish_reason ?? null,
      toolCalls: rawCalls.map((c) => ({ id: c.id, name: c.function.name, arguments: c.function.arguments })),
      tokens: data.usage?.total_tokens ?? 0, fingerprint: data.system_fingerprint ?? null, error: null,
    };
  }
  throw new Error("Still rate-limited after several retries. Try again later or lower the number of runs.");
}

async function ollama(messages, tools, seed, maxTokens) {
  const baseUrl = process.env.OLLAMA_BASE_URL || "http://localhost:11434";
  const response = await fetch(`${baseUrl}/api/chat`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ model: modelName(), messages, tools, stream: false, options: { seed, num_predict: maxTokens } }),
  });
  if (!response.ok) throw new Error(`Ollama returned ${response.status}: ${await response.text()}`);
  const data = await response.json();
  const rawCalls = data.message.tool_calls || [];
  const content = data.message.content || "";
  const message = { role: "assistant", content };
  if (rawCalls.length) message.tool_calls = rawCalls;
  return {
    content, message, finishReason: data.done_reason ?? null,
    // Ollama returns arguments as an object; keep the JSON text so both providers look the same.
    toolCalls: rawCalls.map((c, i) => ({ id: c.id ?? `call_${i}`, name: c.function.name, arguments: pyDumps(c.function.arguments ?? {}) })),
    tokens: (data.prompt_eval_count ?? 0) + (data.eval_count ?? 0), fingerprint: null, error: null,
  };
}
