"""
Prompt development on the dev conversations only (c01 to c04): runs the summary and case-record maintenance
and the answers under the prompt-dependent strategies. It prints every intermediate summary, every change to
the case record, and every answer, for reading by hand; maintenance.jsonl keeps every maintenance call in full
(request size, Ollama's count, raw output, parse errors).

Every maintenance request is checked before it is sent: it must leave room for its whole output in the window
(num_ctx - num_predict), because Ollama silently drops messages from an oversized request (step 0). A request
over its limit stops the run.

  python dev.py                    # runs/python/dev/<prompts version>/

Test conversations are refused. Development runs are not results: the experiments are run separately, after
the prompts are frozen.
"""
import argparse
import json
import os

import chat_template
import context
import ollama
from common import RUNS, dumps, grade, load

DEV = ["c01", "c02", "c03", "c04"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--conversations", default=",".join(DEV))
    args = parser.parse_args()
    data = load()
    settings, prompts = data["settings"], data["prompts"]
    ids = args.conversations.split(",")
    if any(data["conversations"][c]["split"] != "dev" for c in ids):
        raise SystemExit("dev.py runs on dev conversations only")
    out = RUNS / "dev" / prompts["version"]
    out.mkdir(parents=True, exist_ok=True)
    options = settings["model"]["options"]
    small, large = settings["context"]["small_window"], settings["context"]["large_window"]
    limit = small["prompt_limit"]
    schema = settings["state_schema"]["json_schema"]
    model = ollama.chat_model()
    ollama.wait_for_quiet({os.getpid()})
    calls = 0
    summary_limit = small["num_ctx"] - settings["model"]["summary"]["num_predict"]
    extraction_limit = small["num_ctx"] - settings["model"]["extraction"]["num_predict"]

    def preflight(messages, limit_, what):
        size = chat_template.count(messages)
        if size > limit_:
            raise SystemExit(f"{what}: the request is {size} tokens, over its limit of {limit_}; run stopped")
        return size

    def chat(messages, num_ctx, num_predict, fmt=None):
        nonlocal calls
        calls += 1
        return ollama.chat(messages, {**options, "num_ctx": num_ctx, "num_predict": num_predict}, fmt)

    summaries, states, history = {}, {}, {}
    with open(out / "maintenance.jsonl", "w") as log:
        for cid in ids:
            turns = data["conversations"][cid]["turns"]
            summary = None
            for start in (0, 4, 8, 12):  # after turns 8, 12, 16, 20: turns 1-4, 5-8, 9-12, 13-16 leave the window
                messages = context.summary_update(prompts, summary, turns[start:start + 4])
                size = preflight(messages, summary_limit, f"{cid} summary of turns 1-{start + 4}")
                reply = chat(messages, small["num_ctx"], settings["model"]["summary"]["num_predict"])
                summary = reply["message"]["content"].strip()
                cut = reply["eval_count"] >= settings["model"]["summary"]["num_predict"]
                history.setdefault(cid, []).append(f"summary of turns 1-{start + 4} ({reply['eval_count']} tokens"
                                                   f"{', CUT OFF AT THE CAP' if cut else ''}): {summary}")
                log.write(dumps({"kind": "summary", "conversation": cid, "covers": [1, start + 4], "input_tokens": size,
                                 "prompt_eval_count": reply["prompt_eval_count"], "eval_count": reply["eval_count"],
                                 "cut_off": cut, "output": summary}) + "\n")
            summaries[cid] = summary
            state = dict(settings["state_schema"]["initial"])
            failed = []
            for i, turn in enumerate(turns, 1):
                messages = context.state_update(prompts, state, turn)
                size = preflight(messages, extraction_limit, f"{cid} case record after turn {i}")
                reply = chat(messages, small["num_ctx"], settings["model"]["extraction"]["num_predict"], schema)
                raw = reply["message"]["content"]
                error = None
                try:
                    new = json.loads(raw)
                except json.JSONDecodeError as e:
                    error = str(e)
                if error is None:
                    if new != state:
                        history[cid].append(f"record after turn {i}: {json.dumps(new)}")
                    state = new
                else:
                    failed.append(i)
                    history[cid].append(f"record after turn {i}: PARSE ERROR ({error}); raw output {raw!r}; previous record kept")
                log.write(dumps({"kind": "state", "conversation": cid, "turn": i, "input_tokens": size,
                                 "prompt_eval_count": reply["prompt_eval_count"], "eval_count": reply["eval_count"],
                                 "raw": raw, "parse_error": error, "state": state}) + "\n")
            states[cid] = state
            if failed:
                history[cid].append(f"FINAL RECORD INVALID: extraction failed after turns {failed}")

    strategies = [
        ("token_budget", small["num_ctx"], lambda c, q: context.token_budget(prompts, c, q, limit)),
        ("summary_recent", small["num_ctx"], lambda c, q: context.summary_recent(prompts, c, q, summaries[c["id"]], 4)),
        ("state_recent", small["num_ctx"], lambda c, q: context.state_recent(prompts, c, q, states[c["id"]], 4)),
        ("no_history", large["num_ctx"], lambda c, q: context.no_history(prompts, c, q)),
        ("full", large["num_ctx"], lambda c, q: context.full(prompts, c, q)),
    ]
    answers = []
    with open(out / "answers.jsonl", "w") as log:
        for name, num_ctx, build in strategies:
            for cid in ids:
                c = data["conversations"][cid]
                facts = {f["id"]: f for f in c["facts"]}
                for p in c["probes"]:
                    messages = build(c, p["question"])
                    size = chat_template.count(messages)
                    reply = chat(messages, num_ctx, settings["model"]["answer"]["num_predict"])
                    answer = reply["message"]["content"].strip()
                    row = {"strategy": name, "conversation": cid, "probe": p["id"], "fact": p["fact"], "tokens": size,
                           "over_limit": num_ctx == small["num_ctx"] and size > limit,
                           "grade": grade(answer, facts[p["fact"]]), "answer": answer}
                    answers.append(row)
                    log.write(dumps(row) + "\n")
    if not ollama.other_connections({os.getpid()}):
        ollama.unload(model)

    print(f"prompts {prompts['version']}: {calls} calls, saved {out.relative_to(RUNS.parent.parent)}")
    for cid in ids:
        print(f"\n===== {cid}")
        for line in history[cid]:
            print(f"  {line}")
        for p in data["conversations"][cid]["probes"]:
            print(f"  {p['id']} ({p['fact']}) {p['question']}")
            for r in answers:
                if r["conversation"] == cid and r["probe"] == p["id"]:
                    flag = " OVER LIMIT" if r["over_limit"] else ""
                    print(f"     {r['strategy']:<15} {r['grade']:<8} [{r['tokens']}{flag}] {r['answer']}")
    print("\ngrades:")
    for name, *_ in strategies:
        rs = [r for r in answers if r["strategy"] == name]
        print(f"   {name:<15} " + ", ".join(f"{g} {sum(r['grade'] == g for r in rs)}" for g in ("correct", "stale", "both", "other")))


if __name__ == "__main__":
    main()
