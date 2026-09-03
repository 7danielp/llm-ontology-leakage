"""Aggregation of the Min-K% runs into CSV and LaTeX tables"""

import csv
from pathlib import Path

from ..core.config import GRID_FORMATS, GRID_MODELS, ONTOLOGY_PRESETS
from ..core.reporting import fmt_cell, latex_matrix, ordered
from ..core.runs import load_runs
from .runner import METHOD, MINK_TASKS, PRIMARY_RATIO, RATIO_SWEEP, min_k_score


def aggregate_mink(results_dir: Path) -> dict[str, Path]:
    """Collect all Min-K runs and write mink_aggregate.csv plus the mean min-20 matrix (CSV and LaTeX)"""
    runs = [r for r in load_runs(results_dir) if r["meta"].get("method") == METHOD]
    if not runs:
        raise RuntimeError(f"No min-k runs found under {results_dir / 'runs'}")

    # collect all records of a cell for the "all" row (ontology x model x format)
    groups: dict[tuple[str, str, str], list[dict]] = {}
    idents: dict[tuple[str, str, str], dict] = {}
    for run in runs:
        ident = run["meta"]["identity"]
        key = (ident["ontology_name"], ident["model"], ident["id_format"])
        groups.setdefault(key, []).extend(run["records"])
        idents[key] = ident
    for key, recs in groups.items():
        block_keys = [(r["task"], r["key"]) for r in recs]
        if len(block_keys) != len(set(block_keys)):
            raise RuntimeError(
                f"duplicate min-k blocks for {key}! The runs directory probably "
                "mixes an old combined run with new per-task runs, delete one."
            )

    rows: list[dict] = []
    cells: dict[tuple[str, str, str], float | None] = {}
    task_order = ["all", *MINK_TASKS]
    for group_key, records in groups.items():
        ident = idents[group_key]
        per_task: dict[str, list[dict]] = {"all": list(records)}
        for r in records:
            per_task.setdefault(r["task"], []).append(r)
        for task in [t for t in task_order if t in per_task]:
            rs = per_task[task]
            row = {
                "method": METHOD,
                "ontology": ident["ontology_name"],
                "model": ident["model"],
                "id_format": ident["id_format"],
                "task": task,
                "n_blocks": len(rs),
                "n_axioms": sum(r["n_axioms"] for r in rs),
                "n_tokens": sum(
                    sum(1 for x in r["token_logprobs"] if x is not None) for r in rs
                ),
            }
            # recompute the scores from the logged token log probs
            for ratio in RATIO_SWEEP:
                scores = [min_k_score(r["token_logprobs"], ratio) for r in rs]
                row[f"mean_min_{int(ratio * 100)}"] = fmt_cell(sum(scores) / len(scores))
            rows.append(row)
            key = (f"{ident['ontology_name']}/{task}", ident["model"], ident["id_format"])
            primary = [min_k_score(r["token_logprobs"], PRIMARY_RATIO) for r in rs]
            cells[key] = sum(primary) / len(primary)

    # row and column order follows the grid configuration
    onto_tasks = ordered(
        {r["ontology"] + "/" + r["task"] for r in rows},
        [f"{p['ontology_name']}/{t}" for p in ONTOLOGY_PRESETS.values() for t in task_order],
    )
    models = ordered({r["model"] for r in rows}, GRID_MODELS)
    formats = ordered({r["id_format"] for r in rows}, list(GRID_FORMATS))
    rows.sort(
        key=lambda r: (
            onto_tasks.index(r["ontology"] + "/" + r["task"]),
            models.index(r["model"]),
            formats.index(r["id_format"]),
        )
    )

    outputs: dict[str, Path] = {}

    # complete results in one CSV table (one row per cell x task, plus the pooled "all" row)
    agg_path = results_dir / "mink_aggregate.csv"
    fieldnames = ["method", "ontology", "model", "id_format", "task", "n_blocks", "n_axioms",
                  "n_tokens"] + [f"mean_min_{int(r * 100)}" for r in RATIO_SWEEP]
    with open(agg_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    outputs["mink_aggregate"] = agg_path

    # compact overview matrix, where each cell is the mean min-20 of one cell (rows include the "all" row)
    matrix_path = results_dir / "mink_matrix.csv"
    with open(matrix_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["ontology/task"] + [f"{m}|{fmt}" for m in models for fmt in formats])
        for ot in onto_tasks:
            writer.writerow(
                [ot] + [fmt_cell(cells.get((ot, m, fmt))) for m in models for fmt in formats]
            )
    outputs["mink_matrix"] = matrix_path

    # LaTeX version of the matrix
    tex_path = results_dir / "mink_matrix.tex"
    tex_path.write_text(latex_matrix(onto_tasks, models, formats, cells), encoding="utf-8")
    outputs["mink_latex"] = tex_path
    return outputs
