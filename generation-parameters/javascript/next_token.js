// Part 1: what the sampler settings do to the model's next-token choice.
// Same experiment and output as ../python/next_token.py.
//
//   node next_token.js
//   node next_token.js --model qwen2.5:3b
import { readFileSync } from "node:fs";
import { parseArgs } from "node:util";

const { values: args } = parseArgs({ options: { model: { type: "string" } } });
if (args.model) process.env.OLLAMA_CHAT_MODEL = args.model;

const { chat, modelName, unload } = await import("./ollama.js");
const { justAsk } = await import("./prompts.js");
const { DEFAULTS, predict } = await import("./sampler.js");

const SAMPLES = 500;
const TOP = 20;
const SETTINGS = [
  ["Ollama defaults", {}],
  ["temperature 0", { temperature: 0 }],
  ["temperature 0.3", { temperature: 0.3 }],
  ["temperature 1.5", { temperature: 1.5 }],
  ["temperature 1.5, top_p 1 (off)", { temperature: 1.5, top_p: 1.0 }],
  ["top_k 2", { top_k: 2 }],
  ["top_p 0.5", { top_p: 0.5 }],
  ["min_p 0.5, top_p 1 (off)", { min_p: 0.5, top_p: 1.0 }],
];
const QUESTIONS = [
  ["refunds", "How long do I have to ask for a refund?", ["refunds", "cancel"]],
  ["free trial (not in the documents)", "Do you offer a free trial, and how long is it?", ["plans", "cancel"]],
];

const pct = (x, digits = 1) => `${(100 * x).toFixed(digits)}%`;
// Matches Python's repr() for the tokens printed here.
const repr = (token) => {
  const body = token.replace(/\\/g, "\\\\").replace(/\n/g, "\\n").replace(/\t/g, "\\t").replace(/\r/g, "\\r");
  if (token.includes("'") && !token.includes('"')) return `"${body}"`;
  return `'${body.replace(/'/g, "\\'")}'`;
};

const { documents } = JSON.parse(readFileSync(new URL("../data/help_center.json", import.meta.url), "utf8"));
await unload();
console.log(`Model: ${modelName()} | prompt: just_ask (Article #5) | ${SAMPLES} samples per setting, seeds 1-${SAMPLES}\n`);

for (const [label, question, context] of QUESTIONS) {
  const messages = justAsk(question, context.map((d) => [d, documents[d]]));

  // Asked twice: the first request after the model loads gave slightly different
  // probabilities from every later identical request (see ../python/next_token.py).
  const firstTokenProbabilities = async () => {
    const response = await chat(messages, { num_predict: 1, seed: 0 }, TOP);
    return response.logprobs[0].top_logprobs.map((t) => [t.token, Math.exp(t.logprob)]);
  };
  const cold = await firstTokenProbabilities();
  const probabilities = await firstTokenProbabilities();
  const covered = probabilities.reduce((sum, [, p]) => sum + p, 0);
  console.log(`=== ${label}: "${question}"`);
  console.log("Model's first-token probabilities (top 6 of the 20 returned):");
  console.log("   first request:  " + cold.slice(0, 6).map(([t, p]) => `${repr(t)} ${pct(p, 2)}`).join(", "));
  console.log("   later requests: " + probabilities.slice(0, 6).map(([t, p]) => `${repr(t)} ${pct(p, 2)}`).join(", "));
  console.log(`   (predictions use the later ones; the 20 returned tokens cover ${pct(covered)})`);

  for (const [name, overrides] of SETTINGS) {
    const predicted = predict(probabilities, { ...DEFAULTS, ...overrides });
    const picks = new Map();
    for (let seed = 1; seed <= SAMPLES; seed++) {
      const token = (await chat(messages, { ...overrides, num_predict: 1, seed })).message.content;
      picks.set(token, (picks.get(token) || 0) + 1);
    }
    const shown = [...new Set([...predicted.keys(), ...picks.keys()])].sort(
      (a, b) => (predicted.get(b) || 0) - (predicted.get(a) || 0) || (picks.get(b) || 0) - (picks.get(a) || 0) || (a < b ? -1 : a > b ? 1 : 0),
    );
    console.log(`\n  ${name}:  (${predicted.size} token(s) can be picked${predicted.size < TOP ? "" : ", or more"})`);
    for (const token of shown.slice(0, 6)) {
      const p = predicted.has(token) ? pct(predicted.get(token)).padStart(6) : "     -";
      console.log(`     ${repr(token).padEnd(18)} predicted ${p}   observed ${pct((picks.get(token) || 0) / SAMPLES).padStart(6)}`);
    }
    const rest = shown.slice(6).reduce((sum, t) => sum + (picks.get(t) || 0), 0);
    if (rest) console.log(`     ${"(other tokens)".padEnd(18)} ${"".padEnd(16)}   observed ${pct(rest / SAMPLES).padStart(6)}`);
  }

  // The whole reply that temperature 0 produces (always the most likely token).
  const greedy = (await chat(messages, { temperature: 0, seed: 1, num_predict: 300 })).message.content;
  console.log(`\n  Full reply at temperature 0: ${repr(greedy)}`);
  console.log();
}
