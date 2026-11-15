"""
The app server: it drafts a reply for one email and passes it to the client (data/settings.json, "path").

  POST /reply  {"id", "email", "stream", "policy", "on_disconnect"}
    stream false        one JSON body after Ollama's non-streaming reply is complete
    stream true         server-sent events: a 'text' event per chunk, then 'done' with the server's timestamps
    policy              none, check-whole, stream-then-check, or sentence-gate (experiment 4)
    on_disconnect       ignore (keep reading the model's stream) or cancel (close the connection to Ollama)
  GET /health

Each event is written and flushed as soon as it is ready. Every request also appends a record to
<runs>/server.jsonl, because a client that disconnects never receives the 'done' event.

  python app_server.py --port 8710 --runs ../runs/python
"""
import argparse
import hashlib
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import check
import ollama
from common import draft_messages, dumps, load, now_ms, questions

STATS = ["prompt_eval_count", "eval_count", "prompt_eval_duration", "eval_duration", "load_duration", "total_duration"]


class Reply:
    """One request: draft the reply and pass it on according to the policy."""

    def __init__(self, handler: BaseHTTPRequestHandler, body: dict, t_received: float):
        app = handler.server.app
        self.handler, self.policy, self.on_disconnect = handler, body.get("policy", "none"), body.get("on_disconnect", "ignore")
        eid = body["email"]
        excerpts = app.excerpts[eid]
        self.messages = draft_messages(app.data["prompts"], app.data["emails"][eid], questions(app.data, eid), excerpts)
        self.references = [e["text"] for e in excerpts] + [app.data["emails"][eid]]
        self.options = app.data["settings"]["model"]["options"]
        self.record = {"id": body["id"], "email": eid, "stream": body["stream"], "policy": self.policy,
                       "on_disconnect": self.on_disconnect, "t_received": t_received, "t_model_first": None,
                       "t_model_done": None, "t_write_failed": None, "events_written": 0,
                       "upstream_events_after_disconnect": 0, "cancelled": False}
        self.generated = ""
        self.gone = False
        self.sentences = check.Sentences()
        self.withheld = False

    # ---- writing to the client -----------------------------------------------------------------------------

    def write(self, name: str, data: dict) -> None:
        if self.gone:
            return
        payload = f"event: {name}\ndata: {dumps(data)}\n\n".encode()
        try:
            self.handler.wfile.write(payload)
            self.handler.wfile.flush()
            self.record["events_written"] += 1
        except OSError:  # the client has gone: BrokenPipeError, ConnectionResetError, ...
            self.gone = True
            self.record["t_write_failed"] = now_ms()

    def text(self, text: str) -> None:
        self.write("text", {"text": text, "sent_at": int(now_ms())})

    # ---- the policies --------------------------------------------------------------------------------------

    def on_chunk(self, content: str) -> None:
        if self.policy in ("none", "stream-then-check"):
            self.text(content)
        elif self.policy == "sentence-gate":
            for sentence in self.sentences.feed(content):
                self.gate(sentence)
        # check-whole: nothing is sent until the reply is complete

    def gate(self, sentence: str) -> None:
        if self.withheld:
            self.record["chars_held_back"] += len(sentence)
            return
        found = check.flagged(sentence, self.references)
        if found:
            self.withheld = True
            self.record["chars_held_back"] += len(sentence)
            self.record["flagged"] = found
            self.write("withheld", {"flagged": found, "sentence": sentence})
        else:
            self.record["sentences_sent"] += bool(sentence.strip())
            self.text(sentence)

    def finish(self) -> None:
        """After Ollama's last chunk: apply the policy's final step."""
        if self.policy == "none":
            return
        if self.policy == "sentence-gate":
            for sentence in self.sentences.finish():
                self.gate(sentence)
            self.record["outcome"] = "withheld" if self.withheld else "passed"
            return
        found = check.flagged(self.generated, self.references)
        self.record["flagged"] = found
        if self.policy == "check-whole":
            self.record["outcome"] = "withheld" if found else "passed"
            if found:
                self.write("withheld", {"flagged": found})
            else:
                self.text(self.generated)
        else:  # stream-then-check
            self.record["outcome"] = "retracted" if found else "passed"
            self.write("retracted" if found else "passed", {"flagged": found})

    # ---- the two kinds of response -------------------------------------------------------------------------

    def run(self) -> dict:
        if self.policy == "sentence-gate":
            self.record.update({"sentences_sent": 0, "chars_held_back": 0})
        if self.record["stream"]:
            self.streaming()
        else:
            self.whole()
        self.record["generated"] = self.generated
        self.record["generated_sha256"] = hashlib.sha256(self.generated.encode()).hexdigest()
        return self.record

    def whole(self) -> None:
        reply = ollama.chat(self.messages, self.options)
        self.record["t_model_done"] = now_ms()
        self.generated = reply["message"]["content"]
        self.record["ollama"] = {k: reply.get(k) for k in STATS}
        body = dumps({"text": self.generated, "server": self.server_times()}).encode()
        h = self.handler
        h.send_response(200)
        h.send_header("Content-Type", "application/json")
        h.send_header("Content-Length", str(len(body)))
        h.end_headers()
        h.wfile.write(body)

    def streaming(self) -> None:
        h = self.handler
        h.send_response(200)
        h.send_header("Content-Type", "text/event-stream")
        h.send_header("Cache-Control", "no-cache")
        h.end_headers()
        stream = ollama.ChatStream(self.messages, self.options)
        try:
            for arrived, chunk in stream:
                content = chunk.get("message", {}).get("content", "")
                if content:
                    if self.record["t_model_first"] is None:
                        self.record["t_model_first"] = arrived
                    self.generated += content
                    if self.gone:
                        self.record["upstream_events_after_disconnect"] += 1
                    else:
                        self.on_chunk(content)
                    if self.gone and self.on_disconnect == "cancel":
                        self.record["cancelled"] = True
                        return
                if chunk.get("done"):
                    self.record["t_model_done"] = arrived
                    self.record["ollama"] = {k: chunk.get(k) for k in STATS}
            self.finish()
            self.write("done", {"server": self.server_times()})
        finally:
            stream.close()

    def server_times(self) -> dict:
        keys = ["t_received", "t_model_first", "t_model_done", "outcome", "flagged", "sentences_sent", "chars_held_back"]
        return {k: self.record[k] for k in keys if k in self.record}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"  # one request per connection; the connection closes after each response

    def log_message(self, *args) -> None:
        pass

    def do_GET(self) -> None:
        self.send_response(200 if self.path == "/health" else 404)
        self.end_headers()

    def do_POST(self) -> None:
        t_received = now_ms()
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        record = Reply(self, body, t_received).run()
        with open(self.server.app.runs / "server.jsonl", "a") as f:
            f.write(dumps(record) + "\n")


class App:
    def __init__(self, runs: Path):
        self.runs = runs
        self.data = load()
        self.excerpts = json.loads((runs / "excerpts.json").read_text())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--runs", required=True)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    server.daemon_threads = True
    server.app = App(Path(args.runs))
    server.serve_forever()


if __name__ == "__main__":
    main()
