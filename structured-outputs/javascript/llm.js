// Chat provider: Groq (default, free tier) or a local Ollama model.
// Same behavior as ../python/llm.py. Output modes:
//   null     free text (whatever the prompt asks for)
//   "json"   JSON mode: any syntactically valid JSON
//   object   a JSON schema the output is constrained to
import "dotenv/config";

const GROQ_URL = "https://api.groq.com/openai/v1/chat/completions";

export function provider() {
  return (process.env.LLM_PROVIDER || "groq").toLowerCase();
}

export function modelName() {
  if (provider() === "groq") return process.env.GROQ_MODEL || "openai/gpt-oss-20b";
  return process.env.OLLAMA_CHAT_MODEL || "llama3.2:1b";
}

/** Sends one request. Returns the reply text, why generation stopped, tokens used, and (Groq) the backend fingerprint. */
export async function chat(messages, seed, maxTokens, output = null) {
  if (provider() === "groq") return groq(messages, seed, maxTokens, output);
  if (provider() === "ollama") return ollama(messages, seed, maxTokens, output);
  throw new Error(`Unsupported LLM provider: ${provider()}`);
}

/** Ollama: unload the model so runs start from the same state and free memory afterwards. */
export async function reset() {
  if (provider() !== "ollama") return;
  const baseUrl = process.env.OLLAMA_BASE_URL || "http://localhost:11434";
  const response = await fetch(`${baseUrl}/api/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ model: modelName(), keep_alive: 0 }),
  });
  if (!response.ok) throw new Error(`Ollama unload failed: ${response.status}`);
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function groq(messages, seed, maxTokens, output) {
  const key = process.env.GROQ_API_KEY;
  if (!key) throw new Error("Set GROQ_API_KEY in javascript/.env (create a free key at https://console.groq.com).");
  const body = { model: modelName(), messages, seed, max_completion_tokens: maxTokens };
  if (output === "json") body.response_format = { type: "json_object" };
  else if (output && typeof output === "object") {
    body.response_format = { type: "json_schema", json_schema: { name: "support_reply", strict: true, schema: output } };
  }

  for (let attempt = 0; attempt < 8; attempt++) {
    const response = await fetch(GROQ_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${key}` },
      body: JSON.stringify(body),
    });
    if (response.status === 429) {
      // Free-tier rate limit: wait as long as Groq asks, then retry.
      const wait = Number(response.headers.get("retry-after") || 10);
      await sleep(Math.min(Math.max(wait, 1), 120) * 1000);
      continue;
    }
    if (response.status >= 400) {
      // Keep API errors (for example a rejected generation) as results instead of crashing the run.
      return { content: "", finish_reason: `error ${response.status}`, tokens: 0, fingerprint: null, error: (await response.text()).slice(0, 300) };
    }
    const data = await response.json();
    const choice = data.choices[0];
    return {
      content: choice.message.content || "",
      finish_reason: choice.finish_reason ?? null,
      tokens: data.usage?.total_tokens ?? 0,
      fingerprint: data.system_fingerprint ?? null,
      error: null,
    };
  }
  throw new Error("Still rate-limited after several retries. Try again later or lower RUNS.");
}

async function ollama(messages, seed, maxTokens, output) {
  const baseUrl = process.env.OLLAMA_BASE_URL || "http://localhost:11434";
  const body = { model: modelName(), messages, stream: false, options: { seed, num_predict: maxTokens } };
  if (output !== null) body.format = output;
  const response = await fetch(`${baseUrl}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw new Error(`Ollama request failed: ${response.status} ${await response.text()}`);
  const data = await response.json();
  return {
    content: data.message.content,
    finish_reason: data.done_reason ?? null,
    tokens: (data.prompt_eval_count || 0) + (data.eval_count || 0),
    fingerprint: null,
    error: null,
  };
}
