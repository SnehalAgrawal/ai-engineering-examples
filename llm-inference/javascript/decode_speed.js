// Why a smaller model generates faster, and what a cold start costs.
// Same experiment as ../python/decode_speed.py.
//
//   node decode_speed.js
//   node decode_speed.js --bandwidth-gbs 273      # your machine's memory bandwidth
import { writeFileSync } from "node:fs";
import { parseArgs } from "node:util";
import { QUESTION, fixed, generate, median, modelSizeBytes, unload, version } from "./ollama_client.js";

const { values: args, positionals } = parseArgs({
  allowPositionals: true,
  options: { models: { type: "string", multiple: true }, reps: { type: "string" }, "bandwidth-gbs": { type: "string" } },
});
const models = args.models ? [...args.models, ...positionals] : ["llama3.2:1b", "llama3.2:3b"];
const reps = args.reps ? Number(args.reps) : 3;
const bandwidth = args["bandwidth-gbs"] ? Number(args["bandwidth-gbs"]) : null;

console.log(`Ollama ${await version()} | temperature 0 | 128 output tokens | ${reps} warm runs per model, medians\n`);
let header = "model".padEnd(14) + "weights".padStart(9) + "cold load".padStart(11) + "cold first token".padStart(18) + "warm first token".padStart(18) + "decode speed".padStart(15);
if (bandwidth) header += "upper bound".padStart(14) + "of bound".padStart(10);
console.log(header);

const saved = {};
for (const model of models) {
  await unload(model);
  const cold = await generate("Hello", 1, model);
  const warm = [];
  for (let r = 1; r <= reps; r++) warm.push(await generate(`Request ${r}.\n${QUESTION}`, 128, model));
  await unload(model);
  const size = await modelSizeBytes(model);
  const speed = median(warm.map((r) => r.output_tokens / r.decode_s));
  let row = model.padEnd(14) + `${fixed(size / 1e9, 2, 6)} GB${fixed(cold.load_s, 2, 9)} s${fixed(cold.ttft_s * 1000, 0, 15)} ms` +
    `${fixed(median(warm.map((r) => r.ttft_s)) * 1000, 0, 15)} ms${fixed(speed, 1, 9)} tok/s`;
  if (bandwidth) {
    const bound = (bandwidth * 1e9) / size;
    row += `${fixed(bound, 0, 8)} tok/s${`${Math.round((speed / bound) * 100)}%`.padStart(9)}`;
  }
  console.log(row);
  saved[model] = { weights_bytes: size, cold, warm };
}

console.log("\ncold: the first request after the model was unloaded, including loading it into memory.");
console.log("upper bound: memory bandwidth / weights size, if every token reads all the weights once.");
writeFileSync("results-decode.json", JSON.stringify(saved, null, 1));
console.log("Every run was saved to results-decode.json.");
