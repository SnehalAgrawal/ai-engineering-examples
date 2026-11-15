"""
Shared by every script: the frozen inputs, timestamps, and the prompt messages.

Every timestamp is wall-clock Unix time in milliseconds, taken by whichever process sees the event, so the
client's, the app server's, and the proxy's times can be compared (data/settings.json, "measurement").
"""
import json
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "data"
RUNS = HERE.parent / "runs" / "python"


def now_ms() -> float:
    return time.time_ns() / 1e6


def dumps(value) -> str:
    """Compact JSON, written the same way as JavaScript's JSON.stringify."""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def load() -> dict:
    return {
        "settings": json.loads((DATA / "settings.json").read_text()),
        "prompts": json.loads((DATA / "prompts.json").read_text()),
        "documents": {p.name: p.read_text() for p in sorted((DATA / "documents").glob("*.md"))},
        "emails": {p.stem: p.read_text() for p in sorted((DATA / "emails").glob("*.txt"))},
        "labels": json.loads((DATA / "labels.json").read_text())["emails"],
    }


def questions(data: dict, eid: str) -> list[str]:
    """The labelled questions of an email, used as retrieval queries (settings: inputs.questions)."""
    return [q["asks"] for q in data["labels"][eid]["questions"]]


def draft_messages(prompts: dict, email: str, questions_: list[str], excerpts: list[dict]) -> list[dict]:
    """The drafting prompt, as in Article #18: the email, its questions, and numbered excerpts."""
    p = prompts["draft"]
    numbered = "\n".join(f"{k}. {q}" for k, q in enumerate(questions_, 1))
    blocks = "\n\n".join(f"[{k}] ({e['document']})\n{e['text']}" for k, e in enumerate(excerpts, 1))
    user = p["user"].replace("{email}", email).replace("{questions}", numbered).replace("{excerpts}", blocks)
    return [{"role": "system", "content": p["system"]}, {"role": "user", "content": user}]
