"""
Shared by every script: the frozen inputs, the matching rule, and small helpers.

The matching rule (data/settings.json, inputs.matching) is used for every search for a value: in fact
positions, in the context sent to the model, in maintenance traces, and in answers.
"""
import json
import re
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
    prompts = DATA / "prompts.json"
    return {
        "settings": json.loads((DATA / "settings.json").read_text()),
        "prompts": json.loads(prompts.read_text()) if prompts.exists() else None,
        "conversations": {p.stem: json.loads(p.read_text()) for p in sorted((DATA / "conversations").glob("c*.json"))},
    }


def norm(text: str) -> str:
    """Lowercase, and collapse runs of whitespace to one space."""
    return re.sub(r"\s+", " ", text.lower())


def appears(text: str, forms: list[str]) -> bool:
    """Whether any of the forms appears in the text as a whole word or phrase: not directly preceded or
    followed by a letter or digit."""
    t = norm(text)
    return any(re.search(r"(?<![a-z0-9])" + re.escape(norm(f)) + r"(?![a-z0-9])", t) for f in forms)


def turn_text(turn: dict) -> str:
    return turn["user"] + "\n" + turn["assistant"]


def mentions(conversation: dict, forms: list[str]) -> list[int]:
    """The turns (1-based) whose customer or assistant message contains one of the forms."""
    return [i for i, t in enumerate(conversation["turns"], 1) if appears(turn_text(t), forms)]


def position_class(turn: int) -> str:
    return "early" if turn <= 5 else "middle" if turn <= 15 else "late"


def grade(answer: str, fact: dict) -> str:
    """The mechanical grade of an answer for one fact (settings: grading.answer)."""
    current = appears(answer, fact["accepted"])
    stale = any(appears(answer, s["accepted"]) for s in fact["stale"])
    return "both" if current and stale else "correct" if current else "stale" if stale else "other"
