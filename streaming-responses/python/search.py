"""
Keyword search and rank fusion, as in rag-engineering (05-hybrid-search), with the weighted-sum fusion removed.

  keyword   BM25 over the chunk text. The words analyzer turns text into lowercase runs of letters and
            digits ("SSO-104" -> sso, 104); the identifiers analyzer also keeps each identifier whole.
            Only chunks that contain at least one query token are returned.
  hybrid    reciprocal rank fusion (RRF) of the vector ranking and the keyword ranking

All rankings break ties by chunk order, so Python and JavaScript rank identically.
"""
import math
import re

WORD = re.compile(r"[a-z0-9]+")
IDENTIFIER = re.compile(r"[a-z0-9]+(?:[-_./:]+[a-z0-9]+)+")


def analyze(text: str, analyzer: str) -> list[str]:
    lowered = text.lower()
    tokens = WORD.findall(lowered)
    if analyzer == "identifiers":
        tokens += IDENTIFIER.findall(lowered)
    elif analyzer != "words":
        raise ValueError(f"unknown analyzer {analyzer!r}")
    return tokens


class BM25:
    """BM25 as in Lucene: idf = ln(1 + (N - df + 0.5) / (df + 0.5))."""

    def __init__(self, texts: list[str], analyzer: str, k1: float, b: float):
        self.analyzer, self.k1, self.b = analyzer, k1, b
        self.counts = []
        for text in texts:
            counts: dict[str, int] = {}
            for token in analyze(text, analyzer):
                counts[token] = counts.get(token, 0) + 1
            self.counts.append(counts)
        self.lengths = [sum(c.values()) for c in self.counts]
        self.average_length = sum(self.lengths) / len(self.lengths)
        df: dict[str, int] = {}
        for counts in self.counts:
            for token in counts:
                df[token] = df.get(token, 0) + 1
        n = len(texts)
        self.idf = {t: math.log(1 + (n - d + 0.5) / (d + 0.5)) for t, d in df.items()}

    def scores(self, query: str) -> list[float]:
        tokens = analyze(query, self.analyzer)
        result = []
        for counts, length in zip(self.counts, self.lengths):
            score = 0.0
            norm = self.k1 * (1 - self.b + self.b * length / self.average_length)
            for token in tokens:  # each query token counts once per occurrence
                tf = counts.get(token, 0)
                if tf:
                    score += self.idf[token] * tf * (self.k1 + 1) / (tf + norm)
            result.append(score)
        return result


def rank(scores: list[float], matched_only: bool = False) -> list[int]:
    """Chunk indexes, best first; ties by chunk order. matched_only drops chunks with a score of 0."""
    order = sorted(range(len(scores)), key=lambda i: (-scores[i], i))
    return [i for i in order if scores[i] > 0] if matched_only else order


def rrf(rankings: list[list[int]], k: int, size: int) -> list[float]:
    """Reciprocal rank fusion: each ranking adds 1 / (k + rank) for every chunk in it, rank starting at 1."""
    fused = [0.0] * size
    for ranking in rankings:
        for position, i in enumerate(ranking, 1):
            fused[i] += 1 / (k + position)
    return fused
