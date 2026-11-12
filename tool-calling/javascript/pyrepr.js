// Python's repr() of a string (the common cases), so both languages print identical output.
export function pyRepr(text) {
  if (text === null || text === undefined) return "None";
  const body = text.replace(/\\/g, "\\\\").replace(/\n/g, "\\n").replace(/\t/g, "\\t").replace(/\r/g, "\\r");
  if (text.includes("'") && !text.includes('"')) return `"${body}"`;
  return `'${body.replace(/'/g, "\\'")}'`;
}
