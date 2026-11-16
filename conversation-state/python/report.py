"""
The report, from a saved run (runs/python/<out>/): counts and outcomes first, which should match the
JavaScript report exactly, then timings, which vary from run to run.

  python report.py                 # runs/python/main
  python report.py --out smoke

Grades are the mechanical ones (settings: grading.answer) unless data/hand_labels.json has a label for the
answer's SHA-256; both are shown where hand labels exist.
"""
import argparse
import json
import statistics

import chat_template
import context
from common import DATA, RUNS, load, mentions, position_class

GRADES = ("correct", "stale", "both", "other")
FINAL = ("correct", "stale", "both", "not stated", "wrong", "invented")
STRATEGIES = ("1b_full", "3_last_n", "3_token_budget", "3_summary_recent", "3_state_recent")


def spread(values: list, digits: int = 0) -> str:
    """median (minimum to maximum). With digits 0, whole numbers stay whole and a median halfway between two
    is shown with one decimal."""
    vs = [v for v in values if v is not None]
    if not vs:
        return "n/a"

    def fmt(v):
        if digits:
            return f"{v:.{digits}f}"
        return f"{v:.0f}" if float(v).is_integer() else f"{v:.1f}"
    return f"{fmt(statistics.median(vs))} ({fmt(min(vs))} to {fmt(max(vs))})"


def tally(rows: list[dict], key: str = "grade") -> str:
    return ", ".join(f"{g} {sum(r[key] == g for r in rows)}" for g in GRADES)


