// The client: it sends one request and records when each piece of the reply arrives. Same behaviour as
// ../python/client.py: raw bytes are decoded incrementally as UTF-8 and server-sent events are framed on the
// blank line that ends each event, so one read may hold part of an event or several.
import http from "node:http";

import { contains } from "./check.js";
import { nowMs } from "./common.js";

export function parseEvent(raw) {
  let name = "message";
  let data = "";
  for (const line of raw.split("\n")) {
    if (line.startsWith("event: ")) name = line.slice("event: ".length);
    else if (line.startsWith("data: ")) data += line.slice("data: ".length);
  }
  return [name, data ? JSON.parse(data) : {}];
}

// Send one request. closeAfter: close the connection after this many text events (experiment 3).
export function request(port, body, proxyMode = null, closeAfter = null) {
  return new Promise((resolve, reject) => {
    const headers = { "Content-Type": "application/json", "X-Request-Id": body.id };
    if (proxyMode) headers["X-Proxy-Mode"] = proxyMode;
    const record = {
      t_start: null, t_first_text: null, t_last_text: null, t_done: null, t_closed: null, t_retracted: null,
      events: {}, text_events: 0, visible_text: "", outcome: null, flagged: null, server: null,
    };
    const payload = JSON.stringify(body);
    record.t_start = nowMs();
    const req = http.request({ host: "127.0.0.1", port, path: "/reply", method: "POST", headers });
    req.on("error", (error) => (record.t_closed === null ? reject(error) : null));
    req.end(payload);
    req.on("response", (res) => {
      if (res.headers["content-type"] === "application/json") {
        const parts = [];
        res.on("data", (d) => parts.push(d));
        res.on("end", () => {
          const reply = JSON.parse(Buffer.concat(parts).toString("utf8"));
          const t = nowMs();
          Object.assign(record, {
            t_first_text: reply.text.trim() ? t : null, t_last_text: t, t_done: t, visible_text: reply.text,
            server: reply.server, events: { body: 1 },
          });
          resolve(record);
        });
        return;
      }
      const decoder = new TextDecoder("utf-8");
      let pending = "";
      let shown = "";
      let t = null;
      const timeline = [];
      let closed = false;
      const finish = () => {
        record.t_done = t;
        record.visible_text = shown;
        if (record.outcome === null && record.server) record.outcome = record.server.outcome ?? null;
        resolve(record);
      };
      res.on("data", (data) => {
        if (closed) return;
        t = nowMs();
        pending += decoder.decode(data, { stream: true });
        while (pending.includes("\n\n") && !closed) {
          const cut = pending.indexOf("\n\n");
          const raw = pending.slice(0, cut);
          pending = pending.slice(cut + 2);
          const [name, event] = parseEvent(raw);
          record.events[name] = (record.events[name] || 0) + 1;
          if (name === "text") {
            shown += event.text;
            record.text_events += 1;
            timeline.push([t, shown.length]);
            if (record.t_first_text === null && event.text.trim()) record.t_first_text = t;
            record.t_last_text = t;
            if (closeAfter && record.text_events >= closeAfter) {
              record.t_closed = nowMs();
              closed = true;
              res.destroy(); // the user leaves: the connection closes
              finish();
            }
          } else if (["withheld", "retracted", "passed"].includes(name)) {
            record.outcome = name;
            record.flagged = event.flagged ?? null;
            if (name === "retracted") {
              // the client removes the reply it had shown; first, when was the flagged value first visible?
              record.t_retracted = t;
              const first = event.flagged[0];
              const seen = timeline.find(([, n]) => contains(shown.slice(0, n), first));
              record.t_flagged_visible = seen ? seen[0] : null;
              shown = "";
            }
          } else if (name === "done") record.server = event.server;
        }
      });
      res.on("end", () => {
        if (closed) return;
        t = nowMs();
        pending += decoder.decode();
        finish();
      });
    });
  });
}
