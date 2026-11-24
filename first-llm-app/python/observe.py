"""
One complaint, three records (Article #34): what Article #11's application can tell you about a wrong
answer, depending on what it records.

  python observe.py                      # about 6 seconds; exit status 0 if every step behaved as expected
  python observe.py --negative-control   # two expectations deliberately changed: must report 2 and exit 1

The application (app.py, llm.py) is used unchanged, against the same SIMULATED provider as readiness.py
(Article #31): a small HTTP server on 127.0.0.1 that answers POST /api/chat with scripted replies. No model
runs, and nothing leaves this machine.

Two requests get the same scripted reply, "The Pro plan costs $25 per month...", citing the plans article:
  right  "How much is the Pro plan?"     (readiness.py's probe 1)
  wrong  "How much is the Basic plan?"   (readiness.py's probe 7)
Each is recorded three ways:
  1. the log record app.py already writes
  2. OpenTelemetry spans without message content (the GenAI conventions' default)
  3. the same spans with message content captured (opt-in)
Then: token usage as each layer sees it, the article's instrumentation snippet, and a provider error for
contrast.

Instrumentation is added from the outside, without editing app.py or llm.py:
  - a root span around handle(), carrying the application's own fields from its log record (app.*);
  - a span around the model call, made by wrapping the `chat` function app.py imported, the way client
    instrumentation libraries wrap a client (gen_ai.* names from the OpenTelemetry GenAI semantic
    conventions v0.1.0, status Development: the names can still change).
Spans go to an in-memory exporter. Each step compares what it observed with EXPECTED, which was written
before the first run, from reading the code.
"""
import json
import sys

import requests
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

import app  # Article #11's application, unchanged
import llm
from readiness import PRO_ANSWER, PRO_QUESTION, Provider, http_status, model_answers  # sets the model name

BASIC_QUESTION = "How much is the Basic plan?"
BASIC_FACT = "The Basic plan costs $10 per month"  # in the plans article, which app.py sends with every request
ROOT = "support.answer"
CHAT = f"chat {llm.model_name()}"
VARIABLE = {"app.request_id", "app.latency_ms"}  # change on every run; never compared

exporter = InMemorySpanExporter()
provider = TracerProvider()
provider.add_span_processor(SimpleSpanProcessor(exporter))
trace.set_tracer_provider(provider)
tracer = trace.get_tracer("first-llm-app.observe")


# --- Instrumentation, added from outside the application --------------------------------------------------------

def as_messages(messages: list[dict]) -> str:
    """Chat messages in the conventions' shape (role + parts), as a JSON string: span attributes are flat."""
    return json.dumps([{"role": m["role"], "parts": [{"type": "text", "content": m["content"]}]} for m in messages])


def traced_chat(original, capture_content: bool):
    """Wrap llm.chat the way a client instrumentation library would: it sees the call, not the application."""
    def chat(messages, **kwargs):
        model = llm.model_name()
        with tracer.start_as_current_span(f"chat {model}") as span:
            span.set_attribute("gen_ai.operation.name", "chat")
            span.set_attribute("gen_ai.provider.name", "ollama")  # llm.py speaks Ollama's API; a stand-in answers
            span.set_attribute("gen_ai.request.model", model)
            span.set_attribute("gen_ai.request.max_tokens", kwargs.get("max_tokens", 300))
            if capture_content:
                span.set_attribute("gen_ai.input.messages", as_messages(messages))
            result = original(messages, **kwargs)  # an LLMError propagates: the span records it, then handle() catches it
            if result["done_reason"]:
                span.set_attribute("gen_ai.response.finish_reasons", [result["done_reason"]])
            span.set_attribute("gen_ai.usage.input_tokens", result["prompt_tokens"])
            span.set_attribute("gen_ai.usage.output_tokens", result["output_tokens"])
            if capture_content:
                span.set_attribute("gen_ai.output.messages", as_messages([{"role": "assistant",
                                                                             "content": result["content"]}]))
            return result
    return chat


