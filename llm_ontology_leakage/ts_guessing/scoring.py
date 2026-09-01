"""Scoring for TS-Guessing, strict Exact Match (EM) and pooled precision/recall/F1"""

from ..core.parsing import parse_elements
from ..core.reporting import SEGMENTS
from ..core.tasks import MatchMode

SCORINGS = ("strict",)


def strict_match(parsed: list[str], gold_rendered: list[str], match_mode: MatchMode) -> bool:
    """Strict match for the single answer tasks and the property task"""
    if match_mode == "any_of":  # single answer tasks (answer must be one of the golds)
        return bool(parsed) and parsed[0] in set(gold_rendered)
    return set(parsed) == set(gold_rendered)  # property task (answer must match the whole gold set)


def confusion_counts(
    parsed: list[str], gold_rendered: list[str], match_mode: MatchMode
) -> tuple[int, int, int]:
    """Count (tp, fp, fn) of one record for precision/recall/F1"""
    gold = set(gold_rendered)
    if match_mode == "any_of":
        answer = parsed[0] if parsed else ""
        if answer in gold:
            return 1, 0, 0
        return (0, 1, 1) if answer else (0, 0, 1)  # miss is one fp and fn, empty answer only one fn
    # property task
    predicted = set(parsed) - {""}  # drop empty elements
    tp = len(predicted & gold)
    return tp, len(predicted) - tp, len(gold) - tp


def score(
    raw_output: str,
    gold_rendered: list[str],
    *,
    list_valued: bool,
    match_mode: MatchMode,
) -> tuple[list[str], bool]:
    """Parse raw model output"""
    parsed = parse_elements(raw_output, list_valued)
    return parsed, strict_match(parsed, gold_rendered, match_mode)


def metrics_table(scored: list[dict]) -> dict[str, dict[str, dict]]:
    """Compute EM and pooled precision/recall/F1 per segment"""
    table: dict[str, dict[str, dict]] = {}
    for scoring in SCORINGS:
        table[scoring] = {}
        for segment in SEGMENTS:
            if segment == "all":
                rows = scored
            elif segment == "gold_in_ns":
                rows = [r for r in scored if r["gold_in_ns"]]
            else:
                rows = [r for r in scored if not r["gold_in_ns"]]
            n, n_match = len(rows), sum(bool(r[scoring]) for r in rows)
            # segment counts pooled first, then ratios computed once (micro averaging)
            tp = sum(r["tp"] for r in rows)
            fp = sum(r["fp"] for r in rows)
            fn = sum(r["fn"] for r in rows)
            precision = tp / (tp + fp) if (tp + fp) else None
            recall = tp / (tp + fn) if (tp + fn) else None
            if precision is None or recall is None:
                f1 = None
            elif precision + recall == 0:
                f1 = 0.0
            else:
                f1 = 2 * precision * recall / (precision + recall)
            table[scoring][segment] = {
                "n": n,
                "n_match": n_match,
                "em": (n_match / n) if n else None,
                "tp": tp,
                "fp": fp,
                "fn": fn,
                "precision": precision,
                "recall": recall,
                "f1": f1,
            }
    return table
