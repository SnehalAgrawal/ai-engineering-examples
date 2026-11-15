"""
Step 0 (data/settings.json, run_plan.step_0): before the experiments, check that Ollama's log can be read
for completed and for cancelled requests. Python only; four drafting calls.

For e01 and e02, one request runs to completion and one is cancelled after 20 text chunks by closing the
connection to Ollama. For each, the log lines appended during the request are read (ollama_log.py).

  completed: release n_tokens - prompt tokens must equal eval_count, within 1
  cancelled: (a) one task id, with 'processing task', 'cancel task', and release lines;
             (b) a release n_tokens value;
             (c) release n_tokens - prompt tokens between the chunks received and the completed eval_count

Writes runs/python/step0.json.
"""
import json
import os
import time

import ollama
import ollama_log
from common import RUNS, draft_messages, dumps, load, questions
from retrieval import Index
from run import wait_for_quiet

EMAILS = ["e01", "e02"]
CLOSE_AFTER = 20
SETTLE_S = 1.0  # time for Ollama to write its log lines after a request ends


def main() -> None:
    data = load()
    settings = data["settings"]
    wait_for_quiet({os.getpid()})  # the log lines must belong to this script's requests only
    index = Index(settings, data["documents"])
    ollama.unload(ollama.embedding_model())
    options = settings["model"]["options"]
    results, ok = [], True
    for eid in EMAILS:
        messages = draft_messages(data["prompts"], data["emails"][eid], questions(data, eid), index.excerpts(questions(data, eid)))

        start = ollama_log.position()
        final = None
        stream = ollama.ChatStream(messages, options)
        for _, chunk in stream:
            if chunk.get("done"):
                final = chunk
        stream.close()
        time.sleep(SETTLE_S)
        done = ollama_log.read_task(ollama_log.lines_since(start))
        completed_ok = (done.get("generated_estimate") is not None
                        and abs(done["generated_estimate"] - final["eval_count"]) <= 1)
        results.append({"email": eid, "kind": "completed", "eval_count": final["eval_count"],
                        "prompt_eval_count": final["prompt_eval_count"], "log": done, "ok": completed_ok})

        start = ollama_log.position()
        stream = ollama.ChatStream(messages, options)
        received = 0
        for _, chunk in stream:
            if chunk.get("message", {}).get("content"):
                received += 1
                if received >= CLOSE_AFTER:
                    break
        stream.close()
        time.sleep(SETTLE_S)
        cut = ollama_log.read_task(ollama_log.lines_since(start))
        estimate = cut.get("generated_estimate")
        checks = {"a_one_task_cancel_and_release": cut["task"] is not None and cut["cancelled"]
                  and cut["release_n_tokens"] is not None,
                  "b_release_n_tokens": cut["release_n_tokens"] is not None,
                  "c_plausible": estimate is not None and received <= estimate <= final["eval_count"]}
        results.append({"email": eid, "kind": "cancelled", "chunks_received": received, "log": cut, "checks": checks,
                        "ok": all(checks.values())})
        ok = ok and completed_ok and all(checks.values())
    ollama.unload(ollama.chat_model())

    for r in results:
        log = r["log"]
        print(f"{r['email']} {r['kind']:<9} task {log['task']} (tasks seen {log['tasks_seen']}), prompt tokens "
              f"{log['prompt_tokens']}, release n_tokens {log['release_n_tokens']}, estimate "
              f"{log.get('generated_estimate')}, cancel line {log['cancelled']}", end="")
        if r["kind"] == "completed":
            print(f"; eval_count {r['eval_count']}: {'ok' if r['ok'] else 'MISMATCH'}")
        else:
            print(f"; chunks received {r['chunks_received']}; checks {r['checks']}: {'ok' if r['ok'] else 'FAILED'}")
    print("step 0:", "passed: the log can be read for experiment 3" if ok
          else "FAILED: experiment 3 reports app-side observations only")
    RUNS.mkdir(parents=True, exist_ok=True)
    (RUNS / "step0.json").write_text(json.dumps({"passed": ok, "results": results}, indent=1) + "\n")
    print(dumps({"passed": ok}))


if __name__ == "__main__":
    main()
