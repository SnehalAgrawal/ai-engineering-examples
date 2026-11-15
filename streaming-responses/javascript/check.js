// Article #18's value check, and the sentence splitter that experiment 4's sentence gate uses. Same behaviour
// as ../python/check.py, where both are described; normalize, contains, and values are copied from
// production-ai-patterns/01-reliable-llm-pipeline/javascript/steps.js unchanged.

export function normalize(text) {
  return text.toLowerCase().replace(/’|‘/g, "'").replace(/“|”/g, '"')
    .replace(/–|—/g, "-")
    .replace(/(?<=\d),(?=\d{3}\b)/g, "")
    .replace(/\s+/g, " ");
}

const escape = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

// The phrase appears in the text as a whole word or phrase: no letter or digit directly before or after.
export function contains(text, phrase) {
  return new RegExp(`(?<![a-z0-9])${escape(normalize(phrase).trim())}(?![a-z0-9])`).test(normalize(text));
}

const EMAIL_ADDRESS = /[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+/g;
const CODE = /\b[A-Z][A-Z0-9]*-[0-9]+\b/g;
const SNAKE = /\b[a-z0-9]+(?:_[a-z0-9]+)+\b/g;
const NUMBER = /[A-Za-z]*[0-9]+(?:[.,][0-9]+)*[A-Za-z]*/g; // a word with digits, whole: "16th", "SHA256", "v2"

// The values a text states. Citation markers such as [2] and list numbers at the start of a line are not values.
export function values(reply) {
  let text = reply.replace(/\[[0-9]+(?:\s*,\s*[0-9]+)*\]/g, " ").replace(/^\s*[0-9]+[.)]\s/gm, " ");
  const found = [];
  for (const pattern of [EMAIL_ADDRESS, CODE, SNAKE]) {
    found.push(...(text.match(pattern) || []));
    text = text.replace(pattern, " ");
  }
  found.push(...(text.match(NUMBER) || []).map((n) => n.replace(/(?<=[0-9]),(?=[0-9]{3}\b)/g, "")));
  return [...new Set(found)];
}

// The values in the text that appear in none of the references.
export const flagged = (text, references) => values(text).filter((v) => !references.some((r) => contains(r, v)));

const LIST_NUMBER = /^\s*[0-9]+$/;

// Splits streamed text into sentences as it arrives. Joining the sentences gives back the text exactly.
export class Sentences {
  constructor() {
    this.pending = "";
  }

  feed(text) {
    this.pending += text;
    const sentences = [];
    for (;;) {
      const end = this.boundary();
      if (end === null) return sentences;
      sentences.push(this.pending.slice(0, end));
      this.pending = this.pending.slice(end);
    }
  }

  // Whatever is left when the stream ends is the last sentence.
  finish() {
    const rest = this.pending;
    this.pending = "";
    return rest ? [rest] : [];
  }

  // The end (exclusive) of the first complete sentence in the pending text, or null if there isn't one yet.
  boundary() {
    const text = this.pending;
    for (let i = 0; i < text.length; i++) {
      const c = text[i];
      if (c === "\n") return i + 1;
      if (".!?".includes(c)) {
        if (i + 1 === text.length) return null; // the next character decides; wait for more text
        if (!/\s/.test(text[i + 1])) continue;
        const lineStart = text.lastIndexOf("\n", i - 1) + 1;
        if (c === "." && LIST_NUMBER.test(text.slice(lineStart, i))) continue;
        return i + 1;
      }
    }
    return null;
  }
}
