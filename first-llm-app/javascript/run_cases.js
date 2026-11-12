// Sends the same ten inputs to the naive version and to the application, and shows what
// the customer would see from each. Same experiment and output as ../python/run_cases.py.
//
//   node run_cases.js
//   node run_cases.js --model qwen2.5:3b
import { readFileSync, writeFileSync } from "node:fs";
import { parseArgs } from "node:util";

const { values: args } = parseArgs({ options: { model: { type: "string" } } });
if (args.model) process.env.OLLAMA_CHAT_MODEL = args.model;

const naive = await import("./naive.js");
const { DOCUMENTS, handle, unsupportedValues } = await import("./app.js");
const { chat, modelName, unload } = await import("./llm.js");

const { cases: CASES } = JSON.parse(readFileSync(new URL("../data/cases.json", import.meta.url), "utf8"));
const UNREACHABLE = "http://127.0.0.1:9"; // nothing listens here

// Python-style printing, so both languages produce the same text.
const pyRepr = (text) => {
  const body = text.replace(/\\/g, "\\\\").replace(/\n/g, "\\n").replace(/\t/g, "\\t");
  return text.includes("'") && !text.includes('"') ? `"${body}"` : `'${body.replace(/'/g, "\\'")}'`;
};
const pyList = (items) => `[${items.map(pyRepr).join(", ")}]`;
const pyDumps = (obj) => `{${Object.entries(obj).map(([k, v]) => `${JSON.stringify(k)}: ${JSON.stringify(v)}`).join(", ")}}`;
const n = (x) => x.toLocaleString("en-US");
const passes = (check, text) => !check || check.patterns.some((p) => new RegExp(p, "i").test(text));
const short = (text, width = 150) => {
  const flat = text.split(/\s+/).filter(Boolean).join(" ");
  return flat.length <= width ? flat : flat.slice(0, width - 1) + "…";
};

await unload();
console.log(`Model: ${modelName()} | temperature 0, seed 1 | ${CASES.length} inputs, each sent to both versions\n`);
const records = [];
for (const testCase of CASES) {
  const url = testCase.fault === "unavailable" ? UNREACHABLE : null;
  let naiveShown, naiveError = null;
  try {
    naiveShown = await naive.answer(testCase.input, url);
  } catch (error) { // the naive version has no error handling: this is what reaches the user
    naiveError = error.constructor.name;
    naiveShown = `(unhandled ${naiveError}: the request fails with a server error)`;
  }
  const result = await handle(testCase.input, url);
  records.push({ case: testCase.id, kind: testCase.kind, naive: naiveShown, naive_error: naiveError, app: result.message,
    app_status: result.status, app_sources: result.sources, app_model_output: result.model_output, log: result.log });
}
await unload();

const allDocs = Object.values(DOCUMENTS);
records.forEach((r, i) => {
  const testCase = CASES[i];
  console.log(`[${r.case}]  input: ${pyRepr(short(testCase.input, 90))} (${n(testCase.input.length)} characters)`);
  console.log(`  naive: ${short(r.naive)}`);
  console.log(`  app:   ${r.app_status} ${r.log.outcome}: ${short(r.app)}` + (r.app_sources.length ? `  sources: ${pyList(r.app_sources)}` : ""));
  const notes = [];
  if (testCase.check) notes.push(`key fact: naive ${passes(testCase.check, r.naive) ? "yes" : "NO"}, app ${passes(testCase.check, r.app) ? "yes" : "NO"}`);
  const inventedNaive = r.naive_error ? [] : unsupportedValues(r.naive, allDocs);
  const inventedApp = unsupportedValues(r.app, allDocs);
  if (inventedNaive.length || inventedApp.length) notes.push(`values not in the help center: naive ${pyList(inventedNaive)}, app ${pyList(inventedApp)}`);
  if (r.log.prompt_tokens !== null) notes.push(`app prompt tokens: ${n(r.log.prompt_tokens)}`);
  if (notes.length) console.log("  " + notes.join(" | "));
  console.log();
});

const oversized = CASES.find((c) => c.kind === "oversized");
const probe = await chat([{ role: "user", content: oversized.input }], { maxTokens: 1 });
await unload();
console.log(`The oversized input as the naive version sends it: the model server processed ${n(probe.prompt_tokens)} prompt tokens ` +
  `and returned no error (${n(oversized.input.length)} characters sent).`);

console.log("\nApplication log (one record per request; request ids and latencies differ on every run):");
for (const r of records) console.log("  " + pyDumps(r.log));
writeFileSync(`results-cases-${modelName().replace(/[:/]/g, "_")}.jsonl`, records.map((r) => JSON.stringify(r) + "\n").join(""));
