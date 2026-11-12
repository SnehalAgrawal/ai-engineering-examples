// Prompt caching: when a request starts with the same tokens as an earlier one, the server
// can reuse the work it already did for that prefix. Same experiment as ../python/prompt_cache.py.
//
//   node prompt_cache.js
//   node prompt_cache.js --model llama3.2:1b
import { writeFileSync } from "node:fs";
import { parseArgs } from "node:util";
import { document, fixed, generate, median, modelName, unload, version } from "./ollama_client.js";

const { values: args } = parseArgs({ options: { model: { type: "string" }, reps: { type: "string" } } });
const model = args.model || modelName();
const reps = args.reps ? Number(args.reps) : 3;

const DOC = document(80);
const Q1 = "Which section explains how to cancel a subscription? Answer with the section number only.";
const Q2 = "Which section explains how to export data? Answer with the section number only.";
const STEPS = [
  ["1. document, question 1", `${DOC}\n\n${Q1}`],
  ["2. same document, question 2", `${DOC}\n\n${Q2}`],
  ["3. question 2, then the document", `${Q2}\n\n${DOC}`],
  ["4. document, question 1 again", `${DOC}\n\n${Q1}`],
];

const results = Object.fromEntries(STEPS.map(([label]) => [label, []]));
for (let rep = 0; rep < reps; rep++) {
  await unload(model);
  await generate("Hello", 1, model); // load the model first, so loading isn't measured
  for (const [label, prompt] of STEPS) results[label].push(await generate(prompt, 8, model));
}
await unload(model);

console.log(`Model: ${model} | Ollama ${await version()} | temperature 0 | ${reps} sequences, medians\n`);
console.log("request".padEnd(36) + "input tokens".padStart(13) + "reused".padStart(9) + "computed".padStart(10) + "prefill".padStart(11) + "first token".padStart(13));
for (const [label, runs] of Object.entries(results)) {
  const get = (key) => median(runs.map((r) => r[key]));
  console.log(label.padEnd(36) + fixed(get("input_tokens"), 0, 13) + fixed(get("cached_tokens"), 0, 9) +
    fixed(get("input_tokens") - get("cached_tokens"), 0, 10) + `${fixed(get("prefill_s") * 1000, 0, 8)} ms${fixed(get("ttft_s") * 1000, 0, 10)} ms`);
}
console.log("\nreused: input tokens Ollama read from its cache (prompt_eval_cached_count).");
const out = `results-cache-${model.replace(/:/g, "_")}.json`;
writeFileSync(out, JSON.stringify({ model, runs: results }, null, 1));
console.log(`Every run was saved to ${out}.`);
