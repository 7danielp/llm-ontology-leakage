"""Numbers of Section sec:results-mink: Min-K% Prob per ontology, tier, format and model"""
import collections
import statistics

from scipy.stats import ttest_rel

from analysis.common import FORMATS, MAKI, ONTOLOGIES, RESULTS, SHORT, TIERS, load_records, number

from llm_ontology_leakage.min_k.runner import min_k_score

TASKS = ["taxonomy", "domain", "range"]
REAL = ["Popular", "Medium", "Unpopular"]
W3C = "W3C Organization Ontology"
PAIRS = [(x, y) for a, b in [(0, 1), (0, 2), (1, 2)] for x in TIERS[REAL[a]] for y in TIERS[REAL[b]]]  # x from the higher tier
blocks = {(o, t, m, f): load_records(RESULTS / "runs" / "min-k" / f"MK__{o.replace(' ', '-')}__{t}__{m}__{f}")
          for o in ONTOLOGIES for t in TASKS for m in MAKI for f in FORMATS}


def short(o: str) -> str:
    return SHORT.get(o, o)


def run_score(o: str, t: str, m: str, f: str) -> float:
    """Mean over the blocks of one task, a cell of tab:mink-full"""
    return statistics.mean(r["scores"]["min_20"] for r in blocks[(o, t, m, f)])


def ontology_score(o: str, m: str, f: str, ten: bool = False) -> float:
    """Mean over the blocks of the three tasks, the row all of tab:mink-full, with ten only the blocks of ten axiom lines"""
    return statistics.mean(r["scores"]["min_20"] for t in TASKS for r in blocks[(o, t, m, f)] if r["n_axioms"] == 10 or not ten)


def table_score(o: str, m: str, ten: bool = False) -> float:
    """Entry of tab:mink"""
    return statistics.mean(ontology_score(o, m, f, ten) for f in FORMATS)


def tier_score(k: str, m: str, f: str) -> float:
    """Mean of the rows all of a tier in one format"""
    return statistics.mean(ontology_score(o, m, f) for o in TIERS[k])


def table_tier(k: str, m: str) -> float:
    """Grey row of tab:mink"""
    return statistics.mean(table_score(o, m) for o in TIERS[k])


def tier_mean(k: str, m: str, f: str) -> float:
    """Tier score in one format, with f = "mean" the grey row of tab:mink"""
    return table_tier(k, m) if f == "mean" else tier_score(k, m, f)


def without_single(o: str, m: str) -> float:
    """Table score without the blocks of a single axiom line"""
    return statistics.mean(statistics.mean(r["scores"]["min_20"] for t in TASKS for r in blocks[(o, t, m, f)] if r["n_axioms"] > 1)
                           for f in FORMATS)


def tier_spread(m: str) -> float:
    """Largest difference between two grey rows of tab:mink"""
    means = [table_tier(k, m) for k in TIERS]
    return max(means) - min(means)


def smallest_format_step(m: str) -> float:
    """Smallest step from one format to the next of the mean over the twelve ontologies"""
    means = [statistics.mean(ontology_score(o, m, f) for o in ONTOLOGIES) for f in FORMATS]
    return min(means[i + 1] - means[i] for i in range(len(means) - 1))


def real_order(m: str, f: str) -> bool:
    """Popular above medium above unpopular tier in one format"""
    return tier_score("Popular", m, f) > tier_score("Medium", m, f) > tier_score("Unpopular", m, f)


def p_text(p: float) -> str:
    """Three decimals, below 0.0005 as < 0.001"""
    return f"p = {p:.3f}" if p >= 0.0005 else "p < 0.001"


def token_lines(r: dict) -> list[int]:
    """Line of every token of a block, a newline token ends its line"""
    lines, line = [], 0
    for token in r["tokens"]:
        lines.append(line)
        line += token.count("\n")
    return lines


def without_repeated(rs: list[dict]) -> list[float]:
    """Min-20% of every block of a task over the lines whose subject starts no other line of the task"""
    count = collections.Counter(line.split(" ")[0] for r in rs for line in r["text"].split("\n"))
    result = []
    for r in rs:
        subjects = [line.split(" ")[0] for line in r["text"].split("\n")]
        kept = [lp for lp, i in zip(r["token_logprobs"], token_lines(r)) if lp is not None and count[subjects[i]] == 1]
        if kept:
            result.append(min_k_score(kept, 0.2))
    return result


print("sec:results-mink-ontologies")
print("real tier pairs in expected order (of 27): " + ", ".join(
    f"{m} {sum(table_score(x, m) > table_score(y, m) for x, y in PAIRS)}" for m in MAKI)
      + "; popular above unpopular (of 9): " + ", ".join(
    f"{m} {sum(table_score(x, m) > table_score(y, m) for x in TIERS['Popular'] for y in TIERS['Unpopular'])}" for m in MAKI))
against = {m: [(x, y) for x, y in PAIRS if not table_score(x, m) > table_score(y, m)] for m in MAKI}
print("pairs against the order: " + "; ".join(
    f"{m} " + ", ".join(f"{short(x)} below {short(y)}" for x, y in against[m]) for m in MAKI))
named = sum(bool({x, y} & {W3C, "GoodRelations", "EP-Plan"}) for m in MAKI for x, y in against[m])
print(f"pairs against the order with W3C Organization, GoodRelations or EP-Plan: {named} of {sum(len(v) for v in against.values())}")
print("lowest ontology of a tier: " + "; ".join(
    f"{k} " + ", ".join(short(min(TIERS[k], key=lambda o: table_score(o, m))) for m in MAKI) for k in REAL))
