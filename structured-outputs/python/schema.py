"""
The output contract as a JSON schema, and a validator for it.

The schema is built per request: `source_ids` may only contain the ids of the
documents retrieval returned for that question. That is a business rule a
schema CAN express. "The cited document actually supports the answer" is one
it can't.
"""
import json


def reply_schema(retrieved_ids: list[str]) -> dict:
    return {
        "type": "object",
        "properties": {
            "answered": {"type": "boolean"},
            "answer": {"type": "string"},
            "source_ids": {"type": "array", "items": {"type": "string", "enum": retrieved_ids}},
        },
        "required": ["answered", "answer", "source_ids"],
        "additionalProperties": False,
    }


def parse_strict(reply: str):
    """The reply as a JSON object, or None. No cleanup: a Markdown fence counts as invalid."""
    try:
        data = json.loads(reply)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def matches_schema(data, retrieved_ids: list[str]) -> bool:
    """True when the parsed reply has exactly the three fields, with the right types and allowed ids."""
    return (
        isinstance(data, dict)
        and set(data) == {"answered", "answer", "source_ids"}
        and isinstance(data["answered"], bool)
        and isinstance(data["answer"], str)
        and isinstance(data["source_ids"], list)
        and all(isinstance(i, str) and i in retrieved_ids for i in data["source_ids"])
    )
