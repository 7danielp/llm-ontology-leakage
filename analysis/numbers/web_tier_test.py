"""Numbers of Section sec:results-web: permutation test of the medium against the popular tier with web search"""
import itertools
from fractions import Fraction

from analysis.common import FORMATS, TASKS, TIERS
from analysis.web import f1, ts_counts, web_records

SIX = TIERS["Popular"] + TIERS["Medium"]  # popular at the indices 0 to 2, medium at 3 to 5


def task_f1(condition: str, ontology: str) -> dict[str, Fraction]:
    """F1 per task, the micro F1 per format averaged over the three formats"""
    runs = web_records("ts-guessing", condition, ontology)
    return {t: sum((f1(*map(sum, zip(*map(ts_counts, runs[(t, f)])))) for f in FORMATS), Fraction(0)) / len(FORMATS)
            for t in TASKS}


for c in ["1 call", "3 calls"]:
    values = [task_f1(c, o) for o in SIX]
    # medium minus popular sum of each task for all 20 ways to split the six ontologies into two tiers of three
    splits = {t: [sum(values[i][t] for i in medium) - sum(values[i][t] for i in range(6) if i not in medium)
                  for medium in itertools.combinations(range(6), 3)] for t in TASKS}
    observed = sum(sum(v[t] for v in values[3:]) - sum(v[t] for v in values[:3]) for t in TASKS)
    # exact one-sided p over all 20^4 combinations of the splits of the four tasks
    reached = sum(sum(combo) >= observed for combo in itertools.product(*splits.values()))
    print(f"{c}: p = {reached / 20 ** len(TASKS):.3f}")
