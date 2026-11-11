"""Table tab:ts-format-tiers: TS-Guessing micro F1 per tier, model and identifier format"""
from analysis.common import FORMATS, MODELS, TIERS, number
from analysis.tables.tab_ts_formats import form_f1, macro, strict_f1

BLOCKS = {f"{f.capitalize()} format": (strict_f1, f) for f in FORMATS} | {"Plain format, form-independent": (form_f1, "plain")}


def broken(block: dict[str, list[float]]) -> str:
    """Models whose values do not fall from the popular over the medium to the unpopular tier"""
    return ", ".join(m for m in MODELS if not block[m][0] > block[m][1] > block[m][2]) or "none"


# {block: {model: tier values, popular to synthetic}}
blocks = {name: {m: [macro(value, ontologies, m, f) for ontologies in TIERS.values()] for m in MODELS}
          for name, (value, f) in BLOCKS.items()}
for name, block in blocks.items():
    print(rf"\rowcolor{{tierrow}}\multicolumn{{6}}{{l}}{{\textbf{{{name}}}}} \\")
    for i, tier in enumerate(TIERS):
        print(rf"\quad {tier} & " + " & ".join(number(block[m][i]) for m in MODELS) + r" \\")
print("% order of the three real tiers broken: " + "; ".join(f"{name} {broken(block)}" for name, block in blocks.items()))
print("% unpopular minus synthetic per block: " + "; ".join(
    f"{name} " + ", ".join(number(block[m][2] - block[m][3], signed=True) for m in MODELS) for name, block in blocks.items()))
