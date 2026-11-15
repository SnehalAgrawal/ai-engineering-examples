"""
Checks the frozen inputs before anything uses them, and prints where each fact sits in its conversation.

  python check_data.py
  python check_data.py --derive    # also computes N for last_n and writes data/derived.json

1. Every frozen file matches the SHA-256 in data/README.md.
2. Every conversation follows data/settings.json: 20 turns; a size between 2,500 and 3,400 tokens, rendered
   with the chat template (and the system prompt, once data/prompts.json exists); six facts (order_id,
   issue, status, three others) with issue and status values from the schema's lists; current and stale
   forms of a fact, and the forms of different facts, never overlapping; every value mentioned; one probe per
   fact, which doesn't contain the fact's values.
3. Fact positions, computed by the matching rule (inputs.position): the last turn that mentions the current
   value, and the turns that mention each stale value.

4. With --derive: N for the last_n strategy (settings: strategies.last_n), the largest N whose request fits
   prompt_limit for every probe of every dev conversation, counted with the frozen prompts. It requires the
   frozen prompts and a passed step 0 (the token counts were checked against Ollama's), and it never looks at
   a test conversation.

Exits with status 1 if any check fails.
"""
import hashlib
import json
import re
import sys

import chat_template
import context
from common import DATA, RUNS, appears, load, mentions, position_class


def frozen_hashes() -> dict[str, str]:
    """The table of file names and SHA-256 hashes in data/README.md."""
    rows = re.findall(r"^\| ([\w./-]+\.json) \| `([0-9a-f]{64})` \|$", (DATA / "README.md").read_text(), re.M)
    return dict(rows)


def transcript(conversation: dict, system: str | None) -> list[dict]:
    messages = [{"role": "system", "content": system}] if system else []
    for t in conversation["turns"]:
        messages += [{"role": "user", "content": t["user"]}, {"role": "assistant", "content": t["assistant"]}]
    return messages


def forms(fact: dict) -> list[str]:
    return fact["accepted"] + [f for s in fact["stale"] for f in s["accepted"]]


def overlap(a: list[str], b: list[str]) -> bool:
    return any(appears(x, b) for x in a) or any(appears(x, a) for x in b)


def check_conversation(c: dict, settings: dict, system: str | None) -> list[str]:
    problems = []
    schema = settings["state_schema"]["json_schema"]["properties"]
    if any(ord(ch) > 126 for t in c["turns"] for ch in t["user"] + t["assistant"]):
        problems.append("a message has a non-ASCII character")
    if len(c["turns"]) != 20:
        problems.append(f"{len(c['turns'])} turns, not 20")
    size = chat_template.count(transcript(c, system))
    if not 2500 <= size <= 3400:
        problems.append(f"size {size} tokens, outside 2,500 to 3,400")
    fields = sorted(f["field"] for f in c["facts"])
    if fields != sorted(["order_id", "issue", "status", "other", "other", "other"]):
        problems.append(f"facts are {fields}")
    for f in c["facts"]:
        if not mentions(c, f["accepted"]):
            problems.append(f"{f['id']}: the current value is never mentioned")
        for s in f["stale"]:
            if not mentions(c, s["accepted"]):
                problems.append(f"{f['id']}: the stale value {s['value']!r} is never mentioned")
            if overlap(f["accepted"], s["accepted"]):
                problems.append(f"{f['id']}: current and stale forms overlap")
        if f["change"] and not f["stale"]:
            problems.append(f"{f['id']}: changed, but no stale value")
        if f["field"] in ("issue", "status"):
            for v in [f["value"]] + [s["value"] for s in f["stale"]]:
                if v not in schema[f["field"]]["enum"]:
                    problems.append(f"{f['id']}: {v!r} is not in the schema's {f['field']} list")
    for i, a in enumerate(c["facts"]):
        for b in c["facts"][i + 1:]:
            if overlap(forms(a), forms(b)):
                problems.append(f"the forms of {a['id']} and {b['id']} overlap")
    facts = {f["id"]: f for f in c["facts"]}
    if sorted(p["fact"] for p in c["probes"]) != sorted(facts):
        problems.append("the probes don't cover each fact exactly once")
    for p in c["probes"]:
        if appears(p["question"], forms(facts[p["fact"]])):
            problems.append(f"{p['id']}: the question contains a value of its fact")
    return problems


def derive(data: dict) -> dict:
    prompts, settings = data["prompts"], data["settings"]
    if not prompts or not prompts["version"].endswith("frozen"):
        raise SystemExit("--derive needs the frozen prompts")
    step0 = RUNS / "step0.json"
    if not step0.exists() or not json.loads(step0.read_text())["passed"]:
        raise SystemExit("--derive needs a passed step 0 (python step0.py)")
    limit = settings["context"]["small_window"]["prompt_limit"]
    dev = [c for c in data["conversations"].values() if c["split"] == "dev"]
    largest = {n: max(chat_template.count(context.last_n(prompts, c, p["question"], n)) for c in dev for p in c["probes"])
               for n in range(1, 21)}
    n = max(k for k, size in largest.items() if size <= limit)
    return {"last_n": n, "rule": "the largest N whose request fits prompt_limit for every probe of every dev conversation",
            "prompt_limit": limit, "prompts_version": prompts["version"], "conversations": [c["id"] for c in dev],
            "largest_request_by_n": largest}


def main() -> None:
    data = load()
    failed = False
    for name, expected in frozen_hashes().items():
        actual = hashlib.sha256((DATA / name).read_bytes()).hexdigest()
        if actual != expected:
            print(f"CHANGED since the freeze: {name}")
            failed = True
    if not frozen_hashes():
        print("no hashes found in data/README.md")
        failed = True
    system = data["prompts"]["system"] if data["prompts"] else None
    print("sizes rendered with the chat template" + (" and the system prompt" if system else
          " (no system prompt yet: data/prompts.json doesn't exist)"))
    for cid, c in data["conversations"].items():
        size = chat_template.count(transcript(c, system))
        print(f"\n{cid} ({c['split']}), {size} tokens")
        for f in c["facts"]:
            turns = mentions(c, f["accepted"])
            where = f"{position_class(turns[-1])} (turn {turns[-1]})" if turns else "never mentioned"
            stale = "; ".join(f"{s['value']!r} in turns {mentions(c, s['accepted'])}" for s in f["stale"])
            print(f"   {f['id']:<12} {f['field']:<9} {f['change'] or '-':<11} {f['value']!r}: {where}"
                  + (f"; stale {stale}" if stale else ""))
        for problem in check_conversation(c, data["settings"], system):
            print(f"   PROBLEM: {problem}")
            failed = True
    if "--derive" in sys.argv and not failed:
        derived = derive(data)
        (DATA / "derived.json").write_text(json.dumps(derived, indent=2) + "\n")
        print(f"\nN for last_n: {derived['last_n']} (largest dev request {derived['largest_request_by_n'][derived['last_n']]} "
              f"tokens; {derived['last_n'] + 1} turns would need {derived['largest_request_by_n'].get(derived['last_n'] + 1)}); "
              "wrote data/derived.json")
    print("\nall checks passed" if not failed else "\nSOME CHECKS FAILED")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
