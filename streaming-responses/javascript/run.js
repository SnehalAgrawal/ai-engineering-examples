// Runs experiments 1 to 4 and saves every request. Same behaviour as ../python/run.py, where the steps are
// described: one 60-second wait for a quiet Ollama before the first call, the ten blocks in order, each
// starting with the chat model unloaded and the warm-up request, and requests one at a time.
//
//   node run.js                          # everything, into runs/javascript/main
//   node run.js --out smoke --emails e01,e02 --experiments 1,4
import { spawn } from "node:child_process";
import { appendFileSync, existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import http from "node:http";
import { join, relative } from "node:path";
import { setTimeout as sleep } from "node:timers/promises";

import * as client from "./client.js";
import { HERE, load, questions, RUNS } from "./common.js";
import * as ollama from "./ollama.js";
import * as ollamaLog from "./ollama_log.js";
import { Index } from "./retrieval.js";

const QUIET_S = 60;
const SETTLE_S = 1.0;

function blocks(emails) {
  const first20 = emails.slice(0, 20);
  const first10 = emails.slice(0, 10);
  return [
    ...["non-streaming", "streaming"].map((m) => ({ experiment: "1", mode: m, emails, body: { stream: m === "streaming" } })),
    ...["pass-through", "buffer-all", "buffer-4096"].map((m) => ({ experiment: "2", mode: m, emails: first20, body: { stream: true }, proxy: m })),
    ...["ignore", "cancel"].map((m) => ({ experiment: "3", mode: m, emails: first10, body: { stream: true, on_disconnect: m }, closeAfter: 20 })),
    ...["check-whole", "stream-then-check", "sentence-gate"].map((m) => ({ experiment: "4", mode: m, emails, body: { stream: true, policy: m } })),
  ];
}

// Return once no other program has been connected to Ollama for quietS seconds (see ../python/run.py).
async function waitForQuiet(own, quietS = QUIET_S) {
  let quietSince = Date.now();
  let waiting = false;
  let required = quietS;
  for (;;) {
    const others = ollama.otherConnections(own);
    if (others.length) {
      if (!waiting) console.log(`   waiting: another program is connected to Ollama: ${others.join(", ")}`);
      quietSince = Date.now();
      waiting = true;
      required = QUIET_S;
    } else if ((Date.now() - quietSince) / 1000 >= required) return;
    await sleep(required ? 5000 : 0);
  }
}

const start = (script, ...args) => spawn(process.execPath, [join(HERE, script), ...args], { cwd: HERE, stdio: "inherit" });

async function waitHealthy(port) {
  for (let i = 0; i < 100; i++) {
    const ok = await new Promise((resolve) => {
      http.get({ host: "127.0.0.1", port, path: "/health", timeout: 1000 }, (res) => {
        res.resume();
        resolve(res.statusCode === 200);
      }).on("error", () => resolve(false));
    });
    if (ok) return;
    await sleep(100);
  }
  throw new Error(`nothing answers on port ${port}`);
}

// The record with this id in a JSON-lines file, waiting for it to be written.
async function find(path, requestId, timeoutS = 900) {
  const deadline = Date.now() + timeoutS * 1000;
  while (Date.now() < deadline) {
    if (existsSync(path)) {
      for (const line of readFileSync(path, "utf8").split("\n").filter(Boolean)) {
        const record = JSON.parse(line);
        if (record.id === requestId) return record;
      }
    }
    await sleep(50);
  }
  throw new Error(`no record ${requestId} in ${path}`);
}

async function main() {
  const args = process.argv.slice(2);
  const option = (name, fallback) => (args.includes(name) ? args[args.indexOf(name) + 1] : fallback);
  const data = load();
  const { settings } = data;
  const emails = option("--emails", null)?.split(",") ?? Object.keys(data.emails).sort();
  const wanted = option("--experiments", "1,2,3,4").split(",");
  const out = join(RUNS, option("--out", "main"));
  if (existsSync(out)) rmSync(out, { recursive: true });
  mkdirSync(join(out, "texts"), { recursive: true });
  mkdirSync(join(out, "disconnect-log"));

  await waitForQuiet(new Set([process.pid])); // even the embedding calls would slow someone else's measured run
  const index = await new Index().init(settings, data.documents);
  const excerpts = {};
  for (const eid of Object.keys(data.emails).sort()) excerpts[eid] = await index.excerpts(questions(data, eid));
  writeFileSync(join(out, "excerpts.json"), `${JSON.stringify(excerpts, null, 1)}\n`);
  const ports = settings.path.ports.javascript;
  const app = start("app_server.js", "--port", String(ports.app), "--runs", out);
  const proxy = start("proxy.js", "--port", String(ports.proxy), "--upstream", String(ports.app), "--runs", out);
  const own = new Set([process.pid, app.pid, proxy.pid]);
  try {
    await waitHealthy(ports.app);
    await waitHealthy(ports.proxy);
    await ollama.unload(ollama.embeddingModel());
    const warmUp = [{ role: "user", content: data.prompts.warm_up }];
    for (const block of blocks(emails)) {
      if (!wanted.includes(block.experiment)) continue;
      console.log(`experiment ${block.experiment}, ${block.mode}: ${block.emails.length} emails`);
      await waitForQuiet(own, 0); // the full wait came before the excerpts; here only if someone has connected since
      await ollama.unload(ollama.chatModel());
      await ollama.chat(warmUp, { ...settings.model.options, num_predict: 5 });
      for (const eid of block.emails) {
        const requestId = `${block.experiment}|${block.mode}|${eid}`;
        const body = { id: requestId, email: eid, ...block.body };
        const port = block.proxy ? ports.proxy : ports.app;
        const seen = ollama.otherConnections(own);
        const logStart = block.experiment === "3" ? ollamaLog.position() : null;
        const record = await client.request(port, body, block.proxy ?? null, block.closeAfter ?? null);
        const server = await find(join(out, "server.jsonl"), requestId);
        const line = { experiment: block.experiment, mode: block.mode, email: eid, client: record };
        if (block.proxy) line.proxy = await find(join(out, "proxy.jsonl"), requestId);
        if (logStart !== null) {
          await sleep(SETTLE_S * 1000);
          const text = ollamaLog.linesSince(logStart);
          writeFileSync(join(out, "disconnect-log", `${eid}-${block.mode}.txt`), text);
          line.log = ollamaLog.readTask(text);
        }
        const { generated } = server;
        delete server.generated;
        writeFileSync(join(out, "texts", `${server.generated_sha256}.txt`), generated);
        line.server = server;
        line.overlap = [...new Set([...seen, ...ollama.otherConnections(own)])].sort();
        appendFileSync(join(out, "requests.jsonl"), `${JSON.stringify(line)}\n`);
      }
    }
  } finally {
    app.kill();
    proxy.kill();
    if (!ollama.otherConnections(own).length) {
      await ollama.unload(ollama.chatModel());
      await ollama.unload(ollama.embeddingModel());
    }
  }
  console.log(`saved ${relative(join(HERE, ".."), out)}`);
}

await main();
