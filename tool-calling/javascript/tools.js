// The four tools, and the code that decides whether a tool call actually runs.
// Same behaviour as ../python/tools.py: the model only requests a call; this
// code parses and validates the arguments, applies the business rules, and
// only then executes it.
import { readFileSync } from "node:fs";

const dataDir = new URL("../data/", import.meta.url);
const load = (name) => JSON.parse(readFileSync(new URL(name, dataDir), "utf8"));
const toolsFile = load("tools.json");
export const TOOLS = toolsFile.tools;
export const ACTIONS = new Set(toolsFile.actions);
const SCHEMAS = Object.fromEntries(TOOLS.map((t) => [t.function.name, t.function.parameters]));
const DOCUMENTS = load("help_center.json").documents;
const ACCOUNT = load("account.json");

const STOPWORDS = new Set(["a", "an", "and", "are", "can", "do", "does", "for", "how", "i", "if", "in", "is", "it",
  "my", "of", "on", "or", "the", "to", "what", "when", "where", "which", "with", "you", "your"]);

function terms(text) {
  const words = text.toLowerCase().match(/[a-z0-9]+/g) || [];
  return new Set(words.filter((w) => !STOPWORDS.has(w)).map((w) => (w.length > 3 && w.endsWith("s") ? w.slice(0, -1) : w)));
}

// Keyword search: the three entries sharing the most terms with the query (ties keep file order).
export function searchHelpCenter(query) {
  const queryTerms = terms(query);
  const scored = Object.entries(DOCUMENTS).map(([id, text], i) => {
    const docTerms = terms(text);
    return { score: [...queryTerms].filter((t) => docTerms.has(t)).length, i, id };
  });
  return scored.filter((s) => s.score > 0).sort((a, b) => b.score - a.score || a.i - b.i).slice(0, 3)
    .map(({ id }) => ({ id, text: DOCUMENTS[id] }));
}

// Checks the arguments against the tool's JSON schema (the subset the tools use). Returns an error or null.
function validArguments(name, args) {
  const schema = SCHEMAS[name];
  if (typeof args !== "object" || args === null || Array.isArray(args)) return "arguments must be a JSON object";
  const missing = schema.required.filter((k) => !(k in args));
  if (missing.length) return `missing required argument(s): ${missing.join(", ")}`;
  const extra = Object.keys(args).filter((k) => !(k in schema.properties));
  if (extra.length) return `unknown argument(s): ${extra.join(", ")}`;
  for (const [key, value] of Object.entries(args)) {
    if (schema.properties[key].type === "string" && typeof value !== "string") return `argument '${key}' must be a string`;
  }
  return null;
}

const days = (from, to) => Math.round((Date.parse(`${to}T00:00:00Z`) - Date.parse(`${from}T00:00:00Z`)) / 86400000);

// One conversation with the signed-in customer. Tracks refunds so an invoice can't be refunded twice.
export class Session {
  constructor() {
    this.customer = ACCOUNT.customer;
    this.today = ACCOUNT.today;
    this.refunded = new Set();
  }

  run(name, argumentsText) {
    const record = { tool: name, arguments: argumentsText, args: null, executed: false };
    if (!(name in SCHEMAS)) return { ...record, result: { error: `Unknown tool: ${name}` } };
    let args;
    try {
      args = argumentsText.trim() ? JSON.parse(argumentsText) : {};
    } catch {
      return { ...record, result: { error: "Arguments are not valid JSON." } };
    }
    record.args = args;
    const problem = validArguments(name, args);
    if (problem) return { ...record, result: { error: `Invalid arguments: ${problem}.` } };
    const refusal = this.policy(name, args);
    if (refusal) return { ...record, result: { error: refusal } };
    return { ...record, executed: true, result: this.execute(name, args) };
  }

  invoices() {
    return ACCOUNT.invoices.filter((i) => i.customer === this.customer.id);
  }

  // Business rules, enforced in code. Returns why a call is refused, or null.
  policy(name, args) {
    if (name === "issue_refund") {
      const invoice = this.invoices().find((i) => i.id === args.invoice_id);
      // Another customer's invoice gets the same answer as a missing one.
      if (!invoice) return `No invoice ${args.invoice_id} was found for this customer.`;
      if (this.refunded.has(invoice.id)) return `${invoice.id} has already been refunded.`;
      const age = days(invoice.date, this.today);
      if (age > ACCOUNT.refund_window_days) {
        return `${invoice.id} was paid on ${invoice.date}, ${age} days ago. Refunds are only possible within ${ACCOUNT.refund_window_days} days, so it was not refunded.`;
      }
    }
    if (name === "send_email" && args.to.trim().toLowerCase() !== this.customer.email) {
      return "Emails can only be sent to the signed-in customer's own address. Nothing was sent.";
    }
    return null;
  }

  execute(name, args) {
    if (name === "search_help_center") return searchHelpCenter(args.query);
    if (name === "get_invoices") return this.invoices().map(({ id, date, amount, status }) => ({ id, date, amount, status }));
    if (name === "issue_refund") {
      this.refunded.add(args.invoice_id);
      const amount = this.invoices().find((i) => i.id === args.invoice_id).amount;
      return { status: "refunded", invoice_id: args.invoice_id, amount };
    }
    if (name === "send_email") return { status: "sent", to: args.to }; // demo: nothing is actually sent
    throw new Error(name);
  }
}
