"""Numbers of Section sec:results-ts-models: TS-Guessing micro F1 per tier and model, without the name-inferable questions"""
import statistics
from decimal import ROUND_HALF_UP, Decimal

from analysis.common import MAKI, MODELS, TIERS, number
from analysis.ts_filtered import ontology_f1

TIER_NAMES = list(TIERS)  # popular to synthetic
REAL_TIERS = TIER_NAMES[:3]


def three_decimals(x: float) -> str:
    """Signed difference with three decimals"""
    text = str(Decimal(repr(abs(x))).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP))
    return f"$-${text}" if x < 0 else f"$+${text}" if x > 0 else text


def tier_means(filtered: bool) -> dict[str, dict[str, float]]:
    """{tier: {model: mean over the three ontologies of the tier}}"""
    return {tier: {m: statistics.mean(ontology_f1(o, m, filtered) for o in ontologies) for m in MODELS}
            for tier, ontologies in TIERS.items()}


def order_counts(means: dict[str, dict[str, float]]) -> str:
    real_order = sum(means["Popular"][m] > means["Medium"][m] > means["Unpopular"][m] for m in MODELS)
    synthetic_lowest = sum(means["Synthetic"][m] < min(means[t][m] for t in REAL_TIERS) for m in MODELS)
    return (f"order of the three real tiers holds for {real_order} of {len(MODELS)} models, "
            f"synthetic the lowest tier for {synthetic_lowest} of {len(MODELS)}")


means, means_all = tier_means(True), tier_means(False)

print("tier means per model, popular to synthetic")
for m in MODELS:
    print(f"  {m}: " + ", ".join(number(means[tier][m]) for tier in TIERS))
for tier, by_model in means.items():
    best = max(MAKI, key=by_model.get)
    print(f"{tier}: models from {number(min(by_model.values()))} to {number(max(by_model.values()))}, "
          f"gpt-5.6-luna minus the best MAKI model ({best}) {three_decimals(by_model['gpt-5.6-luna'] - by_model[best])}")

spread = {tier: max(by_model.values()) - min(by_model.values()) for tier, by_model in means.items()}
print("spread over the five models per tier: " + ", ".join(f"{tier} {number(x)}" for tier, x in spread.items())
      + f"; largest {max(spread, key=spread.get)}, smallest {min(spread, key=spread.get)}")
real_spread = {m: max(means[t][m] for t in REAL_TIERS) - min(means[t][m] for t in REAL_TIERS) for m in MODELS}
for m in MODELS:
    v = [means[tier][m] for tier in TIER_NAMES]
    steps = ", ".join(f"{TIER_NAMES[k].lower()} > {TIER_NAMES[k + 1].lower()} {'holds' if v[k] > v[k + 1] else 'breaks'}"
                      for k in range(3))
    print(f"  {m}: real tiers within {number(real_spread[m])}, unpopular minus synthetic {three_decimals(v[2] - v[3])}; {steps}")
print(f"smallest spread of the three real tiers: {min(real_spread, key=real_spread.get)} {number(min(real_spread.values()))}, "
      f"the next model {number(sorted(real_spread.values())[1])}")

decline = {m: means["Popular"][m] - means["Synthetic"][m] for m in MODELS}
steepest = max(decline, key=decline.get)
print(f"steepest decline from the popular to the synthetic tier: {steepest} {number(means['Popular'][steepest])} "
      f"to {number(means['Synthetic'][steepest])}; declines " + ", ".join(f"{m} {number(d)}" for m, d in decline.items()))
print(order_counts(means))
rank = {tier: sorted(MODELS, key=lambda m: -by_model[m]).index("gpt-5.6-luna") + 1 for tier, by_model in means.items()}
print("rank of gpt-5.6-luna among the five models per tier: " + ", ".join(f"{tier} {r}" for tier, r in rank.items()))

print("all questions:")
for tier, by_model in means_all.items():
    print(f"  {tier}: models from {number(min(by_model.values()))} to {number(max(by_model.values()))}")
print(f"  {order_counts(means_all)}")
