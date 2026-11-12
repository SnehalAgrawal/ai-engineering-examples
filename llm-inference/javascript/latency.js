// Where the time goes in one request: prefill (reading the prompt) and decode
// (generating the answer). Same experiment as ../python/latency.py.
//
//   node latency.js
//   node latency.js --model llama3.2:1b
import { execFileSync } from "node:child_process";
import { writeFileSync } from "node:fs";
import { arch, platform } from "node:os";
import { parseArgs } from "node:util";
import { QUESTION, document, fixed, generate, median, modelName, unload, version } from "./ollama_client.js";

const { values: args } = parseArgs({ options: { model: { type: "string" }, reps: { type: "string" } } });
const model = args.model || modelName();
const reps = args.reps ? Number(args.reps) : 3;
const SECTIONS = [8, 16, 32, 64, 100];
const OUTPUT_TOKENS = [16, 64, 256];

function powerSource() {
  if (platform() !== "darwin") return "unknown";
  const out = execFileSync("pmset", ["-g", "batt"], { encoding: "utf8" });
  return out.includes("Battery Power") ? "battery" : out.includes("AC Power") ? "AC power" : "unknown";
}

await unload(model);
const warm = await generate("Hello", 1, model); // loads the model; not part of the measurements
console.log(`Model: ${model} | Ollama ${await version()} | ${arch() === "arm64" ? "arm64" : arch()} | power: ${powerSource()} | ` +
  `temperature 0 | ${reps} runs per setting, medians`);
console.log(`Model load before the runs: ${warm.load_s.toFixed(2)} s\n`);

const part1 = Object.fromEntries(SECTIONS.map((n) => [n, []]));
const part2 = Object.fromEntries(OUTPUT_TOKENS.map((n) => [n, []]));
for (let rep = 1; rep <= reps; rep++) {
  for (const n of SECTIONS) part1[n].push(await generate(`Request ${rep}-${n}.\n${document(n)}\n\n${QUESTION}`, 32, model));
  for (const n of OUTPUT_TOKENS) part2[n].push(await generate(`Request ${rep}-out${n}.\n${QUESTION}`, n, model));
}
await unload(model);

const m = (runs, key) => median(runs.map((r) => r[key]));

console.log("1. Longer prompt, same 32-token answer");
console.log("input tokens".padStart(13) + "processed".padStart(11) + "prefill".padStart(11) + "prefill speed".padStart(16) + "first token".padStart(13) + "decode speed".padStart(15));
for (const n of SECTIONS) {
  const runs = part1[n];
  console.log(fixed(m(runs, "input_tokens"), 0, 13) + fixed(m(runs, "input_tokens") - m(runs, "cached_tokens"), 0, 11) +
    `${fixed(m(runs, "prefill_s") * 1000, 0, 8)} ms` +
    `${fixed(median(runs.map((r) => (r.input_tokens - r.cached_tokens) / r.prefill_s)), 0, 10)} tok/s` +
    `${fixed(m(runs, "ttft_s") * 1000, 0, 10)} ms` +
    `${fixed(median(runs.map((r) => r.output_tokens / r.decode_s)), 1, 9)} tok/s`);
}

console.log("\n2. Same short prompt, longer answer");
console.log("output tokens".padStart(14) + "first token".padStart(13) + "decode".padStart(11) + "total".padStart(11) + "decode speed".padStart(15));
for (const n of OUTPUT_TOKENS) {
  const runs = part2[n];
  console.log(fixed(m(runs, "output_tokens"), 0, 14) + `${fixed(m(runs, "ttft_s") * 1000, 0, 10)} ms${fixed(m(runs, "decode_s"), 2, 9)} s` +
    `${fixed(m(runs, "total_s"), 2, 9)} s${fixed(median(runs.map((r) => r.output_tokens / r.decode_s)), 1, 9)} tok/s`);
}

console.log("\nprocessed: input tokens actually computed (input tokens minus tokens reused from Ollama's cache).");
console.log("first token: time from sending the request to receiving the first generated text, measured by this script.");
const out = `results-latency-${model.replace(/:/g, "_")}.json`;
writeFileSync(out, JSON.stringify({ model, part1, part2 }, null, 1));
console.log(`Every run was saved to ${out}.`);
