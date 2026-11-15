// The calls to the local Ollama server. Same behaviour as ../python/ollama.py.
import "dotenv/config";
import { execFileSync } from "node:child_process";
import http from "node:http";
import { setTimeout as sleep } from "node:timers/promises";

export const baseUrl = () => process.env.OLLAMA_BASE_URL || "http://localhost:11434";
export const chatModel = () => process.env.OLLAMA_CHAT_MODEL || "llama3.2:3b";

export function post(path, body) {
  return new Promise((resolve, reject) => {
    const req = http.request(new URL(path, baseUrl()), { method: "POST", headers: { "Content-Type": "application/json" } });
    req.on("error", reject);
    req.on("response", (res) => {
      const parts = [];
      res.on("data", (d) => parts.push(d));
      res.on("end", () => {
        const text = Buffer.concat(parts).toString("utf8");
        if (res.statusCode !== 200) reject(new Error(`${path} failed: HTTP ${res.statusCode} ${text.slice(0, 200)}`));
        else resolve(JSON.parse(text));
      });
    });
    req.end(JSON.stringify(body));
  });
}

export const unload = (model) => post("/api/generate", { model, keep_alive: 0 });

// One non-streaming chat call. fmt, when given, is a JSON schema the reply must follow.
export function chat(messages, options, fmt = null) {
  const body = { model: chatModel(), messages, stream: false, options };
  if (fmt !== null) body.format = fmt;
  return post("/api/chat", body);
}

// Processes other than ours with an open connection to Ollama's port (macOS/Linux, needs lsof).
export function otherConnections(ownPids) {
  const port = new URL(baseUrl()).port || "80";
  let out = "";
  try {
    out = execFileSync("lsof", ["-nP", `-iTCP:${port}`, "-sTCP:ESTABLISHED", "-Fpc"], { encoding: "utf8" });
  } catch (error) {
    out = error.stdout || ""; // lsof exits with 1 when nothing matches
  }
  const found = new Set();
  let pid = null;
  for (const line of out.split("\n")) {
    if (line.startsWith("p")) pid = Number(line.slice(1));
    else if (line.startsWith("c")) {
      const command = line.slice(1);
      if (!ownPids.has(pid) && command !== "ollama") found.add(`${command} (${pid})`);
    }
  }
  return [...found].sort();
}

// Return once no other program has been connected to Ollama for quietS seconds. With quietS 0, return at once
// if nobody else is connected; if someone is, wait until they have been gone for 60 seconds (as in Article #19).
export async function waitForQuiet(ownPids, quietS = 60) {
  let quietSince = Date.now();
  let waiting = false;
  for (;;) {
    const others = otherConnections(ownPids);
    if (others.length) {
      if (!waiting) console.log(`   waiting: another program is connected to Ollama: ${others.join(", ")}`);
      quietSince = Date.now();
      waiting = true;
      quietS = 60;
    } else if ((Date.now() - quietSince) / 1000 >= quietS) return;
    await sleep(quietS ? 5000 : 0);
  }
}
