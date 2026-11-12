// A small Ollama client that measures one request. Same behaviour as ../python/ollama_client.py.
// Ollama reports its own timings (nanoseconds); this client adds time to first token,
// measured from sending the request to receiving the first piece of generated text.
import "dotenv/config";
import { readFileSync } from "node:fs";

export const BASE_URL = process.env.OLLAMA_BASE_URL || "http://localhost:11434";
const { paragraphs } = JSON.parse(readFileSync(new URL("../data/paragraphs.json", import.meta.url), "utf8"));
export const QUESTION = "Write the numbers from 1 to 1000, separated by commas.";

export const modelName = () => process.env.OLLAMA_CHAT_MODEL || "llama3.2:3b";

// A document of numbered sections built from the help-center paragraphs.
// A different offset gives a different document of the same length.
export function document(sections, offset = 0) {
  return Array.from({ length: sections }, (_, i) => `Section ${i + 1}. ${paragraphs[(i + offset) % paragraphs.length]}`).join("\n");
}

async function post(path, body) {
  const response = await fetch(`${BASE_URL}${path}`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  if (!response.ok) throw new Error(`Ollama returned ${response.status}: ${await response.text()}`);
  return response;
}

// Streams one request at temperature 0 and returns Ollama's timings plus time to first token (seconds).
export async function generate(prompt, numPredict, model = null, numCtx = null) {
  const options = { temperature: 0, num_predict: numPredict };
  if (numCtx) options.num_ctx = numCtx;
  const start = performance.now();
  const response = await post("/api/generate", { model: model || modelName(), prompt, stream: true, options });
  let firstToken = null, final = null, buffer = "";
  const decoder = new TextDecoder();
  for await (const part of response.body) {
    buffer += decoder.decode(part, { stream: true });
    let newline;
    while ((newline = buffer.indexOf("\n")) >= 0) {
      const line = buffer.slice(0, newline).trim();
      buffer = buffer.slice(newline + 1);
      if (!line) continue;
      const chunk = JSON.parse(line);
      if (firstToken === null && chunk.response) firstToken = (performance.now() - start) / 1000;
      if (chunk.done) final = chunk;
    }
  }
  const total = (performance.now() - start) / 1000;
  const ns = 1e9;
  return {
    input_tokens: final.prompt_eval_count,
    cached_tokens: final.prompt_eval_cached_count ?? 0,
    output_tokens: final.eval_count,
    load_s: (final.load_duration ?? 0) / ns,
    prefill_s: final.prompt_eval_duration / ns,
    decode_s: final.eval_duration / ns,
    ttft_s: firstToken,
    total_s: total,
    done_reason: final.done_reason ?? null,
  };
}

export async function unload(model = null) {
  await post("/api/generate", { model: model || modelName(), keep_alive: 0 });
}

export async function show(model = null) {
  return (await post("/api/show", { model: model || modelName() })).json();
}

// Size of the model's weights on disk, from Ollama's model list.
export async function modelSizeBytes(model = null) {
  const name = model || modelName();
  const { models } = await (await fetch(`${BASE_URL}/api/tags`)).json();
  return models.find((m) => m.name === name).size;
}

export async function version() {
  return (await (await fetch(`${BASE_URL}/api/version`)).json()).version;
}

export function median(values) {
  const sorted = [...values].sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
}

// Python-style number formatting helpers, so both languages print the same layout.
export const fixed = (value, digits, width) => value.toFixed(digits).padStart(width);
export const thousands = (n) => Math.round(n).toLocaleString("en-US");
