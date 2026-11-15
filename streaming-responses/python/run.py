"""
Runs experiments 1 to 4 (data/settings.json) and saves every request.

  1. computes each email's excerpts once (runs/python/<out>/excerpts.json)
  2. starts the app server and the proxy as separate processes
  3. runs the ten blocks in order. Before the first Ollama call it waits until no other program has been
     connected to Ollama for 60 seconds (Ollama may be shared with other work, which would distort the
     timings); before each later block it waits again only if another program has connected since. Each block
     then unloads the chat model and sends the unmeasured warm-up request. Requests run one at a time.
  4. writes requests.jsonl (one line per request: the client's, the app server's, and the proxy's records,
     the Ollama log reading for experiment 3, and any other program seen connected to Ollama), texts/, and
     disconnect-log/

  python run.py                          # everything, into runs/python/main
  python run.py --out smoke --emails e01,e02 --experiments 1,4
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request

import client
import ollama
import ollama_log
from common import HERE, RUNS, dumps, load, questions
from retrieval import Index

QUIET_S = 60
SETTLE_S = 1.0  # after a disconnected request, time for the app server and Ollama to finish and log


def blocks(emails: list[str]) -> list[dict]:
    first20, first10 = emails[:20], emails[:10]
    result = [{"experiment": "1", "mode": m, "emails": emails, "body": {"stream": m == "streaming"}}
              for m in ("non-streaming", "streaming")]
    result += [{"experiment": "2", "mode": m, "emails": first20, "body": {"stream": True}, "proxy": m}
               for m in ("pass-through", "buffer-all", "buffer-4096")]
    result += [{"experiment": "3", "mode": m, "emails": first10, "body": {"stream": True, "on_disconnect": m},
                "close_after": 20} for m in ("ignore", "cancel")]
    result += [{"experiment": "4", "mode": m, "emails": emails, "body": {"stream": True, "policy": m}}
               for m in ("check-whole", "stream-then-check", "sentence-gate")]
    return result


def wait_for_quiet(own: set[int], quiet_s: float = QUIET_S) -> None:
    """Return once no other program has been connected to Ollama for quiet_s seconds. With quiet_s 0, return at
    once if nobody else is connected; if someone is, wait until they have been gone for QUIET_S seconds."""
    quiet_since, waiting = time.time(), False
    while True:
        others = ollama.other_connections(own)
        if others:
            if not waiting:
                print(f"   waiting: another program is connected to Ollama: {', '.join(others)}", flush=True)
            quiet_since, waiting, quiet_s = time.time(), True, QUIET_S
        elif time.time() - quiet_since >= quiet_s:
            return
        time.sleep(5 if quiet_s else 0)


def start(script: str, *args: str) -> subprocess.Popen:
    return subprocess.Popen([sys.executable, str(HERE / script), *args], cwd=HERE)


def wait_healthy(port: int) -> None:
    for _ in range(100):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1)
            return
        except OSError:
            time.sleep(0.1)
    raise RuntimeError(f"nothing answers on port {port}")


def find(path, request_id: str, timeout: float = 900) -> dict:
    """The record with this id in a JSON-lines file, waiting for it to be written."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if path.exists():
            for line in path.read_text().splitlines():
                record = json.loads(line)
                if record["id"] == request_id:
                    return record
        time.sleep(0.05)
    raise RuntimeError(f"no record {request_id} in {path.name}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="main")
    parser.add_argument("--emails", help="comma-separated email ids (default: all 40)")
    parser.add_argument("--experiments", default="1,2,3,4")
    args = parser.parse_args()
    data = load()
    settings = data["settings"]
    emails = args.emails.split(",") if args.emails else sorted(data["emails"])
    wanted = args.experiments.split(",")
    out = RUNS / args.out
    if out.exists():
        shutil.rmtree(out)
    (out / "texts").mkdir(parents=True)
    (out / "disconnect-log").mkdir()

    wait_for_quiet({os.getpid()})  # even the embedding calls would slow someone else's measured run
    index = Index(settings, data["documents"])
    excerpts = {eid: index.excerpts(questions(data, eid)) for eid in sorted(data["emails"])}
    (out / "excerpts.json").write_text(json.dumps(excerpts, indent=1, ensure_ascii=False) + "\n")
    ports = settings["path"]["ports"]["python"]
    app = start("app_server.py", "--port", str(ports["app"]), "--runs", str(out))
    proxy = start("proxy.py", "--port", str(ports["proxy"]), "--upstream", str(ports["app"]), "--runs", str(out))
    own = {os.getpid(), app.pid, proxy.pid}
    try:
        wait_healthy(ports["app"])
        wait_healthy(ports["proxy"])
        ollama.unload(ollama.embedding_model())
        warm_up = [{"role": "user", "content": data["prompts"]["warm_up"]}]
        for block in blocks(emails):
            if block["experiment"] not in wanted:
                continue
            print(f"experiment {block['experiment']}, {block['mode']}: {len(block['emails'])} emails", flush=True)
            wait_for_quiet(own, 0)  # the full wait came before the excerpts; here only if someone has connected since
            ollama.unload(ollama.chat_model())
            ollama.chat(warm_up, {**settings["model"]["options"], "num_predict": 5})
            for eid in block["emails"]:
                request_id = f"{block['experiment']}|{block['mode']}|{eid}"
                body = {"id": request_id, "email": eid, **block["body"]}
                port = ports["proxy"] if "proxy" in block else ports["app"]
                seen = ollama.other_connections(own)
                log_start = ollama_log.position() if block["experiment"] == "3" else None
                record = client.request(port, body, block.get("proxy"), block.get("close_after"))
                server = find(out / "server.jsonl", request_id)
                line = {"experiment": block["experiment"], "mode": block["mode"], "email": eid, "client": record}
                if "proxy" in block:
                    line["proxy"] = find(out / "proxy.jsonl", request_id)
                if log_start is not None:
                    time.sleep(SETTLE_S)
                    text = ollama_log.lines_since(log_start)
                    (out / "disconnect-log" / f"{eid}-{block['mode']}.txt").write_text(text)
                    line["log"] = ollama_log.read_task(text)
                generated = server.pop("generated")
                (out / "texts" / f"{server['generated_sha256']}.txt").write_text(generated)
                line["server"] = server
                line["overlap"] = sorted(set(seen) | set(ollama.other_connections(own)))
                with open(out / "requests.jsonl", "a") as f:
                    f.write(dumps(line) + "\n")
    finally:
        app.terminate()
        proxy.terminate()
        if not ollama.other_connections(own):
            ollama.unload(ollama.chat_model())
            ollama.unload(ollama.embedding_model())
    print(f"saved {out.relative_to(RUNS.parent.parent)}")


if __name__ == "__main__":
    main()
