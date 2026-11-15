"""
The report, from a saved run (runs/python/<out>/requests.jsonl) and step 0 (runs/python/step0.json).

The first part holds counts and outcomes, which Python and JavaScript should produce identically. The second
part holds timings, which vary from run to run and between the languages.

  python report.py            # runs/python/main
  python report.py --out smoke
"""
import argparse
import json
from collections import Counter

from common import RUNS

EXPERIMENT_MODES = {"1": ["non-streaming", "streaming"], "2": ["pass-through", "buffer-all", "buffer-4096"],
                    "3": ["ignore", "cancel"], "4": ["check-whole", "stream-then-check", "sentence-gate"]}


def median(values: list[float]) -> float:
    ordered = sorted(values)
    n = len(ordered)
    return ordered[n // 2] if n % 2 else (ordered[n // 2 - 1] + ordered[n // 2]) / 2


def spread(values: list[float]) -> str:
    """median (minimum to maximum), in seconds"""
    values = [v for v in values if v is not None]
    if not values:
        return "n/a"
    return f"{median(values):.2f} ({min(values):.2f} to {max(values):.2f})"


def seconds(record: dict, key: str) -> float | None:
    """A client timestamp as seconds after t_start."""
    t = record["client"].get(key)
    return None if t is None else (t - record["client"]["t_start"]) / 1000


def server_seconds(record: dict, key: str) -> float | None:
    t = record["server"].get(key)
    return None if t is None else (t - record["client"]["t_start"]) / 1000


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="main")
    args = parser.parse_args()
    lines = [json.loads(line) for line in (RUNS / args.out / "requests.jsonl").read_text().splitlines()]
    by = {}
    for r in lines:
        by.setdefault((r["experiment"], r["mode"]), []).append(r)
    step0_path = RUNS / "step0.json"
    step0 = json.loads(step0_path.read_text()) if step0_path.exists() else None

    print(f"Streaming responses: {len(lines)} requests")
    print("Step 0, reading Ollama's log:", "not run" if step0 is None else "passed" if step0["passed"] else "FAILED")

    # ------------------------------------------------------------------------------------------------ counts
    print("\nCOUNTS AND OUTCOMES (the same in Python and JavaScript)")
    complete = [r for r in lines if r["experiment"] != "3" or r["mode"] == "ignore"]
    texts = {}
    for r in complete:
        texts.setdefault(r["email"], set()).add(r["server"]["generated_sha256"])
    print(f"emails whose generated reply was the same in every complete request: "
          f"{sum(len(s) == 1 for s in texts.values())} of {len(texts)}")
    overlap = [r for r in lines if r["overlap"]]
    print(f"requests during which another program was connected to Ollama: {len(overlap)}")
    for r in overlap:  # flagged, not dropped: their timings may be distorted
        print(f"   {r['experiment']}|{r['mode']}|{r['email']}: {', '.join(r['overlap'])}")

    if ("1", "streaming") in by:
        print("\n1. What the user waits for")
        for mode in EXPERIMENT_MODES["1"]:
            print(f"   {mode}: {len(by[('1', mode)])} requests")

    if ("2", "buffer-all") in by:
        print("\n2. Where streams get stuck")
        for mode in EXPERIMENT_MODES["2"]:
            rs = by[("2", mode)]
            if mode == "buffer-all":
                print(f"   {mode}: {len(rs)} requests, {sum(r['proxy']['writes'] == 1 for r in rs)} delivered in one write")
            else:
                print(f"   {mode}: {len(rs)} requests")

    if ("3", "cancel") in by:
        print("\n3. When the user leaves")
        for mode in EXPERIMENT_MODES["3"]:
            rs = by[("3", mode)]
            print(f"   {mode}: {len(rs)} requests; the client closed after 20 text events in "
                  f"{sum(r['client']['t_closed'] is not None for r in rs)} of them; log matched to one task: "
                  f"{sum(r['log']['task'] is not None for r in rs)}; 'cancel task' line: "
                  f"{sum(r['log']['cancelled'] for r in rs)}; app server stopped reading: {sum(r['server']['cancelled'] for r in rs)}")
        full = {r["email"]: r["server"]["ollama"]["eval_count"] for r in by.get(("1", "streaming"), [])}
        ignore = by[("3", "ignore")]
        if full:
            # Step 0 found the log's estimate one below eval_count for completed requests (the last token isn't
            # counted at the slot's release), so a request that ran to the end shows eval_count - 1.
            same = sum(r["log"].get("generated_estimate") == full.get(r["email"], 0) - 1 for r in ignore)
            print(f"   ignore: estimated tokens generated equal to the completed reply's eval_count - 1 (as in step 0): "
                  f"{same} of {len(ignore)}")

    if ("4", "sentence-gate") in by:
        print("\n4. Streaming and checks")
        flagged = {}
        for mode in EXPERIMENT_MODES["4"]:
            rs = by[("4", mode)]
            outcomes = Counter(r["client"]["outcome"] for r in rs)
            shown = sum(len(r["client"]["visible_text"]) for r in rs)
            print(f"   {mode}: " + ", ".join(f"{k} {outcomes[k]}" for k in ("passed", "withheld", "retracted") if outcomes[k])
                  + f"; characters left visible in total: {shown}")
            flagged[mode] = {r["email"] for r in rs if r["client"]["outcome"] != "passed"}
        gate = by[("4", "sentence-gate")]
        print(f"   sentence-gate: sentences sent {sum(r['server']['sentences_sent'] for r in gate)}, characters held back "
              f"{sum(r['server']['chars_held_back'] for r in gate)}")
        whole, sentence = flagged["check-whole"], flagged["sentence-gate"]
        print(f"   emails flagged: check-whole {len(whole)}, stream-then-check {len(flagged['stream-then-check'])}, "
              f"sentence-gate {len(sentence)}; flagged by both whole-reply and sentence checks {len(whole & sentence)}; "
              f"only whole {sorted(whole - sentence)}; only sentence {sorted(sentence - whole)}")

    # ------------------------------------------------------------------------------------------------ timings
    print("\nTIMINGS (seconds after the client sent the request; median (minimum to maximum); vary from run to run)")
    if ("1", "streaming") in by:
        print("\n1. What the user waits for")
        for mode in EXPERIMENT_MODES["1"]:
            rs = by[("1", mode)]
            print(f"   {mode:<14} first text {spread([seconds(r, 't_first_text') for r in rs])}, "
                  f"done {spread([seconds(r, 't_done') for r in rs])}")
        stream = {r["email"]: r for r in by[("1", "streaming")]}
        sooner = [seconds(r, "t_first_text") - seconds(stream[r["email"]], "t_first_text") for r in by[("1", "non-streaming")]]
        print(f"   first words sooner with streaming, per email: {spread(sooner)}")
        rs = by[("1", "streaming")]
        print(f"   streaming: app server received the request {spread([server_seconds(r, 't_received') for r in rs])}, "
              f"first model token {spread([server_seconds(r, 't_model_first') for r in rs])}, "
              f"post-model delay {spread([seconds(r, 't_first_text') - server_seconds(r, 't_model_first') for r in rs])}")

    if ("2", "buffer-all") in by:
        print("\n2. Where streams get stuck")
        for mode in EXPERIMENT_MODES["2"]:
            rs = by[("2", mode)]
            print(f"   {mode:<13} first text {spread([seconds(r, 't_first_text') for r in rs])}, first model token "
                  f"{spread([server_seconds(r, 't_model_first') for r in rs])}, post-model delay "
                  f"{spread([seconds(r, 't_first_text') - server_seconds(r, 't_model_first') for r in rs])}, "
                  f"done {spread([seconds(r, 't_done') for r in rs])}, proxy writes {spread([r['proxy']['writes'] for r in rs])}")

    if ("3", "cancel") in by:
        print("\n3. When the user leaves")
        full = {r["email"]: r["server"]["ollama"]["eval_count"] for r in by.get(("1", "streaming"), [])}
        for mode in EXPERIMENT_MODES["3"]:
            rs = by[("3", mode)]
            detected = [(r["server"]["t_write_failed"] - r["client"]["t_closed"]) / 1000
                        for r in rs if r["server"]["t_write_failed"] is not None]
            print(f"   {mode}: disconnect detected after {spread(detected)} ({len(detected)} of {len(rs)} detected); "
                  f"upstream text events after it {spread([r['server']['upstream_events_after_disconnect'] for r in rs])}; "
                  f"estimated tokens generated (Ollama log) {spread([r['log'].get('generated_estimate') for r in rs])}; "
                  f"completed reply for the same emails {spread([full.get(r['email']) for r in rs])}")

    if ("4", "sentence-gate") in by:
        print("\n4. Streaming and checks")
        for mode in EXPERIMENT_MODES["4"]:
            rs = by[("4", mode)]
            print(f"   {mode:<17} first text {spread([seconds(r, 't_first_text') for r in rs])}, "
                  f"done {spread([seconds(r, 't_done') for r in rs])}")
        retracted = [r for r in by[("4", "stream-then-check")] if r["client"]["outcome"] == "retracted"]
        visible = [(r["client"]["t_retracted"] - r["client"]["t_flagged_visible"]) / 1000
                   for r in retracted if r["client"].get("t_flagged_visible") is not None]
        print(f"   stream-then-check: a flagged value was on screen before the retraction for {spread(visible)} "
              f"({len(visible)} of {len(retracted)} retracted replies)")


if __name__ == "__main__":
    main()
