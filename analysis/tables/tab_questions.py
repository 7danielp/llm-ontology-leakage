"""Table tab:questions: questions and Min-K% axiom lines per ontology and task"""
from analysis.common import ONTOLOGIES, RESULTS, SHORT, TASKS, TIERS, load_records

MINK_TASKS = ["taxonomy", "domain", "range"]


def count(method: str, prefix: str, ontology: str, task: str, field: str | None = None) -> int:
    """Number of records, or the sum of a field over them, the same in every run of an ontology and task"""
    found = set()
    for run_dir in (RESULTS / "runs" / method).glob(f"{prefix}__{ontology.replace(' ', '-')}__{task}__*"):
        records = load_records(run_dir)
        found.add(sum(r[field] for r in records) if field else len(records))
    assert len(found) == 1, (method, ontology, task, found)
    return found.pop()


counts = {}  # ontology -> questions per task, then axiom lines per Min-K% task
for o in ONTOLOGIES:
    questions = [count("ts-guessing", "TS", o, t) for t in TASKS]
    assert questions == [count("guided-prompting", "GP", o, t) for t in TASKS], o  # same questions in both methods
    counts[o] = questions + [count("min-k", "MK", o, t, "n_axioms") for t in MINK_TASKS]

for tier, ontologies in TIERS.items():
    print(rf"\rowcolor{{tierrow}}\multicolumn{{8}}{{l}}{{\textbf{{{tier}}}}} \\")
    for o in ontologies:
        print(rf"\quad {SHORT.get(o, o)} & " + " & ".join(f"{n:,}" for n in counts[o]) + r" \\")
print(r"\midrule")
columns = len(TASKS) + len(MINK_TASKS)
print(r"\textbf{All} & " + " & ".join(f"{sum(c[i] for c in counts.values()):,}" for i in range(columns)) + r" \\")
