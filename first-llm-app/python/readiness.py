"""
Readiness probes (Article #31): questions someone asks before launch, put to
Article #11's application exactly as it is.

  python readiness.py

The application (app.py) and its HTTP service (server.py) are imported and
used unchanged. The model server is replaced by a SIMULATED provider on
127.0.0.1: a small HTTP server that answers POST /api/chat with scripted
replies (a correct answer, a wrong one, a 429, a 500, a broken response, a
slow one). No model runs, and nothing leaves this machine.

Each probe sets up one condition and compares what the application did with
the behaviour written down before the first run (EXPECTED). Stable fields are
printed first; timings, which change on every run, are printed separately.
The exit status is 1 if any probe differs from its expectation.

Scope: Python only. The probes exercise python/app.py and python/server.py.
The JavaScript version (javascript/) is not probed, and its HTTP server is
built differently, so nothing here describes it.
"""
import json
import os
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer, ThreadingHTTPServer

os.environ["OLLAMA_CHAT_MODEL"] = "simulated-provider"  # what the log's "model" field will say

import requests  # noqa: E402

import server  # noqa: E402  (Article #11's HTTP service: its Handler, unchanged)
from app import PROMPT, handle  # noqa: E402

UNREACHABLE = "http://127.0.0.1:9"  # nothing listens here (as in run_cases.py)
PRO_QUESTION = "How much is the Pro plan?"
PRO_ANSWER = "The Pro plan costs $25 per month and includes unlimited projects."
DELAY = 1.0  # seconds the simulated provider waits in the concurrency probe
VARIABLE = {"request_id", "latency_ms"}  # log fields that change on every run


# --- The simulated provider ------------------------------------------------------------------------------------

class Provider:
    """A scripted stand-in for the model server's POST /api/chat. It never runs a model.

    `reply(request_body)` returns (status, headers, body bytes). The provider itself handles requests in
    parallel (ThreadingHTTPServer), so it is never the bottleneck in the concurrency probe.
    """

    def __init__(self, reply):
        self.reply, self.requests = reply, []
        provider = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
                provider.requests.append(body)
                status, headers, payload = provider.reply(body)
                self.send_response(status)
                for name, value in headers.items():
                    self.send_header(name, value)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *args):
                pass

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.httpd.shutdown()
        self.httpd.server_close()


def model_says(content: str, delay: float = 0.0):
    """A well-formed /api/chat response whose message is `content`. It reports no token counts."""
    def reply(_body):
        time.sleep(delay)
        envelope = {"model": "simulated-provider", "message": {"role": "assistant", "content": content},
                    "done": True, "done_reason": "stop"}
        return 200, {"Content-Type": "application/json"}, json.dumps(envelope).encode()
    return reply


def model_answers(answer: str, sources: list[str], delay: float = 0.0):
    return model_says(json.dumps({"answered": True, "answer": answer, "source_ids": sources}), delay)


def http_status(code: int, headers: dict, body: str):
    return lambda _body: (code, headers, body.encode())


# --- Helpers ---------------------------------------------------------------------------------------------------

def shown(message: str) -> str:
    """Name the application's fixed messages instead of repeating them."""
    return {PROMPT["decline"]: "(decline message)", PROMPT["unavailable"]: "(unavailable message)"}.get(message, message)


def stable(log: dict) -> dict:
    return {k: v for k, v in log.items() if k not in VARIABLE}


def ask(question: str, reply=None, url: str | None = None):
    """Run handle() once, against a provider scripted with `reply`, or against `url`."""
    if reply is None:
        return handle(question, url=url), []
    with Provider(reply) as provider:
        return handle(question, url=provider.url), provider.requests


PROBES = []


def probe(number, question, condition, expected):
    def register(fn):
        PROBES.append({"number": number, "question": question, "condition": condition, "expected": expected,
                       "run": fn})
        return fn
    return register


# --- What #11 already handles ----------------------------------------------------------------------------------

@probe(1, "Does a normal question still get its checked answer?",
       "the provider returns a correct, well-formed answer",
       {"status": 200, "outcome": "answered", "error": None, "reply": PRO_ANSWER, "sources": ["plans"],
        "provider calls": 1, "schema sent": True, "token limit sent": 300, "messages sent": ["system", "user"],
        "prompt_version logged": "support-v1", "token counts logged": [0, 0]})
def baseline():
    result, sent = ask(PRO_QUESTION, model_answers(PRO_ANSWER, ["plans"]))
    log = result["log"]
    PROBES[0]["log"] = log
    return result, {
        "status": result["status"], "outcome": log["outcome"], "error": log["error"],
        "reply": shown(result["message"]), "sources": result["sources"], "provider calls": len(sent),
        "schema sent": "format" in sent[0], "token limit sent": sent[0]["options"]["num_predict"],
        "messages sent": [m["role"] for m in sent[0]["messages"]],
        "prompt_version logged": log["prompt_version"], "token counts logged": [log["prompt_tokens"], log["output_tokens"]],
    }


