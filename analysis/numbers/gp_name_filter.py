"""Guided Prompting without the name-inferable questions for Table tab:name-filter: gap per run, ontology and tier"""
import functools
import statistics

from scipy.stats import ttest_rel

from analysis.common import MODELS, RESULTS, TASKS, TIERS, load_records, name_inferable

RUNS = RESULTS / "runs" / "guided-prompting"


@functools.cache
def records(ontology: str, task: str, model: str) -> tuple[dict, ...]:
    """Records of a run in the plain format"""
    return tuple(load_records(RUNS / f"GP__{ontology.replace(' ', '-')}__{task}__{model}__plain"))


def run_gap(ontology: str, task: str, model: str, filtered: bool) -> float | None:
    """Gap of a run, without the name-inferable questions if filtered, None if no question remains"""
    rs = [r for r in records(ontology, task, model) if not (filtered and name_inferable(r))]
    if not rs:
        return None
    return statistics.mean(r["sim_guided"]["wup"] for r in rs) - statistics.mean(r["sim_normal"]["wup"] for r in rs)


def ontology_gap(ontology: str, model: str, filtered: bool) -> float:
    """Mean over the tasks that keep questions"""
    return statistics.mean(v for t in TASKS if (v := run_gap(ontology, t, model, filtered)) is not None)


def tier_means(model: str, filtered: bool) -> list[float]:
    return [statistics.mean(ontology_gap(o, model, filtered) for o in ontologies) for ontologies in TIERS.values()]


def removed(ontology: str, task: str) -> tuple[int, int]:
    """(name-inferable questions, all questions) of an ontology and task, the same for every model"""
    rs = records(ontology, task, MODELS[0])
    return sum(name_inferable(r) for r in rs), len(rs)


def tier_tests(filtered: bool) -> list[tuple[float, float]]:
    """(Delta, p) of the one-sided paired t-tests between neighbouring tiers over the five models"""
    means = [tier_means(m, filtered) for m in MODELS]
    result = []
    for i in range(len(TIERS) - 1):
        upper, lower = [v[i] for v in means], [v[i + 1] for v in means]
        result.append((statistics.mean(u - l for u, l in zip(upper, lower)), ttest_rel(upper, lower, alternative="greater").pvalue))
    return result
