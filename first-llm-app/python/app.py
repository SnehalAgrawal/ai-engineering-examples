"""
The same model, inside an application. handle() is the whole request path:

  1. validate the input        the application decides what reaches the model
  2. build the context         the help center, inside a versioned prompt
  3. call the model            with a schema, a token limit, and a timeout
  4. check the output          schema, sources, and values against the sources
  5. decide the reply          the application owns what the customer sees
  6. log the request           one record per request, success or not

handle() never raises: every path returns a status, a message, and a log record.
"""
import json
import re
import time
import uuid
from pathlib import Path

from llm import LLMError, chat, model_name

DATA = Path(__file__).resolve().parent.parent / "data"
DOCUMENTS = json.loads((DATA / "help_center.json").read_text())["documents"]
PROMPT = json.loads((DATA / "prompt.json").read_text())
MAX_INPUT_CHARS = 2000

ARTICLES = "\n".join(f"[{doc_id}] {text}" for doc_id, text in DOCUMENTS.items())
SYSTEM = PROMPT["system"].replace("{articles}", ARTICLES)
SCHEMA = {
    "type": "object",
    "properties": {
        "answered": {"type": "boolean"},
        "answer": {"type": "string"},
        "source_ids": {"type": "array", "items": {"type": "string", "enum": list(DOCUMENTS)}},
    },
    "required": ["answered", "answer", "source_ids"],
    "additionalProperties": False,
}

# Article #9's value-presence check: prices, durations, emails, and ids in the
# answer must appear in the articles it cites.
VALUE = re.compile(
    r"\$\s?\d[\d,]*(?:\.\d+)?"
    r"|\b\d+(?:\s*(?:-|–|to)\s*\d+)?\s*(?:business\s+)?(?:minutes?|hours?|days?|weeks?|months?)\b"
    r"|\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+",
    re.IGNORECASE,
)


def _normalize(value: str) -> str:
    return re.sub(r"\.0+(?!\d)", "", re.sub(r"[\s,$]", "", value.lower()))


def unsupported_values(answer: str, sources: list[str]) -> list[str]:
    known = {_normalize(v) for text in sources for v in VALUE.findall(text)}
    return [v for v in VALUE.findall(answer) if _normalize(v) not in known]


def _parse(content: str):
    """The model's JSON reply, or None if it isn't exactly the agreed shape."""
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return None
    if (not isinstance(data, dict) or set(data) != {"answered", "answer", "source_ids"}
            or not isinstance(data["answered"], bool) or not isinstance(data["answer"], str)
            or not isinstance(data["source_ids"], list)
            or not all(s in DOCUMENTS for s in data["source_ids"])):
        return None
    return data


def handle(text: str, url: str | None = None) -> dict:
    start = time.perf_counter()
    question = text.strip()
    log = {
        "request_id": str(uuid.uuid4()),
        "prompt_version": PROMPT["version"],
        "model": model_name(),
        "input_chars": len(question),
        "prompt_tokens": None,
        "output_tokens": None,
        "error": None,
    }

    model_output = None  # kept for debugging and evaluation; never shown to the customer

    def reply(status: int, message: str, outcome: str, sources=()):
        log.update(status=status, outcome=outcome, latency_ms=round((time.perf_counter() - start) * 1000))
        return {"status": status, "message": message, "sources": list(sources), "model_output": model_output, "log": log}

    # 1. Validate the input.
    if not question:
        return reply(400, "Please type a question.", "empty_input")
    if len(question) > MAX_INPUT_CHARS:
        return reply(413, f"Your message is too long ({len(question):,} characters). Please keep questions under "
                          f"{MAX_INPUT_CHARS:,} characters and leave out logs or attachments.", "input_too_long")

    # 2 and 3. Build the context, and call the model with a schema, a token limit, and a timeout.
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": question}]
    try:
        result = chat(messages, schema=SCHEMA, max_tokens=300, timeout=60, url=url)
    except LLMError as error:
        log["error"] = str(error)
        return reply(503, PROMPT["unavailable"], "model_unavailable")
    log.update(prompt_tokens=result["prompt_tokens"], output_tokens=result["output_tokens"])
    model_output = result["content"]

    # 4. Check the output.
    data = _parse(result["content"])
    if data is None:
        return reply(200, PROMPT["decline"], "invalid_output")
    if not data["answered"]:
        return reply(200, PROMPT["decline"], "declined")
    cited = [DOCUMENTS[s] for s in data["source_ids"]]
    if not data["answer"].strip() or not cited or unsupported_values(data["answer"], cited):
        return reply(200, PROMPT["decline"], "unsupported_answer")

    # 5. The application decides the reply: the checked answer, with its sources.
    return reply(200, data["answer"].strip(), "answered", data["source_ids"])
