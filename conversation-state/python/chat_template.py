"""
The request as the model reads it: llama3.2:3b's chat template from Ollama 0.40.16, rendered and counted.

prompt_limit in data/settings.json counts the whole rendered request, so the app renders it the way the
template does: the begin-of-text token, a fixed system header (with the line 'Cutting Knowledge Date:
December 2023' that the template always adds), each message between header and end-of-turn tokens, and a
closing assistant header after the last user message. Special tokens count one each; the text between them
is counted with the tokenizer. Step 0 checks the total against Ollama's prompt_eval_count.

Ollama passes system messages to the template as one system text (joined by a blank line) and the other
messages in order; the requests here have at most one system message, first.
"""
from tokens import Tokenizer

_tokenizer = None


def tokenizer() -> Tokenizer:
    global _tokenizer
    if _tokenizer is None:
        _tokenizer = Tokenizer()
    return _tokenizer


def render(messages: list[dict]) -> list[str]:
    """The request as a list of pieces: special tokens as '<|...|>' strings, and plain text."""
    system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
    rest = [m for m in messages if m["role"] != "system"]
    pieces = ["<|begin_of_text|>", "<|start_header_id|>", "system", "<|end_header_id|>",
              "\n\nCutting Knowledge Date: December 2023\n\n" + system, "<|eot_id|>"]
    for i, m in enumerate(rest):
        last = i == len(rest) - 1
        if m["role"] == "user":
            pieces += ["<|start_header_id|>", "user", "<|end_header_id|>", "\n\n" + m["content"], "<|eot_id|>"]
            if last:
                pieces += ["<|start_header_id|>", "assistant", "<|end_header_id|>", "\n\n"]
        elif m["role"] == "assistant":
            pieces += ["<|start_header_id|>", "assistant", "<|end_header_id|>", "\n\n" + m["content"]]
            if not last:
                pieces.append("<|eot_id|>")
        else:
            raise ValueError(f"unexpected role {m['role']!r}")
    return pieces


def count(messages: list[dict]) -> int:
    tok = tokenizer()
    return sum(1 if p in tok.special else tok.count(p) for p in render(messages))
