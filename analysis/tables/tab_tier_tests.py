"""Tier means of each method and model for Table tab:tier-tests (tab_tier_matrix.py), and the neighbouring tier tests
of TS-Guessing with all questions for the text on Table tab:ts-f1"""
import statistics

from scipy.stats import ttest_rel

from analysis.common import FORMATS, MODELS, TASKS, TIERS, number, read_matrix
from analysis.tables.tab_methods import COVERED, methods, tier_means

tiers = list(TIERS)
ts_f1 = read_matrix("ts_matrix_f1.csv")  # TS-Guessing with all questions

# {method: {model: [tier mean, popular to synthetic]}}, from the scores of tab_methods.py
means = {k: {m: tier_means(methods[k], m) for m in COVERED[k]} for k in methods}
ts_all = {m: [statistics.mean(ts_f1[(o, t, m, f)] for o in TIERS[k] for t in TASKS for f in FORMATS) for k in tiers] for m in MODELS}


def delta(per_model: dict[str, list[float]], i: int) -> float:
    """Mean over the models of tier i minus tier i + 1"""
    return statistics.mean(v[i] - v[i + 1] for v in per_model.values())


def p_value(per_model: dict[str, list[float]], i: int) -> float:
    """One-sided paired t-test over the models, tier i higher than tier i + 1"""
    return ttest_rel([v[i] for v in per_model.values()], [v[i + 1] for v in per_model.values()], alternative="greater").pvalue


def entries(per_model: dict[str, list[float]], i: int) -> list[str]:
    """Delta and p as in the table"""
    return [number(delta(per_model, i), signed=True), f"{p_value(per_model, i):.3f}"]


def step(i: int) -> str:
    return f"{tiers[i]} > {tiers[i + 1].lower()}"


if __name__ == "__main__":
    print("% TS-Guessing Delta with three decimals: " + ", ".join(f"{step(i)} {delta(means['TS'], i):+.3f}" for i in range(3)))
    print("% TS-Guessing row with all questions, Delta and p: " + ", ".join(f"{step(i)} " + " ".join(entries(ts_all, i)) for i in range(3)))
