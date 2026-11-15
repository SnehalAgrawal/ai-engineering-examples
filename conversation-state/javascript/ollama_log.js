// Reading Ollama's server log, for experiments 1c and 2. Same behaviour as ../python/ollama_log.py, where the
// reading is described. The format is that of the runner in Ollama 0.40.16.
import { closeSync, openSync, readSync, statSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

const LOG = process.env.OLLAMA_SERVER_LOG || join(homedir(), ".ollama", "logs", "server.log");

const PROCESSING = /task (\d+) \| processing task/g;
const NEW_PROMPT = /task (\d+) \| new prompt, .*task\.n_tokens = (\d+)/g;
const CANCEL = /stop: cancel task, id_task = (\d+)/g;
const RELEASE = /task (\d+) \| stop processing: n_tokens = (\d+)/g;
const TRUNCATED = /task (\d+) \| stop processing: n_tokens = \d+, truncated = (\d+)/g;
const SHIFT = /task (\d+) \| slot context shift, n_keep = (\d+), n_left = (\d+), n_discard = (\d+)/g;
const PROMPT_EVAL = /[^\n]*task (\d+) \| prompt eval time =\s*([\d.]+) ms \/\s*(\d+) tokens[^\n]*/g;

export const position = () => statSync(LOG).size;

export function linesSince(start) {
  const size = statSync(LOG).size;
  const from = size < start ? 0 : start; // the log was rotated
  const buffer = Buffer.alloc(size - from);
  const fd = openSync(LOG, "r");
  readSync(fd, buffer, 0, buffer.length, from);
  closeSync(fd);
  return buffer.toString("utf8");
}

const all = (pattern, text) => [...text.matchAll(pattern)];

// The task in these lines: its id, prompt tokens, whether it was cancelled, its token count at release, the
// tokens actually evaluated for the prompt (with the raw line), any context shifts, and the truncated flag.
export function readTask(text) {
  const tasks = [...new Set(all(PROCESSING, text).map((m) => m[1]))];
  const result = { tasks_seen: tasks.sort((a, b) => Number(a) - Number(b)), task: null, prompt_tokens: null, cancelled: false, release_n_tokens: null };
  if (tasks.length !== 1) return result;
  const [task] = tasks;
  result.task = Number(task);
  const prompt = all(NEW_PROMPT, text).find((m) => m[1] === task);
  result.prompt_tokens = prompt ? Number(prompt[2]) : null;
  result.cancelled = all(CANCEL, text).some((m) => m[1] === task);
  const release = all(RELEASE, text).find((m) => m[1] === task);
  result.release_n_tokens = release ? Number(release[2]) : null;
  const line = all(PROMPT_EVAL, text).find((m) => m[1] === task);
  result.evaluated_tokens = line ? Number(line[3]) : null;
  result.prompt_eval_line = line ? line[0].trim() : null;
  result.context_shifts = all(SHIFT, text).filter((m) => m[1] === task)
    .map((m) => ({ n_keep: Number(m[2]), n_left: Number(m[3]), n_discard: Number(m[4]) }));
  const truncated = all(TRUNCATED, text).find((m) => m[1] === task);
  result.truncated = truncated ? Number(truncated[2]) : null;
  if (result.prompt_tokens !== null && result.release_n_tokens !== null) {
    result.generated_estimate = result.release_n_tokens - result.prompt_tokens;
  }
  return result;
}