@probe(2, "What does the customer see when the model's reply isn't the agreed JSON?",
       "the provider responds normally, but the model's message is prose, not the JSON contract",
       {"status": 200, "outcome": "invalid_output", "error": None, "reply": "(decline message)",
        "model output kept in the result": True, "model output in the log record": False})
def invalid_model_output():
    content = "Sure! The Pro plan is $25 a month."
    result, _ = ask(PRO_QUESTION, model_says(content))
    log = result["log"]
    return result, {
        "status": result["status"], "outcome": log["outcome"], "error": log["error"], "reply": shown(result["message"]),
        "model output kept in the result": result["model_output"] == content,
        "model output in the log record": content in json.dumps(log),
    }


@probe(3, "What does the customer see when the model server is down?",
       f"nothing listens at {UNREACHABLE}",
       {"status": 503, "outcome": "model_unavailable", "error": "ConnectionError", "reply": "(unavailable message)"})
def provider_down():
    result, _ = ask(PRO_QUESTION, url=UNREACHABLE)
    log = result["log"]
    return result, {"status": result["status"], "outcome": log["outcome"], "error": log["error"],
                    "reply": shown(result["message"])}


@probe(4, "What if the provider's response itself is broken?",
       "the provider returns HTTP 200 with a body cut off mid-JSON",
       {"status": 503, "outcome": "model_unavailable", "error": "InvalidResponse", "reply": "(unavailable message)",
        "same outcome as invalid model output (probe 2)": False})
def broken_provider_response():
    cut_off = '{"model": "simulated-provider", "message": {"role": "assist'
    result, _ = ask(PRO_QUESTION, http_status(200, {"Content-Type": "application/json"}, cut_off))
    log = result["log"]
    return result, {"status": result["status"], "outcome": log["outcome"], "error": log["error"],
                    "reply": shown(result["message"]),
                    "same outcome as invalid model output (probe 2)": log["outcome"] == "invalid_output"}


# --- What it can't answer yet ----------------------------------------------------------------------------------

@probe(5, "What does the customer see when we're rate-limited?",
       "the provider returns 429 with Retry-After: 30 (simulated: a hosted provider's rate-limit response)",
       {"status": 503, "outcome": "model_unavailable", "error": "HTTPError", "reply": "(unavailable message)",
        "Retry-After value in the result or log": False})
def rate_limited():
    result, _ = ask(PRO_QUESTION, http_status(429, {"Retry-After": "30", "Content-Type": "application/json"},
                                              '{"error": "rate limit exceeded (simulated)"}'))
    log = result["log"]
    PROBES[4]["result"] = result
    return result, {"status": result["status"], "outcome": log["outcome"], "error": log["error"],
                    "reply": shown(result["message"]),
                    "Retry-After value in the result or log": "30" in result["message"]
                    or any(str(v) == "30" for v in stable(log).values())}


@probe(6, "Can the log tell a rate limit from a provider error?",
       "the provider returns 500 (compared with probe 5's 429)",
       {"status": 503, "outcome": "model_unavailable", "error": "HTTPError", "reply": "(unavailable message)",
        "same customer message as the 429": True, "same log error as the 429": True,
        "HTTP status code (429 or 500) in either log": False})
def server_error():
    result, _ = ask(PRO_QUESTION, http_status(500, {"Content-Type": "application/json"},
                                              '{"error": "internal error (simulated)"}'))
    log, limited = result["log"], PROBES[4]["result"]
    logs = list(stable(log).values()) + list(stable(limited["log"]).values())
    return result, {"status": result["status"], "outcome": log["outcome"], "error": log["error"],
                    "reply": shown(result["message"]),
                    "same customer message as the 429": result["message"] == limited["message"],
                    "same log error as the 429": log["error"] == limited["log"]["error"],
                    "HTTP status code (429 or 500) in either log": any(str(v) in {"429", "500"} for v in logs)}


@probe(7, "Does a fluent, wrong answer raise anything?",
       "asked about the Basic plan, the provider answers with the Pro plan's facts, citing the plans article",
       {"status": 200, "outcome": "answered", "error": None, "reply": PRO_ANSWER,
        "reply states the Basic price ($10)": False, "log fields that differ from probe 1": ["input_chars"]})
def fluent_wrong_answer():
    result, _ = ask("How much is the Basic plan?", model_answers(PRO_ANSWER, ["plans"]))
    log, right = stable(result["log"]), stable(PROBES[0]["log"])
    return result, {"status": result["status"], "outcome": log["outcome"], "error": log["error"],
                    "reply": shown(result["message"]),
                    "reply states the Basic price ($10)": "$10" in result["message"],
                    "log fields that differ from probe 1": sorted(k for k in log if log[k] != right.get(k))}


