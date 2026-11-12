// Part 3: max tokens and stop sequences cut the output; they don't shape it.
// Same experiment and output as ../python/limits.py.
//
//   node limits.js
//   node limits.js --model qwen2.5:3b
import { readFileSync } from "node:fs";
import { parseArgs } from "node:util";

const { values: args } = parseArgs({ options: { model: { type: "string" } } });
if (args.model) process.env.OLLAMA_CHAT_MODEL = args.model;

const { chat, modelName, unload } = await import("./ollama.js");
const { parseContract } = await import("./checks.js");
const { interfacePrompt, justAsk } = await import("./prompts.js");

// Python's repr() of a string, so both languages print identical output.
const repr = (text) => {
  const body = text.replace(/\\/g, "\\\\").replace(/\n/g, "\\n").replace(/\t/g, "\\t").replace(/\r/g, "\\r");
  if (text.includes("'") && !text.includes('"')) return `"${body}"`;
  return `'${body.replace(/'/g, "\\'")}'`;
};

const { documents } = JSON.parse(readFileSync(new URL("../data/help_center.json", import.meta.url), "utf8"));
const context = [["export", documents.export]];
const question = "Where do I export my data?";
await unload();
console.log(`Model: ${modelName()} | temperature 0 | question: "${question}"\n`);

async function run(messages, options) {
  const response = await chat(messages, { temperature: 0, seed: 1, ...options });
  return [response.message.content, response.done_reason, response.eval_count];
}

console.log("1. Max tokens (num_predict) with the interface prompt's JSON contract");
for (const limit of [300, 30, 10]) {
  const [reply, reason, tokens] = await run(interfacePrompt(question, context), { num_predict: limit });
  const { contract } = parseContract(reply);
  console.log(`   num_predict ${String(limit).padStart(3)}: done_reason=${repr(reason)}, ${tokens} tokens, usable JSON: ${contract ? "yes" : "NO"}`);
  console.log(`      ${repr(reply)}`);
}

console.log("\n2. Max tokens on a free-text reply (just_ask prompt)");
for (const limit of [300, 40]) {
  const [reply, reason, tokens] = await run(justAsk(question, context), { num_predict: limit });
  console.log(`   num_predict ${String(limit).padStart(3)}: done_reason=${repr(reason)}, ${tokens} tokens, ends with: ${repr(reply.slice(-60))}`);
}

console.log('\n3. Stop sequence "}" with the interface prompt');
const [reply, reason, tokens] = await run(interfacePrompt(question, context), { num_predict: 300, stop: ["}"] });
const { contract } = parseContract(reply);
console.log(`   done_reason=${repr(reason)}, ${tokens} tokens, usable JSON: ${contract ? "yes" : "NO"}`);
console.log(`      ${repr(reply)}`);
