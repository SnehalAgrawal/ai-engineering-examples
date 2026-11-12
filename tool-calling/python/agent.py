"""
The tool-calling loop.

  1. Send the conversation and the tool definitions to the model.
  2. If the reply contains tool calls, run each one through tools.Session
     (parse, validate, apply the business rules, execute) and append the
     results to the conversation.
  3. Repeat until the model replies without tool calls, or MAX_STEPS is reached.
"""
import json

from llm import chat, tool_message
from tools import TOOLS, Session

MAX_STEPS = 5  # model calls per conversation; a loop that never finishes stops here
MAX_TOKENS = 1000


def run_conversation(system_prompt: str, question: str, seed: int, on_event=None) -> dict:
    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": question}]
    session = Session()
    calls, finish_reasons, fingerprints = [], [], []
    tokens, error, final = 0, None, None
    for _ in range(MAX_STEPS):
        response = chat(messages, TOOLS, seed, MAX_TOKENS)
        tokens += response["tokens"]
        finish_reasons.append(response["finish_reason"])
        fingerprints.append(response["fingerprint"])
        if on_event:
            on_event("model", response)
        if response["error"]:
            error = response["error"]
            break
        if not response["tool_calls"]:
            final = response["content"]
            break
        messages.append(response["message"])
        for call in response["tool_calls"]:
            outcome = session.run(call["name"], call["arguments"])
            calls.append(outcome)
            if on_event:
                on_event("tool", outcome)
            messages.append(tool_message(call, json.dumps(outcome["result"], ensure_ascii=False)))
    return {
        "final": final,
        "calls": calls,
        "steps": len(finish_reasons),
        "step_limit": final is None and error is None,
        "finish_reasons": finish_reasons,
        "tokens": tokens,
        "fingerprints": fingerprints,
        "error": error,
    }
