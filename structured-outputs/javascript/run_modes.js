// Asking for JSON versus enforcing it. Same experiment and output as ../python/run_modes.py:
// Article #5's 24 cases in four modes (prompt_only, json_mode, schema, schema_no_contract).
//
//   node run_modes.js
//   LLM_PROVIDER=ollama node run_modes.js   # local model instead of Groq
import { readFileSync, writeFileSync } from "node:fs";
import { parseArgs } from "node:util";

const { values: args } = parseArgs({ options: { model: { type: "string" }, runs: { type: "string" }, regrade: { type: "string" } } });
if (args.model) process.env[(process.env.LLM_PROVIDER || "groq") === "groq" ? "GROQ_MODEL" : "OLLAMA_CHAT_MODEL"] = args.model;

const { chat, modelName, provider, reset } = await import("./llm.js");
const { passes } = await import("./checks.js");
const { interfacePrompt, justAsk } = await import("./prompts.js");
const { matchesSchema, parseStrict, replySchema } = await import("./schema.js");

const RUNS = 2;
const runs = args.runs ? Number(args.runs) : RUNS; // fewer runs save free-tier tokens
const MAX_TOKENS = 1000; // gpt-oss is a reasoning model: its reasoning counts toward this limit
const MODES = ["prompt_only", "json_mode", "schema", "schema_no_contract"];
const CATEGORIES = [
  ["answerable", "key fact present"],
  ["not_in_docs", "no invented value"],
  ["injection", "payload not surfaced"],
];
// What the `answered` flag should say for each kind of question. Questions with a
// planted instruction are answerable from the legitimate document.
const EXPECTED_ANSWERED = { answerable: true, not_in_docs: false, injection: true };

// One decimal place, rounding halves up, using integers so Python and JavaScript agree.
function percent(part, whole) {
  const tenths = Math.floor((2000 * part + whole) / (2 * whole));
  return `${Math.floor(tenths / 10)}.${tenths % 10}%`;
}

const dataDir = new URL("../data/", import.meta.url);
const { documents } = JSON.parse(readFileSync(new URL("help_center.json", dataDir), "utf8"));
const { cases } = JSON.parse(readFileSync(new URL("cases.json", dataDir), "utf8"));

if (args.regrade) {
  // Grading only: the saved replies are re-checked with the current checks.
  const byId = Object.fromEntries(cases.map((c) => [c.id, c]));
  const saved = readFileSync(args.regrade, "utf8").split("\n").filter((line) => line.trim()).map((line) => JSON.parse(line));
  for (const r of saved) {
    const testCase = byId[r.case];
    const data = parseStrict(r.reply);
    const valid = matchesSchema(data, testCase.context);
    Object.assign(r, {
      json: data !== null, schema: valid,
      passed: passes(testCase.check, valid ? data.answer : r.reply),
      flag_ok: valid && data.answered === EXPECTED_ANSWERED[testCase.category],
      empty: valid && !data.answer.trim(),
    });
  }
  console.log(`Regraded ${saved.length} saved replies from ${args.regrade} with the current checks (no API calls)\n`);
  report(saved);
  process.exit(0);
}

await reset();
console.log(`Model: ${modelName()} (${provider()}) | ${cases.length} cases x ${runs} runs per mode (seeds 1-${runs}) | default sampling, max tokens ${MAX_TOKENS}\n`);

const records = [];
for (const mode of MODES) {
  for (const testCase of cases) {
    const context = testCase.context.map((d) => [d, documents[d]]);
    const messages = mode === "schema_no_contract" ? justAsk(testCase.question, context) : interfacePrompt(testCase.question, context);
    const output = mode === "prompt_only" ? null : mode === "json_mode" ? "json" : replySchema(testCase.context);
    for (let run = 1; run <= runs; run++) {
      const response = await chat(messages, run, MAX_TOKENS, output);
      const reply = response.content;
      const data = parseStrict(reply);
      const valid = matchesSchema(data, testCase.context);
      const visible = valid ? data.answer : reply;
      records.push({
        mode, case: testCase.id, category: testCase.category, run,
        json: data !== null, schema: valid,
        passed: passes(testCase.check, visible),
        flag_ok: valid && data.answered === EXPECTED_ANSWERED[testCase.category],
        empty: valid && !data.answer.trim(),
        finish_reason: response.finish_reason, tokens: response.tokens,
        fingerprint: response.fingerprint, error: response.error, reply,
      });
      process.stderr.write(".");
    }
  }
  process.stderr.write("\n");
}
await reset();

const out = `results-modes-${modelName().replace(/[:/]/g, "_")}.jsonl`;
writeFileSync(out, records.map((r) => JSON.stringify(r) + "\n").join(""));
report(records);
console.log(`\nEvery reply was saved to ${out}.`);

function report(records) {
  // Python prints None for missing values; match it so both languages print the same text.
  const str = (v) => (v === null || v === undefined ? "None" : String(v));
  console.log("mode".padEnd(20) + "valid JSON".padStart(14) + "matches schema".padStart(16) + CATEGORIES.map(([, label]) => label.padStart(22)).join("") + "flag matches".padStart(15) + "empty answer".padStart(14));
  for (const mode of MODES) {
    const rows = records.filter((r) => r.mode === mode);
    const n = rows.length;
    const count = (list, key) => list.filter((r) => r[key]).length;
    let cells = percent(count(rows, "json"), n).padStart(14) + percent(count(rows, "schema"), n).padStart(16);
    for (const [category] of CATEGORIES) {
      const subset = rows.filter((r) => r.category === category);
      cells += percent(count(subset, "passed"), subset.length).padStart(22);
    }
    cells += percent(count(rows, "flag_ok"), n).padStart(15) + String(count(rows, "empty")).padStart(14);
    console.log(mode.padEnd(20) + cells);
  }
  console.log("\nvalid JSON: the reply parses as a JSON object, with no cleanup.");
  console.log("matches schema: exactly answered/answer/source_ids, right types, ids only from the retrieved documents.");
  console.log("flag matches: `answered` is true for answerable questions and false for questions the documents don't answer.");
  const errors = records.filter((r) => r.error).length;
  const reasons = {};
  for (const r of records) reasons[str(r.finish_reason)] = (reasons[str(r.finish_reason)] || 0) + 1;
  console.log(`\nAPI errors: ${errors} | finish reasons: ` + Object.keys(reasons).sort().map((k) => `${k} ${reasons[k]}`).join(", "));
  const tokens = records.reduce((sum, r) => sum + r.tokens, 0);
  const fingerprints = [...new Set(records.map((r) => str(r.fingerprint)))].sort();
  console.log(`Tokens used: ${tokens.toLocaleString("en-US")} | backend fingerprints: ${fingerprints.join(", ")}`);
}
