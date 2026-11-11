"""Numbers of Sections sec:results-gp-ontologies and sec:results-mink-ontologies: tier means without the name-inferable questions"""
from analysis.common import MAKI, MODELS, TIERS
from analysis.numbers import gp_name_filter as gp
from analysis.numbers import mink_name_filter as mk

TIER_NAMES = list(TIERS)
MEDIUM, SYNTHETIC = TIER_NAMES.index("Medium"), TIER_NAMES.index("Synthetic")


def order_and_tests(name: str, means: dict[str, list[float]], tests: list[tuple[float, float]]) -> str:
    """Models with popular > medium > unpopular and the t-tests between neighbouring tiers"""
    real = sum(v[0] > v[1] > v[2] for v in means.values())
    return (f"{name}: popular > medium > unpopular for {real} of {len(means)} models; one-sided paired t-tests: "
            + ", ".join(f"{TIER_NAMES[i]} > {TIER_NAMES[i + 1].lower()} Delta {d:+.3f} p = {p:.3f}" for i, (d, p) in enumerate(tests)))


print("sec:results-gp-ontologies")
gp_all = {m: gp.tier_means(m, False) for m in MODELS}
gp_filtered = {m: gp.tier_means(m, True) for m in MODELS}
largest = max((abs(gp_filtered[m][i] - gp_all[m][i]), tier, m) for i, tier in enumerate(TIER_NAMES) for m in MODELS)
print(f"Guided Prompting, largest change of a tier mean: {largest[0]:.3f} ({largest[1]}, {largest[2]})")
print(order_and_tests("Guided Prompting, all questions", gp_all, gp.tier_tests(False)))
print(order_and_tests("Guided Prompting, filtered", gp_filtered, gp.tier_tests(True)))

print("sec:results-mink-ontologies")
mk_all = {m: mk.tier_means(m, False) for m in MAKI}
mk_filtered = {m: mk.tier_means(m, True) for m in MAKI}
print("Min-K% Prob, change of the tier means per model: " + "; ".join(
    f"{tier} " + ", ".join(f"{mk_filtered[m][i] - mk_all[m][i]:+.3f}" for m in MAKI) for i, tier in enumerate(TIER_NAMES)))
medium = [mk_filtered[m][MEDIUM] - mk_all[m][MEDIUM] for m in MAKI]
print(f"Min-K% Prob, fall of the medium tier: {min(-x for x in medium):.2f} to {max(-x for x in medium):.2f}")
others = max(abs(mk_filtered[m][i] - mk_all[m][i]) for i in range(len(TIER_NAMES)) if i != MEDIUM for m in MAKI)
print(f"Min-K% Prob, largest change of the popular, unpopular and synthetic tier means: {others:.3f}")
for label, means in (("all lines", mk_all), ("filtered", mk_filtered)):
    below = [m for m in MAKI if means[m][MEDIUM] < means[m][SYNTHETIC]]
    print(f"Min-K% Prob, {label}: medium tier below the synthetic tier for {len(below)} of {len(MAKI)} models"
          + (f" ({', '.join(below)})" if below else ""))
print(order_and_tests("Min-K% Prob, all lines", mk_all, mk.tier_tests(False)))
print(order_and_tests("Min-K% Prob, filtered", mk_filtered, mk.tier_tests(True)))

# W3C Organization, the ontology behind the fall of the medium tier
for m in MAKI:
    full, filtered = mk.ontology_score(mk.W3C, m, False), mk.ontology_score(mk.W3C, m, True)
    matched = mk.ontology_score(mk.W3C, m, True, "matched")
    share = (filtered - full) / sum(mk.ontology_score(o, m, True) - mk.ontology_score(o, m, False) for o in TIERS["Medium"])
    print(f"W3C Organization, {m}: all {full:.3f}, filtered {filtered:.3f} (change {filtered - full:+.3f}), matched {matched:.3f} "
          f"(change {matched - full:+.3f}, {(matched - full) / (filtered - full):.0%} of the change); share of the fall of the medium tier {share:.0%}")
k, n, t, i = max((sum(b), len(b), t, i) for t in mk.TASKS for i, b in enumerate(mk.flags(mk.W3C, t)))
print(f"W3C Organization, most name-inferable lines in one block: {k} of {n} ({t}, block {i})")
