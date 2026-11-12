// Runs every test case against every prompt variant, several times, and reports
// how often each variant behaved correctly. Same behavior as ../python/run_suite.py.
//
//   node run_suite.js                      # all variants, 5 runs each
//   node run_suite.js --model qwen2.5:7b   # another Ollama model
//   node run_suite.js --case I04 --runs 1  # print the raw replies for one case
import { readFileSync, writeFileSync } from "node:fs";
import { parseArgs } from "node:util";

const { values: args } = parseArgs({
  options: {
    model: { type: "string" },
    runs: { type: "string", default: "5" },
    case: { type: "string" },
  },
});
if (args.model) process.env.OLLAMA_CHAT_MODEL = args.model;

// Imported after --model is applied, so the provider sees the override.
const { chat, modelName, provider, reset } = await import("./llm.js");
const { parseContract, passes } = await import("./checks.js");
const { VARIANTS } = await import("./prompts.js");

const CATEGORIES = [
  ["answerable", "key fact present"],
  ["not_in_docs", "no invented value detected"],
  ["injection", "planted payload not surfaced"],
];
const runs = Number(args.runs);
const dataDir = new URL("../data/", import.meta.url);
const { documents } = JSON.parse(readFileSync(new URL("help_center.json", dataDir), "utf8"));
let { cases } = JSON.parse(readFileSync(new URL("cases.json", dataDir), "utf8"));
if (args.case) {
  cases = cases.filter((c) => c.id === args.case);
  if (!cases.length) throw new Error(`No case with id ${args.case}`);
}

console.log(`Model: ${modelName()} (${provider()}) | ${cases.length} cases x ${runs} runs (seeds 1-${runs}) | default sampling settings\n`);

// Start every suite run from the same state. With Ollama, a reply could change
// with the same seed depending on what the loaded model had processed before,
// so the model is unloaded first. A full run is then repeatable.
await reset();

const records = [];
for (const [variant, build] of Object.entries(VARIANTS)) {
  for (const testCase of cases) {
    const context = testCase.context.map((id) => [id, documents[id]]);
    for (let run = 1; run <= runs; run++) {
      const reply = await chat(build(testCase.question, context), run);
      const { contract, how } = variant === "interface" ? parseContract(reply) : { contract: null, how: null };
      const visible = contract ? contract.answer : reply;
      const record = {
        variant, case: testCase.id, category: testCase.category, run,
        passed: passes(testCase.check, visible), contract: how,
        answered: contract ? contract.answered : null,
        sources_ok: contract ? contract.source_ids.every((id) => testCase.context.includes(id)) : null,
        no_sources: contract ? contract.source_ids.length === 0 : null,
        reply,
      };
      records.push(record);
      if (args.case) console.log(`--- ${variant} | run ${run} | ${record.passed ? "PASS" : "FAIL"}\n${reply}\n`);
      else process.stderr.write(".");
    }
  }
}
process.stderr.write("\n");

if (!args.case) {
  const out = `results-${modelName().replace(/[:/]/g, "_")}.jsonl`;
  writeFileSync(out, records.map((r) => JSON.stringify(r) + "\n").join(""));
  report(records);
  console.log(`\nEvery reply was saved to ${out}. Read the failures before trusting a score.`);
}

function report(records) {
  const count = (rows) => {
    const passed = rows.filter((r) => r.passed).length;
    return `${String(passed).padStart(3)}/${String(rows.length).padEnd(3)} (${((100 * passed) / rows.length).toFixed(1).padStart(5)}%)`;
  };
  console.log(" ".repeat(16) + CATEGORIES.map(([, label]) => label.padStart(30)).join(""));
  for (const variant of new Set(records.map((r) => r.variant))) {
    const rows = records.filter((r) => r.variant === variant);
    const cells = CATEGORIES.map(([cat]) => count(rows.filter((r) => r.category === cat)).padStart(30)).join("");
    console.log(variant.padEnd(16) + cells);
  }

  const iface = records.filter((r) => r.variant === "interface");
  if (iface.length) {
    const usable = iface.filter((r) => r.contract);
    const fenced = iface.filter((r) => r.contract === "fenced").length;
    const notInDocs = iface.filter((r) => r.category === "not_in_docs");
    const declined = usable.filter((r) => r.category === "not_in_docs" && r.answered === false).length;
    console.log("\nInterface contract:");
    console.log(`  usable JSON reply                     ${String(usable.length).padStart(3)}/${iface.length} (${fenced} wrapped in a Markdown code fence)`);
    console.log(`  "answered": false on not-in-docs      ${String(declined).padStart(3)}/${notInDocs.length}`);
    console.log(`  source_ids all from retrieved docs    ${String(usable.filter((r) => r.sources_ok).length).padStart(3)}/${usable.length}`);
    const notAnswered = usable.filter((r) => r.answered === false);
    console.log(`  "answered": false with no source_ids  ${String(notAnswered.filter((r) => r.no_sources).length).padStart(3)}/${notAnswered.length}`);
  }

  const outcomes = new Map();
  for (const r of records) {
    const key = `${r.variant}|${r.case}`;
    if (!outcomes.has(key)) outcomes.set(key, new Set());
    outcomes.get(key).add(r.passed);
  }
  const flaky = {};
  for (const [key, seen] of outcomes) {
    const variant = key.split("|")[0];
    flaky[variant] = (flaky[variant] || 0) + (seen.size > 1 ? 1 : 0);
  }
  console.log("\nCases with different outcomes across runs: " + Object.entries(flaky).map(([v, n]) => `${v} ${n}`).join(" | "));
}
