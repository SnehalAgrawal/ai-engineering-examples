"""
The hand-labelling worklist (data/settings.json, grading.by_hand), from a saved run, and a check of
data/hand_labels.json against it. Python only: it reads a run and writes no results.

  python label.py                  # runs/python/main/hand-label-worklist.md
  python label.py --check          # also checks that every required answer has a label

Which answers are read by hand, for every probe block (1a, 1b, 2, and the four strategies of 3):
  1. every answer not graded correct by the mechanical check;
  2. every answer to a status probe;
  3. a random sample of 10 of the remaining correct answers per block (random.Random(20), from the correct
     answers sorted by conversation and probe; all of them if there are fewer than 10).
A request that returned no answer (an error) is listed separately, never dropped.

Labels are keyed by conversation, probe, and the SHA-256 of the answer, because the same text (such as "I
don't have that information.") can answer different probes. Labels:
  correct     gives the current value (for status: the latest status, as the current one)
  stale       gives an earlier value as the current one
  both        gives the current and an earlier value without saying which is current
  not stated  says it doesn't have the information
  wrong       gives another value from the conversation
  invented    gives a value the conversation doesn't contain
"""
import argparse
import json
import random

from common import DATA, RUNS, load

BLOCKS = ("1a_no_history", "1b_full", "2_full_small", "3_last_n", "3_token_budget", "3_summary_recent", "3_state_recent")
LABELS = ("correct", "stale", "both", "not stated", "wrong", "invented")


def key(r: dict) -> str:
    return f"{r['conversation']}|{r['probe']}|{r['output_sha256']}"


def worklist(rows: list[dict]) -> tuple[list[tuple[str, dict]], list[dict]]:
    items, failed = [], []
    for block in BLOCKS:
        rs = sorted((r for r in rows if r["block"] == block), key=lambda r: (r["conversation"], r["probe"]))
        failed += [r for r in rs if r.get("output_sha256") is None]
        answered = [r for r in rs if r.get("output_sha256") is not None]
        for r in answered:
            if r["grade"] != "correct":
                items.append(("not graded correct", r))
            elif r["fact"] == "status":
                items.append(("status probe", r))
        rest = [r for r in answered if r["grade"] == "correct" and r["fact"] != "status"]
        for r in sorted(random.Random(20).sample(rest, min(10, len(rest))), key=lambda r: (r["conversation"], r["probe"])):
            items.append(("sample of correct answers", r))
    return items, failed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="main")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    data = load()
    convs = data["conversations"]
    run = RUNS / args.out
    rows = [json.loads(line) for line in open(run / "requests.jsonl")]
    items, failed = worklist(rows)
    summaries = {p.stem: [json.loads(line) for line in open(p)][-1]["summary"] for p in (run / "summaries").glob("*.jsonl")}
    states = {p.stem: [json.loads(line) for line in open(p)][-1]["state"] for p in (run / "state").glob("*.jsonl")}

    groups: dict[str, list[tuple[str, dict]]] = {}
    for reason, r in items:
        groups.setdefault(key(r), []).append((reason, r))
    lines = [f"# Hand-label worklist: runs/python/{args.out}", "",
             f"{len(groups)} answers to label: one entry per key (conversation, probe, answer SHA-256), with every block "
             f"in which that answer was selected ({len(items)} selections in all). Label each entry once. "
             f"{len(failed)} requests without an answer are listed at the end.", "",
             "Labels: " + ", ".join(LABELS) + ". For status, the answer must give the latest status as the current one.", ""]
    for k, occurrences in groups.items():
        r0 = occurrences[0][1]
        c = convs[r0["conversation"]]
        f = next(x for x in c["facts"] if x["id"] == r0["fact"])
        q = next(p for p in c["probes"] if p["id"] == r0["probe"])
        answer = (run / "texts" / f"{r0['output_sha256']}.txt").read_text()
        lines += [f"## {k}", "",
                  f"- probe ({r0['fact']}, {f['field']}, change {f['change']}): {q['question']}",
                  f"- current: {f['value']} {f['accepted']}; stale: {[(s['value'], s['accepted']) for s in f['stale']]}",
                  f"- selected in {len(occurrences)} block(s):"]
        for reason, r in occurrences:
            evidence = [f"current value in the context sent: {r['in_context']['current']}, stale: {r['in_context']['stale']}"]
            if r.get("over_limit"):
                evidence.append(f"over prompt_limit ({r['app_tokens']} tokens)")
            if r["block"] == "2_full_small":
                evidence.append(f"Ollama kept from turn {r.get('first_kept_turn')}; current value seen: "
                                f"{(r.get('in_context_seen') or {}).get('current')}; context shifts: {r['log']['context_shifts']}; "
                                f"truncated: {r['log']['truncated']}")
            if r["block"] == "3_summary_recent":
                evidence.append(f"final summary: {summaries.get(r['conversation'])!r}")
            if r["block"] == "3_state_recent":
                evidence.append(f"final case record: {json.dumps(states.get(r['conversation']))}")
            lines.append(f"   - {r['block']}, {r['split']}, {reason}; mechanical grade: {r['grade']}; " + "; ".join(evidence))
        lines += ["", "```text", answer, "```", ""]
    if failed:
        lines += ["## Requests without an answer", ""]
        lines += [f"- {r['block']} {r['conversation']} {r['probe']}: {r.get('error')}" for r in failed]
    (run / "hand-label-worklist.md").write_text("\n".join(lines) + "\n")
    print(f"{len(groups)} answers to label ({len(items)} selections), {len(failed)} without an answer; wrote {(run / 'hand-label-worklist.md').relative_to(RUNS.parent.parent)}")

    if args.check:
        path = DATA / "hand_labels.json"
        labels = json.loads(path.read_text())["labels"] if path.exists() else {}
        missing = sorted({key(r) for _, r in items} - set(labels))
        bad = sorted(k for k, v in labels.items() if v.get("label") not in LABELS)
        print(f"labels: {len(labels)}; required but missing: {len(missing)}; with an unknown label: {len(bad)}")
        for k in missing[:20] + bad[:20]:
            print(f"   {k}")
        raise SystemExit(1 if missing or bad else 0)


if __name__ == "__main__":
    main()
