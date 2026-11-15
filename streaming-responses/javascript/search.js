// Keyword search and rank fusion. Same behaviour as ../python/search.py, where each rule is described.
// All rankings break ties by chunk order, so Python and JavaScript rank identically.

const WORD = /[a-z0-9]+/g;
const IDENTIFIER = /[a-z0-9]+(?:[-_./:]+[a-z0-9]+)+/g;

export function analyze(text, analyzer) {
  const lowered = text.toLowerCase();
  const tokens = lowered.match(WORD) || [];
  if (analyzer === "identifiers") tokens.push(...(lowered.match(IDENTIFIER) || []));
  else if (analyzer !== "words") throw new Error(`unknown analyzer ${analyzer}`);
  return tokens;
}

// BM25 as in Lucene: idf = ln(1 + (N - df + 0.5) / (df + 0.5)).
export class BM25 {
  constructor(texts, analyzer, k1, b) {
    Object.assign(this, { analyzer, k1, b });
    this.counts = texts.map((text) => {
      const counts = new Map();
      for (const token of analyze(text, analyzer)) counts.set(token, (counts.get(token) || 0) + 1);
      return counts;
    });
    this.lengths = this.counts.map((c) => [...c.values()].reduce((s, v) => s + v, 0));
    this.averageLength = this.lengths.reduce((s, v) => s + v, 0) / this.lengths.length;
    const df = new Map();
    for (const counts of this.counts) for (const token of counts.keys()) df.set(token, (df.get(token) || 0) + 1);
    const n = texts.length;
    this.idf = new Map([...df].map(([t, d]) => [t, Math.log(1 + (n - d + 0.5) / (d + 0.5))]));
  }

  scores(query) {
    const tokens = analyze(query, this.analyzer);
    return this.counts.map((counts, i) => {
      let score = 0;
      const norm = this.k1 * (1 - this.b + this.b * this.lengths[i] / this.averageLength);
      for (const token of tokens) { // each query token counts once per occurrence
        const tf = counts.get(token) || 0;
        if (tf) score += this.idf.get(token) * tf * (this.k1 + 1) / (tf + norm);
      }
      return score;
    });
  }
}

// Chunk indexes, best first; ties by chunk order. matchedOnly drops chunks with a score of 0.
export function rank(scores, matchedOnly = false) {
  const order = scores.map((_, i) => i).sort((a, b) => scores[b] - scores[a] || a - b);
  return matchedOnly ? order.filter((i) => scores[i] > 0) : order;
}

// Reciprocal rank fusion: each ranking adds 1 / (k + rank) for every chunk in it, rank starting at 1.
export function rrf(rankings, k, size) {
  const fused = new Array(size).fill(0);
  for (const ranking of rankings) ranking.forEach((i, position) => { fused[i] += 1 / (k + position + 1); });
  return fused;
}
