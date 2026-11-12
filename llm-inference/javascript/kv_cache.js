// Predicts the KV cache size from the model's shape, then compares the prediction with
// what Ollama allocates (from Ollama's server log). Same output as ../python/kv_cache.py.
//
//   node kv_cache.js
//   node kv_cache.js --model llama3.2:1b --ctx 2048 4096 8192
//
// bytes per token = layers x KV heads x (key size + value size) x bytes per value (f16 = 2)
import { existsSync, openSync, readSync, statSync, closeSync } from "node:fs";
import { homedir } from "node:os";
import { parseArgs } from "node:util";
import { fixed, generate, modelName, modelSizeBytes, show, thousands, unload, version } from "./ollama_client.js";

const { values: args, positionals } = parseArgs({ allowPositionals: true, options: { model: { type: "string" }, ctx: { type: "string", multiple: true } } });
const model = args.model || modelName();
const contexts = (args.ctx ? [...args.ctx, ...positionals] : ["4096", "8192"]).map(Number);
const logPath = (process.env.OLLAMA_LOG || "~/.ollama/logs/server.log").replace(/^~/, homedir());

const info = (await show(model)).model_info;
const arch = info["general.architecture"];
const layers = info[`${arch}.block_count`];
const kvHeads = info[`${arch}.attention.head_count_kv`];
const headSize = Math.floor(info[`${arch}.embedding_length`] / info[`${arch}.attention.head_count`]);
const keySize = info[`${arch}.attention.key_length`] ?? headSize;
const valueSize = info[`${arch}.attention.value_length`] ?? headSize;
const perToken = layers * kvHeads * (keySize + valueSize) * 2;
const MiB = 2 ** 20;

console.log(`Model: ${model} | Ollama ${await version()} | weights on disk: ${((await modelSizeBytes(model)) / 1e9).toFixed(2)} GB`);
console.log(`Shape: ${layers} layers, ${kvHeads} KV heads, key size ${keySize}, value size ${valueSize}`);
console.log(`Per token: ${layers} x ${kvHeads} x (${keySize} + ${valueSize}) x 2 bytes = ${thousands(perToken)} bytes (${Math.round(perToken / 1024)} KiB)\n`);
console.log("context".padStart(8) + "predicted".padStart(14) + "Ollama log".padStart(14));

for (const ctx of contexts) {
  const predicted = (perToken * ctx) / MiB;
  await unload(model);
  const start = existsSync(logPath) ? statSync(logPath).size : null;
  await generate("Hi", 1, model, ctx); // loads the model with this context size
  let logged = "n/a";
  if (start !== null) {
    const length = statSync(logPath).size - start;
    const buffer = Buffer.alloc(length);
    const fd = openSync(logPath, "r");
    readSync(fd, buffer, 0, length, start);
    closeSync(fd);
    const sizes = [...buffer.toString("utf8").matchAll(/llama_kv_cache: size =\s*([\d.]+) MiB \(\s*(\d+) cells/g)];
    if (sizes.length) logged = `${Number(sizes.at(-1)[1]).toFixed(2)} MiB`;
  }
  console.log(String(ctx).padStart(8) + `${fixed(predicted, 2, 10)} MiB` + logged.padStart(14));
}
await unload(model);
if (!existsSync(logPath)) console.log(`\nNo server log at ${logPath}; set OLLAMA_LOG to compare with what Ollama allocated.`);
