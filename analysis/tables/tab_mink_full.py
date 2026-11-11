"""Table tab:mink-full: Min-20% score per ontology, task, open-weight model and format"""
import statistics

from analysis.common import FORMATS, MAKI, ONTOLOGIES, RESULTS, full_rows, load_records, number

TASKS = ["taxonomy", "domain", "range"]
COLUMNS = [(m, f) for m in MAKI for f in FORMATS]


def block_scores(ontology: str, task: str, model: str, fmt: str) -> list[float]:
    """Min-20% score of every block of one run"""
    run = RESULTS / "runs" / "min-k" / f"MK__{ontology.replace(' ', '-')}__{task}__{model}__{fmt}"
    return [r["scores"]["min_20"] for r in load_records(run)]


cells = {}  # (ontology, task or all, model, format) -> mean score of the blocks
for o in ONTOLOGIES:
    for m, f in COLUMNS:
        scores = {t: block_scores(o, t, m, f) for t in TASKS}
        scores["all"] = [s for t in TASKS for s in scores[t]]
        for t, values in scores.items():
            cells[(o, t, m, f)] = round(statistics.mean(values), 9)  # rounded, so equal scores stay equal

if __name__ == "__main__":
    print(full_rows(lambda o, t, column: number(cells[(o, t, *column)]), COLUMNS, TASKS + ["all"]))
