"""Table tab:methods: score of each method per tier"""
import statistics

from analysis.common import FORMATS, MAKI, MODELS, ONTOLOGIES, SHORT, TASKS, TIERS, number, read_aggregate, read_matrix
from analysis.ts_filtered import ontology_f1

REAL = ["Popular", "Medium", "Unpopular"]
LUNA = "gpt-5.6-luna"

gap = {(r["ontology"], r["task"], r["model"], r["id_format"]): float(r["gap"])
       for r in read_aggregate("gp_aggregate.csv") if r["measure"] == "wup" and r["segment"] == "all"}
min_k = read_matrix("mink_matrix.csv")

# score per (ontology, model) of each method
methods = {
    "TS": {(o, m): ontology_f1(o, m) for o in ONTOLOGIES for m in MODELS},
    "GP": {(o, m): statistics.mean(gap[(o, t, m, "plain")] for t in TASKS) for o in ONTOLOGIES for m in MODELS},
    "MK": {(o, m): statistics.mean(min_k[(o, "all", m, f)] for f in FORMATS) for o in ONTOLOGIES for m in MAKI},
}
COVERED = {"TS": MODELS, "GP": MODELS, "MK": MAKI}


def tier_mean(scores: dict, ontologies: list[str], models: list[str]) -> float:
    return statistics.mean(scores[(o, m)] for o in ontologies for m in models)


def tier_means(scores: dict, model: str) -> list[float]:
    """Tier means of one model, popular to synthetic"""
    return [tier_mean(scores, ontologies, [model]) for ontologies in TIERS.values()]


def real_order(means: list[float]) -> bool:
    """Popular > medium > unpopular"""
    return means[0] > means[1] > means[2]


def synthetic_lowest(means: list[float]) -> bool:
    return means[3] < min(means[:3])


def real_pairs(scores: dict, models: list[str]) -> int:
    """Pairs of ontologies from two different real tiers in the expected order, 27 per model"""
    return sum(scores[(x, m)] > scores[(y, m)] for m in models for a, b in [(0, 1), (1, 2), (0, 2)]
               for x in TIERS[REAL[a]] for y in TIERS[REAL[b]])


def ranks(scores: dict, o: str, models: list[str]) -> list[int]:
    """Rank of the ontology among the twelve per model, 1 = highest"""
    return [1 + sum(scores[(x, m)] > scores[(o, m)] for x in ONTOLOGIES if x != o) for m in models]


def ts_range(o: str) -> str:
    """Lowest to highest TS-Guessing score of an ontology over the five models"""
    scores = [methods["TS"][(o, m)] for m in MODELS]
    return f"{number(min(scores))} to {number(max(scores))}"


if __name__ == "__main__":
    for tier, ontologies in TIERS.items():
        print(rf"\textbf{{{tier}}} & " + " & ".join(
            number(tier_mean(methods[k], ontologies, COVERED[k]), signed=k == "GP") for k in methods) + r" \\")

    # open-weight models whose own tier means follow the pattern
    open_weight = {k: [tier_means(methods[k], m) for m in MAKI] for k in methods}
    print("% Popular > medium > unpopular: " + ", ".join(f"{k} {sum(real_order(t) for t in open_weight[k])} of 4" for k in methods))
    print("% Synthetic lowest: " + ", ".join(f"{k} {sum(synthetic_lowest(t) for t in open_weight[k])} of 4" for k in methods))
    print("% TS-Guessing tier means per model with three decimals: " + "; ".join(
        f"{m} " + ", ".join(f"{x:.3f}" for x in tier_means(methods["TS"], m)) for m in MODELS))
    for k in ["TS", "GP"]:
        t = tier_means(methods[k], LUNA)
        print(f"% {LUNA} (not in the count rows), {k}: tier means " + ", ".join(number(x, signed=k == "GP") for x in t)
              + f"; popular > medium > unpopular {'yes' if real_order(t) else 'no'}, synthetic lowest {'yes' if synthetic_lowest(t) else 'no'}")

    for k, scores in methods.items():
        print(f"% {k} real tier pairs in expected order: {real_pairs(scores, MAKI)} of 108")
    print(f"% {LUNA}, 27 pairs each: " + "; ".join(
        f"{k} real tier pairs in expected order {real_pairs(methods[k], [LUNA])}" for k in ["TS", "GP"]))

    for o in ["FOAF", "W3C Organization Ontology"]:
        for k, scores in methods.items():
            r = ranks(scores, o, COVERED[k])
            print(f"% {o} {k} rank of 12: " + ", ".join(f"{m} {x}" for m, x in zip(COVERED[k], r)) + f" ({min(r)} to {max(r)})")
    low = TIERS["Unpopular"] + TIERS["Synthetic"]
    top_ontology, top_model = max(((o, m) for o in low for m in MODELS), key=lambda k: methods["TS"][k])
    print(f"% TS, unpopular and synthetic ontologies: at most {number(methods['TS'][(top_ontology, top_model)])} "
          f"({SHORT.get(top_ontology, top_ontology)}, {top_model}); per ontology "
          + ", ".join(f"{SHORT.get(o, o)} {ts_range(o)}" for o in low) + "; W3C Organization " + ts_range("W3C Organization Ontology"))