def rate(rows: list[dict], key: str = "grade") -> str:
    return f"{sum(r[key] == 'correct' for r in rows)} of {len(rows)}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="main")
    args = parser.parse_args()
    data = load()
    convs, prompts = data["conversations"], data["prompts"]
    run = RUNS / args.out
    rows = [json.loads(line) for line in open(run / "requests.jsonl")]
    labels_path = DATA / "hand_labels.json"
    labels = json.loads(labels_path.read_text())["labels"] if labels_path.exists() else {}
    facts = {(c["id"], f["id"]): f for c in convs.values() for f in c["facts"]}
    for r in rows:
        if "fact" in r:
            f = facts[(r["conversation"], r["fact"])]
            r["position"] = position_class(mentions(convs[r["conversation"]], f["accepted"])[-1])
            r["kind"] = "in-schema" if f["field"] != "other" else "other"
            r["changed"] = f["change"]
            r["hand"] = labels.get(f"{r['conversation']}|{r['probe']}|{r.get('output_sha256')}", {}).get("label")
            # The final grade: the hand label where the answer was read, otherwise the mechanical 'correct'
            # (every answer not graded correct is read by hand, so it has a label once labelling is complete).
            r["final"] = r["hand"] or ("correct" if r.get("grade") == "correct" else None)
    by = lambda block, split=None: [r for r in rows if r["block"] == block and (split is None or r["split"] == split)]  # noqa: E731

    print(f"Conversation state: {len(rows)} model calls in runs/python/{args.out}; prompts {prompts['version']}; "
          f"last_n {json.loads((DATA / 'derived.json').read_text())['last_n']}")
    print(f"errors: {sum(bool(r.get('error')) for r in rows)}; requests during which another program was connected to Ollama: "
          f"{sum(bool(r['overlap']) for r in rows)}; hand labels: {len(labels)}")

    print("\nCOUNTS AND OUTCOMES (the same in Python and JavaScript)")
    splits = [s for s in ("test", "dev") if any(r["split"] == s for r in rows)]

    print("\n1a/1b. The model is stateless: the same probes with no history and with the full history (num_ctx 8192)")
    for split in splits:
        for block in ("1a_no_history", "1b_full"):
            if by(block, split):
                print(f"   {split} {block:<14} {tally(by(block, split))}")
                if labels:
                    print("      FINAL: " + ", ".join(f"{g} {sum(r['final'] == g for r in by(block, split))}" for g in FINAL))

    print("\n1c. Growth: tokens sent per turn with the full history")
    sizes = {}
    for cid, c in convs.items():
        per_turn = [chat_template.count([context.system(prompts)] + context.turn_messages(c["turns"][:t - 1])
                                        + [{"role": "user", "content": c["turns"][t - 1]["user"]}]) for t in range(1, 21)]
        sizes[cid] = per_turn
    print(f"   all 12 conversations (counted, no model calls): turn 1 {spread([s[0] for s in sizes.values()])}, "
          f"turn 20 {spread([s[-1] for s in sizes.values()])}; sent over all 20 turns {spread([sum(s) for s in sizes.values()])}, "
          f"{spread([sum(s) / s[-1] for s in sizes.values()], 1)} times the last request")
    growth = by("1c_growth")
    if growth:
        matched = [r for r in growth if r["log"]["evaluated_tokens"] is not None]
        print(f"   measured ({len({r['conversation'] for r in growth})} conversations, {len(growth)} requests): "
              f"app count equal to prompt_eval_count in {sum(r['app_tokens'] == r['prompt_eval_count'] for r in growth)}; "
              f"evaluated tokens found in the log for {len(matched)} (unavailable: {len(growth) - len(matched)})")
        for t in (1, 5, 10, 15, 20):
            ts = [r for r in growth if r["turn"] == t]
            print(f"      turn {t:>2}: sent {spread([r['prompt_eval_count'] for r in ts])}, "
                  f"evaluated {spread([r['log']['evaluated_tokens'] for r in ts])}")
        print(f"      all turns: evaluated / sent {spread([r['log']['evaluated_tokens'] / r['prompt_eval_count'] for r in matched], 2)}")

    two = by("2_full_small")
    if two:
        print("\n2. Past the window: the full history at num_ctx 2048")
        print(f"   sent {spread([r['app_tokens'] for r in two])}; Ollama's prompt_eval_count {spread([r['prompt_eval_count'] for r in two])}; "
              f"errors {sum(bool(r['error']) for r in two)}")
        cut = [r for r in two if r.get("ending_matches") is not None]
        print(f"   requests cut before answering: {len(cut)} of {len(two)}; exactly one matching ending: "
              f"{sum(r['ending_matches'] == 1 for r in cut)}; first turn kept {spread([r['first_kept_turn'] for r in cut])}")
        lost = [r for r in cut if r["in_context"]["current"] and r["in_context_seen"] and not r["in_context_seen"]["current"]]
        print(f"   probes whose current value was sent but not seen: {len(lost)}; correct among them {rate(lost)}")
        seen = [r for r in cut if r["in_context_seen"] and r["in_context_seen"]["current"]]
        print(f"   probes whose current value was seen: {len(seen)}; correct among them {rate(seen)}")
        for split in splits:
            print(f"   {split}: {tally(by('2_full_small', split))}")
            if labels:
                print("      FINAL: " + ", ".join(f"{g} {sum(r['final'] == g for r in by('2_full_small', split))}" for g in FINAL))
        if labels:
            print(f"   FINAL where the current value was sent but not seen: {rate(lost, 'final')}; where it was seen: {rate(seen, 'final')}")
        shifted = [r for r in two if r["log"]["context_shifts"]]
        print(f"   answer length {spread([r['eval_count'] for r in two])} tokens; room left after the prompt "
              f"{spread([2048 - r['prompt_eval_count'] for r in two])} tokens")
        print(f"   requests with a context shift during the answer: {len(shifted)}; tokens discarded "
              f"{spread([s['n_discard'] for r in shifted for s in r['log']['context_shifts']])}; "
              f"truncated = 1 in {sum(r['log']['truncated'] == 1 for r in two)}")

    print("\n3. Strategies (num_ctx 2048; the full history at 8192 for reference)")
    for split in splits:
        print(f"   {split}:")
        for block in STRATEGIES:
            rs = by(block, split)
            if not rs:
                continue
            over = sum(bool(r.get("over_limit")) for r in rs)
            print(f"      {block:<17} {tally(rs)}; prompt tokens {spread([r['app_tokens'] for r in rs])}"
                  + (f"; over the limit {over}" if over else ""))
            print("         by position: " + "; ".join(f"{p} {rate([r for r in rs if r['position'] == p])}" for p in ("early", "middle", "late")))
            print(f"         current value in the context sent: {rate([r for r in rs if r['in_context']['current']])} correct; "
                  f"not in it: {rate([r for r in rs if not r['in_context']['current']])} correct (not answerable from the context)")
            print(f"         in-schema {rate([r for r in rs if r['kind'] == 'in-schema'])}; other {rate([r for r in rs if r['kind'] == 'other'])}; "
                  f"changed facts {rate([r for r in rs if r['changed']])}, stale answers among them {sum(r['grade'] in ('stale', 'both') for r in rs if r['changed'])}")
            if labels:
                print("         FINAL (hand label where read): " + ", ".join(f"{g} {sum(r['final'] == g for r in rs)}" for g in FINAL)
                      + f"; ungraded {sum(r['final'] is None for r in rs)}")
                print("            by position: " + "; ".join(f"{p} {rate([r for r in rs if r['position'] == p], 'final')}" for p in ("early", "middle", "late")))
                print(f"            current value in the context sent: {rate([r for r in rs if r['in_context']['current']], 'final')}; "
                      f"not in it: {rate([r for r in rs if not r['in_context']['current']], 'final')}")
                print(f"            in-schema {rate([r for r in rs if r['kind'] == 'in-schema'], 'final')}; other {rate([r for r in rs if r['kind'] == 'other'], 'final')}; "
                      f"changed facts {rate([r for r in rs if r['changed']], 'final')}, stale or both among them "
                      f"{sum(r['final'] in ('stale', 'both') for r in rs if r['changed'])}")

    for kind, one, block, path in (("summaries", "summary", "summaries", "summaries"), ("case records", "case record", "states", "state")):
        calls = by(block)
        if not calls:
            continue
        print(f"\n3. Maintaining the {kind}")
        per_conv = {}
        for r in calls:
            per_conv.setdefault(r["conversation"], []).append(r)
        print(f"   calls per conversation {spread([len(v) for v in per_conv.values()])}; input tokens per conversation "
              f"{spread([sum(r['app_tokens'] for r in v) for v in per_conv.values()])}; output tokens per conversation "
              f"{spread([sum(r['eval_count'] for r in v) for v in per_conv.values()])}")
        trail = {cid: [json.loads(line) for line in open(run / path / f"{cid}.jsonl")] for cid in per_conv}
        if kind == "summaries":
            print(f"   summaries cut off at the cap: {sum(t['cut_off'] for v in trail.values() for t in v)} of "
                  f"{sum(len(v) for v in trail.values())}; final summaries cut off: {sum(v[-1]['cut_off'] for v in trail.values())} of {len(trail)}")
        else:
            print(f"   outputs that weren't valid JSON: {sum(bool(t['parse_error']) for v in trail.values() for t in v)}")
        for split in splits if kind == "summaries" else []:
            fs = [(cid, f) for cid in trail if convs[cid]["split"] == split for f in convs[cid]["facts"]]
            final = [trail[cid][-1]["output"][f["id"]] for cid, f in fs]
            ever_in = [any(t["input"][f["id"]]["current"] for t in trail[cid]) for cid, f in fs]
            dropped = sum(e and not fin["current"] for e, fin in zip(ever_in, final))
            print(f"   {split}: facts whose current value is in the final {one}: {sum(fin['current'] for fin in final)} of {len(fs)}; "
                  f"with a stale value: {sum(fin['stale'] for fin in final)}; in the input of a summary call but not in the final summary: {dropped}")
        if kind == "case records":
            print("   the record holds order_id, issue, and status only; the three other facts of each conversation aren't in its schema")
            for split in splits:
                for field in ("order_id", "issue", "status"):
                    marks = []
                    for cid in trail:
                        if convs[cid]["split"] != split:
                            continue
                        f = next(x for x in convs[cid]["facts"] if x["field"] == field)
                        value = str(trail[cid][-1]["state"].get(field, ""))
                        stale = [s["value"] for s in f["stale"]]
                        if field == "order_id":
                            cur = any(a.lower() in value.lower() for a in f["accepted"])
                            old = any(a.lower() in value.lower() for s in f["stale"] for a in s["accepted"])
                            marks.append("both" if cur and old else "correct" if cur else "stale" if old else "other")
                        else:
                            marks.append("correct" if value == f["value"] else "stale" if value in stale else "other")
                    print(f"   {split} final {field}: " + ", ".join(f"{g} {marks.count(g)}" for g in GRADES))

    print("\nTIMINGS (vary from run to run; milliseconds; probes after the first in a block reuse Ollama's prompt cache)")
    if growth:
        for t in (1, 5, 10, 15, 20):
            ts = [r for r in growth if r["turn"] == t]
            print(f"   1c turn {t:>2}: prompt evaluation {spread([r['prompt_eval_duration'] / 1e6 for r in ts])}")
    for block in STRATEGIES + ("2_full_small",):
        rs = by(block)
        if rs:
            print(f"   {block:<17} prompt evaluation {spread([r['prompt_eval_duration'] / 1e6 for r in rs if r.get('prompt_eval_duration')])}")
    for block in ("summaries", "states"):
        rs = by(block)
        if rs:
            per = {}
            for r in rs:
                per[r["conversation"]] = per.get(r["conversation"], 0) + r["total_duration"] / 1e6
            print(f"   {block} maintenance per conversation: {spread(list(per.values()))}")


if __name__ == "__main__":
    main()
