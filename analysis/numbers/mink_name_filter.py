"""Min-K% Prob without the name-inferable axiom lines for Table tab:name-filter, scored from the stored log probabilities"""
import functools
import itertools
import statistics

from scipy.stats import ttest_rel

from analysis.common import FORMATS, MAKI, RESULTS, TIERS, load_records, name_inferable, number

from llm_ontology_leakage.core.config import ONTOLOGY_PRESETS, build_run_config
from llm_ontology_leakage.core.ontology import axiom_pairs, load_graph
from llm_ontology_leakage.min_k.runner import BLOCK_SIZE, MINK_TASKS, PRIMARY_RATIO, min_k_score

RUNS = RESULTS / "runs" / "min-k"
TASKS = list(MINK_TASKS)  # taxonomy, domain and range
PRESET = {p["ontology_name"]: key for key, p in ONTOLOGY_PRESETS.items()}
W3C = "W3C Organization Ontology"


@functools.cache
def records(ontology: str, task: str, model: str, fmt: str) -> tuple[dict, ...]:
    return tuple(load_records(RUNS / f"MK__{ontology.replace(' ', '-')}__{task}__{model}__{fmt}"))


@functools.cache
def graph(ontology: str):
    cfg = build_run_config(PRESET[ontology], task="taxonomy", model=MAKI[0], id_format="plain")
    return load_graph(cfg.ontology_source, cfg.prefix_map)


@functools.cache
def flags(ontology: str, task: str) -> tuple[tuple[bool, ...], ...]:
    """Per block of a task, whether each line is name-inferable (the name of its subject contains that of its object as whole words)"""
    # the blocks of the runs: the sorted axiom pairs cut into blocks of BLOCK_SIZE lines
    pairs = sorted(axiom_pairs(graph(ontology), build_run_config(PRESET[ontology], task=task, model=MAKI[0], id_format="plain"), task))
    inferable = [name_inferable({"given_iri": str(s), "gold_iris": [str(o)]}) for s, o in pairs]
    return tuple(tuple(inferable[i:i + BLOCK_SIZE]) for i in range(0, len(inferable), BLOCK_SIZE))


def token_lines(r: dict) -> list[int]:
    """Line of every token of a block, a newline token ends its line"""
    result, line = [], 0
    for token in r["tokens"]:
        result.append(line)
        line += token.count("\n")
    return result


def kept_score(r: dict, drop: set[int]) -> float | None:
    """Min-20% over the stored log probabilities of the tokens outside the lines in drop, None if no token is left"""
    kept = [lp for lp, i in zip(r["token_logprobs"], token_lines(r)) if lp is not None and i not in drop]
    return min_k_score(kept, PRIMARY_RATIO) if kept else None


def block_score(r: dict, block: tuple[bool, ...], filtered: bool, check: str | None = None) -> float | None:
    """Min-20% of a block, without its name-inferable lines if filtered, None if no line remains"""
    inferable = {i for i, x in enumerate(block) if x} if filtered else set()
    if len(inferable) == len(block):
        return None
    if check == "matched":  # as many other lines removed instead, mean over every choice, the first line only if name-inferable
        first = {0} if 0 in inferable else set()
        choices = [first | set(c) for c in itertools.combinations(range(1, len(block)), len(inferable) - len(first))]
        return statistics.mean(kept_score(r, drop) for drop in choices)
    if check == "first":  # the first line left out as well
        return kept_score(r, inferable | {0})
    return kept_score(r, inferable)


@functools.cache
def scores(ontology: str, task: str, model: str, fmt: str, filtered: bool, check: str | None = None) -> tuple[float, ...]:
    """Scores of the blocks of one run that keep a line"""
    values = [block_score(r, b, filtered, check) for r, b in zip(records(ontology, task, model, fmt), flags(ontology, task))]
    return tuple(s for s in values if s is not None)


def ontology_score(ontology: str, model: str, filtered: bool, check: str | None = None) -> float:
    """Mean over all blocks of the three tasks in the three formats"""
    return statistics.mean(x for f in FORMATS for t in TASKS for x in scores(ontology, t, model, f, filtered, check))


def tier_means(model: str, filtered: bool) -> list[float]:
    return [statistics.mean(ontology_score(o, model, filtered) for o in ontologies) for ontologies in TIERS.values()]


def removed(ontology: str, task: str) -> tuple[int, int]:
    """(name-inferable lines, all lines) of an ontology and task"""
    lines = [x for block in flags(ontology, task) for x in block]
    return sum(lines), len(lines)


def tier_tests(filtered: bool) -> list[tuple[float, float]]:
    """(Delta, p) of the one-sided paired t-tests between neighbouring tiers over the four open-weight models"""
    means = [tier_means(m, filtered) for m in MAKI]
    result = []
    for i in range(len(TIERS) - 1):
        upper, lower = [v[i] for v in means], [v[i + 1] for v in means]
        result.append((statistics.mean(a - b for a, b in zip(upper, lower)), ttest_rel(upper, lower, alternative="greater").pvalue))
    return result


if __name__ == "__main__":
    blocks = [b for t in TASKS for b in flags(W3C, t)]
    later = [x for b in blocks for x in b[1:]]
    print(f"name-inferable first lines of all blocks, and other lines: W3C Organization {sum(b[0] for b in blocks)} of {len(blocks)} "
          f"and {sum(later)} of {len(later)}")
    changes = {"name-inferable": [ontology_score(W3C, m, True) - ontology_score(W3C, m, False) for m in MAKI],
               "matched": [ontology_score(W3C, m, True, "matched") - ontology_score(W3C, m, False) for m in MAKI],
               "first line left out": [ontology_score(W3C, m, True, "first") - ontology_score(W3C, m, False, "first") for m in MAKI]}
    print("W3C Organization, change of the score: "
          + ", ".join(f"{label} {number(min(v), True)} to {number(max(v), True)}" for label, v in changes.items()))
