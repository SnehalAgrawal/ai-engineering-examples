"""
The application as a small HTTP service, using only the standard library.

  python server.py
  curl -s localhost:8000/ask -d '{"question": "How much is the Pro plan?"}'

Every request is logged as one JSON line in app.log.
"""
import json
from http.server import BaseHTTPRequestHandler, HTTPServer

from app import handle

PORT = 8000


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/ask":
            return self._send(404, {"error": "Not found. POST /ask with {\"question\": \"...\"}"})
        try:
            length = int(self.headers.get("Content-Length", 0))
            question = json.loads(self.rfile.read(length) or b"{}").get("question", "")
            if not isinstance(question, str):
                raise ValueError
        except ValueError:
            return self._send(400, {"error": "Send JSON like {\"question\": \"...\"}."})
        result = handle(question)
        with open("app.log", "a") as f:
            f.write(json.dumps(result["log"]) + "\n")
        self._send(result["status"], {"answer": result["message"], "sources": result["sources"],
                                      "request_id": result["log"]["request_id"]})

    def _send(self, status: int, body: dict):
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):  # app.log is the request log; keep the console quiet
        pass


if __name__ == "__main__":
    print(f"Listening on http://localhost:{PORT}  (POST /ask)")
    HTTPServer(("localhost", PORT), Handler).serve_forever()
