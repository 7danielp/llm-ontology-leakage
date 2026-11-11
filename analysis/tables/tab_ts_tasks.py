"""Table tab:ts-tasks: TS-Guessing micro F1 per ontology and task without the name-inferable questions"""
import statistics
from collections.abc import Iterable

from analysis.common import FORMATS, MODELS, ONTOLOGIES, SHORT, TASKS, TIERS, iri_name, load_records, name_inferable, number
from analysis.ts_filtered import mean_f1, questions_left, run_dir

from llm_ontology_leakage.core.tasks import TASKS as SPECS
from llm_ontology_leakage.ts_guessing.scoring import confusion_counts, score

DC = "Dublin Core Terms"


def mean(xs: Iterable[float | None]) -> float | None:
    """Mean of the values that are not None, None if there is none"""
    kept = [x for x in xs if x is not None]
    return statistics.mean(kept) if kept else None


def entry(x: float | None) -> str:
    return "--" if x is None else number(x)


def ontology_value(o: str, t: str) -> float | None:
    """Mean run F1 over the five models and three formats, None if the filter empties all runs"""
    return mean_f1((o, t, m, f) for m in MODELS for f in FORMATS)


def model_tier_value(tier: str, t: str, model: str) -> float | None:
    """Mean run F1 of one model over the ontologies of a tier and the formats"""
    return mean_f1((o, t, model, f) for o in TIERS[tier] for f in FORMATS)


def records(o: str, t: str, filtered: bool = True) -> list[dict]:
    """Answers of all models and formats, without the name-inferable questions if filtered"""
    return [r for m in MODELS for f in FORMATS for r in load_records(run_dir(o, t, m, f)) if not (filtered and name_inferable(r))]


def em_rate(o: str, m: str, f: str) -> float:
    """Share of exact sets in one run of the property task"""
    return statistics.mean(r["strict_match"] for r in load_records(run_dir(o, "property", m, f)) if not name_inferable(r))


def property_counts(model: str) -> tuple[int, int, int]:
    """tp, fp and fn of the property task of one model over all ontologies and formats"""
    spec = SPECS["property"]
    tp = fp = fn = 0
    for o in ONTOLOGIES:
        for f in FORMATS:
            for r in load_records(run_dir(o, "property", model, f)):
                if not name_inferable(r):
                    parsed, _ = score(r["raw_output"], r["gold"], list_valued=spec.list_valued, match_mode=spec.match)
                    a, b, c = confusion_counts(parsed, r["gold"], spec.match)
                    tp, fp, fn = tp + a, fp + b, fn + c
    return tp, fp, fn


values = {o: [ontology_value(o, t) for t in TASKS] for o in ONTOLOGIES}
tier_values = {tier: [mean(values[o][i] for o in os) for i in range(len(TASKS))] for tier, os in TIERS.items()}
for tier, os in TIERS.items():
    print(rf"\rowcolor{{tierrow}}\textbf{{{tier}}} & " + " & ".join(entry(x) for x in tier_values[tier]) + r" \\")
    for o in os:
        print(rf"\quad {SHORT.get(o, o)} & " + " & ".join(entry(x) for x in values[o]) + r" \\")

# tier means per task and the models whose popular tier lies above the unpopular and the synthetic tier
names = list(TIERS)
for i, t in enumerate(TASKS):
    means = [tier_values[name][i] for name in names]
    steps = ", ".join(f"{upper.lower()} > {lower.lower()} {'holds' if a > b else 'breaks'}"
                      for upper, lower, a, b in zip(names, names[1:], means, means[1:]))
    above = {lower: sum(model_tier_value("Popular", t, m) > model_tier_value(lower, t, m) for m in MODELS)
             for lower in ("Unpopular", "Synthetic")}
    print(f"% {t}: " + ", ".join(entry(x) for x in means) + " (" + ", ".join(f"{x:.3f}" for x in means) + f"); {steps}; "
          f"popular above unpopular for {above['Unpopular']} of {len(MODELS)} models, above synthetic for {above['Synthetic']} "
          f"of {len(MODELS)}")
print("% mean per task: " + ", ".join(f"{t} {number(mean(values[o][i] for o in ONTOLOGIES))}" for i, t in enumerate(TASKS)))

dom = TASKS.index("domain")
print(f"% domain, popular tier without Dublin Core Terms: {number(mean(values[o][dom] for o in TIERS['Popular'] if o != DC))} "
      f"against medium {number(tier_values['Medium'][dom])}")
dc = records(DC, "domain")
k, n = questions_left(DC, "domain")
print(f"% domain, Dublin Core Terms: {k} of {n} questions left, {sum(r['strict_match'] for r in dc)} of {len(dc)} answers exact, "
      f"golds {sorted({g for r in dc for g in r['gold_iris']})}")

correct = [r for r in records("W3C Organization Ontology", "range") if r["strict_match"]]
org = sum(any(iri_name(g) == "Organization" and "/ns/org" in g for g in r["gold_iris"]) for r in correct)
print(f"% range, W3C Organization correct answers with gold org:Organization: {org} of {len(correct)}")

state = [r for r in records("Weather Patterns", "property", False) if iri_name(r["given_iri"]) == "TemperatureState"]
named = sum(any(g in r["parsed"] for g in r["gold"] if g.endswith("hasTemperature")) for r in state)
print(f"% property, Weather Patterns TemperatureState (name-inferable: {name_inferable(state[0])}): hasTemperature named in "
      f"{named} of {len(state)} answers, gold {state[0]['gold']}")
runs = [(o, m, f) for o in ONTOLOGIES for m in MODELS for f in FORMATS]
print(f"% property task, runs with EM rate 0: {sum(em_rate(*run) == 0 for run in runs)} of {len(runs)}")
counts = {m: property_counts(m) for m in MODELS}
print("% property task, listed per gold property: "
      + ", ".join(f"{m} {(tp + fp) / (tp + fn):.1f}" for m, (tp, fp, fn) in counts.items()))
