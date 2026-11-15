"""
What each strategy sends to the model, and the calls that maintain a summary or a case record
(data/settings.json, "strategies"). Every function returns the messages of one request.

A turn is one customer message and one assistant reply. The probe is the customer's next message.
"""
import json
import re

import chat_template


def fill(template: str, **values: str) -> str:
    """Replace each {name} in the template in one pass, so text inserted from a conversation is never itself
    treated as a placeholder."""
    return re.sub(r"\{(\w+)\}", lambda m: values[m.group(1)] if m.group(1) in values else m.group(0), template)


def turn_messages(turns: list[dict]) -> list[dict]:
    messages = []
    for t in turns:
        messages += [{"role": "user", "content": t["user"]}, {"role": "assistant", "content": t["assistant"]}]
    return messages


def system(prompts: dict, extra: str | None = None) -> dict:
    return {"role": "system", "content": prompts["system"] + (f"\n\n{extra}" if extra else "")}


def probe_message(question: str) -> dict:
    return {"role": "user", "content": question}


def no_history(prompts: dict, conversation: dict, question: str) -> list[dict]:
    return [system(prompts), probe_message(question)]


def full(prompts: dict, conversation: dict, question: str) -> list[dict]:
    return [system(prompts)] + turn_messages(conversation["turns"]) + [probe_message(question)]


def last_n(prompts: dict, conversation: dict, question: str, n: int) -> list[dict]:
    return [system(prompts)] + turn_messages(conversation["turns"][-n:]) + [probe_message(question)]


def token_budget(prompts: dict, conversation: dict, question: str, limit: int) -> list[dict]:
    """The most recent whole messages that fit limit with the system prompt and the probe, newest first."""
    history = turn_messages(conversation["turns"])
    kept: list[dict] = []
    for message in reversed(history):
        candidate = [system(prompts), message] + kept + [probe_message(question)]
        if chat_template.count(candidate) > limit:
            break
        kept.insert(0, message)
    return [system(prompts)] + kept + [probe_message(question)]


def summary_recent(prompts: dict, conversation: dict, question: str, summary: str, recent: int) -> list[dict]:
    block = fill(prompts["summary_block"], summary=summary)
    return [system(prompts, block)] + turn_messages(conversation["turns"][-recent:]) + [probe_message(question)]


def state_recent(prompts: dict, conversation: dict, question: str, state: dict, recent: int) -> list[dict]:
    block = fill(prompts["state_block"], state=json.dumps(state, ensure_ascii=False))
    return [system(prompts, block)] + turn_messages(conversation["turns"][-recent:]) + [probe_message(question)]


# ---- maintenance calls ----------------------------------------------------------------------------------------

def format_turns(prompts: dict, turns: list[dict]) -> str:
    return "\n\n".join(fill(prompts["turn_format"], user=t["user"], assistant=t["assistant"]) for t in turns)


def summary_update(prompts: dict, summary: str | None, turns: list[dict]) -> list[dict]:
    user = fill(prompts["summary_user"], summary=summary or prompts["summary_empty"], turns=format_turns(prompts, turns))
    return [{"role": "system", "content": prompts["summary_system"]}, {"role": "user", "content": user}]


def state_update(prompts: dict, state: dict, turn: dict) -> list[dict]:
    user = fill(prompts["extraction_user"], state=json.dumps(state, ensure_ascii=False), turn=format_turns(prompts, [turn]))
    return [{"role": "system", "content": prompts["extraction_system"]}, {"role": "user", "content": user}]
