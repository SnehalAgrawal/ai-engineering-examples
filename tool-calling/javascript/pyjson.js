// JSON text in the same format as Python's json.dumps(value, ensure_ascii=False):
// ", " between items and ": " after keys. Tool results are sent to the model as
// text, so both languages must produce exactly the same characters.
export function pyDumps(value) {
  if (value === null || value === undefined) return "null";
  if (Array.isArray(value)) return `[${value.map(pyDumps).join(", ")}]`;
  if (typeof value === "object") {
    return `{${Object.entries(value).map(([k, v]) => `${JSON.stringify(k)}: ${pyDumps(v)}`).join(", ")}}`;
  }
  if (typeof value === "number" && !Number.isInteger(value)) {
    throw new Error("Use integers in the data: Python and JavaScript print some floats differently.");
  }
  return JSON.stringify(value);
}
