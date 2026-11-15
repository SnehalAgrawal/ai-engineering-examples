// The calls to the local Ollama server. Same behaviour as ../python/ollama.py: streaming responses are read
// with node:http, chunk by chunk as they arrive, one JSON object per line.
import "dotenv/config";
import { execFileSync } from "node:child_process";
import http from "node:http";

import { nowMs } from "./common.js";

export const baseUrl = () => process.env.OLLAMA_BASE_URL || "http://localhost:11434";
export const chatModel = () => process.env.OLLAMA_CHAT_MODEL || "llama3.2:3b";
export const embeddingModel = () => process.env.OLLAMA_EMBEDDING_MODEL || "nomic-embed-text";

function open(path, body) {
  const url = new URL(path, baseUrl());
  const req = http.request(url, { method: "POST", headers: { "Content-Type": "application/json" } });
  req.end(JSON.stringify(body));
  return req;
}

export function post(path, body) {
  return new Promise((resolve, reject) => {
    const req = open(path, body);
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
  });
}

export const embed = async (texts) => (await post("/api/embed", { model: embeddingModel(), input: texts, truncate: false })).embeddings;
export const unload = (model) => post("/api/generate", { model, keep_alive: 0 });

// One non-streaming chat call: the whole reply arrives at once.
export const chat = (messages, options) => post("/api/chat", { model: chatModel(), messages, stream: false, options });

// A streaming chat call. Iterate to get [arrival time in ms, chunk] for each line Ollama sends.
export class ChatStream {
  constructor(messages, options) {
    this.req = open("/api/chat", { model: chatModel(), messages, stream: true, options });
    this.response = new Promise((resolve, reject) => {
      this.req.on("response", resolve);
      this.req.on("error", reject);
    });
  }

  async *[Symbol.asyncIterator]() {
    const res = await this.response;
    if (res.statusCode !== 200) throw new Error(`/api/chat failed: HTTP ${res.statusCode}`);
    const decoder = new TextDecoder("utf-8");
    let pending = "";
    try {
      for await (const data of res) {
        const arrived = nowMs();
        pending += decoder.decode(data, { stream: true });
        const lines = pending.split("\n");
        pending = lines.pop();
        for (const line of lines) if (line.trim()) yield [arrived, JSON.parse(line)];
      }
    } catch (error) {
      if (!this.closed) throw error;
    }
  }

  // Close the connection to Ollama, whether or not the reply has finished.
  close() {
    this.closed = true;
    this.req.destroy();
  }
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
