// The report, from a saved run (runs/javascript/<out>/). Same output as ../python/report.py: counts and outcomes
// first, which should match Python's exactly, then timings, which vary from run to run.
//
//   node report.js                 # runs/javascript/main
//   node report.js --out smoke
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

import * as chatTemplate from "./chat_template.js";
import * as context from "./context.js";
import { DATA, RUNS, load, mentions, positionClass } from "./common.js";

const GRADES = ["correct", "stale", "both", "other"];
const FINAL = ["correct", "stale", "both", "not stated", "wrong", "invented"];
const STRATEGIES = ["1b_full", "3_last_n", "3_token_budget", "3_summary_recent", "3_state_recent"];
const readJsonl = (path) => readFileSync(path, "utf8").split("\n").filter(Boolean).map((l) => JSON.parse(l));

// Fixed-point formatting as Python's format() does it: an exact tie rounds to even (toFixed rounds it up).
function fixed(v, digits) {
  const scaled = v * 10 ** digits;
  if (Number.isInteger(scaled * 2) && !Number.isInteger(scaled)) {
    const down = Math.floor(scaled);
    const even = down % 2 === 0 ? down : down + 1;
    return (even / 10 ** digits).toFixed(digits);
  }
  return v.toFixed(digits);
}

function median(values) {
  const s = [...values].sort((a, b) => a - b);
  const n = s.length;
  return n % 2 ? s[(n - 1) / 2] : (s[n / 2 - 1] + s[n / 2]) / 2;
}

// median (minimum to maximum). With digits 0, whole numbers stay whole and a median halfway between two is shown
// with one decimal.
function spread(values, digits = 0) {
  const vs = values.filter((v) => v !== null && v !== undefined);
  if (!vs.length) return "n/a";
  const fmt = (v) => (digits ? fixed(v, digits) : Number.isInteger(v) ? fixed(v, 0) : fixed(v, 1));
  return `${fmt(median(vs))} (${fmt(Math.min(...vs))} to ${fmt(Math.max(...vs))})`;
}

const tally = (rows, key = "grade") => GRADES.map((g) => `${g} ${rows.filter((r) => r[key] === g).length}`).join(", ");
const rate = (rows, key = "grade") => `${rows.filter((r) => r[key] === "correct").length} of ${rows.length}`;
const sum = (xs) => xs.reduce((a, b) => a + b, 0);
const pad = (s, n) => String(s).padEnd(n);

