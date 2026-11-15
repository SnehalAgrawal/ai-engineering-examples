// Shared by every script: the frozen inputs, the matching rule, and small helpers. Same as ../python/common.py.
//
// The matching rule (data/settings.json, inputs.matching) is used for every search for a value: in fact
// positions, in the context sent to the model, in maintenance traces, and in answers.
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

export const HERE = dirname(fileURLToPath(import.meta.url));
export const DATA = join(HERE, "..", "data");
export const RUNS = join(HERE, "..", "runs", "javascript");
export const PYTHON_RUNS = join(HERE, "..", "runs", "python");

const readJson = (path) => JSON.parse(readFileSync(path, "utf8"));

export function load() {
  const prompts = join(DATA, "prompts.json");
  const dir = join(DATA, "conversations");
  const conversations = Object.fromEntries(readdirSync(dir).filter((f) => /^c.*\.json$/.test(f)).sort()
    .map((f) => [f.slice(0, -5), readJson(join(dir, f))]));
  return { settings: readJson(join(DATA, "settings.json")), prompts: existsSync(prompts) ? readJson(prompts) : null, conversations };
}

// Compact JSON, as Python's dumps in common.py writes it.
export const dumps = (value) => JSON.stringify(value);

// JSON as Python's json.dumps writes it by default: ", " and ": " separators. ensureAscii writes non-ASCII
// characters as \uXXXX escapes, as Python does unless told otherwise. Used where the text reaches the model.
export function pyJson(value, ensureAscii = false) {
  let text;
  if (Array.isArray(value)) text = `[${value.map((v) => pyJson(v, ensureAscii)).join(", ")}]`;
  else if (value !== null && typeof value === "object") {
    text = `{${Object.entries(value).map(([k, v]) => `${pyJson(k, ensureAscii)}: ${pyJson(v, ensureAscii)}`).join(", ")}}`;
  } else text = JSON.stringify(value);
  return ensureAscii ? text.replace(/[\u0080-\uffff]/g, (c) => `\\u${c.charCodeAt(0).toString(16).padStart(4, "0")}`) : text;
}

// Lowercase, and collapse runs of whitespace to one space.
export const norm = (text) => text.toLowerCase().replace(/\s+/g, " ");

const escape = (text) => text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

// Whether any of the forms appears in the text as a whole word or phrase: not directly preceded or followed by
// a letter or digit.
export function appears(text, forms) {
  const t = norm(text);
  return forms.some((f) => new RegExp(`(?<![a-z0-9])${escape(norm(f))}(?![a-z0-9])`).test(t));
}

export const turnText = (turn) => `${turn.user}\n${turn.assistant}`;

// The turns (1-based) whose customer or assistant message contains one of the forms.
export const mentions = (conversation, forms) => conversation.turns.map((t, i) => (appears(turnText(t), forms) ? i + 1 : 0)).filter(Boolean);

export const positionClass = (turn) => (turn <= 5 ? "early" : turn <= 15 ? "middle" : "late");

// The mechanical grade of an answer for one fact (settings: grading.answer).
export function grade(answer, fact) {
  const current = appears(answer, fact.accepted);
  const stale = fact.stale.some((s) => appears(answer, s.accepted));
  return current && stale ? "both" : current ? "correct" : stale ? "stale" : "other";
}
