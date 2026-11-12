"""
The four tools, and the code that decides whether a tool call actually runs.

The model only *requests* a call: a tool name plus arguments as JSON text.
Everything here is ordinary application code. It parses and validates the
arguments, applies the business rules that the model can't be trusted with,
and only then executes the call.
"""
import json
import re
from datetime import date
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
TOOLS_FILE = json.loads((DATA / "tools.json").read_text())
TOOLS = TOOLS_FILE["tools"]
ACTIONS = set(TOOLS_FILE["actions"])
SCHEMAS = {t["function"]["name"]: t["function"]["parameters"] for t in TOOLS}
DOCUMENTS = json.loads((DATA / "help_center.json").read_text())["documents"]
ACCOUNT = json.loads((DATA / "account.json").read_text())

STOPWORDS = {"a", "an", "and", "are", "can", "do", "does", "for", "how", "i", "if", "in", "is", "it",
             "my", "of", "on", "or", "the", "to", "what", "when", "where", "which", "with", "you", "your"}


def _terms(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {w[:-1] if len(w) > 3 and w.endswith("s") else w for w in words if w not in STOPWORDS}


def search_help_center(query: str) -> list[dict]:
    """Keyword search: the three entries sharing the most terms with the query (ties keep file order)."""
    query_terms = _terms(query)
    scored = [(len(query_terms & _terms(text)), i, doc_id) for i, (doc_id, text) in enumerate(DOCUMENTS.items())]
    best = sorted((s for s in scored if s[0] > 0), key=lambda s: (-s[0], s[1]))[:3]
    return [{"id": doc_id, "text": DOCUMENTS[doc_id]} for _, _, doc_id in best]


def _valid_arguments(name: str, args) -> str | None:
    """Checks the arguments against the tool's JSON schema (the subset the tools use). Returns an error or None."""
    schema = SCHEMAS[name]
    if not isinstance(args, dict):
        return "arguments must be a JSON object"
    missing = [k for k in schema["required"] if k not in args]
    if missing:
        return f"missing required argument(s): {', '.join(missing)}"
    extra = [k for k in args if k not in schema["properties"]]
    if extra:
        return f"unknown argument(s): {', '.join(extra)}"
    for key, value in args.items():
        if schema["properties"][key]["type"] == "string" and not isinstance(value, str):
            return f"argument '{key}' must be a string"
    return None


class Session:
    """One conversation with the signed-in customer. Tracks refunds so an invoice can't be refunded twice."""

    def __init__(self):
        self.customer = ACCOUNT["customer"]
        self.today = date.fromisoformat(ACCOUNT["today"])
        self.refunded: set[str] = set()

    def run(self, name: str, arguments: str) -> dict:
        """
        Handles one tool call the model requested. Returns what happened:
        the parsed arguments, whether the call executed, and the result sent
        back to the model (a result or an error).
        """
        record = {"tool": name, "arguments": arguments, "args": None, "executed": False}
        if name not in SCHEMAS:
            return {**record, "result": {"error": f"Unknown tool: {name}"}}
        try:
            args = json.loads(arguments) if arguments.strip() else {}
        except json.JSONDecodeError:
            return {**record, "result": {"error": "Arguments are not valid JSON."}}
        record["args"] = args
        problem = _valid_arguments(name, args)
        if problem:
            return {**record, "result": {"error": f"Invalid arguments: {problem}."}}
        refusal = self._policy(name, args)
        if refusal:
            return {**record, "result": {"error": refusal}}
        return {**record, "executed": True, "result": self._execute(name, args)}

    def _invoices(self) -> list[dict]:
        return [i for i in ACCOUNT["invoices"] if i["customer"] == self.customer["id"]]

    def _policy(self, name: str, args: dict) -> str | None:
        """Business rules, enforced in code. Returns why a call is refused, or None."""
        if name == "issue_refund":
            invoice = next((i for i in self._invoices() if i["id"] == args["invoice_id"]), None)
            if invoice is None:
                # Another customer's invoice gets the same answer as a missing one.
                return f"No invoice {args['invoice_id']} was found for this customer."
            if invoice["id"] in self.refunded:
                return f"{invoice['id']} has already been refunded."
            age = (self.today - date.fromisoformat(invoice["date"])).days
            if age > ACCOUNT["refund_window_days"]:
                return (f"{invoice['id']} was paid on {invoice['date']}, {age} days ago. Refunds are only "
                        f"possible within {ACCOUNT['refund_window_days']} days, so it was not refunded.")
        if name == "send_email" and args["to"].strip().lower() != self.customer["email"]:
            return "Emails can only be sent to the signed-in customer's own address. Nothing was sent."
        return None

    def _execute(self, name: str, args: dict):
        if name == "search_help_center":
            return search_help_center(args["query"])
        if name == "get_invoices":
            return [{k: i[k] for k in ("id", "date", "amount", "status")} for i in self._invoices()]
        if name == "issue_refund":
            self.refunded.add(args["invoice_id"])
            amount = next(i["amount"] for i in self._invoices() if i["id"] == args["invoice_id"])
            return {"status": "refunded", "invoice_id": args["invoice_id"], "amount": amount}
        if name == "send_email":
            return {"status": "sent", "to": args["to"]}  # demo: nothing is actually sent
        raise ValueError(name)
