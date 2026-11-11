"""Table tab:ts-outside: TS-Guessing micro F1 inside and outside the namespace of each real ontology"""
import statistics

from analysis.common import FORMATS, MODELS, SHORT, TIERS, golds_outside, load_records, name_inferable, number, outside_namespace
from analysis.ts_filtered import run_dir

TASKS = ["taxonomy", "domain", "range"]
# the synthetic ontologies have no golds outside their namespace
REAL = {tier: ontologies for tier, ontologies in TIERS.items() if tier != "Synthetic"}


def values(o: str) -> tuple[int, int, float, float | None]:
    """(questions, outside questions, F1 inside, F1 outside or None without outside questions), without the
    name-inferable questions"""
    namespace = outside_namespace(run_dir(o, TASKS[0], MODELS[0], "plain"))
    questions = [r for t in TASKS for r in load_records(run_dir(o, t, MODELS[0], "plain")) if not name_inferable(r)]
    answers = [r for t in TASKS for m in MODELS for f in FORMATS for r in load_records(run_dir(o, t, m, f))
               if not name_inferable(r)]
    # F1 = EM rate here, since every answer names one class
    em = {inside: [r["strict_match"] for r in answers if golds_outside(r, namespace) != inside] for inside in (True, False)}
    outside = sum(golds_outside(r, namespace) for r in questions)
    return len(questions), outside, statistics.mean(em[True]), statistics.mean(em[False]) if em[False] else None


results = {o: values(o) for ontologies in REAL.values() for o in ontologies}
for tier, ontologies in REAL.items():
    print(rf"\rowcolor{{tierrow}}\multicolumn{{5}}{{l}}{{\textbf{{{tier}}}}} \\")
    for o in ontologies:
        questions, n, inside, outside = results[o]
        print(rf"\quad {SHORT.get(o, o)} & {questions:,} & {n} & {number(inside)} & {'--' if outside is None else number(outside)} \\")

with_outside = {o: x for o, x in results.items() if x[3] is not None}
inside, outside = [x[2] for x in with_outside.values()], [x[3] for x in with_outside.values()]
closest = min(with_outside, key=lambda o: with_outside[o][2] - with_outside[o][3])
print(f"% F1 score per ontology: outside {number(min(outside))} to {number(max(outside))}, inside {number(min(inside))} to "
      f"{number(max(inside))}; outside below inside on {sum(x[3] < x[2] for x in with_outside.values())} of the "
      f"{len(with_outside)} ontologies with outside questions, closest {SHORT.get(closest, closest)} "
      f"{number(with_outside[closest][3])} against {number(with_outside[closest][2])}")
