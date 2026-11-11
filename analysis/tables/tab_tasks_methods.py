"""Tables tab:gp-tasks and tab:mink-tasks: Guided Prompting and Min-K% Prob per ontology and task"""
import statistics
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple

from analysis.common import FORMATS, MAKI, MODELS, ONTOLOGIES, RESULTS, SHORT, TASKS, TIERS, load_records, number, read_aggregate
from analysis.tables import tab_mink_full
from analysis.ts_filtered import matrix, mean_f1

MK_TASKS = ["taxonomy", "domain", "range"]
REAL = ["Popular", "Medium", "Unpopular"]
DC = "Dublin Core Terms"


def gp_run(o: str, t: str, m: str, fmt: str) -> Path:
    return RESULTS / "runs" / "guided-prompting" / f"GP__{o.replace(' ', '-')}__{t}__{m}__{fmt}"


def mk_run(o: str, t: str, m: str, fmt: str) -> Path:
    return RESULTS / "runs" / "min-k" / f"MK__{o.replace(' ', '-')}__{t}__{m}__{fmt}"


# values per (ontology, task, model, format)
ts = matrix(True)  # TS-Guessing run F1 without the name-inferable questions, None where no question is left
gp = {(r["ontology"], r["task"], r["model"], r["id_format"]): float(r["gap"])
      for r in read_aggregate("gp_aggregate.csv") if r["measure"] == "wup" and r["segment"] == "all"}
mk = tab_mink_full.cells


class Method(NamedTuple):
    tasks: list[str]
    models: list[str]
    value: Callable[[str, str, str], float | None]  # value of one ontology, task and model
    signed: bool  # entries with an explicit plus


METHODS = {
    "TS": Method(TASKS, MODELS, lambda o, t, m: mean_f1((o, t, m, f) for f in FORMATS), False),
    "GP": Method(TASKS, MODELS, lambda o, t, m: gp[(o, t, m, "plain")], True),
    "MK": Method(MK_TASKS, MAKI, lambda o, t, m: statistics.mean(mk[(o, t, m, f)] for f in FORMATS), False),
}
NAMES = {"TS": "TS-Guessing micro F1", "GP": "Guided Prompting gap, plain format", "MK": "Min-20% score"}


def mean(xs) -> float | None:
    """Mean of the values that are not None, None if there is none"""
    kept = [x for x in xs if x is not None]
    return statistics.mean(kept) if kept else None


def ontology_value(k: str, o: str, t: str) -> float | None:
    """Mean over the models of the method, for TS-Guessing over all runs of the task"""
    method = METHODS[k]
    if k == "TS":
        return mean_f1((o, t, m, f) for m in method.models for f in FORMATS)
    return statistics.mean(method.value(o, t, m) for m in method.models)


def tier_value(k: str, tier: str, t: str, model: str | None = None) -> float | None:
    """Mean over the ontologies of a tier that still have questions, for one model or over the models of the method"""
    if model is None:
        return mean(ontology_value(k, o, t) for o in TIERS[tier])
    return mean(METHODS[k].value(o, t, model) for o in TIERS[tier])


def per_model(k: str, t: str) -> dict[str, list[float]]:
    """Tier means of every model of the method, in the order of TIERS"""
    return {m: [tier_value(k, tier, t, m) for tier in TIERS] for m in METHODS[k].models}


def entry(k: str, x: float | None) -> str:
    return "--" if x is None else number(x, METHODS[k].signed)


if __name__ == "__main__":
    # the Guided Prompting columns form tab:gp-tasks, the Min-K% Prob columns tab:mink-tasks
    columns = [(k, t) for k in ("GP", "MK") for t in METHODS[k].tasks]
    for tier, ontologies in TIERS.items():
        entries = [entry(k, tier_value(k, tier, t)) for k, t in columns]
        print(rf"\rowcolor{{tierrow}}\textbf{{{tier}}} & " + " & ".join(entries) + r" \\")
        for o in ontologies:
            entries = [entry(k, ontology_value(k, o, t)) for k, t in columns]
            print(rf"\quad {SHORT.get(o, o)} & " + " & ".join(entries) + r" \\")

    # tier means per method and task, models counted on their own tier means
    for k, method in METHODS.items():
        n = len(method.models)
        print(f"% {NAMES[k]}, tier means per task")
        for t in method.tasks:
            means = [tier_value(k, tier, t) for tier in TIERS]  # popular, medium, unpopular, synthetic
            by_model = per_model(k, t).values()
            order = sum(v[0] > v[1] > v[2] for v in by_model)
            print(f"%   {t}: " + ", ".join(entry(k, x) for x in means)
                  + f"; order {'holds' if means[0] > means[1] > means[2] else 'breaks'}, {order} of {n} models"
                  + f" (popular > medium {sum(v[0] > v[1] for v in by_model)}, medium > unpopular {sum(v[1] > v[2] for v in by_model)})"
                  + f"; synthetic below unpopular {sum(v[3] < v[2] for v in by_model)} of {n} models")

    pairs = [(x, y) for a, b in [(0, 1), (1, 2), (0, 2)] for x in TIERS[REAL[a]] for y in TIERS[REAL[b]]]  # x from the higher tier
    mk_value = METHODS["MK"].value
    print(f"% MK real tier pairs in expected order (of {len(MAKI) * len(pairs)}): " + ", ".join(
        f"{t} {sum(mk_value(x, t, m) > mk_value(y, t, m) for m in MAKI for x, y in pairs)}" for t in MK_TASKS))
    # blocks per ontology and task, the same for every model and format
    blocks = {(o, t): len(load_records(mk_run(o, t, MAKI[0], "plain"))) for o in ONTOLOGIES for t in MK_TASKS}
    print("% MK blocks per task and tier: " + "; ".join(
        f"{tier} " + ", ".join(f"{t} {sum(blocks[(o, t)] for o in TIERS[tier])}" for t in MK_TASKS) for tier in TIERS))
    print("% MK tasks with a single block: " + ", ".join(f"{SHORT.get(o, o)} {t}" for (o, t), n in blocks.items() if n == 1))

    print(f"% domain task, {DC} against the popular tier without it and the medium tier, models with popular above medium")
    rest = [o for o in TIERS["Popular"] if o != DC]
    for k, method in METHODS.items():
        lead = sum(mean(method.value(o, "domain", m) for o in rest) > tier_value(k, "Medium", "domain", m) for m in method.models)
        without_dc = mean(ontology_value(k, o, "domain") for o in rest)
        print(f"%   {k}: {DC} {entry(k, ontology_value(k, DC, 'domain'))}, popular without it {entry(k, without_dc)}, "
              f"medium {entry(k, tier_value(k, 'Medium', 'domain'))}; {lead} of {len(method.models)} models")
    records = [r for m in MODELS for r in load_records(gp_run(DC, "domain", m, "plain"))]
    golds = sorted({g for r in records for g in r["gold_iris"]})
    normal, guided = sum(r["sim_normal"]["wup"] > 0 for r in records), sum(r["sim_guided"]["wup"] > 0 for r in records)
    ts_hits = sum(ts[(DC, "domain", m, f)] > 0 for m in MODELS for f in FORMATS)
    print(f"%   {DC} domain questions {len(records) // len(MODELS)}, golds {golds}; "
          f"plain GP answers with similarity above 0: normal {normal}, guided {guided} of {len(records)}; "
          f"TS F1 above 0 in {ts_hits} of {len(MODELS) * len(FORMATS)} runs")
    block = load_records(mk_run(DC, "domain", MAKI[0], "plain"))
    print(f"%   MK {DC} domain: {len(block)} block of {block[0]['n_axioms']} axioms")
