// Runs experiments 1 to 3 and saves every model call. Same behaviour and records as ../python/run.py, where the
// blocks, the waits, and the records are described.
//
//   node run.js                                        # everything, into runs/javascript/main
//   node run.js --smoke --out smoke --conversations c01 --blocks 1a_no_history,summaries,3_summary_recent
import { createHash } from "node:crypto";
import { appendFileSync, existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { join, relative } from "node:path";
import { setTimeout as sleep } from "node:timers/promises";

import * as chatTemplate from "./chat_template.js";
import * as context from "./context.js";
import { DATA, HERE, RUNS, appears, dumps, grade, load, pyJson } from "./common.js";
import * as ollama from "./ollama.js";
import * as ollamaLog from "./ollama_log.js";

const SETTLE_S = 1.0; // time for Ollama's log to be written before it is read

const sha = (text) => createHash("sha256").update(text, "utf8").digest("hex");
const forms = (fact) => [fact.accepted, fact.stale.flatMap((s) => s.accepted)];

// For each fact, whether the text holds its current value and a stale value (settings: grading.in_context).
function trace(text, conversation) {
  return Object.fromEntries(conversation.facts.map((f) => {
    const [current, stale] = forms(f);
    return [f.id, { current: appears(text, current), stale: appears(text, stale) }];
  }));
}

// Everything sent before the probe: the system message (with any summary or record) and the kept turns.
const contextText = (messages) => messages.slice(0, -1).map((m) => m.content).join("\n");
const allText = (messages) => messages.map((m) => m.content).join("\n");

// When Ollama evaluated fewer tokens than the app sent, find the ending of the conversation whose count equals
// Ollama's, and check the fact against what the model saw (see ../python/run.py).
function seenContext(record, messages, conversation, fact) {
  const endings = [];
  for (let k = 1; k < messages.length - 1; k++) {
    if (chatTemplate.count([messages[0], ...messages.slice(k)]) === record.prompt_eval_count) endings.push(k);
  }
  record.kept_from_message = endings.length === 1 ? endings[0] : null;
  record.ending_matches = endings.length;
  if (endings.length === 1) {
    const k = endings[0];
    record.first_kept_turn = Math.floor((k + 1) / 2);
    record.in_context_seen = trace(contextText([messages[0], ...messages.slice(k)]), conversation)[fact];
  } else {
    record.first_kept_turn = null;
    record.in_context_seen = null;
  }
}

class Runner {
  constructor(out, settings) {
    Object.assign(this, { out, settings, own: new Set([process.pid]), options: settings.model.options });
  }

  async warmUp(numCtx) {
    await ollama.waitForQuiet(this.own, 0);
    await ollama.unload(ollama.chatModel());
    await ollama.chat([{ role: "user", content: "Reply with the word ready." }], { ...this.options, num_ctx: numCtx, num_predict: 5 });
  }

  async call(record, messages, numCtx, numPredict, fmt = null, readLog = false) {
    record = { ...record, num_ctx: numCtx, app_tokens: chatTemplate.count(messages) };
    const seen = ollama.otherConnections(this.own);
    const start = readLog ? ollamaLog.position() : null;
    const t0 = Date.now();
    let reply = null;
    try {
      reply = await ollama.chat(messages, { ...this.options, num_ctx: numCtx, num_predict: numPredict }, fmt);
      record.error = null;
    } catch (error) {
      record.error = error.message;
    }
    record.wall_ms = Math.round((Date.now() - t0) * 10) / 10;
    if (reply) {
      for (const k of ["prompt_eval_count", "prompt_eval_duration", "eval_count", "eval_duration", "load_duration", "total_duration"]) record[k] = reply[k] ?? null;
      const output = reply.message.content;
      record.output_sha256 = sha(output);
      writeFileSync(join(this.out, "texts", `${record.output_sha256}.txt`), output);
      record.output = output;
    }
    if (readLog) {
      await sleep(SETTLE_S * 1000);
      const text = ollamaLog.linesSince(start);
      writeFileSync(join(this.out, "ollama-log", `${record.block}-${record.conversation}-${record.probe ?? record.turn}.txt`), text);
      record.log = ollamaLog.readTask(text);
    }
    record.overlap = [...new Set([...seen, ...ollama.otherConnections(this.own)])].sort();
    return record;
  }

  // One line per model call; the output itself is in texts/, under its SHA-256.
  save(record) {
    const { output: _output, ...rest } = record;
    appendFileSync(join(this.out, "requests.jsonl"), `${dumps(rest)}\n`);
  }
}

async function main() {
  const args = process.argv.slice(2);
  const option = (name, fallback = null) => (args.includes(name) ? args[args.indexOf(name) + 1] : fallback);
  const smoke = args.includes("--smoke");
  const data = load();
  const { settings, prompts } = data;
  const derived = JSON.parse(readFileSync(join(DATA, "derived.json"), "utf8"));
  if (!prompts.version.endsWith("frozen") || derived.prompts_version !== prompts.version) {
    throw new Error("run.js needs the frozen prompts and the derived.json computed from them");
  }
  const convs = data.conversations;
  const ids = option("--conversations") ? option("--conversations").split(",") : Object.keys(convs).sort();
  if (smoke && ids.some((c) => convs[c].split !== "dev")) throw new Error("--smoke runs on dev conversations only");
  const growthSplit = smoke ? "dev" : "test";
  const small = settings.context.small_window;
  const large = settings.context.large_window;
  const limit = small.prompt_limit;
  const n = derived.last_n;
  const m = settings.model;
  const out = join(RUNS, option("--out", "main"));
  if (existsSync(out)) rmSync(out, { recursive: true });
  for (const sub of ["texts", "ollama-log", "summaries", "state"]) mkdirSync(join(out, sub), { recursive: true });
  const run = new Runner(out, settings);
  await ollama.waitForQuiet(run.own);
  const summaries = {};
  const states = {};

  async function probes(block, experiment, numCtx, build, readLog = false) {
    await run.warmUp(numCtx);
    for (const cid of ids) {
      const c = convs[cid];
      const facts = Object.fromEntries(c.facts.map((f) => [f.id, f]));
      for (const p of c.probes) {
        const messages = build(c, p.question);
        const record = { block, experiment, conversation: cid, split: c.split, probe: p.id, fact: p.fact };
        if (numCtx === small.num_ctx) record.over_limit = chatTemplate.count(messages) > limit;
        record.in_context = trace(contextText(messages), c)[p.fact];
        const r = await run.call(record, messages, numCtx, m.answer.num_predict, null, readLog);
        if (readLog && r.prompt_eval_count !== null && r.prompt_eval_count !== undefined && r.prompt_eval_count < r.app_tokens) {
          seenContext(r, messages, c, p.fact);
        }
        r.grade = r.output !== undefined ? grade(r.output, facts[p.fact]) : null;
        run.save(r);
      }
    }
  }

  async function maintainSummaries() {
    await run.warmUp(m.summary.num_ctx);
    for (const cid of ids) {
      const c = convs[cid];
      let summary = null;
      const lines = [];
      for (const start of [0, 4, 8, 12]) {
        const messages = context.summaryUpdate(prompts, summary, c.turns.slice(start, start + 4));
        if (chatTemplate.count(messages) > m.summary.num_ctx - m.summary.num_predict) throw new Error(`${cid}: summary request over its limit; run stopped`);
        const r = await run.call({ block: "summaries", experiment: "3", conversation: cid, split: c.split, turn: start + 4 },
          messages, m.summary.num_ctx, m.summary.num_predict);
        run.save(r);
        const next = r.output.trim();
        lines.push(dumps({ covers: [1, start + 4], cut_off: r.eval_count >= m.summary.num_predict,
          input: trace(allText(messages), c), output: trace(next, c), summary: next }));
        summary = next;
      }
      writeFileSync(join(out, "summaries", `${cid}.jsonl`), `${lines.join("\n")}\n`);
      summaries[cid] = summary;
    }
  }

  async function maintainStates() {
    await run.warmUp(m.extraction.num_ctx);
    const schema = settings.state_schema.json_schema;
    for (const cid of ids) {
      const c = convs[cid];
      let state = { ...settings.state_schema.initial };
      const failed = [];
      const lines = [];
      for (const [i, turn] of c.turns.entries()) {
        const messages = context.stateUpdate(prompts, state, turn);
        if (chatTemplate.count(messages) > m.extraction.num_ctx - m.extraction.num_predict) throw new Error(`${cid}: extraction request over its limit; run stopped`);
        const r = await run.call({ block: "states", experiment: "3", conversation: cid, split: c.split, turn: i + 1 },
          messages, m.extraction.num_ctx, m.extraction.num_predict, schema);
        run.save(r);
        let error = null;
        let next;
        try {
          next = JSON.parse(r.output);
        } catch (e) {
          error = e.message;
          next = state;
          failed.push(i + 1);
        }
        lines.push(dumps({ turn: i + 1, parse_error: error, input: trace(allText(messages), c), output: trace(pyJson(next, true), c), state: next }));
        state = next;
      }
      writeFileSync(join(out, "state", `${cid}.jsonl`), `${lines.join("\n")}\n`);
      states[cid] = { ...state, _invalid: failed.length > 0, _failed_turns: failed };
    }
  }

  async function growth() {
    await run.warmUp(large.num_ctx);
    for (const cid of ids.filter((c) => convs[c].split === growthSplit)) {
      const c = convs[cid];
      for (let t = 1; t <= 20; t++) {
        const messages = [context.system(prompts), ...context.turnMessages(c.turns.slice(0, t - 1)), { role: "user", content: c.turns[t - 1].user }];
        run.save(await run.call({ block: "1c_growth", experiment: "1c", conversation: cid, split: c.split, turn: t },
          messages, large.num_ctx, m.growth.num_predict, null, true));
      }
    }
  }

  function loadMaintenance(kind) {
    for (const cid of ids) {
      const target = kind === "summaries" ? summaries : states;
      if (cid in target) continue;
      const rows = readFileSync(join(out, kind, `${cid}.jsonl`), "utf8").trim().split("\n").map((l) => JSON.parse(l));
      if (kind === "summaries") target[cid] = rows.at(-1).summary;
      else {
        const failed = rows.filter((r) => r.parse_error).map((r) => r.turn);
        target[cid] = { ...rows.at(-1).state, _invalid: failed.length > 0, _failed_turns: failed };
      }
    }
  }

  const stripped = (state) => Object.fromEntries(Object.entries(state).filter(([k]) => !k.startsWith("_")));
  const blocks = {
    "1a_no_history": () => probes("1a_no_history", "1a", large.num_ctx, (c, q) => context.noHistory(prompts, c, q)),
    "1b_full": () => probes("1b_full", "1b", large.num_ctx, (c, q) => context.full(prompts, c, q)),
    "1c_growth": growth,
    "2_full_small": () => probes("2_full_small", "2", small.num_ctx, (c, q) => context.full(prompts, c, q), true),
    summaries: maintainSummaries,
    states: maintainStates,
    "3_last_n": () => probes("3_last_n", "3", small.num_ctx, (c, q) => context.lastN(prompts, c, q, n)),
    "3_token_budget": () => probes("3_token_budget", "3", small.num_ctx, (c, q) => context.tokenBudget(prompts, c, q, limit)),
    "3_summary_recent": () => {
      loadMaintenance("summaries");
      return probes("3_summary_recent", "3", small.num_ctx, (c, q) => context.summaryRecent(prompts, c, q, summaries[c.id], 4));
    },
    "3_state_recent": () => {
      loadMaintenance("state");
      return probes("3_state_recent", "3", small.num_ctx, (c, q) => context.stateRecent(prompts, c, q, stripped(states[c.id]), 4));
    },
  };
  const wanted = option("--blocks") ? option("--blocks").split(",") : Object.keys(blocks);
  for (const [name, block] of Object.entries(blocks)) {
    if (!wanted.includes(name)) continue;
    console.log(`${name}: ${ids.length} conversations`);
    await block();
  }
  writeFileSync(join(out, "final_states.json"), `${JSON.stringify(states, null, 1)}\n`);
  if (!ollama.otherConnections(run.own).length) await ollama.unload(ollama.chatModel());
  console.log(`saved ${relative(join(HERE, ".."), out)}`);
}

await main();
