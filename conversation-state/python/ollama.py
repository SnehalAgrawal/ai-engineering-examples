"""
The calls to the local Ollama server, with the standard library only (as in Article #19's demo, without
streaming or embeddings, which this demo doesn't use).
"""
import http.client
import json
import os
import subprocess
import time
import urllib.parse

from dotenv import load_dotenv

load_dotenv()


def base_url() -> str:
    return os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")


def chat_model() -> str:
    return os.environ.get("OLLAMA_CHAT_MODEL", "llama3.2:3b")


def connect(timeout: float = 600) -> http.client.HTTPConnection:
    url = urllib.parse.urlsplit(base_url())
    return http.client.HTTPConnection(url.hostname, url.port or 80, timeout=timeout)


def post(path: str, body: dict, timeout: float = 600) -> dict:
    conn = connect(timeout)
    try:
        conn.request("POST", path, json.dumps(body), {"Content-Type": "application/json"})
        response = conn.getresponse()
        data = response.read()
        if response.status != 200:
            raise RuntimeError(f"{path} failed: HTTP {response.status} {data[:200]!r}")
        return json.loads(data)
    finally:
        conn.close()


def unload(model: str) -> None:
    post("/api/generate", {"model": model, "keep_alive": 0}, 60)


def chat(messages: list[dict], options: dict, fmt: dict | None = None) -> dict:
    """One non-streaming chat call. fmt, when given, is a JSON schema the reply must follow."""
    body = {"model": chat_model(), "messages": messages, "stream": False, "options": options}
    if fmt is not None:
        body["format"] = fmt
    return post("/api/chat", body)


def other_connections(own_pids: set[int]) -> list[str]:
    """Processes other than ours with an open connection to Ollama's port (macOS/Linux, needs lsof)."""
    port = urllib.parse.urlsplit(base_url()).port or 80
    out = subprocess.run(["lsof", "-nP", f"-iTCP:{port}", "-sTCP:ESTABLISHED", "-Fpc"],
                         capture_output=True, text=True).stdout
    found, pid, command = [], None, None
    for line in out.splitlines():
        if line.startswith("p"):
            pid = int(line[1:])
        elif line.startswith("c"):
            command = line[1:]
            if pid not in own_pids and command != "ollama":
                found.append(f"{command} ({pid})")
    return sorted(set(found))


def wait_for_quiet(own_pids: set[int], quiet_s: float = 60) -> None:
    """Return once no other program has been connected to Ollama for quiet_s seconds. With quiet_s 0, return at
    once if nobody else is connected; if someone is, wait until they have been gone for 60 seconds (as in
    Article #19)."""
    quiet_since, waiting = time.time(), False
    while True:
        others = other_connections(own_pids)
        if others:
            if not waiting:
                print(f"   waiting: another program is connected to Ollama: {', '.join(others)}", flush=True)
            quiet_since, waiting, quiet_s = time.time(), True, 60
        elif time.time() - quiet_since >= quiet_s:
            return
        time.sleep(5 if quiet_s else 0)
