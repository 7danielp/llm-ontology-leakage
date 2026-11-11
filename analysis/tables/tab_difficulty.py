"""Table tab:difficulty: difficulty of the questions per ontology and task, without any model answer"""
import collections
import statistics
from pathlib import Path

from analysis.common import (MODELS, ONTOLOGIES, RESULTS, SHORT, TASKS, TIERS, golds_outside, iri_name, load_records, name_inferable,
                    number, outside_namespace)

# column groups of the table, the property task only under name-inferable
COLUMNS = [("name-inferable", TASKS)] + [(m, TASKS[:3]) for m in ("most frequent gold", "different golds", "outside")]
BOLD = 0.5  # table values from 0.50 on in bold


def run_dir(ontology: str, task: str) -> Path:
    """TS-Guessing run of the first model in the plain format, every run has the same questions"""
    return RESULTS / "runs" / "ts-guessing" / f"TS__{ontology.replace(' ', '-')}__{task}__{MODELS[0]}__plain"


def count_measures(records: list[dict], namespace: str) -> dict:
    """Counts behind the measures of one task, golds by local name, marked (outside) outside the namespace"""
    gold_counts = collections.Counter(g for r in records for g in set(r["gold_iris"]))  # each gold once per question
    k = max(gold_counts.values())

    def label(gold: str) -> str:
        return iri_name(gold) + ("" if gold.startswith(namespace) else " (outside)")

    most_frequent = sorted(label(g) for g, c in gold_counts.items() if c == k)
    next_two = sorted((g for g, c in gold_counts.items() if c < k), key=lambda g: (-gold_counts[g], label(g)))[:2]
    return {"n": len(records),
            "inferable": sum(name_inferable(r) for r in records),
            "different": len(gold_counts),
            "k": k,
            "most frequent": most_frequent if len(most_frequent) <= 4 else [f"{len(most_frequent)} golds tied"],
            "next": [(label(g), gold_counts[g]) for g in next_two],
            "outside": sum(golds_outside(r, namespace) for r in records)}


def value(c: dict, measure: str) -> float:
    """Table value of a measure, a count divided by the number of questions"""
    key = {"name-inferable": "inferable", "most frequent gold": "k", "different golds": "different", "outside": "outside"}[measure]
    return c[key] / c["n"]


def entry(v: float) -> str:
    """Table value with two decimals, bold from BOLD on"""
    return rf"\textbf{{{number(v)}}}" if round(v, 2) >= BOLD else number(v)


def given_in_gold(record: dict) -> bool:
    """Name of the given class inside the name of a gold property, as Game in gameItem"""
    return any(name_inferable({"given_iri": g, "gold_iris": [record["given_iri"]]}) for g in record["gold_iris"])


counts = {(o, t): count_measures(load_records(run_dir(o, t)), outside_namespace(run_dir(o, t))) for o in ONTOLOGIES for t in TASKS}

for tier, ontologies in TIERS.items():
    print(rf"\rowcolor{{tierrow}}\multicolumn{{14}}{{l}}{{\textbf{{{tier}}}}} \\")
    for o in ontologies:
        print(rf"\quad {SHORT.get(o, o)} & " + " & ".join(entry(value(counts[(o, t)], m)) for m, tasks in COLUMNS for t in tasks) + r" \\")

for o in ONTOLOGIES:
    for t in TASKS:
        c = counts[(o, t)]
        next_two = "".join(f", then {name} {n}" for name, n in c["next"])
        print(f"% {SHORT.get(o, o)} {t}: n {c['n']}; inferable {c['inferable']}; different {c['different']}; "
              f"k {c['k']} ({'/'.join(c['most frequent'])}{next_two}); outside {c['outside']}")

for m, tasks in COLUMNS:
    print(f"% tier means, {m}: " + "; ".join(
        f"{tier} " + " ".join(number(statistics.mean(value(counts[(o, t)], m) for o in ontologies)) for t in tasks)
        for tier, ontologies in TIERS.items()))

parts = []
for o in ONTOLOGIES:
    records = load_records(run_dir(o, "property"))
    n = sum(map(given_in_gold, records))
    parts.append(f"{SHORT.get(o, o)} {n} of {len(records)} ({number(n / len(records))})")
print("% given name inside a gold, property task: " + ", ".join(parts))
