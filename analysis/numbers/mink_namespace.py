"""Numbers of Section sec:results-mink-formats: namespace, extra tokens and rise from plain to full per ontology"""
import collections
import re
from decimal import ROUND_HALF_UP, Decimal

from scipy.stats import spearmanr

from analysis.common import MAKI, ONTOLOGIES, RESULTS, SHORT, TIERS, load_records, number
from analysis.tables.tab_mink_full import TASKS, cells

SCHEMA = "schema.org"
REAL = [o for k in ("Popular", "Medium", "Unpopular") for o in TIERS[k]]


def text(x: float, signed: bool = False) -> str:
    """Two decimals as in the table, with a plain minus or plus sign"""
    return number(x, signed).replace("$", "")


def one(x: float) -> str:
    """One decimal, rounded half up as number()"""
    return str(Decimal(repr(x)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def records(o: str, m: str, f: str) -> list[dict]:
    """Blocks of the three tasks of an ontology in one model and format"""
    return [r for t in TASKS for r in load_records(RESULTS / "runs" / "min-k" / f"MK__{o.replace(' ', '-')}__{t}__{m}__{f}")]


def namespace(o: str) -> str:
    """Most frequent namespace of the subject and object IRIs in the full-format lines"""
    lines = [line.split(" ") for r in records(o, MAKI[0], "full") for line in r["text"].split("\n")]
    count = collections.Counter(re.match(r".*[/#]", iri).group(0) for parts in lines for iri in (parts[0], parts[2]))
    return count.most_common(1)[0][0]


# extra tokens per axiom line in the full against the plain format, rise of the row all of tab:mink-full
extra, rise = {}, {}
for o in ONTOLOGIES:
    for m in MAKI:
        plain, full = records(o, m, "plain"), records(o, m, "full")
        tokens_full, tokens_plain = sum(len(r["tokens"]) for r in full), sum(len(r["tokens"]) for r in plain)
        extra[(o, m)] = (tokens_full - tokens_plain) / sum(r["n_axioms"] for r in plain)
        rise[(o, m)] = cells[(o, "all", m, "full")] - cells[(o, "all", m, "plain")]
spaces = {o: namespace(o) for o in ONTOLOGIES}

print("extra tokens per axiom line and rise from plain to full")
print(f"{'':18s} {'namespace':58s} {'chars':>5s}  " + "  ".join(f"{m:>18s}" for m in MAKI))
for o in ONTOLOGIES:
    columns = "  ".join(f"{'+' + one(extra[(o, m)]):>8s} {text(rise[(o, m)], True):>9s}" for m in MAKI)
    print(f"{SHORT.get(o, o):18s} {spaces[o]:58s} {len(spaces[o]):5d}  " + columns)
print("spearman of extra tokens and rise, twelve ontologies: " + ", ".join(
    f"{m} {spearmanr([extra[(o, m)] for o in ONTOLOGIES], [rise[(o, m)] for o in ONTOLOGIES]).statistic:.2f}" for m in MAKI)
      + "; nine real ontologies: " + ", ".join(
    f"{m} {spearmanr([extra[(o, m)] for o in REAL], [rise[(o, m)] for o in REAL]).statistic:.2f}" for m in MAKI))

schema_extra = [extra[(SCHEMA, m)] for m in MAKI]
other_extra = [extra[(o, m)] for o in ONTOLOGIES if o != SCHEMA for m in MAKI]
fewest = sum(all(extra[(SCHEMA, m)] < extra[(o, m)] for o in ONTOLOGIES if o != SCHEMA) for m in MAKI)
print(f"schema.org extra tokens per axiom line: {one(min(schema_extra))} to {one(max(schema_extra))}, "
      f"other eleven ontologies {one(min(other_extra))} to {one(max(other_extra))}, fewest for {fewest} of 4 models")
schema_rise = [rise[(SCHEMA, m)] for m in MAKI]
other_rise = [rise[(o, m)] for o in REAL if o != SCHEMA for m in MAKI]
lowest = sum(all(rise[(SCHEMA, m)] < rise[(o, m)] for o in REAL if o != SCHEMA) for m in MAKI)
print(f"schema.org rise from plain to full: {text(min(schema_rise), True)} to {text(max(schema_rise), True)}, "
      f"other eight real ontologies {text(min(other_rise), True)} to {text(max(other_rise), True)}, "
      f"lowest of the nine real ontologies for {lowest} of 4 models")

# models for which schema.org lies above or below all three medium ontologies, rows all of tab:mink-full
position = []
for f in ("plain", "prefix", "full"):
    above = sum(all(cells[(SCHEMA, "all", m, f)] > cells[(o, "all", m, f)] for o in TIERS["Medium"]) for m in MAKI)
    below = sum(all(cells[(SCHEMA, "all", m, f)] < cells[(o, "all", m, f)] for o in TIERS["Medium"]) for m in MAKI)
    position.append(f"{f} above all three {above}, below all three {below}")
print("schema.org against the three medium ontologies (of 4 models): " + ", ".join(position))
