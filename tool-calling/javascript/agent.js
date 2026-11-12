// The tool-calling loop. Same behaviour as ../python/agent.py:
//   1. Send the conversation and the tool definitions to the model.
//   2. If the reply contains tool calls, run each one through Session (parse, validate,
//      apply the business rules, execute) and append the results to the conversation.
//   3. Repeat until the model replies without tool calls, or MAX_STEPS is reached.
import { chat, toolMessage } from "./llm.js";
import { pyDumps } from "./pyjson.js";
import { Session, TOOLS } from "./tools.js";

export const MAX_STEPS = 5; // model calls per conversation; a loop that never finishes stops here
export const MAX_TOKENS = 1000;

export async function runConversation(systemPrompt, question, seed, onEvent = null) {
  const messages = [{ role: "system", content: systemPrompt }, { role: "user", content: question }];
  const session = new Session();
  const calls = [], finishReasons = [], fingerprints = [];
  let tokens = 0, error = null, final = null;
  for (let step = 0; step < MAX_STEPS; step++) {
    const response = await chat(messages, TOOLS, seed, MAX_TOKENS);
    tokens += response.tokens;
    finishReasons.push(response.finishReason);
    fingerprints.push(response.fingerprint);
    if (onEvent) onEvent("model", response);
    if (response.error) {
      error = response.error;
      break;
    }
    if (!response.toolCalls.length) {
      final = response.content;
      break;
    }
    messages.push(response.message);
    for (const call of response.toolCalls) {
      const outcome = session.run(call.name, call.arguments);
      calls.push(outcome);
      if (onEvent) onEvent("tool", outcome);
      messages.push(toolMessage(call, pyDumps(outcome.result)));
    }
  }
  return {
    final, calls, steps: finishReasons.length, step_limit: final === null && error === null,
    finish_reasons: finishReasons, tokens, fingerprints, error,
  };
}
