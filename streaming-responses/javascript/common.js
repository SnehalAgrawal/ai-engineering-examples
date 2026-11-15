// Shared by every script: the frozen inputs, timestamps, and the prompt messages. Same as ../python/common.py.
// Every timestamp is wall-clock Unix time in milliseconds, taken by whichever process sees the event.
import { readFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

export const HERE = dirname(fileURLToPath(import.meta.url));
export const DATA = join(HERE, "..", "data");
export const RUNS = join(HERE, "..", "runs", "javascript");
export const PYTHON_RUNS = join(HERE, "..", "runs", "python");

export const nowMs = () => performance.timeOrigin + performance.now();

const readJson = (path) => JSON.parse(readFileSync(path, "utf8"));
const byName = (dir, ext, keepExt) => Object.fromEntries(readdirSync(join(DATA, dir)).filter((f) => f.endsWith(ext)).sort()
  .map((f) => [keepExt ? f : f.slice(0, -ext.length), readFileSync(join(DATA, dir, f), "utf8")]));

export function load() {
  return {
    settings: readJson(join(DATA, "settings.json")),
    prompts: readJson(join(DATA, "prompts.json")),
    documents: byName("documents", ".md", true),
    emails: byName("emails", ".txt", false),
    labels: readJson(join(DATA, "labels.json")).emails,
  };
}

// The labelled questions of an email, used as retrieval queries (settings: inputs.questions).
export const questions = (data, eid) => data.labels[eid].questions.map((q) => q.asks);

// The drafting prompt, as in Article #18: the email, its questions, and numbered excerpts.
export function draftMessages(prompts, email, questionList, excerpts) {
  const p = prompts.draft;
  const numbered = questionList.map((q, k) => `${k + 1}. ${q}`).join("\n");
  const blocks = excerpts.map((e, k) => `[${k + 1}] (${e.document})\n${e.text}`).join("\n\n");
  const user = p.user.replaceAll("{email}", () => email).replaceAll("{questions}", () => numbered)
    .replaceAll("{excerpts}", () => blocks);
  return [{ role: "system", content: p.system }, { role: "user", content: user }];
}
