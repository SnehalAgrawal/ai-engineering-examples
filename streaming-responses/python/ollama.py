"""
The calls to the local Ollama server, with the standard library only.

Streaming responses are read with HTTPResponse.read1, which returns whatever bytes have arrived instead of
waiting for a fixed amount, so each chunk is seen as soon as Ollama sends it. Ollama streams one JSON object
per line.
"""
import http.client
import json
import os
import subprocess
import urllib.parse

from dotenv import load_dotenv

from common import now_ms

load_dotenv()


def base_url() -> str:
    return os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")


def chat_model() -> str:
    return os.environ.get("OLLAMA_CHAT_MODEL", "llama3.2:3b")


def embedding_model() -> str:
    return os.environ.get("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text")


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


def embed(texts: list[str]) -> list[list[float]]:
    return post("/api/embed", {"model": embedding_model(), "input": texts, "truncate": False})["embeddings"]


def unload(model: str) -> None:
    post("/api/generate", {"model": model, "keep_alive": 0}, 60)


def chat(messages: list[dict], options: dict) -> dict:
    """One non-streaming chat call: the whole reply arrives at once."""
    return post("/api/chat", {"model": chat_model(), "messages": messages, "stream": False, "options": options})


class ChatStream:
    """A streaming chat call. Iterate to get (arrival time in ms, chunk) for each line Ollama sends."""

    def __init__(self, messages: list[dict], options: dict):
        self.conn = connect()
        body = {"model": chat_model(), "messages": messages, "stream": True, "options": options}
        self.conn.request("POST", "/api/chat", json.dumps(body), {"Content-Type": "application/json"})
        self.response = self.conn.getresponse()
        if self.response.status != 200:
            raise RuntimeError(f"/api/chat failed: HTTP {self.response.status}")

    def __iter__(self):
        pending = b""
        while True:
            data = self.response.read1(65536)
            if not data:
                return
            arrived = now_ms()
            pending += data
            *lines, pending = pending.split(b"\n")
            for line in lines:
                if line.strip():
                    yield arrived, json.loads(line)

    def close(self) -> None:
        """Close the connection to Ollama, whether or not the reply has finished."""
        self.response.close()
        self.conn.close()


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
