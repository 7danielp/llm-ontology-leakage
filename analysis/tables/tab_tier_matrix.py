"""Table tab:tier-tests: one-sided paired t-tests between any two tiers for each method"""
import itertools
import statistics

from scipy.stats import ttest_rel

from analysis.common import TIERS, number
from analysis.tables.tab_tier_tests import means  # {method: {model: [tier mean, popular to synthetic]}}

NAMES = {"TS": "TS-Guessing", "GP": "Guided Prompting", "MK": r"Min-K\% Prob"}
tiers = list(TIERS)
PAIRS = list(itertools.combinations(range(len(tiers)), 2))  # (i, j) with tier i expected above tier j


def delta(per_model: dict[str, list[float]], i: int, j: int) -> float:
    """Mean over the models of tier i minus tier j"""
    return statistics.mean(v[i] - v[j] for v in per_model.values())


def p_value(per_model: dict[str, list[float]], i: int, j: int) -> float:
    """One-sided paired t-test over the models, tier i higher than tier j"""
    return ttest_rel([v[i] for v in per_model.values()], [v[j] for v in per_model.values()], alternative="greater").pvalue


def p_text(p: float) -> str:
    """Three decimals, below 0.0005 as <0.001"""
    return f"{p:.3f}" if p >= 0.0005 else "$<$0.001"


def entry(per_model: dict[str, list[float]], i: int, j: int) -> tuple[str, str]:
    """Delta and p as in the table"""
    return number(delta(per_model, i, j), signed=True), p_text(p_value(per_model, i, j))


def pair(i: int, j: int) -> str:
    return f"{tiers[i]} > {tiers[j].lower()}"


print(r"  \begin{tabular}{l" + "cc" * len(means) + "}")
print(r"    \toprule")
print("     & " + " & ".join(rf"\multicolumn{{2}}{{c}}{{{NAMES[k]}}}" for k in means) + r" \\")
print("    " + "".join(rf"\cmidrule(lr){{{2 * n + 2}-{2 * n + 3}}}" for n in range(len(means))))
print("     & " + " & ".join([r"$\Delta$ & $p$"] * len(means)) + r" \\")
print(r"    \midrule")
for n, (i, j) in enumerate(PAIRS):
    if n and i != PAIRS[n - 1][0]:
        print(r"    \addlinespace")
    print(f"    {tiers[i]} $>$ {tiers[j].lower()} & " + " & ".join(e for per_model in means.values() for e in entry(per_model, i, j)) + r" \\")
print(r"    \bottomrule")
print(r"  \end{tabular}")

for k, per_model in means.items():
    name = NAMES[k].replace("\\", "")
    ps = {(i, j): p_value(per_model, i, j) for i, j in PAIRS}
    print(f"% {name}, Delta and p with four decimals: " + ", ".join(
        f"{pair(i, j)} {delta(per_model, i, j):+.4f} {ps[(i, j)]:.4f}" for i, j in PAIRS))
    print(f"% {name}, significant (p < 0.05) in {sum(p < 0.05 for p in ps.values())} of {len(PAIRS)} pairs, not significant: "
          + (", ".join(pair(i, j) for (i, j), p in ps.items() if p >= 0.05) or "none"))
    print(f"% {name}, models with the first tier higher (of {len(per_model)}): " + ", ".join(
        f"{pair(i, j)} {sum(v[i] > v[j] for v in per_model.values())}" for i, j in PAIRS))
