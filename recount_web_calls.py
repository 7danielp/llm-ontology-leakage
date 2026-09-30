"""Rewrite web_searches in finished web runs as the number of completed web tool calls

web_searches used to be 1 if the model used the web at all. It now counts every completed tool call
(search, open_page, find_in_page) once. Runs with one call per request (+web) keep their values, since
there the two are the same. Runs with more calls (+web3) get the real count. The count comes from the
stored web_search_actions, nothing is sent anywhere.

Changes only web_searches (TS), web_searches_normal and web_searches_guided (GP) in records.jsonl and
n_web_searches in summary.json. Every other byte stays as it was, the script checks that before writing.

    uv run python recount_web_calls.py --results-dir results/3-websearches-urbaniot           # shows what would change
    uv run python recount_web_calls.py --results-dir results/3-websearches-urbaniot --write   # writes it
"""
import argparse
import json
from pathlib import Path

FIELDS = {"ts-guessing": [("web_searches", "web_search_actions")],
          "guided-prompting": [("web_searches_normal", "web_search_actions_normal"),
                               ("web_searches_guided", "web_search_actions_guided")]}


def calls(actions: list[dict]) -> int:
    return sum(a.get("status") == "completed" for a in actions or [])


def recount(run: Path, method: str, write: bool) -> tuple[int, int, int]:
    """(records changed, n_web_searches before, after) for one run"""
    text = (run / "records.jsonl").read_text(encoding="utf-8")
    lines = [l for l in text.split("\n") if l.strip()]  # "\n" only, snippets may hold U+2028
    out, changed, total = [], 0, 0
    for line in lines:
        record = json.loads(line)
        if json.dumps(record, ensure_ascii=False) != line:
            raise SystemExit(f"{run.name}: a record would not be written back byte for byte, nothing changed")
        before = [record.get(f) for f, _ in FIELDS[method]]
        for field, actions in FIELDS[method]:
            record[field] = calls(record.get(actions))
            total += record[field]
        changed += before != [record[f] for f, _ in FIELDS[method]]
        out.append(json.dumps(record, ensure_ascii=False))
    summary = json.loads((run / "summary.json").read_text(encoding="utf-8"))
    old_total = summary.get("n_web_searches")
    if write and (changed or old_total != total):
        (run / "records.jsonl").write_text("".join(l + "\n" for l in out), encoding="utf-8")
        summary["n_web_searches"] = total
        (run / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return changed, old_total, total


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--results-dir", type=Path, required=True)
    ap.add_argument("--write", action="store_true", help="write the new counts (default: only show them)")
    args = ap.parse_args()
    n_runs = n_changed = 0
    for method in FIELDS:
        folder = args.results_dir / "runs" / method / "sample-web"
        for run in sorted(p for p in folder.iterdir() if p.is_dir()) if folder.is_dir() else []:
            if not (run / "summary.json").is_file():
                continue
            changed, before, after = recount(run, method, args.write)
            n_runs += 1
            n_changed += changed
            if changed or before != after:
                print(f"  {run.name}: {changed} records changed, n_web_searches {before} -> {after}")
    verb = "changed" if args.write else "would change"
    print(f"{n_runs} web runs checked, {n_changed} records {verb}{'' if args.write else ' (dry run, add --write)'}")


if __name__ == "__main__":
    main()