def handle_traced(question: str, reply, capture_content: bool):
    """Run handle() once inside a root span; return (result, finished spans by name)."""
    exporter.clear()
    original = app.chat
    app.chat = traced_chat(original, capture_content)
    try:
        with tracer.start_as_current_span(ROOT) as root, Provider(reply) as stand_in:
            result = app.handle(question, url=stand_in.url)
            for key, value in result["log"].items():  # the application's own facts: only it knows them
                if value is not None:
                    root.set_attribute(f"app.{key}", value)
            if result["status"] >= 500:
                root.set_status(trace.Status(trace.StatusCode.ERROR, result["log"]["outcome"]))
    finally:
        app.chat = original
    return result, {s.name: s for s in exporter.get_finished_spans()}


def attributes(spans: dict) -> dict:
    return {f"{name}: {key}": value for name, span in spans.items()
            for key, value in span.attributes.items() if key not in VARIABLE}


def differing(a: dict, b: dict) -> list[str]:
    return sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))


def status(span) -> str:
    return span.status.status_code.name


def content_of(span, attribute: str, role: str) -> str:
    return " ".join(p["content"] for m in json.loads(span.attributes[attribute]) if m["role"] == role
                    for p in m["parts"])


# --- The article's snippet: usage read where the provider's response is read -------------------------------------

def generate(call_model, messages, model, provider, prompt):
    # Span name and gen_ai.* names: GenAI semantic conventions v0.1.0 (status: Development)
    with tracer.start_as_current_span(f"chat {model}") as span:
        span.set_attribute("gen_ai.operation.name", "chat")
        span.set_attribute("gen_ai.provider.name", provider)
        span.set_attribute("gen_ai.request.model", model)
        span.set_attribute("gen_ai.prompt.name", prompt["name"])
        span.set_attribute("gen_ai.prompt.version", prompt["version"])

        reply = call_model(model=model, messages=messages)  # message content is not recorded

        span.set_attribute("gen_ai.response.model", reply["model"])
        span.set_attribute("gen_ai.response.finish_reasons", [reply["finish_reason"]])
        usage = reply.get("usage")
        if usage is None:
            span.set_attribute("app.usage_missing", True)  # a visible gap, not a zero
        else:
            span.set_attribute("gen_ai.usage.input_tokens", usage["input_tokens"])
            span.set_attribute("gen_ai.usage.output_tokens", usage["output_tokens"])
        return reply


def ollama_client(url: str):
    """A minimal client that keeps "not reported" apart from 0, by reading the provider's response itself."""
    def call_model(model, messages):
        data = requests.post(f"{url}/api/chat", json={"model": model, "messages": messages, "stream": False},
                             timeout=10).json()
        counts = ("prompt_eval_count", "eval_count")
        usage = ({"input_tokens": data[counts[0]], "output_tokens": data[counts[1]]}
                 if all(c in data for c in counts) else None)
        return {"model": data.get("model"), "finish_reason": data.get("done_reason"), "usage": usage,
                "content": data["message"]["content"]}
    return call_model


def reports_usage(reply_function, prompt_tokens: int, output_tokens: int):
    """The same scripted reply, with token counts added to the provider's envelope."""
    def reply(body):
        code, headers, payload = reply_function(body)
        envelope = json.loads(payload) | {"prompt_eval_count": prompt_tokens, "eval_count": output_tokens}
        return code, headers, json.dumps(envelope).encode()
    return reply


# --- Steps ----------------------------------------------------------------------------------------------------

STEPS = []


def step(number, question, expected):
    def register(fn):
        STEPS.append({"number": number, "question": question, "expected": expected, "run": fn})
        return fn
    return register


RIGHT = (PRO_QUESTION, model_answers(PRO_ANSWER, ["plans"]))
WRONG = (BASIC_QUESTION, model_answers(PRO_ANSWER, ["plans"]))
SHOW = {}  # spans printed after the steps


@step(1, "The log record app.py writes: can it tell the wrong answer from the right one?",
      {"status (right, wrong)": [200, 200], "outcome (right, wrong)": ["answered", "answered"],
       "log fields that differ": ["input_chars"], "question text in the log": False, "reply text in the log": False})
def the_log():
    right, _ = handle_traced(*RIGHT, capture_content=False)
    wrong, _ = handle_traced(*WRONG, capture_content=False)
    logs = [{k: v for k, v in r["log"].items() if f"app.{k}" not in VARIABLE} for r in (right, wrong)]
    text = json.dumps([right["log"], wrong["log"]])
    return {"status (right, wrong)": [right["status"], wrong["status"]],
            "outcome (right, wrong)": [right["log"]["outcome"], wrong["log"]["outcome"]],
            "log fields that differ": differing(*logs),
            "question text in the log": BASIC_QUESTION in text, "reply text in the log": PRO_ANSWER in text}


