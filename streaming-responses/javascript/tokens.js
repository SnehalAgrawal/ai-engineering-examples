// Token counts in the answer model's own tokens (Llama 3.2). Same algorithm as ../python/tokens.py:
// a regular expression splits the text into pieces, each piece is written as bytes, and the bytes are
// merged pairwise by rank, from the model's tokenizer.json. check_tokens.js compares the counts with Ollama's.
//
// The documents and questions are ASCII, so the expression's letter and digit classes (\p{L}, \p{N}) are
// written as [A-Za-z] and [0-9], and its case-insensitive group (?i:'s|'t|...) is spelled out.
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
export const TOKENIZER_PATH = process.env.TOKENIZER_PATH || join(here, "..", "data", "tokenizer.json");

const PATTERN = /'[sS]|'[tT]|'[rR][eE]|'[vV][eE]|'[mM]|'[lL][lL]|'[dD]|[^\r\nA-Za-z0-9]?[A-Za-z]+|[0-9]{1,3}| ?[^\sA-Za-z0-9]+[\r\n]*|\s*[\r\n]+|\s+(?!\S)|\s+/g;

function byteToUnicode() {
  // The byte-level alphabet: every byte gets a printable character (as in GPT-2 and Llama 3).
  const range = (a, b) => Array.from({ length: b - a + 1 }, (_, i) => a + i);
  const printable = [...range(0x21, 0x7e), ...range(0xa1, 0xac), ...range(0xae, 0xff)];
  const codes = [...printable];
  let extra = 0;
  for (let b = 0; b < 256; b++) {
    if (!printable.includes(b)) {
      printable.push(b);
      codes.push(256 + extra);
      extra += 1;
    }
  }
  return new Map(printable.map((b, i) => [b, String.fromCharCode(codes[i])]));
}

const BYTE_TO_UNICODE = byteToUnicode();
const UNICODE_TO_BYTE = new Map([...BYTE_TO_UNICODE].map(([b, c]) => [c, b]));

export class Tokenizer {
  constructor(path = TOKENIZER_PATH) {
    if (!existsSync(path)) {
      console.error(`No tokenizer at ${path}. See the README: Get the tokenizer.`);
      process.exit(1);
    }
    const model = JSON.parse(readFileSync(path, "utf8")).model;
    this.vocab = new Map(Object.entries(model.vocab));
    this.idToToken = new Map([...this.vocab].map(([t, i]) => [i, t]));
    this.ranks = new Map();
    model.merges.forEach((m, rank) => {
      const [a, b] = Array.isArray(m) ? m : m.split(" ");
      this.ranks.set(`${a} ${b}`, rank);
    });
    this.cache = new Map();
  }

  bpe(piece) {
    if (this.vocab.has(piece)) return [this.vocab.get(piece)]; // ignore_merges: a known piece stays whole
    const parts = [...piece];
    while (parts.length > 1) {
      let best = null;
      for (let i = 0; i < parts.length - 1; i++) {
        const rank = this.ranks.get(`${parts[i]} ${parts[i + 1]}`);
        if (rank !== undefined && (best === null || rank < best.rank)) best = { rank, i };
      }
      if (best === null) break;
      parts.splice(best.i, 2, parts[best.i] + parts[best.i + 1]);
    }
    return parts.map((p) => this.vocab.get(p));
  }

  encode(text) {
    if ([...text].some((c) => c.charCodeAt(0) > 127)) throw new Error("tokens.js handles ASCII text only");
    const ids = [];
    for (const piece of text.match(PATTERN) || []) {
      if (!this.cache.has(piece)) {
        const bytes = [...Buffer.from(piece, "utf8")].map((b) => BYTE_TO_UNICODE.get(b)).join("");
        this.cache.set(piece, this.bpe(bytes));
      }
      ids.push(...this.cache.get(piece));
    }
    return ids;
  }

  decode(ids) {
    const bytes = ids.flatMap((i) => [...this.idToToken.get(i)].map((c) => UNICODE_TO_BYTE.get(c)));
    return Buffer.from(bytes).toString("utf8");
  }

  count(text) {
    return this.encode(text).length;
  }
}
