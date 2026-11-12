// The same model, inside an application. Same behaviour as ../python/app.py.
// handle() is the whole request path:
//   1. validate the input        the application decides what reaches the model
//   2. build the context         the help center, inside a versioned prompt
//   3. call the model            with a schema, a token limit, and a timeout
//   4. check the output          schema, sources, and values against the sources
//   5. decide the reply          the application owns what the customer sees
//   6. log the request           one record per request, success or not
// handle() never throws: every path returns a status, a message, and a log record.
import { randomUUID } from "node:crypto";
import { readFileSync } from "node:fs";
import { LLMError, chat, modelName } from "./llm.js";

const load = (name) => JSON.parse(readFileSync(new URL(`../data/${name}`, import.meta.url), "utf8"));
export const DOCUMENTS = load("help_center.json").documents;
const PROMPT = load("prompt.json");
export const MAX_INPUT_CHARS = 2000;

const ARTICLES = Object.entries(DOCUMENTS).map(([id, text]) => `[${id}] ${text}`).join("\n");
const SYSTEM = PROMPT.system.replace("{articles}", ARTICLES);
const SCHEMA = {
  type: "object",
  properties: {
    answered: { type: "boolean" },
    answer: { type: "string" },
    source_ids: { type: "array", items: { type: "string", enum: Object.keys(DOCUMENTS) } },
  },
  required: ["answered", "answer", "source_ids"],
  additionalProperties: false,
};

// Article #9's value-presence check: prices, durations, emails, and ids in the answer
// must appear in the articles it cites.
const VALUE = /\$\s?\d[\d,]*(?:\.\d+)?|\b\d+(?:\s*(?:-|–|to)\s*\d+)?\s*(?:business\s+)?(?:minutes?|hours?|days?|weeks?|months?)\b|\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+/gi;
const normalize = (value) => value.toLowerCase().replace(/[\s,$]/g, "").replace(/\.0+(?!\d)/g, "");
const values = (text) => text.match(VALUE) || [];

export function unsupportedValues(answer, sources) {
  const known = new Set(sources.flatMap((text) => values(text).map(normalize)));
  return values(answer).filter((v) => !known.has(normalize(v)));
}

// The model's JSON reply, or null if it isn't exactly the agreed shape.
function parse(content) {
  let data;
  try {
    data = JSON.parse(content);
  } catch {
    return null;
  }
  const keys = data && typeof data === "object" && !Array.isArray(data) ? Object.keys(data).sort().join(",") : "";
  if (keys !== "answer,answered,source_ids" || typeof data.answered !== "boolean" || typeof data.answer !== "string"
      || !Array.isArray(data.source_ids) || !data.source_ids.every((s) => s in DOCUMENTS)) return null;
  return data;
}

export async function handle(text, url = null) {
  const start = performance.now();
  const question = text.trim();
  const log = {
    request_id: randomUUID(),
    prompt_version: PROMPT.version,
    model: modelName(),
    input_chars: question.length,
    prompt_tokens: null,
    output_tokens: null,
    error: null,
  };
  let modelOutput = null; // kept for debugging and evaluation; never shown to the customer
  const reply = (status, message, outcome, sources = []) => {
    Object.assign(log, { status, outcome, latency_ms: Math.round(performance.now() - start) });
    return { status, message, sources: [...sources], model_output: modelOutput, log };
  };

  // 1. Validate the input.
  if (!question) return reply(400, "Please type a question.", "empty_input");
  if (question.length > MAX_INPUT_CHARS) {
    return reply(413, `Your message is too long (${question.length.toLocaleString("en-US")} characters). Please keep questions under ` +
      `${MAX_INPUT_CHARS.toLocaleString("en-US")} characters and leave out logs or attachments.`, "input_too_long");
  }

  // 2 and 3. Build the context, and call the model with a schema, a token limit, and a timeout.
  const messages = [{ role: "system", content: SYSTEM }, { role: "user", content: question }];
  let result;
  try {
    result = await chat(messages, { schema: SCHEMA, maxTokens: 300, timeout: 60, url });
  } catch (error) {
    if (!(error instanceof LLMError)) throw error;
    log.error = error.message;
    return reply(503, PROMPT.unavailable, "model_unavailable");
  }
  Object.assign(log, { prompt_tokens: result.prompt_tokens, output_tokens: result.output_tokens });
  modelOutput = result.content;

  // 4. Check the output.
  const data = parse(result.content);
  if (data === null) return reply(200, PROMPT.decline, "invalid_output");
  if (!data.answered) return reply(200, PROMPT.decline, "declined");
  const cited = data.source_ids.map((s) => DOCUMENTS[s]);
  if (!data.answer.trim() || !cited.length || unsupportedValues(data.answer, cited).length) {
    return reply(200, PROMPT.decline, "unsupported_answer");
  }

  // 5. The application decides the reply: the checked answer, with its sources.
  return reply(200, data.answer.trim(), "answered", data.source_ids);
}
