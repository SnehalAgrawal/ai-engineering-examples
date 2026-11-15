"""
Reading Ollama's server log, for step 0 and experiment 2 (data/settings.json): what the server did with a
request larger than the context window. Copied from Article #19's demo.

The log is long, so only the lines appended after a remembered position are read. Requests run one at a time,
so those lines belong to one task: its id comes from the 'processing task' line, and only lines with that id
are used. The format is that of the runner in Ollama 0.40.16; another version may log differently.
"""
import os
import re
from pathlib import Path

LOG = Path(os.environ.get("OLLAMA_SERVER_LOG", Path.home() / ".ollama" / "logs" / "server.log"))

PROCESSING = re.compile(r"task (\d+) \| processing task")
NEW_PROMPT = re.compile(r"task (\d+) \| new prompt, .*task\.n_tokens = (\d+)")
CANCEL = re.compile(r"stop: cancel task, id_task = (\d+)")
RELEASE = re.compile(r"task (\d+) \| stop processing: n_tokens = (\d+)")
TRUNCATED = re.compile(r"task (\d+) \| stop processing: n_tokens = \d+, truncated = (\d+)")
SHIFT = re.compile(r"task (\d+) \| slot context shift, n_keep = (\d+), n_left = (\d+), n_discard = (\d+)")
PROMPT_EVAL = re.compile(r"[^\n]*task (\d+) \| prompt eval time =\s*([\d.]+) ms /\s*(\d+) tokens[^\n]*")


def position() -> int:
    return LOG.stat().st_size


def lines_since(start: int) -> str:
    size = LOG.stat().st_size
    if size < start:  # the log was rotated
        start = 0
    with open(LOG, "rb") as f:
        f.seek(start)
        return f.read(size - start).decode("utf-8", errors="replace")


def read_task(text: str) -> dict:
    """The task in these lines: its id, prompt tokens, whether it was cancelled, and its token count at release."""
    tasks = PROCESSING.findall(text)
    result = {"tasks_seen": sorted(set(tasks), key=int), "task": None, "prompt_tokens": None, "cancelled": False,
              "release_n_tokens": None}
    if len(set(tasks)) != 1:
        return result
    task = tasks[0]
    result["task"] = int(task)
    result["prompt_tokens"] = next((int(n) for t, n in NEW_PROMPT.findall(text) if t == task), None)
    result["cancelled"] = task in CANCEL.findall(text)
    result["release_n_tokens"] = next((int(n) for t, n in RELEASE.findall(text) if t == task), None)
    # The tokens Ollama actually evaluated for the prompt (fewer than the prompt when a cached prefix was reused),
    # with the raw line, so the parsed value can be audited. None when no line names the task.
    line = next((m for m in PROMPT_EVAL.finditer(text) if m.group(1) == task), None)
    result["evaluated_tokens"] = int(line.group(3)) if line else None
    result["prompt_eval_line"] = line.group(0).strip() if line else None
    # A context shift: generation ran out of window, and the runner discarded n_discard tokens of context to go on.
    result["context_shifts"] = [{"n_keep": int(k), "n_left": int(n), "n_discard": int(d)}
                                for t, k, n, d in SHIFT.findall(text) if t == task]
    result["truncated"] = next((int(v) for t, v in TRUNCATED.findall(text) if t == task), None)
    if result["prompt_tokens"] is not None and result["release_n_tokens"] is not None:
        result["generated_estimate"] = result["release_n_tokens"] - result["prompt_tokens"]
    return result
