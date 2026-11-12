// A schema constrains which tokens can come next. It can't make the model finish.
// Same experiment and output as ../python/truncation.py.
//
//   node truncation.js
//   LLM_PROVIDER=ollama node truncation.js
import { readFileSync } from "node:fs";

const { chat, modelName, provider, reset } = await import("./llm.js");
const { interfacePrompt } = await import("./prompts.js");
const { matchesSchema, parseStrict, replySchema } = await import("./schema.js");

// Python's repr() of a string, so both languages print identical output.
const repr = (text) => {
  if (text === null || text === undefined) return "None";
  const body = text.replace(/\\/g, "\\\\").replace(/\n/g, "\\n").replace(/\t/g, "\\t").replace(/\r/g, "\\r");
  if (text.includes("'") && !text.includes('"')) return `"${body}"`;
  return `'${body.replace(/'/g, "\\'")}'`;
};

const { documents } = JSON.parse(readFileSync(new URL("../data/help_center.json", import.meta.url), "utf8"));
const question = "Where do I export my data?";
const contextIds = ["export"];
const messages = interfacePrompt(question, contextIds.map((d) => [d, documents[d]]));
await reset();
console.log(`Model: ${modelName()} (${provider()}) | schema enforced | question: "${question}"\n`);
for (const limit of [1000, 60, 12]) {
  const response = await chat(messages, 1, limit, replySchema(contextIds));
  const reply = response.content;
  const data = parseStrict(reply);
  console.log(`max tokens ${String(limit).padStart(4)}: finish=${repr(response.finish_reason)}, ${response.tokens} tokens, ` +
    `valid JSON: ${data !== null ? "yes" : "NO"}, matches schema: ${matchesSchema(data, contextIds) ? "yes" : "NO"}`);
  console.log(`   reply: ${repr(reply)}`);
  if (response.error) console.log(`   API error: ${response.error}`);
}
await reset();
