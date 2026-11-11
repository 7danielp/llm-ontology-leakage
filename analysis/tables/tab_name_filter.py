"""Table tab:name-filter: Guided Prompting and Min-K% Prob per tier and model with all and without the name-inferable questions"""
from analysis.common import MAKI, MODELS, ONTOLOGIES, TASKS, TIERS, number
from analysis.numbers import gp_name_filter as gp
from analysis.numbers import mink_name_filter as mk

columns = 1 + 2 * len(MODELS)
print(rf"\rowcolor{{tierrow}}\multicolumn{{{columns}}}{{l}}{{\textbf{{Guided Prompting}}}} \\")
for i, tier in enumerate(TIERS):
    entries = [number(gp.tier_means(m, filtered)[i], True) for m in MODELS for filtered in (False, True)]
    print(rf"\quad {tier} & " + " & ".join(entries) + r" \\")
print(rf"\rowcolor{{tierrow}}\multicolumn{{{columns}}}{{l}}{{\textbf{{Min-K\% Prob}}}} \\")
for i, tier in enumerate(TIERS):
    entries = [number(mk.tier_means(m, filtered)[i]) if m in MAKI else "--" for m in MODELS for filtered in (False, True)]
    print(rf"\quad {tier} & " + " & ".join(entries) + r" \\")

gp_three = "; ".join(f"{tier} " + ", ".join(f"{gp.tier_means(m, False)[i]:+.3f}/{gp.tier_means(m, True)[i]:+.3f}" for m in MODELS)
                     for i, tier in enumerate(TIERS))
mk_three = "; ".join(f"{tier} " + ", ".join(f"{mk.tier_means(m, False)[i]:.3f}/{mk.tier_means(m, True)[i]:.3f}" for m in MAKI)
                     for i, tier in enumerate(TIERS))
print(f"% the same with three decimals, all and filtered per model: Guided Prompting {gp_three}; Min-K% Prob {mk_three}")
print("% name-inferable questions: " + ", ".join(f"{t} {sum(gp.removed(o, t)[0] for o in ONTOLOGIES):,}" for t in TASKS))
print("% name-inferable axiom lines: " + ", ".join(f"{t} {sum(mk.removed(o, t)[0] for o in ONTOLOGIES):,}" for t in mk.TASKS))
