"""
Runs experiments 1 to 3 (data/settings.json) and saves every model call.

  python run.py                                        # everything, into runs/python/main
  python run.py --smoke --out smoke --conversations c01 --blocks 1a_no_history,summaries,3_summary_recent

--smoke checks the code on dev conversations only: it refuses test conversations, and lets the growth block
(test conversations only in a real run) use the dev ones it is given.

Blocks run in the order of the run plan. Each block starts with the model unloaded and one unmeasured warm-up
request at the block's num_ctx. Before the first call the runner waits until no other program has been
connected to Ollama for 60 seconds, and before each later block again if one has connected since; any
overlap is recorded per request. The maintenance blocks (summaries, states) run before the answer blocks that
read their output.
"""
import argparse
import hashlib
import json
import os
import shutil
import time

import chat_template
import context
import ollama
import ollama_log
from common import DATA, RUNS, appears, dumps, grade, load

SETTLE_S = 1.0  # time for Ollama's log to be written before it is read


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def forms(fact: dict) -> tuple[list[str], list[str]]:
    return fact["accepted"], [f for s in fact["stale"] for f in s["accepted"]]


def trace(text: str, conversation: dict) -> dict:
    """For each fact, whether the text holds its current value and a stale value (settings: grading.in_context)."""
    out = {}
    for f in conversation["facts"]:
        current, stale = forms(f)
        out[f["id"]] = {"current": appears(text, current), "stale": appears(text, stale)}
    return out


def context_text(messages: list[dict]) -> str:
    """Everything sent before the probe: the system message (with any summary or record) and the kept turns."""
    return "\n".join(m["content"] for m in messages[:-1])


def all_text(messages: list[dict]) -> str:
    return "\n".join(m["content"] for m in messages)


def seen_context(record: dict, messages: list[dict], conversation: dict, fact: str) -> None:
    """When Ollama evaluated fewer tokens than the app sent (step 0: it drops whole messages from the start and
    keeps the system message), find the ending of the conversation whose count equals Ollama's, and check the
    fact against what the model saw. No match is recorded as such."""
    endings = [k for k in range(1, len(messages) - 1)
               if chat_template.count([messages[0]] + messages[k:]) == record["prompt_eval_count"]]
    record["kept_from_message"] = endings[0] if len(endings) == 1 else None
    record["ending_matches"] = len(endings)
    if len(endings) == 1:
        k = endings[0]
        record["first_kept_turn"] = (k + 1) // 2
        record["in_context_seen"] = trace(context_text([messages[0]] + messages[k:]), conversation)[fact]
    else:
        record["first_kept_turn"] = record["in_context_seen"] = None


