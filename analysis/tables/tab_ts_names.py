"""Table tab:ts-names: TS-Guessing micro F1 per ontology and model, with all questions and without the name-inferable ones"""
import statistics

from scipy.stats import ttest_rel

from analysis.common import MODELS, ONTOLOGIES, TASKS, TIERS, tier_rows
from analysis.ts_filtered import ontology_f1, questions_left

# per model all questions, then filtered
values = {o: [ontology_f1(o, m, filtered) for m in MODELS for filtered in (False, True)] for o in ONTOLOGIES}
print(tier_rows(values))

left = {o: {t: questions_left(o, t) for t in TASKS} for o in ONTOLOGIES}  # (questions left, all questions)
total = {o: sum(n for _, n in left[o].values()) for o in ONTOLOGIES}
removed = {o: total[o] - sum(k for k, _ in left[o].values()) for o in ONTOLOGIES}
# share of name-inferable questions, mean of the ontologies of a tier
print("% removed share per tier: "
      + ", ".join(f"{t} {statistics.mean(removed[o] / total[o] for o in os):.0%}" for t, os in TIERS.items()))
k, n = left["EP-Plan"]["taxonomy"]
print(f"% EP-Plan removed {removed['EP-Plan']} of {total['EP-Plan']} ({removed['EP-Plan'] / total['EP-Plan']:.0%}), "
      f"taxonomy questions left {k} of {n}")

# filtered tier means per model, each tier against the next one
filtered = {o: values[o][1::2] for o in ONTOLOGIES}
tier_mean = {t: [statistics.mean(filtered[o][i] for o in os) for i in range(len(MODELS))] for t, os in TIERS.items()}
tiers = list(TIERS)
print("% filtered one-sided paired t-tests: " + ", ".join(
    f"{upper} > {lower.lower()} p = {ttest_rel(tier_mean[upper], tier_mean[lower], alternative='greater').pvalue:.3f}"
    for upper, lower in zip(tiers, tiers[1:])))
