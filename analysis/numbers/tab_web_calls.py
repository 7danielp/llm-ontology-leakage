"""Values of Figure fig:web-calls and numbers of Section sec:results-web-calls: tool calls of gpt-5.6-luna per tier"""
import statistics

from analysis.common import ONTOLOGIES, TIERS, number
from analysis.web import blocked, completed, web_records

RUNS = ("1 call", "3 calls")


def actions(run: str, ontology: str) -> list[list[dict] | None]:
    """Web search actions of every TS-Guessing answer and every guided answer of Guided Prompting"""
    ts = web_records("ts-guessing", run, ontology)
    gp = web_records("guided-prompting", run, ontology)
    return ([r.get("web_search_actions") for records in ts.values() for r in records]
            + [r.get("web_search_actions_guided") for records in gp.values() for r in records])


# answers, answers with a call, completed calls and answers that asked for more calls than allowed, per (run, ontology)
counts = {}
for run in RUNS:
    for o in ONTOLOGIES:
        answers = actions(run, o)
        counts[(run, o)] = {"answers": len(answers), "with a call": sum(completed(a) > 0 for a in answers),
                            "calls": sum(completed(a) for a in answers), "blocked": sum(blocked(a) for a in answers)}


def mean_share(run: str, key: str, ontologies: list[str]) -> float:
    """Count per answer of each ontology, mean over the ontologies"""
    return statistics.mean(counts[(run, o)][key] / counts[(run, o)]["answers"] for o in ontologies)


def pooled(run: str, key: str, ontologies: list[str]) -> str:
    k, n = (sum(counts[(run, o)][c] for o in ontologies) for c in (key, "answers"))
    return f"{k:,} of {n:,}"


if __name__ == "__main__":
    for label, key, groups in (("calls per answer", "calls", TIERS), ("answers with a call", "with a call", {**TIERS, "All": ONTOLOGIES}),
                               ("asked for more calls than allowed", "blocked", TIERS)):
        for run in RUNS:
            print(f"{label}, {run}: " + ", ".join(f"{g} {number(mean_share(run, key, os))}" for g, os in groups.items()))
    for run in RUNS:
        print(f"asked for more calls than allowed, pooled, {run}: " + ", ".join(f"{t} {pooled(run, 'blocked', os)}" for t, os in TIERS.items()))