function main() {
  const args = process.argv.slice(2);
  const out = args.includes("--out") ? args[args.indexOf("--out") + 1] : "main";
  const data = load();
  const { conversations: convs, prompts } = data;
  const run = join(RUNS, out);
  const rows = readJsonl(join(run, "requests.jsonl"));
  const labelsPath = join(DATA, "hand_labels.json");
  const labels = existsSync(labelsPath) ? JSON.parse(readFileSync(labelsPath, "utf8")).labels : {};
  const facts = new Map(Object.values(convs).flatMap((c) => c.facts.map((f) => [`${c.id}|${f.id}`, f])));
  for (const r of rows) {
    if (!("fact" in r)) continue;
    const f = facts.get(`${r.conversation}|${r.fact}`);
    r.position = positionClass(mentions(convs[r.conversation], f.accepted).at(-1));
    r.kind = f.field !== "other" ? "in-schema" : "other";
    r.changed = f.change;
    r.hand = labels[`${r.conversation}|${r.probe}|${r.output_sha256}`]?.label ?? null;
    // The final grade: the hand label where the answer was read, otherwise the mechanical 'correct'.
    r.final = r.hand || (r.grade === "correct" ? "correct" : null);
  }
  const finals = (rs) => FINAL.map((g) => `${g} ${rs.filter((r) => r.final === g).length}`).join(", ");
  const hasLabels = Object.keys(labels).length > 0;
  const by = (block, split = null) => rows.filter((r) => r.block === block && (split === null || r.split === split));

  console.log(`Conversation state: ${rows.length} model calls in runs/javascript/${out}; prompts ${prompts.version}; `
    + `last_n ${JSON.parse(readFileSync(join(DATA, "derived.json"), "utf8")).last_n}`);
  console.log(`errors: ${rows.filter((r) => r.error).length}; requests during which another program was connected to Ollama: `
    + `${rows.filter((r) => r.overlap.length).length}; hand labels: ${Object.keys(labels).length}`);

  console.log("\nCOUNTS AND OUTCOMES (the same in Python and JavaScript)");
  const splits = ["test", "dev"].filter((s) => rows.some((r) => r.split === s));

  console.log("\n1a/1b. The model is stateless: the same probes with no history and with the full history (num_ctx 8192)");
  for (const split of splits) {
    for (const block of ["1a_no_history", "1b_full"]) {
      if (by(block, split).length) {
        console.log(`   ${split} ${pad(block, 14)} ${tally(by(block, split))}`);
        if (hasLabels) console.log(`      FINAL: ${finals(by(block, split))}`);
      }
    }
  }

  console.log("\n1c. Growth: tokens sent per turn with the full history");
  const sizes = Object.values(convs).map((c) => Array.from({ length: 20 }, (_, i) => chatTemplate.count(
    [context.system(prompts), ...context.turnMessages(c.turns.slice(0, i)), { role: "user", content: c.turns[i].user }])));
  console.log(`   all 12 conversations (counted, no model calls): turn 1 ${spread(sizes.map((s) => s[0]))}, `
    + `turn 20 ${spread(sizes.map((s) => s.at(-1)))}; sent over all 20 turns ${spread(sizes.map(sum))}, `
    + `${spread(sizes.map((s) => sum(s) / s.at(-1)), 1)} times the last request`);
  const growth = by("1c_growth");
  if (growth.length) {
    const matched = growth.filter((r) => r.log.evaluated_tokens !== null);
    console.log(`   measured (${new Set(growth.map((r) => r.conversation)).size} conversations, ${growth.length} requests): `
      + `app count equal to prompt_eval_count in ${growth.filter((r) => r.app_tokens === r.prompt_eval_count).length}; `
      + `evaluated tokens found in the log for ${matched.length} (unavailable: ${growth.length - matched.length})`);
    for (const t of [1, 5, 10, 15, 20]) {
      const ts = growth.filter((r) => r.turn === t);
      console.log(`      turn ${String(t).padStart(2)}: sent ${spread(ts.map((r) => r.prompt_eval_count))}, `
        + `evaluated ${spread(ts.map((r) => r.log.evaluated_tokens))}`);
    }
    console.log(`      all turns: evaluated / sent ${spread(matched.map((r) => r.log.evaluated_tokens / r.prompt_eval_count), 2)}`);
  }

  const two = by("2_full_small");
  if (two.length) {
    console.log("\n2. Past the window: the full history at num_ctx 2048");
    console.log(`   sent ${spread(two.map((r) => r.app_tokens))}; Ollama's prompt_eval_count ${spread(two.map((r) => r.prompt_eval_count))}; `
      + `errors ${two.filter((r) => r.error).length}`);
    const cut = two.filter((r) => r.ending_matches !== undefined && r.ending_matches !== null);
    console.log(`   requests cut before answering: ${cut.length} of ${two.length}; exactly one matching ending: `
      + `${cut.filter((r) => r.ending_matches === 1).length}; first turn kept ${spread(cut.map((r) => r.first_kept_turn))}`);
    const lost = cut.filter((r) => r.in_context.current && r.in_context_seen && !r.in_context_seen.current);
    console.log(`   probes whose current value was sent but not seen: ${lost.length}; correct among them ${rate(lost)}`);
    const seen = cut.filter((r) => r.in_context_seen && r.in_context_seen.current);
    console.log(`   probes whose current value was seen: ${seen.length}; correct among them ${rate(seen)}`);
    for (const split of splits) {
      console.log(`   ${split}: ${tally(by("2_full_small", split))}`);
      if (hasLabels) console.log(`      FINAL: ${finals(by("2_full_small", split))}`);
    }
    if (hasLabels) console.log(`   FINAL where the current value was sent but not seen: ${rate(lost, "final")}; where it was seen: ${rate(seen, "final")}`);
    const shifted = two.filter((r) => r.log.context_shifts.length);
    console.log(`   answer length ${spread(two.map((r) => r.eval_count))} tokens; room left after the prompt `
      + `${spread(two.map((r) => 2048 - r.prompt_eval_count))} tokens`);
    console.log(`   requests with a context shift during the answer: ${shifted.length}; tokens discarded `
      + `${spread(shifted.flatMap((r) => r.log.context_shifts.map((s) => s.n_discard)))}; `
      + `truncated = 1 in ${two.filter((r) => r.log.truncated === 1).length}`);
  }

  console.log("\n3. Strategies (num_ctx 2048; the full history at 8192 for reference)");
  for (const split of splits) {
    console.log(`   ${split}:`);
    for (const block of STRATEGIES) {
      const rs = by(block, split);
      if (!rs.length) continue;
      const over = rs.filter((r) => r.over_limit).length;
      console.log(`      ${pad(block, 17)} ${tally(rs)}; prompt tokens ${spread(rs.map((r) => r.app_tokens))}${over ? `; over the limit ${over}` : ""}`);
      console.log(`         by position: ${["early", "middle", "late"].map((p) => `${p} ${rate(rs.filter((r) => r.position === p))}`).join("; ")}`);
      console.log(`         current value in the context sent: ${rate(rs.filter((r) => r.in_context.current))} correct; `
        + `not in it: ${rate(rs.filter((r) => !r.in_context.current))} correct (not answerable from the context)`);
      const changed = rs.filter((r) => r.changed);
      console.log(`         in-schema ${rate(rs.filter((r) => r.kind === "in-schema"))}; other ${rate(rs.filter((r) => r.kind === "other"))}; `
        + `changed facts ${rate(changed)}, stale answers among them ${changed.filter((r) => r.grade === "stale" || r.grade === "both").length}`);
      if (hasLabels) {
        console.log(`         FINAL (hand label where read): ${finals(rs)}; ungraded ${rs.filter((r) => r.final === null).length}`);
        console.log(`            by position: ${["early", "middle", "late"].map((p) => `${p} ${rate(rs.filter((r) => r.position === p), "final")}`).join("; ")}`);
        console.log(`            current value in the context sent: ${rate(rs.filter((r) => r.in_context.current), "final")}; `
          + `not in it: ${rate(rs.filter((r) => !r.in_context.current), "final")}`);
        console.log(`            in-schema ${rate(rs.filter((r) => r.kind === "in-schema"), "final")}; other ${rate(rs.filter((r) => r.kind === "other"), "final")}; `
          + `changed facts ${rate(changed, "final")}, stale or both among them ${changed.filter((r) => r.final === "stale" || r.final === "both").length}`);
      }
    }
  }

  for (const [kind, one, block, path] of [["summaries", "summary", "summaries", "summaries"], ["case records", "case record", "states", "state"]]) {
    const calls = by(block);
    if (!calls.length) continue;
    console.log(`\n3. Maintaining the ${kind}`);
    const perConv = {};
    for (const r of calls) (perConv[r.conversation] ??= []).push(r);
    const groups = Object.values(perConv);
    console.log(`   calls per conversation ${spread(groups.map((v) => v.length))}; input tokens per conversation `
      + `${spread(groups.map((v) => sum(v.map((r) => r.app_tokens))))}; output tokens per conversation `
      + `${spread(groups.map((v) => sum(v.map((r) => r.eval_count))))}`);
    const trail = Object.fromEntries(Object.keys(perConv).map((cid) => [cid, readJsonl(join(run, path, `${cid}.jsonl`))]));
    const trails = Object.values(trail);
    if (kind === "summaries") {
      console.log(`   summaries cut off at the cap: ${sum(trails.map((v) => v.filter((t) => t.cut_off).length))} of `
        + `${sum(trails.map((v) => v.length))}; final summaries cut off: ${trails.filter((v) => v.at(-1).cut_off).length} of ${trails.length}`);
    } else {
      console.log(`   outputs that weren't valid JSON: ${sum(trails.map((v) => v.filter((t) => t.parse_error).length))}`);
    }
    for (const split of kind === "summaries" ? splits : []) {
      const fs = Object.keys(trail).filter((cid) => convs[cid].split === split).flatMap((cid) => convs[cid].facts.map((f) => [cid, f]));
      const final = fs.map(([cid, f]) => trail[cid].at(-1).output[f.id]);
      const everIn = fs.map(([cid, f]) => trail[cid].some((t) => t.input[f.id].current));
      const dropped = everIn.filter((e, i) => e && !final[i].current).length;
      console.log(`   ${split}: facts whose current value is in the final ${one}: ${final.filter((x) => x.current).length} of ${fs.length}; `
        + `with a stale value: ${final.filter((x) => x.stale).length}; in the input of a summary call but not in the final summary: ${dropped}`);
    }
    if (kind === "case records") {
      console.log("   the record holds order_id, issue, and status only; the three other facts of each conversation aren't in its schema");
      for (const split of splits) {
        for (const field of ["order_id", "issue", "status"]) {
          const marks = [];
          for (const cid of Object.keys(trail)) {
            if (convs[cid].split !== split) continue;
            const f = convs[cid].facts.find((x) => x.field === field);
            const value = String(trail[cid].at(-1).state[field] ?? "");
            const stale = f.stale.map((s) => s.value);
            if (field === "order_id") {
              const cur = f.accepted.some((a) => value.toLowerCase().includes(a.toLowerCase()));
              const old = f.stale.some((s) => s.accepted.some((a) => value.toLowerCase().includes(a.toLowerCase())));
              marks.push(cur && old ? "both" : cur ? "correct" : old ? "stale" : "other");
            } else marks.push(value === f.value ? "correct" : stale.includes(value) ? "stale" : "other");
          }
          console.log(`   ${split} final ${field}: ${GRADES.map((g) => `${g} ${marks.filter((m) => m === g).length}`).join(", ")}`);
        }
      }
    }
  }

  console.log("\nTIMINGS (vary from run to run; milliseconds; probes after the first in a block reuse Ollama's prompt cache)");
  if (growth.length) {
    for (const t of [1, 5, 10, 15, 20]) {
      console.log(`   1c turn ${String(t).padStart(2)}: prompt evaluation ${spread(growth.filter((r) => r.turn === t).map((r) => r.prompt_eval_duration / 1e6))}`);
    }
  }
  for (const block of [...STRATEGIES, "2_full_small"]) {
    const rs = by(block);
    if (rs.length) console.log(`   ${pad(block, 17)} prompt evaluation ${spread(rs.filter((r) => r.prompt_eval_duration).map((r) => r.prompt_eval_duration / 1e6))}`);
  }
  for (const block of ["summaries", "states"]) {
    const rs = by(block);
    if (!rs.length) continue;
    const per = {};
    for (const r of rs) per[r.conversation] = (per[r.conversation] ?? 0) + r.total_duration / 1e6;
    console.log(`   ${block} maintenance per conversation: ${spread(Object.values(per))}`);
  }
}

main();
