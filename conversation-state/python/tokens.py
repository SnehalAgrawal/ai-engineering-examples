"""
Token counts in the model's own tokens (Llama 3.2), so context limits mean what the model reads.

Llama 3.2 uses a byte-level BPE tokenizer: a regular expression splits the text into pieces, each piece is
written as bytes, and the bytes are merged pairwise by rank. This file implements exactly that from the
model's tokenizer.json, with no dependency. Step 0 compares the counts with Ollama's.

Unlike Article #19's copy, it accepts any text, not only ASCII: summaries and states written by the model can
contain characters such as curly quotes. Python's re has no \\p{L} or \\p{N}, so the two classes are built
from the Unicode database (letters: categories L*; numbers: N*), as the tokenizer's pattern defines them.
"""
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

TOKENIZER_PATH = Path(os.environ.get("TOKENIZER_PATH", Path(__file__).resolve().parent.parent / "data" / "tokenizer.json"))


def _unicode_class(prefix: str) -> str:
    """A character-class body matching every code point whose general category starts with prefix."""
    ranges, start, prev = [], None, None
    for cp in range(sys.maxunicode + 1):
        if unicodedata.category(chr(cp)).startswith(prefix):
            if start is None:
                start = cp
            prev = cp
        elif start is not None:
            ranges.append((start, prev))
            start = None
    if start is not None:
        ranges.append((start, prev))
    return "".join(re.escape(chr(a)) if a == b else f"{re.escape(chr(a))}-{re.escape(chr(b))}" for a, b in ranges)


L, N = _unicode_class("L"), _unicode_class("N")

# The pre-tokenizer pattern from tokenizer.json, with \p{L} and \p{N} spelled out.
PATTERN = re.compile(
    rf"(?i:'s|'t|'re|'ve|'m|'ll|'d)|[^\r\n{L}{N}]?[{L}]+|[{N}]{{1,3}}| ?[^\s{L}{N}]+[\r\n]*|\s*[\r\n]+|\s+(?!\S)|\s+"
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


class Tokenizer:
    def __init__(self, path: Path = TOKENIZER_PATH):
        if not Path(path).exists():
            raise SystemExit(f"No tokenizer at {path}. See the README: Get the tokenizer.")
        tokenizer = json.loads(Path(path).read_text())
        model = tokenizer["model"]
        self.vocab: dict[str, int] = model["vocab"]
        merges = [m if isinstance(m, list) else m.split(" ") for m in model["merges"]]
        self.ranks = {(a, b): rank for rank, (a, b) in enumerate(merges)}
        self.special = {t["content"]: t["id"] for t in tokenizer["added_tokens"]}
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
        """Ordinary text only: special tokens such as <|eot_id|> are added by the chat template, not here."""
        ids = []
        for piece in PATTERN.findall(text):
            if piece not in self.cache:
                self.cache[piece] = self._bpe("".join(BYTE_TO_UNICODE[b] for b in piece.encode("utf-8")))
            ids.extend(self.cache[piece])
        return ids

    def count(self, text: str) -> int:
        return len(self.encode(text))