@step(2, "Spans without message content (the conventions' default): can they?",
      {"spans per request": [ROOT, CHAT], "span attributes that differ": [f"{ROOT}: app.input_chars"],
       "span status (right, wrong)": [["UNSET", "UNSET"], ["UNSET", "UNSET"]],
       "question or reply text in any span": False})
def spans_without_content():
    _, right = handle_traced(*RIGHT, capture_content=False)
    _, wrong = handle_traced(*WRONG, capture_content=False)
    text = json.dumps([attributes(right), attributes(wrong)], default=str)
    return {"spans per request": sorted(wrong, key=lambda n: n != ROOT),
            "span attributes that differ": differing(attributes(right), attributes(wrong)),
            "span status (right, wrong)": [[status(right[ROOT]), status(right[CHAT])],
                                           [status(wrong[ROOT]), status(wrong[CHAT])]],
            "question or reply text in any span": BASIC_QUESTION in text or PRO_ANSWER in text}


@step(3, "The same spans with message content captured (opt-in): what do they show?",
      {"span attributes that differ": [f"{CHAT}: gen_ai.input.messages", f"{ROOT}: app.input_chars"],
       "output messages identical": True, "question the customer asked (wrong)": BASIC_QUESTION,
       "Basic price in the context the model was sent (wrong)": True,
       "reply states the Basic price ($10) (wrong)": False, "reply states the Pro price ($25) (wrong)": True,
       "span status (right, wrong)": [["UNSET", "UNSET"], ["UNSET", "UNSET"]]})
def spans_with_content():
    _, right = handle_traced(*RIGHT, capture_content=True)
    _, wrong = handle_traced(*WRONG, capture_content=True)
    SHOW["wrong, with content"] = wrong
    chat = wrong[CHAT]
    reply = content_of(chat, "gen_ai.output.messages", "assistant")
    return {"span attributes that differ": differing(attributes(right), attributes(wrong)),
            "output messages identical": right[CHAT].attributes["gen_ai.output.messages"]
            == chat.attributes["gen_ai.output.messages"],
            "question the customer asked (wrong)": content_of(chat, "gen_ai.input.messages", "user"),
            "Basic price in the context the model was sent (wrong)":
                BASIC_FACT in content_of(chat, "gen_ai.input.messages", "system"),
            "reply states the Basic price ($10) (wrong)": "$10" in reply,
            "reply states the Pro price ($25) (wrong)": "$25" in reply,
            "span status (right, wrong)": [[status(right[ROOT]), status(right[CHAT])],
                                           [status(wrong[ROOT]), status(wrong[CHAT])]]}


@step(4, "Token usage, seen from a wrapper around llm.chat: is 0 different from 'not reported'?",
      {"provider reported token counts": False, "usage on the chat span, not reported": [0, 0],
       "usage on the chat span, provider reports 0 and 0": [0, 0], "chat span attributes identical": True})
def usage_above_the_client():
    envelope = json.loads(model_answers(PRO_ANSWER, ["plans"])({})[2])
    _, silent = handle_traced(*RIGHT, capture_content=False)
    _, zero = handle_traced(PRO_QUESTION, reports_usage(model_answers(PRO_ANSWER, ["plans"]), 0, 0),
                            capture_content=False)
    usage = [[s[CHAT].attributes.get(k) for k in ("gen_ai.usage.input_tokens", "gen_ai.usage.output_tokens")]
             for s in (silent, zero)]
    return {"provider reported token counts": "prompt_eval_count" in envelope or "eval_count" in envelope,
            "usage on the chat span, not reported": usage[0],
            "usage on the chat span, provider reports 0 and 0": usage[1],
            "chat span attributes identical": dict(silent[CHAT].attributes) == dict(zero[CHAT].attributes)}


@step(5, "The article's snippet, with usage read from the provider's response: is the gap visible?",
      {"not reported: app.usage_missing": True, "not reported: usage attributes": [None, None],
       "reports 0 and 0: app.usage_missing": None, "reports 0 and 0: usage attributes": [0, 0],
       "response model recorded": "simulated-provider", "prompt version recorded": "support-v1"})
