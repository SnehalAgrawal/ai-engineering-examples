"""
Token counts in the answer model's own tokens (Llama 3.2), so context budgets mean what the model reads.

Llama 3.2 uses a byte-level BPE tokenizer: a regular expression splits the text into pieces, each piece
is written as bytes, and the bytes are merged pairwise by rank. This file implements exactly that from the
model's tokenizer.json, with no dependency. check_tokens.py compares the counts with Ollama's.

The documents and questions are ASCII, so the expression's letter and digit classes (\\p{L}, \\p{N}) are
written as [A-Za-z] and [0-9]. encode() refuses non-ASCII text rather than count it wrongly.
"""
import json
import os
import re
from pathlib import Path

TOKENIZER_PATH = Path(os.environ.get("TOKENIZER_PATH", Path(__file__).resolve().parent.parent / "data" / "tokenizer.json"))

# The pre-tokenizer pattern from tokenizer.json, with \p{L} -> A-Za-z and \p{N} -> 0-9 (ASCII input only).
PATTERN = re.compile(
    r"(?i:'s|'t|'re|'ve|'m|'ll|'d)|[^\r\nA-Za-z0-9]?[A-Za-z]+|[0-9]{1,3}| ?[^\sA-Za-z0-9]+[\r\n]*|\s*[\r\n]+|\s+(?!\S)|\s+"
)


def _byte_to_unicode() -> dict[int, str]:
    """The byte-level alphabet: every byte gets a printable character (as in GPT-2 and Llama 3)."""
    printable = list(range(ord("!"), ord("~") + 1)) + list(range(ord("\xa1"), ord("\xac") + 1)) + list(range(ord("\xae"), 256))
    codes, extra = printable[:], 0
    for b in range(256):
        if b not in printable:
            printable.append(b)
            codes.append(256 + extra)
            extra += 1
    return {b: chr(c) for b, c in zip(printable, codes)}


BYTE_TO_UNICODE = _byte_to_unicode()
UNICODE_TO_BYTE = {c: b for b, c in BYTE_TO_UNICODE.items()}


class Tokenizer:
    def __init__(self, path: Path = TOKENIZER_PATH):
        if not Path(path).exists():
            raise SystemExit(f"No tokenizer at {path}. See the README: Get the tokenizer.")
        model = json.loads(Path(path).read_text())["model"]
        self.vocab: dict[str, int] = model["vocab"]
        self.id_to_token = {i: t for t, i in self.vocab.items()}
        merges = [m if isinstance(m, list) else m.split(" ") for m in model["merges"]]
        self.ranks = {(a, b): rank for rank, (a, b) in enumerate(merges)}
        self.cache: dict[str, list[int]] = {}

    def _bpe(self, piece: str) -> list[int]:
        if piece in self.vocab:  # ignore_merges: a piece that is already a token stays whole
            return [self.vocab[piece]]
        parts = list(piece)
        while len(parts) > 1:
            ranked = [(self.ranks.get((parts[i], parts[i + 1])), i) for i in range(len(parts) - 1)]
            ranked = [(rank, i) for rank, i in ranked if rank is not None]
            if not ranked:
                break
            _, i = min(ranked)
            parts[i:i + 2] = [parts[i] + parts[i + 1]]
        return [self.vocab[p] for p in parts]

    def encode(self, text: str) -> list[int]:
        if not text.isascii():
            raise ValueError("tokens.py handles ASCII text only")
        ids = []
        for piece in PATTERN.findall(text):
            if piece not in self.cache:
                self.cache[piece] = self._bpe("".join(BYTE_TO_UNICODE[b] for b in piece.encode("utf-8")))
            ids.extend(self.cache[piece])
        return ids

    def decode(self, ids: list[int]) -> str:
        return bytes(UNICODE_TO_BYTE[c] for i in ids for c in self.id_to_token[i]).decode("utf-8")

    def count(self, text: str) -> int:
        return len(self.encode(text))
