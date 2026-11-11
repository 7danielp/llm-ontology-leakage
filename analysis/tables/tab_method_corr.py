"""Table tab:method-corr: Spearman correlation between two methods per model, over the ontologies and over the runs"""
import statistics

from scipy.stats import spearmanr

from analysis.common import FORMATS, MAKI, MODELS, ONTOLOGIES, TASKS, number, read_gaps
from analysis.tables import tab_mink_full
from analysis.tables.tab_methods import methods
from analysis.ts_filtered import matrix

MK_TASKS = ["taxonomy", "domain", "range"]  # Min-K% Prob has no property task
NAMES = {"TS": "TS-Guessing", "GP": "Guided Prompting", "MK": "Min-K% Prob"}
PAIRS = [("TS", "GP"), ("TS", "MK"), ("GP", "MK")]

# score per (ontology, task, model, format) of each method, TS-Guessing None where no question is left
runs = {"TS": matrix(), "GP": {cell: gap for cell, (gap, _) in read_gaps().items()}, "MK": tab_mink_full.cells}


def models_of(a: str, b: str) -> list[str]:
    return MAKI if "MK" in (a, b) else MODELS


def tasks_of(a: str, b: str) -> list[str]:
    return MK_TASKS if "MK" in (a, b) else TASKS


def formats_of(a: str, b: str) -> list[str]:
    """Guided Prompting only in the plain format"""
    return ["plain"] if "GP" in (a, b) else FORMATS


def correlate(x: list[float | None], y: list[float | None]) -> tuple[float, int]:
    """Spearman correlation over the pairs where both scores exist, and their number"""
    pairs = [(u, v) for u, v in zip(x, y) if u is not None and v is not None]
    return float(spearmanr(*zip(*pairs))[0]), len(pairs)


def onto_level(a: str, b: str, model: str) -> tuple[float, int]:
    """Correlation over the twelve ontology scores of one model"""
    return correlate([methods[a][(o, model)] for o in ONTOLOGIES], [methods[b][(o, model)] for o in ONTOLOGIES])


def run_level(a: str, b: str, model: str) -> tuple[float, int]:
    """Mean over the formats of the correlation over the runs of one format, and the number of runs in one correlation"""
    per_format = []
    for fmt in formats_of(a, b):
        cells = [(o, t, model, fmt) for o in ONTOLOGIES for t in tasks_of(a, b)]
        per_format.append(correlate([runs[a][c] for c in cells], [runs[b][c] for c in cells]))
    assert len({n for _, n in per_format}) == 1
    return statistics.mean(r for r, _ in per_format), per_format[0][1]


def span(values: list[float]) -> str:
    """Lowest to highest value, two decimals with a plain minus"""
    return f"{number(min(values)).replace('$', '')} to {number(max(values)).replace('$', '')}"


LEVELS = {"ontologies": onto_level, "runs": run_level}

# one row per model, for each pair of methods the columns Ontologies and Runs, then the number of pairs n
entries = {(a, b, level): {m: LEVELS[level](a, b, m) for m in models_of(a, b)} for a, b in PAIRS for level in LEVELS}
for m in MODELS:
    print(f"{m} & " + " & ".join(number(entries[(a, b, level)][m][0]) if m in entries[(a, b, level)] else ""
                                 for a, b in PAIRS for level in LEVELS) + r" \\")
print(r"\midrule")
counts = []
for a, b in PAIRS:
    for level in LEVELS:
        n = {v[1] for v in entries[(a, b, level)].values()}
        assert len(n) == 1
        counts.append(str(n.pop()))
print("$n$ & " + " & ".join(counts) + r" \\")

for level in LEVELS:
    print(f"% ranges over the models, {level}: " + "; ".join(
        f"{NAMES[a]} and {NAMES[b]} {span([r for r, _ in entries[(a, b, level)].values()])}" for a, b in PAIRS))
ps = {m: spearmanr([methods["GP"][(o, m)] for o in ONTOLOGIES], [methods["MK"][(o, m)] for o in ONTOLOGIES],
                   alternative="greater").pvalue for m in MAKI}
print("% ontology level, one-sided p, Guided Prompting and Min-K% Prob: " + ", ".join(f"{m} {p:.3f}" for m, p in ps.items()))
