"""
A proxy between the client and the app server, for experiment 2 (data/settings.json). It forwards the request
unchanged and passes the response back in one of three ways, chosen per request with the X-Proxy-Mode header:

  pass-through   each block read from the app server is written to the client immediately
  buffer-all     the whole response is read first, then written in one write
  buffer-4096    a block is written each time 4,096 bytes are held, plus the remainder at the end

Every write to the client is counted, including the final partial one. Each request appends a record to
<runs>/proxy.jsonl.

  python proxy.py --port 8711 --upstream 8710 --runs ../runs/python
"""
import argparse
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from common import dumps, now_ms

BLOCK = 4096


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"

    def log_message(self, *args) -> None:
        pass

    def do_GET(self) -> None:
        self.send_response(200 if self.path == "/health" else 404)
        self.end_headers()

    def do_POST(self) -> None:
        mode = self.headers["X-Proxy-Mode"]
        body = self.rfile.read(int(self.headers["Content-Length"]))
        upstream = http.client.HTTPConnection("127.0.0.1", self.server.upstream, timeout=600)
        upstream.request("POST", self.path, body, {"Content-Type": "application/json"})
        response = upstream.getresponse()
        self.send_response(response.status)
        self.send_header("Content-Type", response.getheader("Content-Type"))
        self.end_headers()
        record = {"id": self.headers["X-Request-Id"], "mode": mode, "writes": 0, "bytes": 0, "t_first_write": None}

        def send(data: bytes) -> None:
            if record["t_first_write"] is None:
                record["t_first_write"] = now_ms()
            self.wfile.write(data)
            self.wfile.flush()
            record["writes"] += 1
            record["bytes"] += len(data)

        held = b""
        while True:
            data = response.read1(65536)
            if not data:
                break
            if mode == "pass-through":
                send(data)
            else:
                held += data
                while mode == "buffer-4096" and len(held) >= BLOCK:
                    send(held[:BLOCK])
                    held = held[BLOCK:]
        if held:
            send(held)
        upstream.close()
        with open(self.server.runs / "proxy.jsonl", "a") as f:
            f.write(dumps(record) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--upstream", type=int, required=True)
    parser.add_argument("--runs", required=True)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    server.daemon_threads = True
    server.upstream, server.runs = args.upstream, Path(args.runs)
    server.serve_forever()


if __name__ == "__main__":
    main()