print("W3C Organization minus medium and minus unpopular tier: " + ", ".join(
    f"{m} {number(table_score(W3C, m) - table_tier('Medium', m), True)} and "
    f"{number(table_score(W3C, m) - table_tier('Unpopular', m), True)}" for m in MAKI))

remainder = blocks[(W3C, "range", MAKI[0], "plain")][-1]["n_axioms"]
print(f"W3C Organization range, remainder block of {remainder} axiom against the ten-axiom blocks")
for m in MAKI:
    parts = []
    for f in FORMATS:
        rs = [r["scores"]["min_20"] for r in blocks[(W3C, "range", m, f)]]
        parts.append(f"{f} {number(rs[-1])} against {number(min(rs[:-1]))} to {number(max(rs[:-1]))}")
    print(f"  {m}: " + ", ".join(parts))

print("ten-axiom blocks, mean token log probability of the first line against the later lines")
for m in MAKI:
    parts = []
    for f in FORMATS:
        first, later = [], []
        for o in ONTOLOGIES:
            lps = [(lp, i) for t in TASKS for r in blocks[(o, t, m, f)] if r["n_axioms"] == 10
                   for lp, i in zip(r["token_logprobs"], token_lines(r)) if lp is not None]
            first.append(statistics.mean(lp for lp, i in lps if i == 0))
            later.append(statistics.mean(lp for lp, i in lps if i > 0))
        parts.append(f"{f} {number(statistics.mean(first))} against {number(statistics.mean(later))}")
    print(f"  {m}: " + ", ".join(parts))

print("W3C Organization without its single-axiom block (change against tab:mink), GoodRelations, NFO, highest unpopular ontology")
for m in MAKI:
    top = max(TIERS["Unpopular"], key=lambda o: table_score(o, m))
    score = without_single(W3C, m)
    print(f"  {m}: {number(score)} ({number(score - table_score(W3C, m), True)}), "
          f"GoodRelations {number(table_score('GoodRelations', m))}, NFO {number(table_score('NEPOMUK File Ontology', m))}, "
          f"{short(top)} {number(table_score(top, m))}")
print("ten-axiom blocks only, models (of 4) with W3C Organization the lowest medium ontology: "
      f"{sum(min(TIERS['Medium'], key=lambda o: table_score(o, m, True)) == W3C for m in MAKI)}, above every unpopular ontology: "
      f"{sum(all(table_score(W3C, m, True) > table_score(o, m, True) for o in TIERS['Unpopular']) for m in MAKI)}")

print("drop without the lines of properties with more than one line, range over models and formats")
for o, t in [("EP-Plan", "domain"), ("GoodRelations", "domain"), ("EP-Plan", "range")]:
    drops = [run_score(o, t, m, f) - statistics.mean(without_repeated(blocks[(o, t, m, f)])) for m in MAKI for f in FORMATS]
    print(f"  {o} {t}: {number(min(drops))} to {number(max(drops))}")

print("sec:results-mink-synthetic")
print("synthetic minus unpopular tier, mean over the formats: " + ", ".join(
    f"{m} {number(statistics.mean(tier_score('Synthetic', m, f) - tier_score('Unpopular', m, f) for f in FORMATS), True)}" for m in MAKI))

print("sec:results-mink-formats")
print("largest difference between two tier means of Table tab:mink against the smallest step between two formats: "
      + ", ".join(f"{m} {number(tier_spread(m))} against {number(smallest_format_step(m))}" for m in MAKI))
print("tier means per format and model, popular to synthetic")
for f in FORMATS:
    print(f"  {f}: " + "; ".join(f"{m} " + ", ".join(number(tier_score(k, m, f)) for k in TIERS) for m in MAKI)
          + f"; real tier order for {sum(real_order(m, f) for m in MAKI)} of 4 models")
print("popular and medium minus synthetic tier per format and in the mean over the formats, one-sided paired t-test")
for f in FORMATS + ["mean"]:
    parts = []
    for k in ["Popular", "Medium"]:
        xs, ys = [tier_mean(k, m, f) for m in MAKI], [tier_mean("Synthetic", m, f) for m in MAKI]
        p = ttest_rel(xs, ys, alternative="greater").pvalue
        parts.append(f"{k.lower()} " + ", ".join(f"{m} {number(x - y, True)}" for m, x, y in zip(MAKI, xs, ys))
                     + f", {p_text(p)}, above for {sum(x > y for x, y in zip(xs, ys))} of 4 models")
    print(f"  {f}: " + "; ".join(parts))

print("sec:results-mink-models")
print("popular minus unpopular tier per format and in the mean over the formats")
for f in FORMATS + ["mean"]:
    xs = [tier_mean("Popular", m, f) - tier_mean("Unpopular", m, f) for m in MAKI]
    print(f"  {f}: " + ", ".join(f"{m} {number(x)}" for m, x in zip(MAKI, xs))
          + f"; grows with model size: {'yes' if all(a < b for a, b in zip(xs, xs[1:])) else 'no'}")
print("  mean from the rounded grey rows of tab:mink: " + ", ".join(
    f"{m} {number(round(table_tier('Popular', m), 2) - round(table_tier('Unpopular', m), 2))}" for m in MAKI))

print("sec:discussion-formats")
print("synthetic minus unpopular tier per format: " + "; ".join(
    f"{f} " + ", ".join(f"{m} {number(tier_score('Synthetic', m, f) - tier_score('Unpopular', m, f), True)}" for m in MAKI)
    for f in FORMATS))