def the_snippet():
    messages = [{"role": "user", "content": PRO_QUESTION}]
    prompt = {"name": "support", "version": app.PROMPT["version"]}
    seen = []
    for reply in (model_answers(PRO_ANSWER, ["plans"]), reports_usage(model_answers(PRO_ANSWER, ["plans"]), 0, 0)):
        exporter.clear()
        with Provider(reply) as stand_in:
            generate(ollama_client(stand_in.url), messages, llm.model_name(), "ollama", prompt)
        seen.append(exporter.get_finished_spans()[0].attributes)
    keys = ("gen_ai.usage.input_tokens", "gen_ai.usage.output_tokens")
    return {"not reported: app.usage_missing": seen[0].get("app.usage_missing"),
            "not reported: usage attributes": [seen[0].get(k) for k in keys],
            "reports 0 and 0: app.usage_missing": seen[1].get("app.usage_missing"),
            "reports 0 and 0: usage attributes": [seen[1].get(k) for k in keys],
            "response model recorded": seen[0].get("gen_ai.response.model"),
            "prompt version recorded": seen[0].get("gen_ai.prompt.version")}


@step(6, "For contrast, an error the code can see: the provider returns HTTP 500",
      {"status": 503, "outcome": "model_unavailable", "chat span status": "ERROR",
       "chat span has an exception event": True, "root span status": "ERROR", "app.error on the root span": "HTTPError"})
def provider_error():
    result, spans = handle_traced(PRO_QUESTION, http_status(500, {"Content-Type": "application/json"},
                                                            '{"error": "internal error (simulated)"}'),
                                  capture_content=False)
    return {"status": result["status"], "outcome": result["log"]["outcome"],
            "chat span status": status(spans[CHAT]),
            "chat span has an exception event": any(e.name == "exception" for e in spans[CHAT].events),
            "root span status": status(spans[ROOT]), "app.error on the root span": spans[ROOT].attributes.get("app.error")}


# --- Run -------------------------------------------------------------------------------------------------------

def show(spans: dict) -> None:
    for name in sorted(spans, key=lambda n: n != ROOT):
        span = spans[name]
        print(f"  {'' if name == ROOT else '  '}span {name}  (status {status(span)})")
        for key, value in sorted(span.attributes.items()):
            if key in VARIABLE:
                continue
            if key == "gen_ai.input.messages":
                parsed = json.loads(value)
                value = [{"role": m["role"], "content": (c if len(c := m["parts"][0]["content"]) < 80
                                                         else f"{c[:60]}... ({len(c):,} characters)")}
                         for m in parsed]
            print(f"  {'      ' if name == ROOT else '        '}{key} = {value}")


def main(negative_control: bool = False) -> int:
    if negative_control:  # two expectations deliberately wrong: the comparison must catch both
        STEPS[0]["expected"]["log fields that differ"] = []
        STEPS[2]["expected"]["reply states the Basic price ($10) (wrong)"] = True
    print("One complaint, three records: Article #11's Python application (app.py, llm.py), unchanged, against a")
    print("simulated model provider on 127.0.0.1. No model runs; every provider reply is scripted.\n")

    differences = 0
    for s in STEPS:
        try:
            observed = s["run"]()
        except Exception as error:  # a step that crashes is a finding too
            observed = {"step raised": f"{type(error).__name__}: {error}"}
        print(f"[{s['number']}] {s['question']}")
        for key, value in observed.items():
            print(f"    {key}: {value}")
        mismatched = [k for k in set(s["expected"]) | set(observed) if s["expected"].get(k) != observed.get(k)]
        if mismatched:
            differences += 1
            for k in sorted(mismatched):
                print(f"    DIFFERS from expected: {k}: expected {s['expected'].get(k)!r}, observed {observed.get(k)!r}")
        else:
            print("    as expected")
        print()

    for label, spans in SHOW.items():
        print(f"The spans for the {label} (ids and timings left out):")
        show(spans)
    print(f"\n{len(STEPS) - differences} of {len(STEPS)} steps behaved as expected.")
    return 1 if differences else 0


if __name__ == "__main__":
    raise SystemExit(main(negative_control="--negative-control" in sys.argv[1:]))