def two_at_once(server_class):
    """Start #11's Handler under `server_class` and send it two questions at the same moment."""
    httpd = server_class(("127.0.0.1", 0), server.Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{httpd.server_address[1]}/ask"
    barrier, finished, responses = threading.Barrier(2), [], []

    def client():
        barrier.wait()
        start = time.perf_counter()
        response = requests.post(url, json={"question": PRO_QUESTION}, timeout=30)
        finished.append(time.perf_counter() - start)
        responses.append(response)

    clients = [threading.Thread(target=client) for _ in range(2)]
    for c in clients:
        c.start()
    for c in clients:
        c.join()
    httpd.shutdown()
    httpd.server_close()
    return sorted(finished), responses


def pattern(times):
    if times[1] >= 1.8 * DELAY:
        return "one after the other"
    if times[1] <= 1.5 * DELAY:
        return "side by side"
    return "inconclusive"


@probe(8, "What happens to the second customer while the first one waits for the model?",
       f"the provider takes {DELAY:.0f} s per reply; two customers ask at the same moment through #11's "
       "server.Handler, under HTTPServer (as server.py runs it) and, as a control, ThreadingHTTPServer",
       {"HTTPServer (as in server.py)": "one after the other", "ThreadingHTTPServer (control)": "side by side",
        "all four answered 200": True})
def concurrency():
    with Provider(model_answers(PRO_ANSWER, ["plans"], delay=DELAY)) as provider, \
            tempfile.TemporaryDirectory() as workdir:
        os.environ["OLLAMA_BASE_URL"] = provider.url  # server.Handler calls handle() without a url
        cwd = os.getcwd()
        os.chdir(workdir)  # server.Handler appends to ./app.log; keep it out of the demo folder
        try:
            single, single_responses = two_at_once(HTTPServer)
            threaded, threaded_responses = two_at_once(ThreadingHTTPServer)
            with open("app.log") as f:
                lines = [json.loads(line) for line in f]
        finally:
            os.chdir(cwd)
    PROBES[7]["timings"] = {"HTTPServer: first and second reply (s)": [round(t, 2) for t in single],
                            "ThreadingHTTPServer: first and second reply (s)": [round(t, 2) for t in threaded]}
    PROBES[7]["app_log"] = lines
    return None, {"HTTPServer (as in server.py)": pattern(single), "ThreadingHTTPServer (control)": pattern(threaded),
                  "all four answered 200": all(r.status_code == 200 for r in single_responses + threaded_responses)}


@probe(9, "Given a complaint, can we see what the customer asked and what the model said?",
       "the four app.log lines server.Handler wrote in probe 8 (it logs result['log'] only)",
       {"lines written": 4, "question text in app.log": False, "model output in app.log": False,
        "fields per line": ["error", "input_chars", "latency_ms", "model", "outcome", "output_tokens",
                            "prompt_tokens", "prompt_version", "request_id", "status"]})
def request_log():
    lines = PROBES[7]["app_log"]
    text = json.dumps(lines)
    PROBES[8]["timings"] = {"first app.log line": lines[0]}
    return None, {"lines written": len(lines), "question text in app.log": PRO_QUESTION in text,
                  "model output in app.log": "unlimited projects" in text,
                  "fields per line": sorted(lines[0])}


# --- Run -------------------------------------------------------------------------------------------------------

def main() -> int:
    print("Readiness probes: Article #11's Python application (app.py, server.py), unchanged, against a")
    print("simulated model provider on 127.0.0.1. No model runs; every provider reply is scripted.")
    print(f"  (decline message)     {PROMPT['decline']}")
    print(f"  (unavailable message) {PROMPT['unavailable']}\n")

    differences = 0
    for p in PROBES:
        try:
            _, observed = p["run"]()
        except Exception as error:  # a probe that crashes is a finding too
            observed = {"probe raised": f"{type(error).__name__}: {error}"}
        print(f"[{p['number']}] {p['question']}")
        print(f"    condition: {p['condition']}")
        for key, value in observed.items():
            print(f"    {key}: {value}")
        mismatched = [k for k in set(p["expected"]) | set(observed) if p["expected"].get(k) != observed.get(k)]
        if mismatched:
            differences += 1
            for k in sorted(mismatched):
                print(f"    DIFFERS from expected: {k}: expected {p['expected'].get(k)!r}, observed {observed.get(k)!r}")
        else:
            print("    as expected")
        print()

    print("Variable values (change on every run; not compared):")
    for p in PROBES:
        if "log" in p:
            print(f"  [{p['number']}] latency_ms {p['log']['latency_ms']}")
        for key, value in p.get("timings", {}).items():
            print(f"  [{p['number']}] {key}: {value}")
    print(f"\n{len(PROBES) - differences} of {len(PROBES)} probes behaved as expected.")
    return 1 if differences else 0


if __name__ == "__main__":
    raise SystemExit(main())
