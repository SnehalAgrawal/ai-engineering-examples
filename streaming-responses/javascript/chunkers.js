// Structure chunking with headings, as in rag-engineering. Same behaviour as ../python/chunkers.py, where
// it is described. Every chunk is one slice of one document, document.slice(start, end), exactly as written,
// with the heading lines above the slice copied in front of it.

const HEADING = /^#{1,6} /;

export function parseLines(text) {
  const lines = [];
  let position = 0;
  let inCode = false;
  for (const raw of text.split("\n")) {
    const start = position;
    const end = position + raw.length;
    position = end + 1;
    let kind;
    if (raw.startsWith("```")) {
      kind = "fence";
      inCode = !inCode;
    } else if (inCode) kind = "code";
    else if (raw.trim() === "") kind = "blank";
    else if (HEADING.test(raw)) kind = "heading";
    else kind = "text";
    lines.push({ start, end, text: raw, kind });
  }
  return lines;
}

// Paragraphs, tables, lists, and code blocks: runs of lines between blank lines. A heading is its own block.
export function blocks(lines) {
  const result = [];
  let current = [];
  for (const line of lines) {
    if (line.kind === "blank" || line.kind === "heading") {
      if (current.length) result.push(current);
      current = [];
      if (line.kind === "heading") result.push([line]);
    } else current.push(line);
  }
  if (current.length) result.push(current);
  return result;
}

const level = (line) => line.text.length - line.text.replace(/^#+/, "").length;

// The headings in force at a position: the last heading of each level above it, outermost first.
export function headingStack(lines, position) {
  let stack = [];
  for (const line of lines) {
    if (line.start > position) break;
    if (line.kind === "heading") stack = [...stack.filter((h) => level(h) < level(line)), line];
  }
  return stack;
}

// Join consecutive spans while the joined slice stays within maxTokens; split a span that is too big alone.
function pack(spans, document, maxTokens, count, split) {
  const result = [];
  let current = null;
  for (const span of spans) {
    if (count(document.slice(span[0], span[1])) > maxTokens) {
      if (current) result.push(current);
      current = null;
      result.push(...split(span));
      continue;
    }
    if (current && count(document.slice(current[0], span[1])) <= maxTokens) current = [current[0], span[1]];
    else {
      if (current) result.push(current);
      current = span;
    }
  }
  if (current) result.push(current);
  return result;
}

export function fixed(text, size, overlap, tokenizer) {
  const ids = tokenizer.encode(text);
  const offsets = [0];
  for (const token of ids) offsets.push(offsets[offsets.length - 1] + tokenizer.decode([token]).length);
  const spans = [];
  let start = 0;
  for (;;) {
    const end = Math.min(start + size, ids.length);
    spans.push([offsets[start], offsets[end]]);
    if (end === ids.length) return spans;
    start += size - overlap;
  }
}

export function structure(text, maxTokens, count, tokenizer) {
  const lines = parseLines(text);
  const headings = lines.flatMap((line, i) => (line.kind === "heading" ? [i] : []));
  const starts = [...(headings.length && headings[0] !== 0 ? [0] : []), ...headings];
  const sections = [];
  let pending = null;
  starts.forEach((first, k) => {
    const last = k + 1 < starts.length ? starts[k + 1] : lines.length;
    const content = lines.slice(first, last).filter((line) => line.kind !== "blank");
    const begin = pending !== null ? pending : content[0].start;
    if (content.every((line) => line.kind === "heading")) { // a heading with nothing under it
      pending = begin;
      return;
    }
    sections.push([begin, content[content.length - 1].end, blocks(lines.slice(first, last))]);
    pending = null;
  });

  // A single line over maxTokens: cut it into token windows.
  const splitLine = (span) => fixed(text.slice(span[0], span[1]), maxTokens, 0, tokenizer)
    .map(([a, b]) => [span[0] + a, span[0] + b]);
  const splitBlock = (span) => {
    const blockLines = lines.filter((line) => span[0] <= line.start && line.end <= span[1]);
    return pack(blockLines.map((line) => [line.start, line.end]), text, maxTokens, count, splitLine);
  };

  const result = [];
  for (const [begin, end, sectionBlocks] of sections) {
    if (count(text.slice(begin, end)) <= maxTokens) {
      result.push([begin, end]);
      continue;
    }
    const spans = sectionBlocks.map((b) => [b[0].start, b[b.length - 1].end]);
    spans[0] = [begin, spans[0][1]]; // keep a merged empty heading with the first block
    result.push(...pack(spans, text, maxTokens, count, splitBlock));
  }
  return result;
}

export function cosine(a, b) {
  let dot = 0, na = 0, nb = 0;
  for (let i = 0; i < a.length; i++) dot += a[i] * b[i];
  for (let i = 0; i < a.length; i++) na += a[i] * a[i];
  for (let i = 0; i < b.length; i++) nb += b[i] * b[i];
  return dot / (Math.sqrt(na) * Math.sqrt(nb));
}

// Chunks for every document, in document order.
export function chunk(strategy, documents, tokenizer) {
  const count = (t) => tokenizer.count(t);
  const chunks = [];
  for (const [name, text] of Object.entries(documents)) {
    if (strategy.kind !== "structure") throw new Error(`unknown strategy kind ${strategy.kind}`);
    const spans = structure(text, strategy.max_tokens, count, tokenizer);
    const lines = parseLines(text);
    spans.forEach(([start, end], n) => {
      let prefix = "";
      if (strategy.headings) {
        const above = headingStack(lines, start).filter((h) => !(start <= h.start && h.start < end)).map((h) => h.text);
        prefix = above.length ? `${above.join("\n")}\n\n` : "";
      }
      const body = prefix + text.slice(start, end);
      chunks.push({
        id: `${name.replace(/\.md$/, "")}#${n + 1}`, document: name, start, end, prefix, text: body, tokens: count(body),
      });
    });
  }
  return chunks;
}
