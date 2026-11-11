"""TS-Guessing micro F1 of each run without the name-inferable questions"""
import functools
import statistics
from collections.abc import Iterable
from pathlib import Path

from analysis.common import FORMATS, MODELS, ONTOLOGIES, RESULTS, TASKS, load_records, name_inferable

from llm_ontology_leakage.core.tasks import TASKS as SPECS
from llm_ontology_leakage.ts_guessing.scoring import confusion_counts, score

Cell = tuple[str, str, str, str]  # (ontology, task, model, format)


def run_dir(ontology: str, task: str, model: str, fmt: str) -> Path:
    return RESULTS / "runs" / "ts-guessing" / f"TS__{ontology.replace(' ', '-')}__{task}__{model}__{fmt}"


@functools.cache
def _questions(ontology: str, task: str, model: str, fmt: str) -> list[tuple[bool, int, int, int]]:
    """(name-inferable, tp, fp, fn) per question of one run, scored as in the pipeline"""
    spec = SPECS[task]
    questions = []
    for r in load_records(run_dir(ontology, task, model, fmt)):
        parsed, _ = score(r["raw_output"], r["gold"], list_valued=spec.list_valued, match_mode=spec.match)
        questions.append((name_inferable(r), *confusion_counts(parsed, r["gold"], spec.match)))
    return questions


def run_f1(ontology: str, task: str, model: str, fmt: str, filtered: bool = True) -> float | None:
    """Micro F1 of one run, None if the filter removes all its questions"""
    kept = [q for q in _questions(ontology, task, model, fmt) if not (filtered and q[0])]
    tp, fp, fn = (sum(q[i] for q in kept) for i in (1, 2, 3))
    return 2 * tp / (2 * tp + fp + fn) if kept else None


@functools.cache
def questions_left(ontology: str, task: str) -> tuple[int, int]:
    """(questions left after the name filter, all questions) of an ontology and task, the same in every run"""
    records = load_records(run_dir(ontology, task, MODELS[0], "plain"))
    return sum(not name_inferable(r) for r in records), len(records)


@functools.cache
def matrix(filtered: bool = True) -> dict[Cell, float | None]:
    """{(ontology, task, model, format): run F1}"""
    return {(o, t, m, f): run_f1(o, t, m, f, filtered) for o in ONTOLOGIES for t in TASKS for m in MODELS for f in FORMATS}


def mean_f1(cells: Iterable[Cell], filtered: bool = True) -> float | None:
    """Mean run F1 over the cells that still have questions, None if none has"""
    values = [v for c in cells if (v := run_f1(*c, filtered)) is not None]
    return statistics.mean(values) if values else None


def ontology_f1(ontology: str, model: str, filtered: bool = True) -> float:
    """Mean run F1 over the four tasks and three formats, one entry of Table tab:ts-names"""
    return mean_f1(((ontology, t, model, f) for t in TASKS for f in FORMATS), filtered)
