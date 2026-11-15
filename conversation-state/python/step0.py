"""
Step 0 (data/settings.json, run_plan.step_0): before any experiment, check the token counting and find out
what Ollama does with a growing conversation and with a request larger than the context window.

  python step0.py        # about two minutes; writes runs/python/step0.json and the log lines

1. Counting: four requests that fit (the dev conversations, whole, with a probe) and one with text outside
   ASCII, each with the model unloaded first so nothing is cached. The app's count must equal Ollama's
   prompt_eval_count.
2. The prompt cache: the same request twice in a row, then a conversation one turn longer, recording what
   prompt_eval_count and prompt_eval_duration report when a prefix is reused.
3. The window: at num_ctx 2048, a request well below the window and one well above it. Recorded: the HTTP
   status or error, prompt_eval_count beside the app's count, the answer, and the server log lines.
4. What the model saw: for the oversized request, which ending of the conversation has the count Ollama
   reports (if Ollama dropped whole messages from the start), and two probes, one for a fact stated early
   (the order number, turn 2) and one stated late (the neighbour's house number, turn 19).

Step 0 uses a draft system prompt; the frozen prompts come later, from the dev conversations.
"""
import json
import os
import time

import chat_template
import ollama
import ollama_log
from common import RUNS, load

SYSTEM = ("You are the support assistant for Fernwick Goods, an online homeware shop. Answer the customer's last "
          "message from the conversation so far. If the conversation doesn't say, tell the customer you don't have "
          "that information.")
UNICODE_TEXT = ("Here’s my summary — the customer’s order arrived damaged; she wants a refund of 16 € "
                "or a replacement “soon”. Café table, naïve question \U0001F642, 3½ weeks ago.")


def history(conversation: dict, turns: int) -> list[dict]:
    """The system prompt and the first `turns` turns, both messages of each."""
    messages = [{"role": "system", "content": SYSTEM}]
    for t in conversation["turns"][:turns]:
        messages += [{"role": "user", "content": t["user"]}, {"role": "assistant", "content": t["assistant"]}]
    return messages


def ask(messages: list[dict], num_ctx: int, num_predict: int, label: str) -> dict:
    start = ollama_log.position()
    record = {"label": label, "num_ctx": num_ctx, "app_count": chat_template.count(messages), "messages": len(messages)}
    try:
        reply = ollama.chat(messages, {"temperature": 0, "seed": 1, "num_ctx": num_ctx, "num_predict": num_predict})
        record.update({k: reply.get(k) for k in ("prompt_eval_count", "prompt_eval_duration", "eval_count", "load_duration")})
        record["answer"] = reply["message"]["content"]
        record["error"] = None
    except RuntimeError as e:
        record["error"] = str(e)
    time.sleep(1.0)
    text = ollama_log.lines_since(start)
    record["log"] = ollama_log.read_task(text)
    (RUNS / "step0-log").mkdir(parents=True, exist_ok=True)
    (RUNS / "step0-log" / f"{label}.txt").write_text(text)
    print(f"   {label}: app {record['app_count']}, Ollama {record.get('prompt_eval_count')}, "
          f"{(record.get('prompt_eval_duration') or 0) / 1e6:.0f} ms" + (f", ERROR {record['error']}" if record["error"] else ""), flush=True)
    return record


def main() -> None:
    data = load()
    convs = data["conversations"]
    probe = {c: {p["fact"]: p["question"] for p in convs[c]["probes"]} for c in convs}
    model = ollama.chat_model()
    ollama.wait_for_quiet({os.getpid()})
    out = {"model": model}

    print("1. counting (model unloaded before each request)")
    counting = []
    for cid in ["c01", "c02", "c03", "c04"]:
        ollama.unload(model)
        first = convs[cid]["probes"][0]["question"]
        counting.append(ask(history(convs[cid], 20) + [{"role": "user", "content": first}], 8192, 1, f"count-{cid}"))
    ollama.unload(model)
    counting.append(ask([{"role": "system", "content": SYSTEM}, {"role": "user", "content": UNICODE_TEXT}], 8192, 1, "count-unicode"))
    out["counting"] = counting
    out["passed"] = all(r["prompt_eval_count"] == r["app_count"] for r in counting)

    print("2. the prompt cache")
    ollama.unload(model)
    c01 = convs["c01"]
    whole = history(c01, 20) + [{"role": "user", "content": probe["c01"]["order"]}]
    turn10 = history(c01, 9) + [{"role": "user", "content": c01["turns"][9]["user"]}]
    turn11 = history(c01, 10) + [{"role": "user", "content": c01["turns"][10]["user"]}]
    out["cache"] = [ask(whole, 8192, 1, "cache-same-1"), ask(whole, 8192, 1, "cache-same-2"),
                    ask(turn10, 8192, 1, "cache-turn10"), ask(turn11, 8192, 1, "cache-turn11")]

    print("3 and 4. the window: num_ctx 2048")
    ollama.unload(model)
    small = history(c01, 0) + [m for t in c01["turns"][15:] for m in
                               ({"role": "user", "content": t["user"]}, {"role": "assistant", "content": t["assistant"]})]
    window = [ask(small + [{"role": "user", "content": probe["c01"]["neighbour"]}], 2048, 128, "window-small"),
              ask(history(c01, 20) + [{"role": "user", "content": probe["c01"]["order"]}], 2048, 128, "window-large-order"),
              ask(history(c01, 20) + [{"role": "user", "content": probe["c01"]["neighbour"]}], 2048, 128, "window-large-neighbour")]
    # If Ollama drops whole messages from the start (keeping the system prompt), one ending of the conversation
    # has exactly the count it reports: find it.
    for r, fact in zip(window[1:], ["order", "neighbour"]):
        full = history(c01, 20)
        endings = {k: chat_template.count([full[0]] + full[k:] + [{"role": "user", "content": probe["c01"][fact]}])
                   for k in range(1, len(full))}
        r["matching_endings"] = [{"first_kept_message": k, "first_kept_turn": (k + 1) // 2, "role": full[k]["role"]}
                                 for k, n in endings.items() if n == r.get("prompt_eval_count")]
    out["window"] = window

    RUNS.mkdir(parents=True, exist_ok=True)
    (RUNS / "step0.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    if not ollama.other_connections({os.getpid()}):
        ollama.unload(model)
    print(f"counting {'passed' if out['passed'] else 'FAILED'}; saved runs/python/step0.json")


if __name__ == "__main__":
    main()
