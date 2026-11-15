// The report, from a saved run (runs/javascript/<out>/requests.jsonl) and step 0 (runs/python/step0.json; step 0
// runs in Python only). Same output as ../python/report.py: counts and outcomes first, which should match
// Python's exactly, then timings, which vary from run to run.
//
//   node report.js            # runs/javascript/main
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { PYTHON_RUNS, RUNS } from "./common.js";

const EXPERIMENT_MODES = {
  1: ["non-streaming", "streaming"], 2: ["pass-through", "buffer-all", "buffer-4096"],
  3: ["ignore", "cancel"], 4: ["check-whole", "stream-then-check", "sentence-gate"],
};
const chars = (s) => [...s].length; // code points, as Python's len()
const sum = (xs) => xs.reduce((s, x) => s + Number(x), 0);
const pyList = (xs) => `[${xs.map((x) => `'${x}'`).join(", ")}]`;

function median(values) {
  const ordered = [...values].sort((a, b) => a - b);
  const n = ordered.length;
  return n % 2 ? ordered[(n - 1) / 2] : (ordered[n / 2 - 1] + ordered[n / 2]) / 2;
}

// median (minimum to maximum), in seconds
function spread(values) {
  const vs = values.filter((v) => v !== null && v !== undefined);
  if (!vs.length) return "n/a";
  return `${median(vs).toFixed(2)} (${Math.min(...vs).toFixed(2)} to ${Math.max(...vs).toFixed(2)})`;
}

const seconds = (r, key) => (r.client[key] === null || r.client[key] === undefined ? null : (r.client[key] - r.client.t_start) / 1000);
const serverSeconds = (r, key) => (r.server[key] === null || r.server[key] === undefined ? null : (r.server[key] - r.client.t_start) / 1000);

const args = process.argv.slice(2);
const out = args.includes("--out") ? args[args.indexOf("--out") + 1] : "main";
const lines = readFileSync(join(RUNS, out, "requests.jsonl"), "utf8").split("\n").filter(Boolean).map((l) => JSON.parse(l));
const by = new Map();
for (const r of lines) {
  const key = `${r.experiment}|${r.mode}`;
  if (!by.has(key)) by.set(key, []);
  by.get(key).push(r);
}
const get = (e, m) => by.get(`${e}|${m}`);
const step0Path = join(PYTHON_RUNS, "step0.json");
const step0 = existsSync(step0Path) ? JSON.parse(readFileSync(step0Path, "utf8")) : null;

console.log(`Streaming responses: ${lines.length} requests`);
console.log("Step 0, reading Ollama's log:", step0 === null ? "not run" : step0.passed ? "passed" : "FAILED");

// ---------------------------------------------------------------------------------------------------- counts
console.log("\nCOUNTS AND OUTCOMES (the same in Python and JavaScript)");
const texts = new Map();
for (const r of lines.filter((x) => x.experiment !== "3" || x.mode === "ignore")) {
  if (!texts.has(r.email)) texts.set(r.email, new Set());
  texts.get(r.email).add(r.server.generated_sha256);
}
console.log(`emails whose generated reply was the same in every complete request: ${[...texts.values()].filter((s) => s.size === 1).length} of ${texts.size}`);
const overlap = lines.filter((r) => r.overlap.length);
console.log(`requests during which another program was connected to Ollama: ${overlap.length}`);
// flagged, not dropped: their timings may be distorted
for (const r of overlap) console.log(`   ${r.experiment}|${r.mode}|${r.email}: ${r.overlap.join(", ")}`);

if (get("1", "streaming")) {
  console.log("\n1. What the user waits for");
  for (const mode of EXPERIMENT_MODES[1]) console.log(`   ${mode}: ${get("1", mode).length} requests`);
}

if (get("2", "buffer-all")) {
  console.log("\n2. Where streams get stuck");
  for (const mode of EXPERIMENT_MODES[2]) {
    const rs = get("2", mode);
    if (mode === "buffer-all") console.log(`   ${mode}: ${rs.length} requests, ${rs.filter((r) => r.proxy.writes === 1).length} delivered in one write`);
    else console.log(`   ${mode}: ${rs.length} requests`);
  }
}

if (get("3", "cancel")) {
  console.log("\n3. When the user leaves");
  for (const mode of EXPERIMENT_MODES[3]) {
    const rs = get("3", mode);
    console.log(`   ${mode}: ${rs.length} requests; the client closed after 20 text events in `
      + `${rs.filter((r) => r.client.t_closed !== null).length} of them; log matched to one task: `
      + `${rs.filter((r) => r.log.task !== null).length}; 'cancel task' line: `
      + `${rs.filter((r) => r.log.cancelled).length}; app server stopped reading: ${rs.filter((r) => r.server.cancelled).length}`);
  }
  const full = Object.fromEntries((get("1", "streaming") || []).map((r) => [r.email, r.server.ollama.eval_count]));
  const ignore = get("3", "ignore");
  if (Object.keys(full).length) {
    // Step 0 found the log's estimate one below eval_count for completed requests (see ../python/report.py).
    const same = ignore.filter((r) => r.log.generated_estimate === (full[r.email] ?? 0) - 1).length;
    console.log(`   ignore: estimated tokens generated equal to the completed reply's eval_count - 1 (as in step 0): ${same} of ${ignore.length}`);
  }
}

