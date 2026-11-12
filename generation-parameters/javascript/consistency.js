// Part 2: does a lower temperature make the assistant right, or only consistent?
// Same experiment and output as ../python/consistency.py.
//
//   node consistency.js
//   node consistency.js --model qwen2.5:3b
import { readFileSync, writeFileSync } from "node:fs";
import { parseArgs } from "node:util";

const { values: args } = parseArgs({ options: { model: { type: "string" } } });
if (args.model) process.env.OLLAMA_CHAT_MODEL = args.model;

const { chat, modelName, unload } = await import("./ollama.js");
const { parseContract, passes } = await import("./checks.js");
const { interfacePrompt } = await import("./prompts.js");

const TEMPERATURES = [0, 0.4, 0.8, 1.2];
const RUNS = 10;
const CATEGORIES = [
  ["answerable", "key fact present"],
  ["not_in_docs", "no invented value"],
  ["injection", "payload not surfaced"],
];

const dataDir = new URL("../data/", import.meta.url);
const { documents } = JSON.parse(readFileSync(new URL("help_center.json", dataDir), "utf8"));
const { cases } = JSON.parse(readFileSync(new URL("cases.json", dataDir), "utf8"));
await unload();
console.log(`Model: ${modelName()} | prompt: interface (Article #5) | ${cases.length} cases x ${RUNS} runs per temperature (seeds 1-${RUNS})`);
console.log("Other settings: Ollama defaults (top_k 40, top_p 0.9, min_p 0), num_predict 300\n");

const records = [];
for (const temperature of TEMPERATURES) {
  for (const testCase of cases) {
    const messages = interfacePrompt(testCase.question, testCase.context.map((d) => [d, documents[d]]));
    for (let run = 1; run <= RUNS; run++) {
      const reply = (await chat(messages, { temperature, seed: run, num_predict: 300 })).message.content;
      const { contract } = parseContract(reply);
      const visible = contract ? contract.answer : reply;
      records.push({ temperature, case: testCase.id, category: testCase.category, run, passed: passes(testCase.check, visible), reply });
      process.stderr.write(".");
    }
  }
  process.stderr.write("\n");
}

const out = `results-consistency-${modelName().replace(/[:/]/g, "_")}.jsonl`;
writeFileSync(out, records.map((r) => JSON.stringify(r) + "\n").join(""));
report(records);
console.log(`\nEvery reply was saved to ${out}.`);

// One decimal place, rounding halves up, using integers so Python and JavaScript agree.
function percent(part, whole) {
  const tenths = Math.floor((2000 * part + whole) / (2 * whole));
  return `${Math.floor(tenths / 10)}.${tenths % 10}%`;
}

function report(records) {
  // Python prints 0 as "0" and 0.4 as "0.4"; String() does the same.
  console.log("temperature".padEnd(13) + CATEGORIES.map(([, label]) => label.padStart(24)).join("") + "replies per case".padStart(19) + "mixed outcomes".padStart(16));
  for (const temperature of TEMPERATURES) {
    const rows = records.filter((r) => r.temperature === temperature);
    let cells = "";
    for (const [category] of CATEGORIES) {
      const subset = rows.filter((r) => r.category === category);
      const passed = subset.filter((r) => r.passed).length;
      cells += `${passed}/${subset.length} (${percent(passed, subset.length)})`.padStart(24);
    }
    const replies = new Map();
    const outcomes = new Map();
    for (const r of rows) {
      if (!replies.has(r.case)) replies.set(r.case, new Set());
      if (!outcomes.has(r.case)) outcomes.set(r.case, new Set());
      replies.get(r.case).add(r.reply);
      outcomes.get(r.case).add(r.passed);
    }
    const distinct = [...replies.values()].reduce((sum, s) => sum + s.size, 0) / replies.size;
    const mixed = [...outcomes.values()].filter((s) => s.size > 1).length;
    console.log(String(temperature).padEnd(13) + cells + distinct.toFixed(1).padStart(19) + `${mixed}/${outcomes.size}`.padStart(16));
  }

  console.log("\nConsistently wrong (failed in every run):");
  for (const temperature of TEMPERATURES) {
    const rows = records.filter((r) => r.temperature === temperature);
    const passedOnce = new Set(rows.filter((r) => r.passed).map((r) => r.case));
    const always = [...new Set(rows.map((r) => r.case))].filter((c) => !passedOnce.has(c)).sort();
    console.log(`  temperature ${temperature}: ${always.length ? always.join(", ") : "none"}`);
  }

  const zero = records.filter((r) => r.temperature === 0);
  const varied = [...new Set(zero.map((r) => r.case))]
    .filter((c) => new Set(zero.filter((r) => r.case === c).map((r) => r.reply)).size > 1)
    .sort();
  console.log(`\nAt temperature 0, cases with more than one distinct reply: ${varied.length ? varied.join(", ") : "none"}`);
}
