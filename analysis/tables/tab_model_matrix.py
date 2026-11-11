"""Table tab:model-tests: one-sided paired t-tests between any two models for each method"""
import statistics

from scipy.stats import ttest_rel

from analysis.common import MODELS, ONTOLOGIES, number
from analysis.tables.tab_methods import methods

NAMES = {"TS": "TS-Guessing", "GP": "Guided Prompting"}  # Min-K% Prob scores are comparable within one model only
values = {k: methods[k] for k in NAMES}
ROWS, COLUMNS = MODELS[1:], MODELS[:-1]  # models ascending by size, the row model is the larger one
PAIRS = [(a, b) for i, a in enumerate(MODELS) for b in MODELS[:i]]  # (larger, smaller), row by row


def scores(table: dict, model: str) -> list[float]:
    return [table[(o, model)] for o in ONTOLOGIES]


def delta(table: dict, a: str, b: str) -> float:
    """Mean difference a minus b over the twelve ontologies"""
    return statistics.mean(x - y for x, y in zip(scores(table, a), scores(table, b)))


def p_value(table: dict, a: str, b: str) -> float:
    """One-sided paired t-test, a scores higher than b"""
    return ttest_rel(scores(table, a), scores(table, b), alternative="greater").pvalue


def p_text(p: float) -> str:
    """Three decimals, below 0.0005 as <0.001"""
    return f"{p:.3f}" if p >= 0.0005 else "$<$0.001"


def entry(table: dict, a: str, b: str) -> tuple[str, str]:
    """Delta and p as in the table, empty above the diagonal"""
    if (a, b) not in PAIRS:
        return "", ""
    return number(delta(table, a, b), signed=True), p_text(p_value(table, a, b))


print(r"  \begin{tabular}{l" + "cc" * len(COLUMNS) + "}")
print(r"    \toprule")
print("     & " + " & ".join(rf"\multicolumn{{2}}{{c}}{{{m}}}" for m in COLUMNS) + r" \\")
print("    " + "".join(rf"\cmidrule(lr){{{2 * i + 2}-{2 * i + 3}}}" for i in range(len(COLUMNS))))
print("     & " + " & ".join([r"$\Delta$ & $p$"] * len(COLUMNS)) + r" \\")
print(r"    \midrule")
for k, table in values.items():
    print(rf"    \rowcolor{{tierrow}}\multicolumn{{{1 + 2 * len(COLUMNS)}}}{{l}}{{\textbf{{{NAMES[k]}}}}} \\")
    for a in ROWS:
        print(rf"    \quad {a} & " + " & ".join(e for b in COLUMNS for e in entry(table, a, b)) + r" \\")
print(r"    \bottomrule")
print(r"  \end{tabular}")

for k, table in values.items():
    ps = {(a, b): p_value(table, a, b) for a, b in PAIRS}
    significant = [pair for pair in PAIRS if ps[pair] < 0.05]
    print(f"% {NAMES[k]}, Delta and p with four decimals: " + ", ".join(
        f"{a} > {b} {delta(table, a, b):+.4f} {ps[(a, b)]:.4f}" for a, b in PAIRS))
    print(f"% {NAMES[k]}, significant (p < 0.05) in {len(significant)} of {len(PAIRS)} pairs: " + ", ".join(
        f"{a} > {b} ({p_text(ps[(a, b)])})" for a, b in significant))
    print(f"% {NAMES[k]}, not significant: " + ", ".join(
        f"{a} > {b} ({number(delta(table, a, b), signed=True)}, {p_text(ps[(a, b)])})" for a, b in PAIRS if (a, b) not in significant))
    print(f"% {NAMES[k]}, ontologies on which the row model scores higher (of 12): " + ", ".join(
        f"{a} > {b} {sum(x > y for x, y in zip(scores(table, a), scores(table, b)))}" for a, b in PAIRS))
