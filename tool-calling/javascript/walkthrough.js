// Runs one conversation and prints every step: what the model asked for, what the
// application did with it, and the final reply. Same output as ../python/walkthrough.py.
//
//   node walkthrough.js R1                    # case id from data/cases.json
//   node walkthrough.js I1 --prompt basic     # the prompt without rules
//   node walkthrough.js --question "Please refund INV-1002"
import { readFileSync } from "node:fs";
import { parseArgs } from "node:util";
import { pyRepr } from "./pyrepr.js";

const { values: args, positionals } = parseArgs({
  allowPositionals: true,
  options: { question: { type: "string" }, prompt: { type: "string", default: "contract" }, seed: { type: "string", default: "1" }, model: { type: "string" } },
});
if (args.model) process.env[(process.env.LLM_PROVIDER || "ollama") === "groq" ? "GROQ_MODEL" : "OLLAMA_CHAT_MODEL"] = args.model;

const { runConversation } = await import("./agent.js");
const { modelName, provider, reset } = await import("./llm.js");
const { pyDumps } = await import("./pyjson.js");

const dataDir = new URL("../data/", import.meta.url);
const prompts = JSON.parse(readFileSync(new URL("prompts.json", dataDir), "utf8"));
const cases = Object.fromEntries(JSON.parse(readFileSync(new URL("cases.json", dataDir), "utf8")).cases.map((c) => [c.id, c]));
const question = args.question ?? cases[positionals[0] ?? "R1"].question;

function show(kind, event) {
  if (kind === "model") {
    if (event.error) {
      console.log(`\nMODEL  error: ${event.error}`);
    } else if (event.toolCalls.length) {
      for (const call of event.toolCalls) console.log(`\nMODEL  asks to call ${call.name} with arguments ${call.arguments}`);
      if (event.content.trim()) console.log(`       (and wrote: ${pyRepr(event.content.trim())})`);
    } else {
      console.log(`\nMODEL  final reply (finish reason: ${event.finishReason}):\n${event.content.trim()}`);
    }
  } else {
    console.log(`APP    ${event.tool}: ${event.executed ? "executed" : "NOT executed"}`);
    console.log(`       result sent back: ${pyDumps(event.result)}`);
  }
}

await reset();
console.log(`Model: ${modelName()} (${provider()}) | prompt: ${args.prompt} | seed ${args.seed}`);
console.log(`\nCUSTOMER  ${question}`);
const result = await runConversation(prompts[args.prompt], question, Number(args.seed), show);
await reset();
if (result.step_limit) console.log("\n(stopped: step limit reached without a final reply)");
console.log(`\n${result.steps} model call(s), ${result.tokens.toLocaleString("en-US")} tokens`);