class Runner:
    def __init__(self, out_dir, settings, prompts):
        self.out, self.settings, self.prompts = out_dir, settings, prompts
        self.own = {os.getpid()}
        self.options = settings["model"]["options"]
        self.log = open(out_dir / "requests.jsonl", "a")
        self.texts = out_dir / "texts"

    def warm_up(self, num_ctx: int) -> None:
        ollama.wait_for_quiet(self.own, 0)
        ollama.unload(ollama.chat_model())
        ollama.chat([{"role": "user", "content": "Reply with the word ready."}], {**self.options, "num_ctx": num_ctx, "num_predict": 5})

    def call(self, record: dict, messages: list[dict], num_ctx: int, num_predict: int, fmt=None, read_log=False) -> dict:
        record = {**record, "num_ctx": num_ctx, "app_tokens": chat_template.count(messages)}
        seen = ollama.other_connections(self.own)
        start = ollama_log.position() if read_log else None
        t0 = time.time()
        try:
            reply = ollama.chat(messages, {**self.options, "num_ctx": num_ctx, "num_predict": num_predict}, fmt)
            record["error"] = None
        except RuntimeError as e:
            reply, record["error"] = None, str(e)
        record["wall_ms"] = round((time.time() - t0) * 1000, 1)
        if reply:
            for k in ("prompt_eval_count", "prompt_eval_duration", "eval_count", "eval_duration", "load_duration", "total_duration"):
                record[k] = reply.get(k)
            output = reply["message"]["content"]
            record["output_sha256"] = sha(output)
            (self.texts / f"{record['output_sha256']}.txt").write_text(output)
            record["output"] = output
        if read_log:
            time.sleep(SETTLE_S)
            text = ollama_log.lines_since(start)
            name = f"{record['block']}-{record['conversation']}-{record.get('probe') or record.get('turn')}.txt"
            (self.out / "ollama-log" / name).write_text(text)
            record["log"] = ollama_log.read_task(text)
        record["overlap"] = sorted(set(seen) | set(ollama.other_connections(self.own)))
        return record

    def save(self, record: dict) -> None:
        """One line per model call; the output itself is in texts/, under its SHA-256."""
        self.log.write(dumps({k: v for k, v in record.items() if k != "output"}) + "\n")
        self.log.flush()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="main")
    parser.add_argument("--conversations", default=None)
    parser.add_argument("--blocks", default=None)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    data = load()
    settings, prompts = data["settings"], data["prompts"]
    derived = json.loads((DATA / "derived.json").read_text())
    if not prompts["version"].endswith("frozen") or derived["prompts_version"] != prompts["version"]:
        raise SystemExit("run.py needs the frozen prompts and the derived.json computed from them")
    convs = data["conversations"]
    ids = args.conversations.split(",") if args.conversations else sorted(convs)
    if args.smoke and any(convs[c]["split"] != "dev" for c in ids):
        raise SystemExit("--smoke runs on dev conversations only")
    growth_split = "dev" if args.smoke else "test"
    small, large = settings["context"]["small_window"], settings["context"]["large_window"]
    limit, n = small["prompt_limit"], derived["last_n"]
    m = settings["model"]
    out = RUNS / args.out
    if out.exists():
        shutil.rmtree(out)
    for sub in ("texts", "ollama-log", "summaries", "state"):
        (out / sub).mkdir(parents=True)
    run = Runner(out, settings, prompts)
    ollama.wait_for_quiet(run.own)
    summaries: dict[str, str] = {}
    states: dict[str, dict] = {}

    def probes(block, experiment, num_ctx, build, read_log=False):
        run.warm_up(num_ctx)
        for cid in ids:
            c = convs[cid]
            facts = {f["id"]: f for f in c["facts"]}
            for p in c["probes"]:
                messages = build(c, p["question"])
                record = {"block": block, "experiment": experiment, "conversation": cid, "split": c["split"],
                          "probe": p["id"], "fact": p["fact"]}
                if num_ctx == small["num_ctx"]:
                    record["over_limit"] = chat_template.count(messages) > limit
                record["in_context"] = trace(context_text(messages), c)[p["fact"]]
                r = run.call(record, messages, num_ctx, m["answer"]["num_predict"], read_log=read_log)
                if read_log and r.get("prompt_eval_count") is not None and r["prompt_eval_count"] < r["app_tokens"]:
                    seen_context(r, messages, c, p["fact"])
                r["grade"] = grade(r["output"], facts[p["fact"]]) if r.get("output") is not None else None
                run.save(r)

    def maintain_summaries():
        run.warm_up(m["summary"]["num_ctx"])
        for cid in ids:
            c, summary = convs[cid], None
            with open(out / "summaries" / f"{cid}.jsonl", "w") as f:
                for start in (0, 4, 8, 12):
                    turns = c["turns"][start:start + 4]
                    messages = context.summary_update(prompts, summary, turns)
                    if chat_template.count(messages) > m["summary"]["num_ctx"] - m["summary"]["num_predict"]:
                        raise SystemExit(f"{cid}: summary request over its limit; run stopped")
                    r = run.call({"block": "summaries", "experiment": "3", "conversation": cid, "split": c["split"],
                                  "turn": start + 4}, messages, m["summary"]["num_ctx"], m["summary"]["num_predict"])
                    run.save(r)
                    new = r["output"].strip()
                    f.write(dumps({"covers": [1, start + 4], "cut_off": r["eval_count"] >= m["summary"]["num_predict"],
                                   "input": trace(all_text(messages), c), "output": trace(new, c),
                                   "summary": new}) + "\n")
                    summary = new
            summaries[cid] = summary

    def maintain_states():
        run.warm_up(m["extraction"]["num_ctx"])
        schema = settings["state_schema"]["json_schema"]
        for cid in ids:
            c = convs[cid]
            state, failed = dict(settings["state_schema"]["initial"]), []
            with open(out / "state" / f"{cid}.jsonl", "w") as f:
                for i, turn in enumerate(c["turns"], 1):
                    messages = context.state_update(prompts, state, turn)
                    if chat_template.count(messages) > m["extraction"]["num_ctx"] - m["extraction"]["num_predict"]:
                        raise SystemExit(f"{cid}: extraction request over its limit; run stopped")
                    r = run.call({"block": "states", "experiment": "3", "conversation": cid, "split": c["split"], "turn": i},
                                 messages, m["extraction"]["num_ctx"], m["extraction"]["num_predict"], schema)
                    run.save(r)
                    error = None
                    try:
                        new = json.loads(r["output"])
                    except (json.JSONDecodeError, TypeError) as e:
                        error, new = str(e), state
                        failed.append(i)
                    f.write(dumps({"turn": i, "parse_error": error, "input": trace(all_text(messages), c),
                                   "output": trace(json.dumps(new), c), "state": new}) + "\n")
                    state = new
            states[cid] = {**state, "_invalid": bool(failed), "_failed_turns": failed}

    def growth():
        run.warm_up(large["num_ctx"])
        for cid in [c for c in ids if convs[c]["split"] == growth_split]:
            c = convs[cid]
            for t in range(1, 21):
                messages = [context.system(prompts)] + context.turn_messages(c["turns"][:t - 1]) + [
                    {"role": "user", "content": c["turns"][t - 1]["user"]}]
                run.save(run.call({"block": "1c_growth", "experiment": "1c", "conversation": cid, "split": c["split"], "turn": t},
                                  messages, large["num_ctx"], m["growth"]["num_predict"], read_log=True))

    def load_maintenance(kind):
        target = summaries if kind == "summaries" else states
        for cid in ids:
            if cid not in target:
                rows = [json.loads(line) for line in open(out / kind / f"{cid}.jsonl")]
                if kind == "summaries":
                    target[cid] = rows[-1]["summary"]
                else:
                    failed = [row["turn"] for row in rows if row["parse_error"]]
                    target[cid] = {**rows[-1]["state"], "_invalid": bool(failed), "_failed_turns": failed}

    blocks = {
        "1a_no_history": lambda: probes("1a_no_history", "1a", large["num_ctx"], lambda c, q: context.no_history(prompts, c, q)),
        "1b_full": lambda: probes("1b_full", "1b", large["num_ctx"], lambda c, q: context.full(prompts, c, q)),
        "1c_growth": growth,
        "2_full_small": lambda: probes("2_full_small", "2", small["num_ctx"], lambda c, q: context.full(prompts, c, q), read_log=True),
        "summaries": maintain_summaries,
        "states": maintain_states,
        "3_last_n": lambda: probes("3_last_n", "3", small["num_ctx"], lambda c, q: context.last_n(prompts, c, q, n)),
        "3_token_budget": lambda: probes("3_token_budget", "3", small["num_ctx"], lambda c, q: context.token_budget(prompts, c, q, limit)),
        "3_summary_recent": lambda: (load_maintenance("summaries"), probes(
            "3_summary_recent", "3", small["num_ctx"], lambda c, q: context.summary_recent(prompts, c, q, summaries[c["id"]], 4))),
        "3_state_recent": lambda: (load_maintenance("state"), probes(
            "3_state_recent", "3", small["num_ctx"], lambda c, q: context.state_recent(
                prompts, c, q, {k: v for k, v in states[c["id"]].items() if not k.startswith("_")}, 4))),
    }
    wanted = args.blocks.split(",") if args.blocks else list(blocks)
    for name in blocks:
        if name in wanted:
            print(f"{name}: {len(ids)} conversations", flush=True)
            blocks[name]()
    (out / "final_states.json").write_text(json.dumps(states, indent=1) + "\n")
    if not ollama.other_connections(run.own):
        ollama.unload(ollama.chat_model())
    print(f"saved {out.relative_to(RUNS.parent.parent)}")


if __name__ == "__main__":
    main()
