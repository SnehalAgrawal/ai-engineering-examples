// A proxy between the client and the app server, for experiment 2. Same behaviour as ../python/proxy.py,
// where the three modes (pass-through, buffer-all, buffer-4096) are described. Every write to the client is
// counted, including the final partial one.
//
//   node proxy.js --port 8721 --upstream 8720 --runs ../runs/javascript/main
import { appendFileSync } from "node:fs";
import http from "node:http";
import { join } from "node:path";

import { nowMs } from "./common.js";

const BLOCK = 4096;

function main() {
  const args = process.argv.slice(2);
  const option = (name) => args[args.indexOf(name) + 1];
  const upstreamPort = Number(option("--upstream"));
  const runs = option("--runs");
  const server = http.createServer((req, res) => {
    if (req.method === "GET") {
      res.writeHead(req.url === "/health" ? 200 : 404).end();
      return;
    }
    const mode = req.headers["x-proxy-mode"];
    const record = { id: req.headers["x-request-id"], mode, writes: 0, bytes: 0, t_first_write: null };
    const parts = [];
    req.on("data", (d) => parts.push(d));
    req.on("end", () => {
      const upstream = http.request({
        host: "127.0.0.1", port: upstreamPort, path: req.url, method: "POST", headers: { "Content-Type": "application/json" },
      });
      upstream.end(Buffer.concat(parts));
      upstream.on("response", (response) => {
        res.writeHead(response.statusCode, { "Content-Type": response.headers["content-type"], Connection: "close" });
        res.flushHeaders();
        const send = (data) => {
          if (record.t_first_write === null) record.t_first_write = nowMs();
          res.write(data);
          record.writes += 1;
          record.bytes += data.length;
        };
        let held = Buffer.alloc(0);
        response.on("data", (data) => {
          if (mode === "pass-through") send(data);
          else {
            held = Buffer.concat([held, data]);
            while (mode === "buffer-4096" && held.length >= BLOCK) {
              send(held.subarray(0, BLOCK));
              held = held.subarray(BLOCK);
            }
          }
        });
        response.on("end", () => {
          if (held.length) send(held);
          res.end();
          appendFileSync(join(runs, "proxy.jsonl"), `${JSON.stringify(record)}\n`);
        });
      });
    });
  });
  server.listen(Number(option("--port")), "127.0.0.1");
}

main();
