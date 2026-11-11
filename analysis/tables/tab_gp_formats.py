"""Table tab:gp-formats: Guided Prompting gap and share of identical answers per model and identifier format"""
import collections
import statistics

from analysis.common import FORMATS, MODELS, ONTOLOGIES, RESULTS, TASKS, load_records, number, read_aggregate

run_gap = {(r["ontology"], r["task"], r["model"], r["id_format"]): float(r["gap"])
           for r in read_aggregate("gp_aggregate.csv") if r["measure"] == "wup" and r["segment"] == "all"}

# questions whose normal and guided answer are the same text
identical, questions = collections.Counter(), collections.Counter()
for run_dir in (RESULTS / "runs" / "guided-prompting").glob("GP__*"):
    _, _, _, model, fmt = run_dir.name.split("__")
    for r in load_records(run_dir):
        questions[(model, fmt)] += 1
        identical[(model, fmt)] += r["raw_normal"].strip() == r["raw_guided"].strip()

for m in MODELS:
    gaps = [statistics.mean(run_gap[(o, t, m, f)] for o in ONTOLOGIES for t in TASKS) for f in FORMATS]
    shares = [identical[(m, f)] / questions[(m, f)] for f in FORMATS]
    print(f"{m} & " + " & ".join(number(x, signed=True) for x in gaps) + " & " + " & ".join(number(x) for x in shares) + r" \\")
