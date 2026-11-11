"""Table tab:web-condition-tests: one-sided paired t-tests between the web search conditions, paired by ontology"""
import statistics

from scipy.stats import ttest_rel

from analysis.common import ONTOLOGIES, number
from analysis.tables.tab_web_performance import stats

STEPS = [("1 call", "no web"), ("3 calls", "1 call"), ("3 calls", "no web")]  # (later, earlier)

for later, earlier in STEPS:
    cells = []
    for measure in ("f1", "gap"):
        a = [stats[o][later][measure] for o in ONTOLOGIES]
        b = [stats[o][earlier][measure] for o in ONTOLOGIES]
        cells += [number(statistics.mean(x - y for x, y in zip(a, b)), signed=True),
                  f"{ttest_rel(a, b, alternative='greater').pvalue:.3f}"]
    print(f"{later} $>$ {earlier} & " + " & ".join(cells) + r" \\")
