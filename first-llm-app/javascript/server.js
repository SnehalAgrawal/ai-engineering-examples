// The application as a small HTTP service, using only Node's standard library.
// Same behaviour as ../python/server.py.
//
//   node server.js
//   curl -s localhost:8000/ask -d '{"question": "How much is the Pro plan?"}'
//
// Every request is logged as one JSON line in app.log.
import { appendFileSync } from "node:fs";
import { createServer } from "node:http";
import { handle } from "./app.js";

const PORT = 8000;

function send(res, status, body) {
  const payload = JSON.stringify(body);
  res.writeHead(status, { "Content-Type": "application/json", "Content-Length": Buffer.byteLength(payload) });
  res.end(payload);
}

createServer((req, res) => {
  if (req.method !== "POST" || req.url !== "/ask") return send(res, 404, { error: 'Not found. POST /ask with {"question": "..."}' });
  let raw = "";
  req.on("data", (chunk) => (raw += chunk));
  req.on("end", async () => {
    let question;
    try {
      question = (JSON.parse(raw || "{}").question) ?? "";
      if (typeof question !== "string") throw new Error();
    } catch {
      return send(res, 400, { error: 'Send JSON like {"question": "..."}.' });
    }
    const result = await handle(question);
    appendFileSync("app.log", JSON.stringify(result.log) + "\n");
    send(res, result.status, { answer: result.message, sources: result.sources, request_id: result.log.request_id });
  });
}).listen(PORT, "localhost", () => console.log(`Listening on http://localhost:${PORT}  (POST /ask)`));
