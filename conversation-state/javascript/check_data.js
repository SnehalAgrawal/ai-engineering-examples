// Checks the frozen inputs before anything uses them, and prints where each fact sits in its conversation.
// Same checks and output as ../python/check_data.py, where they are described.
//
//   node check_data.js
//   node check_data.js --derive    # also computes N for last_n and writes data/derived.json
import { createHash } from "node:crypto";
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";

import * as chatTemplate from "./chat_template.js";
import * as context from "./context.js";
import { DATA, PYTHON_RUNS, appears, load, mentions, positionClass } from "./common.js";

// The table of file names and SHA-256 hashes in data/README.md.
const frozenHashes = () => Object.fromEntries([...readFileSync(join(DATA, "README.md"), "utf8")
  .matchAll(/^\| ([\w./-]+\.json) \| `([0-9a-f]{64})` \|$/gm)].map((m) => [m[1], m[2]]));

const transcript = (c, system) => [...(system ? [{ role: "system", content: system }] : []), ...context.turnMessages(c.turns)];
const forms = (fact) => [...fact.accepted, ...fact.stale.flatMap((s) => s.accepted)];
const overlap = (a, b) => a.some((x) => appears(x, b)) || b.some((x) => appears(x, a));
const repr = (s) => `'${s}'`;

function checkConversation(c, settings, system) {
  const problems = [];
  const schema = settings.state_schema.json_schema.properties;
  if (c.turns.some((t) => [...(t.user + t.assistant)].some((ch) => ch.codePointAt(0) > 126))) problems.push("a message has a non-ASCII character");
  if (c.turns.length !== 20) problems.push(`${c.turns.length} turns, not 20`);
  const size = chatTemplate.count(transcript(c, system));
  if (size < 2500 || size > 3400) problems.push(`size ${size} tokens, outside 2,500 to 3,400`);
  const fields = c.facts.map((f) => f.field).sort();
  if (JSON.stringify(fields) !== JSON.stringify(["issue", "order_id", "other", "other", "other", "status"])) problems.push(`facts are ${fields}`);
  for (const f of c.facts) {
    if (!mentions(c, f.accepted).length) problems.push(`${f.id}: the current value is never mentioned`);
    for (const s of f.stale) {
      if (!mentions(c, s.accepted).length) problems.push(`${f.id}: the stale value ${repr(s.value)} is never mentioned`);
      if (overlap(f.accepted, s.accepted)) problems.push(`${f.id}: current and stale forms overlap`);
    }
    if (f.change && !f.stale.length) problems.push(`${f.id}: changed, but no stale value`);
    if (f.field === "issue" || f.field === "status") {
      for (const v of [f.value, ...f.stale.map((s) => s.value)]) {
        if (!schema[f.field].enum.includes(v)) problems.push(`${f.id}: ${repr(v)} is not in the schema's ${f.field} list`);
      }
    }
  }
  c.facts.forEach((a, i) => c.facts.slice(i + 1).forEach((b) => {
    if (overlap(forms(a), forms(b))) problems.push(`the forms of ${a.id} and ${b.id} overlap`);
  }));
  const facts = Object.fromEntries(c.facts.map((f) => [f.id, f]));
  if (JSON.stringify(c.probes.map((p) => p.fact).sort()) !== JSON.stringify(Object.keys(facts).sort())) problems.push("the probes don't cover each fact exactly once");
  for (const p of c.probes) if (appears(p.question, forms(facts[p.fact]))) problems.push(`${p.id}: the question contains a value of its fact`);
  return problems;
}

function derive(data) {
  const { prompts, settings } = data;
  if (!prompts || !prompts.version.endsWith("frozen")) throw new Error("--derive needs the frozen prompts");
  const step0 = join(PYTHON_RUNS, "step0.json");
  if (!existsSync(step0) || !JSON.parse(readFileSync(step0, "utf8")).passed) throw new Error("--derive needs a passed step 0 (python step0.py)");
  const limit = settings.context.small_window.prompt_limit;
  const dev = Object.values(data.conversations).filter((c) => c.split === "dev");
  const largest = {};
  for (let n = 1; n <= 20; n++) {
    largest[n] = Math.max(...dev.flatMap((c) => c.probes.map((p) => chatTemplate.count(context.lastN(prompts, c, p.question, n)))));
  }
  const n = Math.max(...Object.entries(largest).filter(([, size]) => size <= limit).map(([k]) => Number(k)));
  return { last_n: n, rule: "the largest N whose request fits prompt_limit for every probe of every dev conversation",
    prompt_limit: limit, prompts_version: prompts.version, conversations: dev.map((c) => c.id), largest_request_by_n: largest };
}

function main() {
  const data = load();
  let failed = false;
  const hashes = frozenHashes();
  for (const [name, expected] of Object.entries(hashes)) {
    const actual = createHash("sha256").update(readFileSync(join(DATA, name))).digest("hex");
    if (actual !== expected) {
      console.log(`CHANGED since the freeze: ${name}`);
      failed = true;
    }
  }
  if (!Object.keys(hashes).length) {
    console.log("no hashes found in data/README.md");
    failed = true;
  }
  const system = data.prompts ? data.prompts.system : null;
  console.log(`sizes rendered with the chat template${system ? " and the system prompt" : " (no system prompt yet: data/prompts.json doesn't exist)"}`);
  for (const [cid, c] of Object.entries(data.conversations)) {
    console.log(`\n${cid} (${c.split}), ${chatTemplate.count(transcript(c, system))} tokens`);
    for (const f of c.facts) {
      const turns = mentions(c, f.accepted);
      const where = turns.length ? `${positionClass(turns.at(-1))} (turn ${turns.at(-1)})` : "never mentioned";
      const stale = f.stale.map((s) => `${repr(s.value)} in turns [${mentions(c, s.accepted).join(", ")}]`).join("; ");
      console.log(`   ${f.id.padEnd(12)} ${f.field.padEnd(9)} ${(f.change || "-").padEnd(11)} ${repr(f.value)}: ${where}${stale ? `; stale ${stale}` : ""}`);
    }
    for (const problem of checkConversation(c, data.settings, system)) {
      console.log(`   PROBLEM: ${problem}`);
      failed = true;
    }
  }
  if (process.argv.includes("--derive") && !failed) {
    const derived = derive(data);
    writeFileSync(join(DATA, "derived.json"), `${JSON.stringify(derived, null, 2)}\n`);
    console.log(`\nN for last_n: ${derived.last_n} (largest dev request ${derived.largest_request_by_n[derived.last_n]} tokens; `
      + `${derived.last_n + 1} turns would need ${derived.largest_request_by_n[derived.last_n + 1] ?? "None"}); wrote data/derived.json`);
  }
  console.log(failed ? "\nSOME CHECKS FAILED" : "\nall checks passed");
  process.exit(failed ? 1 : 0);
}

main();
