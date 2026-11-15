"""
Structure chunking with headings, as in rag-engineering (04-chunking, the strategy 05 and 06 use), with the
other strategies removed. Every chunk is one slice of one document, document[start:end], exactly as written,
with the heading lines above the slice copied in front of it. A chunk's text, which is what gets embedded
and what the drafting model reads, is that prefix plus the slice.

  structure  one chunk per Markdown section; a section over `max_tokens` is split between paragraphs,
             then between lines (a single line over `max_tokens` is cut into token windows).
             A heading with nothing under it joins the section that follows.
"""
import math
import re
from dataclasses import dataclass

HEADING = re.compile(r"#{1,6} ")


@dataclass
class Chunk:
    id: str
    document: str
    start: int
    end: int
    prefix: str
    text: str  # prefix + document[start:end]: what is embedded and what the model reads
    tokens: int


@dataclass
class Line:
    start: int
    end: int
    text: str
    kind: str  # heading, fence, code, blank, text


def parse_lines(text: str) -> list[Line]:
    lines, position, in_code = [], 0, False
    for raw in text.split("\n"):
        start, end = position, position + len(raw)
        position = end + 1
        if raw.startswith("```"):
            kind, in_code = "fence", not in_code
        elif in_code:
            kind = "code"
        elif raw.strip() == "":
            kind = "blank"
        elif HEADING.match(raw):
            kind = "heading"
        else:
            kind = "text"
        lines.append(Line(start, end, raw, kind))
    return lines


def blocks(lines: list[Line]) -> list[list[Line]]:
    """Paragraphs, tables, lists, and code blocks: runs of lines between blank lines. A heading is its own block."""
    result, current = [], []
    for line in lines:
        if line.kind == "blank" or line.kind == "heading":
            if current:
                result.append(current)
            current = [line] if line.kind == "heading" else []
            if line.kind == "heading":
                result.append(current)
                current = []
        else:
            current.append(line)
    if current:
        result.append(current)
    return result


def heading_stack(lines: list[Line], position: int) -> list[Line]:
    """The headings in force at a position: the last heading of each level above it, outermost first."""
    stack: list[Line] = []
    for line in lines:
        if line.start > position:
            break
        if line.kind == "heading":
            level = len(line.text) - len(line.text.lstrip("#"))
            stack = [h for h in stack if len(h.text) - len(h.text.lstrip("#")) < level] + [line]
    return stack


def pack(spans: list[tuple[int, int]], document: str, max_tokens: int, count, split) -> list[tuple[int, int]]:
    """Join consecutive spans while the joined slice stays within max_tokens; split a span that is too big alone."""
    result, current = [], None
    for span in spans:
        if count(document[span[0]:span[1]]) > max_tokens:
            if current:
                result.append(current)
                current = None
            result.extend(split(span))
            continue
        if current and count(document[current[0]:span[1]]) <= max_tokens:
            current = (current[0], span[1])
        else:
            if current:
                result.append(current)
            current = span
    if current:
        result.append(current)
    return result


def fixed(text: str, size: int, overlap: int, tokenizer) -> list[tuple[int, int]]:
    ids = tokenizer.encode(text)
    offsets = [0]
    for token in ids:
        offsets.append(offsets[-1] + len(tokenizer.decode([token])))
    spans, start = [], 0
    while True:
        end = min(start + size, len(ids))
        spans.append((offsets[start], offsets[end]))
        if end == len(ids):
            return spans
        start += size - overlap


def structure(text: str, max_tokens: int, count, tokenizer) -> list[tuple[int, int]]:
    lines = parse_lines(text)
    headings = [i for i, line in enumerate(lines) if line.kind == "heading"]
    starts = ([0] if headings and headings[0] != 0 else []) + headings
    sections, pending = [], None
    for k, first in enumerate(starts):
        last = starts[k + 1] if k + 1 < len(starts) else len(lines)
        content = [line for line in lines[first:last] if line.kind != "blank"]
        begin = pending if pending is not None else content[0].start
        if all(line.kind == "heading" for line in content):  # a heading with nothing under it
            pending = begin
            continue
        sections.append((begin, content[-1].end, blocks(lines[first:last])))
        pending = None

    def split_block(span):
        block_lines = [line for line in lines if span[0] <= line.start and line.end <= span[1]]
        return pack([(line.start, line.end) for line in block_lines], text, max_tokens, count, split_line)

    def split_line(span):  # a single line over max_tokens: cut it into token windows
        return [(span[0] + a, span[0] + b) for a, b in fixed(text[span[0]:span[1]], max_tokens, 0, tokenizer)]

    result = []
    for begin, end, section_blocks in sections:
        if count(text[begin:end]) <= max_tokens:
            result.append((begin, end))
            continue
        spans = [(b[0].start, b[-1].end) for b in section_blocks]
        spans[0] = (begin, spans[0][1])  # keep a merged empty heading with the first block
        result.extend(pack(spans, text, max_tokens, count, split_block))
    return result


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


def chunk(strategy: dict, documents: dict[str, str], tokenizer) -> list[Chunk]:
    """Chunks for every document, in document order."""
    count = tokenizer.count
    chunks = []
    for name, text in documents.items():
        if strategy["kind"] != "structure":
            raise ValueError(f"unknown strategy kind {strategy['kind']!r}")
        spans = structure(text, strategy["max_tokens"], count, tokenizer)
        lines = parse_lines(text)
        for n, (start, end) in enumerate(spans, 1):
            prefix = ""
            if strategy.get("headings"):
                above = [h.text for h in heading_stack(lines, start) if not start <= h.start < end]
                prefix = "\n".join(above) + "\n\n" if above else ""
            body = prefix + text[start:end]
            chunks.append(Chunk(f"{name.removesuffix('.md')}#{n}", name, start, end, prefix, body, count(body)))
    return chunks
