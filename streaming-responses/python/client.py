"""
The client: it sends one request and records when each piece of the reply arrives (data/settings.json,
"measurement").

The response is read as raw bytes in whatever blocks arrive. They are decoded incrementally as UTF-8, so a
character split between two reads is decoded once it is complete. Server-sent events are framed on the blank
line that ends each event, so one read may hold part of an event or several. An event counts as received when
its blank line arrives.
"""
import codecs
import http.client
import json

from check import contains
from common import dumps, now_ms


def parse_event(raw: str) -> tuple[str, dict]:
    name, data = "message", ""
    for line in raw.split("\n"):
        if line.startswith("event: "):
            name = line[len("event: "):]
        elif line.startswith("data: "):
            data += line[len("data: "):]
    return name, json.loads(data) if data else {}


def request(port: int, body: dict, proxy_mode: str | None = None, close_after: int | None = None) -> dict:
    """Send one request. close_after: close the connection after this many text events (experiment 3)."""
    headers = {"Content-Type": "application/json", "X-Request-Id": body["id"]}
    if proxy_mode:
        headers["X-Proxy-Mode"] = proxy_mode
    record = {"t_start": None, "t_first_text": None, "t_last_text": None, "t_done": None, "t_closed": None,
              "t_retracted": None, "events": {}, "text_events": 0, "visible_text": "", "outcome": None,
              "flagged": None, "server": None}
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=600)
    payload = dumps(body)
    record["t_start"] = now_ms()
    conn.request("POST", "/reply", payload.encode(), headers)
    response = conn.getresponse()

    if response.getheader("Content-Type") == "application/json":
        reply = json.loads(response.read())
        t = now_ms()
        record.update({"t_first_text": t if reply["text"].strip() else None, "t_last_text": t, "t_done": t,
                       "visible_text": reply["text"], "server": reply["server"], "events": {"body": 1}})
        response.close()
        return record

    decoder = codecs.getincrementaldecoder("utf-8")()
    pending, shown, timeline = "", "", []
    closed = False
    while not closed:
        data = response.read1(65536)
        t = now_ms()
        if not data:
            pending += decoder.decode(b"", final=True)
            break
        pending += decoder.decode(data)
        while "\n\n" in pending and not closed:
            raw, pending = pending.split("\n\n", 1)
            name, event = parse_event(raw)
            record["events"][name] = record["events"].get(name, 0) + 1
            if name == "text":
                shown += event["text"]
                record["text_events"] += 1
                timeline.append((t, len(shown)))
                if record["t_first_text"] is None and event["text"].strip():
                    record["t_first_text"] = t
                record["t_last_text"] = t
                if close_after and record["text_events"] >= close_after:
                    record["t_closed"] = now_ms()
                    response.close()  # the user leaves: the connection closes
                    closed = True
            elif name in ("withheld", "retracted", "passed"):
                record["outcome"], record["flagged"] = name, event.get("flagged")
                if name == "retracted":
                    # the client removes the reply it had shown; first, when was the flagged value first visible?
                    record["t_retracted"] = t
                    first = event["flagged"][0]
                    seen = next((ts for ts, n in timeline if contains(shown[:n], first)), None)
                    record["t_flagged_visible"] = seen
                    shown = ""
            elif name == "done":
                record["server"] = event["server"]
    record["t_done"] = t
    record["visible_text"] = shown
    if record["outcome"] is None and record["server"]:
        record["outcome"] = record["server"].get("outcome")
    response.close()
    return record
