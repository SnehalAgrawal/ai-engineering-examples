// What each strategy sends to the model, and the calls that maintain a summary or a case record. Same as
// ../python/context.py. Every function returns the messages of one request.
import * as chatTemplate from "./chat_template.js";
import { pyJson } from "./common.js";

// Replace each {name} in the template in one pass, so text inserted from a conversation is never itself
// treated as a placeholder.
export const fill = (template, values) => template.replace(/\{(\w+)\}/g, (m, name) => (name in values ? values[name] : m));

export const turnMessages = (turns) => turns.flatMap((t) => [{ role: "user", content: t.user }, { role: "assistant", content: t.assistant }]);

export const system = (prompts, extra = null) => ({ role: "system", content: prompts.system + (extra ? `\n\n${extra}` : "") });

const probe = (question) => ({ role: "user", content: question });

export const noHistory = (prompts, conversation, question) => [system(prompts), probe(question)];

export const full = (prompts, conversation, question) => [system(prompts), ...turnMessages(conversation.turns), probe(question)];

export const lastN = (prompts, conversation, question, n) => [system(prompts), ...turnMessages(conversation.turns.slice(-n)), probe(question)];

// The most recent whole messages that fit limit with the system prompt and the probe, newest first.
export function tokenBudget(prompts, conversation, question, limit) {
  const history = turnMessages(conversation.turns);
  const kept = [];
  for (const message of [...history].reverse()) {
    if (chatTemplate.count([system(prompts), message, ...kept, probe(question)]) > limit) break;
    kept.unshift(message);
  }
  return [system(prompts), ...kept, probe(question)];
}

export function summaryRecent(prompts, conversation, question, summary, recent) {
  const block = fill(prompts.summary_block, { summary });
  return [system(prompts, block), ...turnMessages(conversation.turns.slice(-recent)), probe(question)];
}

export function stateRecent(prompts, conversation, question, state, recent) {
  const block = fill(prompts.state_block, { state: pyJson(state) });
  return [system(prompts, block), ...turnMessages(conversation.turns.slice(-recent)), probe(question)];
}

// ---- maintenance calls ----------------------------------------------------------------------------------------

export const formatTurns = (prompts, turns) => turns.map((t) => fill(prompts.turn_format, { user: t.user, assistant: t.assistant })).join("\n\n");

export function summaryUpdate(prompts, summary, turns) {
  const user = fill(prompts.summary_user, { summary: summary || prompts.summary_empty, turns: formatTurns(prompts, turns) });
  return [{ role: "system", content: prompts.summary_system }, { role: "user", content: user }];
}

export function stateUpdate(prompts, state, turn) {
  const user = fill(prompts.extraction_user, { state: pyJson(state), turn: formatTurns(prompts, [turn]) });
  return [{ role: "system", content: prompts.extraction_system }, { role: "user", content: user }];
}