if (get("4", "sentence-gate")) {
  console.log("\n4. Streaming and checks");
  const flaggedBy = {};
  for (const mode of EXPERIMENT_MODES[4]) {
    const rs = get("4", mode);
    const count = (k) => rs.filter((r) => r.client.outcome === k).length;
    const shown = sum(rs.map((r) => chars(r.client.visible_text)));
    console.log(`   ${mode}: ${["passed", "withheld", "retracted"].filter((k) => count(k)).map((k) => `${k} ${count(k)}`).join(", ")}`
      + `; characters left visible in total: ${shown}`);
    flaggedBy[mode] = new Set(rs.filter((r) => r.client.outcome !== "passed").map((r) => r.email));
  }
  const gate = get("4", "sentence-gate");
  console.log(`   sentence-gate: sentences sent ${sum(gate.map((r) => r.server.sentences_sent))}, characters held back `
    + `${sum(gate.map((r) => r.server.chars_held_back))}`);
  const whole = flaggedBy["check-whole"];
  const sentence = flaggedBy["sentence-gate"];
  const both = [...whole].filter((e) => sentence.has(e));
  console.log(`   emails flagged: check-whole ${whole.size}, stream-then-check ${flaggedBy["stream-then-check"].size}, `
    + `sentence-gate ${sentence.size}; flagged by both whole-reply and sentence checks ${both.length}; `
    + `only whole ${pyList([...whole].filter((e) => !sentence.has(e)).sort())}; only sentence ${pyList([...sentence].filter((e) => !whole.has(e)).sort())}`);
}

// ---------------------------------------------------------------------------------------------------- timings
console.log("\nTIMINGS (seconds after the client sent the request; median (minimum to maximum); vary from run to run)");
if (get("1", "streaming")) {
  console.log("\n1. What the user waits for");
  for (const mode of EXPERIMENT_MODES[1]) {
    const rs = get("1", mode);
    console.log(`   ${mode.padEnd(14)} first text ${spread(rs.map((r) => seconds(r, "t_first_text")))}, done ${spread(rs.map((r) => seconds(r, "t_done")))}`);
  }
  const stream = Object.fromEntries(get("1", "streaming").map((r) => [r.email, r]));
  const sooner = get("1", "non-streaming").map((r) => seconds(r, "t_first_text") - seconds(stream[r.email], "t_first_text"));
  console.log(`   first words sooner with streaming, per email: ${spread(sooner)}`);
  const rs = get("1", "streaming");
  console.log(`   streaming: app server received the request ${spread(rs.map((r) => serverSeconds(r, "t_received")))}, `
    + `first model token ${spread(rs.map((r) => serverSeconds(r, "t_model_first")))}, `
    + `post-model delay ${spread(rs.map((r) => seconds(r, "t_first_text") - serverSeconds(r, "t_model_first")))}`);
}

if (get("2", "buffer-all")) {
  console.log("\n2. Where streams get stuck");
  for (const mode of EXPERIMENT_MODES[2]) {
    const rs = get("2", mode);
    console.log(`   ${mode.padEnd(13)} first text ${spread(rs.map((r) => seconds(r, "t_first_text")))}, first model token `
      + `${spread(rs.map((r) => serverSeconds(r, "t_model_first")))}, post-model delay `
      + `${spread(rs.map((r) => seconds(r, "t_first_text") - serverSeconds(r, "t_model_first")))}, `
      + `done ${spread(rs.map((r) => seconds(r, "t_done")))}, proxy writes ${spread(rs.map((r) => r.proxy.writes))}`);
  }
}

if (get("3", "cancel")) {
  console.log("\n3. When the user leaves");
  const full = Object.fromEntries((get("1", "streaming") || []).map((r) => [r.email, r.server.ollama.eval_count]));
  for (const mode of EXPERIMENT_MODES[3]) {
    const rs = get("3", mode);
    const detected = rs.filter((r) => r.server.t_write_failed !== null).map((r) => (r.server.t_write_failed - r.client.t_closed) / 1000);
    console.log(`   ${mode}: disconnect detected after ${spread(detected)} (${detected.length} of ${rs.length} detected); `
      + `upstream text events after it ${spread(rs.map((r) => r.server.upstream_events_after_disconnect))}; `
      + `estimated tokens generated (Ollama log) ${spread(rs.map((r) => r.log.generated_estimate))}; `
      + `completed reply for the same emails ${spread(rs.map((r) => full[r.email]))}`);
  }
}

if (get("4", "sentence-gate")) {
  console.log("\n4. Streaming and checks");
  for (const mode of EXPERIMENT_MODES[4]) {
    const rs = get("4", mode);
    console.log(`   ${mode.padEnd(17)} first text ${spread(rs.map((r) => seconds(r, "t_first_text")))}, done ${spread(rs.map((r) => seconds(r, "t_done")))}`);
  }
  const retracted = get("4", "stream-then-check").filter((r) => r.client.outcome === "retracted");
  const visible = retracted.filter((r) => r.client.t_flagged_visible !== null && r.client.t_flagged_visible !== undefined)
    .map((r) => (r.client.t_retracted - r.client.t_flagged_visible) / 1000);
  console.log(`   stream-then-check: a flagged value was on screen before the retraction for ${spread(visible)} `
    + `(${visible.length} of ${retracted.length} retracted replies)`);
}
