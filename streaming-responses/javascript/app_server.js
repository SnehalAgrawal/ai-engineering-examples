// The app server: it drafts a reply for one email and passes it to the client. Same behaviour as
// ../python/app_server.py, where the request and the events are described. Each event is written as soon as it
// is ready; a write counts as failed when Node reports an error for it (the client has gone).
//
//   node app_server.js --port 8720 --runs ../runs/javascript/main
import { createHash } from "node:crypto";
import { appendFileSync, readFileSync } from "node:fs";
import http from "node:http";
import { join } from "node:path";

import * as check from "./check.js";
import { draftMessages, load, nowMs, questions } from "./common.js";
import * as ollama from "./ollama.js";

const STATS = ["prompt_eval_count", "eval_count", "prompt_eval_duration", "eval_duration", "load_duration", "total_duration"];
const pick = (obj, keys) => Object.fromEntries(keys.map((k) => [k, obj[k] ?? null]));

class Reply {
  constructor(app, res, body, tReceived) {
    Object.assign(this, { res, policy: body.policy || "none", onDisconnect: body.on_disconnect || "ignore" });
    const eid = body.email;
    const excerpts = app.excerpts[eid];
    this.messages = draftMessages(app.data.prompts, app.data.emails[eid], questions(app.data, eid), excerpts);
    this.references = [...excerpts.map((e) => e.text), app.data.emails[eid]];
    this.options = app.data.settings.model.options;
    this.record = {
      id: body.id, email: eid, stream: body.stream, policy: this.policy, on_disconnect: this.onDisconnect,
      t_received: tReceived, t_model_first: null, t_model_done: null, t_write_failed: null, events_written: 0,
      upstream_events_after_disconnect: 0, cancelled: false,
    };
    this.generated = "";
    this.gone = false;
    this.sentences = new check.Sentences();
    this.withheld = false;
  }

  // ---- writing to the client -------------------------------------------------------------------------------

  async write(name, data) {
    if (this.gone) return;
    const payload = `event: ${name}\ndata: ${JSON.stringify(data)}\n\n`;
    const error = this.res.destroyed ? new Error("destroyed")
      : await new Promise((resolve) => this.res.write(payload, (err) => resolve(err)));
    if (error) {
      this.gone = true;
      this.record.t_write_failed = nowMs();
    } else this.record.events_written += 1;
  }

  text(text) {
    return this.write("text", { text, sent_at: Math.trunc(nowMs()) });
  }

  // ---- the policies ----------------------------------------------------------------------------------------

  async onChunk(content) {
    if (this.policy === "none" || this.policy === "stream-then-check") await this.text(content);
    else if (this.policy === "sentence-gate") for (const sentence of this.sentences.feed(content)) await this.gate(sentence);
    // check-whole: nothing is sent until the reply is complete
  }

  async gate(sentence) {
    if (this.withheld) {
      this.record.chars_held_back += [...sentence].length; // code points, as Python's len()
      return;
    }
    const found = check.flagged(sentence, this.references);
    if (found.length) {
      this.withheld = true;
      this.record.chars_held_back += [...sentence].length; // code points, as Python's len()
      this.record.flagged = found;
      await this.write("withheld", { flagged: found, sentence });
    } else {
      this.record.sentences_sent += sentence.trim() ? 1 : 0;
      await this.text(sentence);
    }
  }

  // After Ollama's last chunk: apply the policy's final step.
  async finish() {
    if (this.policy === "none") return;
    if (this.policy === "sentence-gate") {
      for (const sentence of this.sentences.finish()) await this.gate(sentence);
      this.record.outcome = this.withheld ? "withheld" : "passed";
      return;
    }
    const found = check.flagged(this.generated, this.references);
    this.record.flagged = found;
    if (this.policy === "check-whole") {
      this.record.outcome = found.length ? "withheld" : "passed";
      if (found.length) await this.write("withheld", { flagged: found });
      else await this.text(this.generated);
    } else {
      this.record.outcome = found.length ? "retracted" : "passed";
      await this.write(found.length ? "retracted" : "passed", { flagged: found });
    }
  }

  // ---- the two kinds of response ---------------------------------------------------------------------------

  async run() {
    if (this.policy === "sentence-gate") Object.assign(this.record, { sentences_sent: 0, chars_held_back: 0 });
    if (this.record.stream) await this.streaming();
    else await this.whole();
    this.record.generated = this.generated;
    this.record.generated_sha256 = createHash("sha256").update(this.generated, "utf8").digest("hex");
    return this.record;
  }

  async whole() {
    const reply = await ollama.chat(this.messages, this.options);
    this.record.t_model_done = nowMs();
    this.generated = reply.message.content;
    this.record.ollama = pick(reply, STATS);
    const body = JSON.stringify({ text: this.generated, server: this.serverTimes() });
    this.res.writeHead(200, { "Content-Type": "application/json", "Content-Length": Buffer.byteLength(body), Connection: "close" });
    this.res.end(body);
  }

  async streaming() {
    this.res.writeHead(200, { "Content-Type": "text/event-stream", "Cache-Control": "no-cache", Connection: "close" });
    this.res.flushHeaders();
    const stream = new ollama.ChatStream(this.messages, this.options);
    try {
      for await (const [arrived, chunk] of stream) {
        const content = chunk.message?.content || "";
        if (content) {
          if (this.record.t_model_first === null) this.record.t_model_first = arrived;
          this.generated += content;
          if (this.gone) this.record.upstream_events_after_disconnect += 1;
          else await this.onChunk(content);
          if (this.gone && this.onDisconnect === "cancel") {
            this.record.cancelled = true;
            return;
          }
        }
        if (chunk.done) {
          this.record.t_model_done = arrived;
          this.record.ollama = pick(chunk, STATS);
        }
      }
      await this.finish();
      await this.write("done", { server: this.serverTimes() });
    } finally {
      stream.close();
      if (!this.res.destroyed) this.res.end();
    }
  }

  serverTimes() {
    const keys = ["t_received", "t_model_first", "t_model_done", "outcome", "flagged", "sentences_sent", "chars_held_back"];
    return Object.fromEntries(keys.filter((k) => k in this.record).map((k) => [k, this.record[k]]));
  }
}

function main() {
  const args = process.argv.slice(2);
  const option = (name) => args[args.indexOf(name) + 1];
  const runs = option("--runs");
  const app = { data: load(), excerpts: JSON.parse(readFileSync(join(runs, "excerpts.json"), "utf8")) };
  const server = http.createServer((req, res) => {
    const tReceived = nowMs();
    if (req.method === "GET") {
      res.writeHead(req.url === "/health" ? 200 : 404).end();
      return;
    }
    const parts = [];
    req.on("data", (d) => parts.push(d));
    req.on("end", async () => {
      const body = JSON.parse(Buffer.concat(parts).toString("utf8"));
      const record = await new Reply(app, res, body, tReceived).run();
      appendFileSync(join(runs, "server.jsonl"), `${JSON.stringify(record)}\n`);
    });
  });
  server.listen(Number(option("--port")), "127.0.0.1");
}

main();
