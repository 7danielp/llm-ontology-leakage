"""Aggregation of the TS-Guessing runs into CSV and LaTeX tables"""

import csv
from pathlib import Path

from ..core.config import GRID_FORMATS, GRID_MODELS, GRID_TASKS, ONTOLOGY_PRESETS
from ..core.reporting import SEGMENTS, fmt_cell, latex_matrix, model_label, ordered, with_run_column
from ..core.runs import load_runs
from ..core.tasks import TASKS
from .runner import METHOD
from .scoring import SCORINGS, confusion_counts, metrics_table, score


def aggregate_ts(results_dir: Path) -> dict[str, Path]:
    """Collect all TS-Guessing runs and write ts_aggregate.csv plus the EM and F1 matrices (CSV and LaTeX)"""
    runs = [r for r in load_runs(results_dir) if r["meta"].get("method") == METHOD]
    if not runs:
        raise RuntimeError(f"No completed ts-guessing runs found under {results_dir / 'runs'}")

    long_rows: list[dict] = []
    cells: dict[str, dict[tuple[str, str, str], float | None]] = {s: {} for s in SCORINGS}
    f1_cells: dict[tuple[str, str, str], float | None] = {}

    for run in runs:
        ident = run["meta"]["identity"]
        spec = TASKS[ident["task"]]

        # recompute the score from raw model output
        scored = []
        for r in run["records"]:
            parsed, strict = score(
                r["raw_output"],
                r["gold"],
                list_valued=spec.list_valued,
                match_mode=spec.match,
            )
            tp, fp, fn = confusion_counts(parsed, r["gold"], spec.match)
            scored.append(
                {
                    "gold_in_ns": r["gold_in_ontology_namespace"],
                    "truncated": r["finish_reason"] == "length",
                    "strict": strict,
                    "tp": tp,
                    "fp": fp,
                    "fn": fn,
                }
            )
        table = metrics_table(scored)
        # matrix rows carry the ontology in their names so runs on different ontologies do not collide
        label = model_label(ident["model"], run["meta"]["run"])
        key = (f"{ident['ontology_name']}/{ident['task']}", label, ident["id_format"])
        f1_cells[key] = table["strict"]["all"]["f1"]
        for scoring in SCORINGS:
            cells[scoring][key] = table[scoring]["all"]["em"]
            for segment in SEGMENTS:
                cell = table[scoring][segment]
                in_segment = [s for s in scored if segment == "all" or s["gold_in_ns"] == (segment == "gold_in_ns")]
                long_rows.append(
                    {
                        "method": run["meta"]["method"],
                        "ontology": ident["ontology_name"],
                        "task": ident["task"],
                        "model": ident["model"],
                        "run": run["meta"]["run"],
                        "id_format": ident["id_format"],
                        "scoring": scoring,
                        "segment": segment,
                        "n": cell["n"],
                        "n_match": cell["n_match"],
                        "n_truncated": sum(s["truncated"] for s in in_segment),
                        "em": fmt_cell(cell["em"]),
                        "tp": cell["tp"],
                        "fp": cell["fp"],
                        "fn": cell["fn"],
                        "precision": fmt_cell(cell["precision"]),
                        "recall": fmt_cell(cell["recall"]),
                        "f1": fmt_cell(cell["f1"]),
                    }
                )

    # row and column order follows the grid configuration
    onto_tasks = ordered(
        {r["ontology"] + "/" + r["task"] for r in long_rows},
        [f"{p['ontology_name']}/{t}" for p in ONTOLOGY_PRESETS.values() for t in GRID_TASKS],
    )
    models = ordered({model_label(r["model"], r["run"]) for r in long_rows}, GRID_MODELS)
    formats = ordered({r["id_format"] for r in long_rows}, list(GRID_FORMATS))

    def sort_key(row: dict) -> tuple:
        """Sort by ontology/task, then model, format, scoring, segment"""
        return (
            onto_tasks.index(row["ontology"] + "/" + row["task"]),
            models.index(model_label(row["model"], row["run"])),
            formats.index(row["id_format"]),
            SCORINGS.index(row["scoring"]),
            SEGMENTS.index(row["segment"]),
        )

    long_rows.sort(key=sort_key)

    outputs: dict[str, Path] = {}

    # complete results in one CSV table (one row per run x scoring x segment)
    agg_path = results_dir / "ts_aggregate.csv"
    with open(agg_path, "w", newline="", encoding="utf-8") as f:
        fieldnames = with_run_column([
            "method", "ontology", "task", "model", "run", "id_format", "scoring", "segment",
            "n", "n_match", "n_truncated", "em", "tp", "fp", "fn", "precision", "recall", "f1",
        ], long_rows)
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(long_rows)
    outputs["ts_aggregate"] = agg_path

    # compact overview matrices, where each cell is the EM or F1 of one run (on segment "all")
    matrices: list[tuple[str, dict[tuple[str, str, str], float | None]]] = [
        (scoring, cells[scoring]) for scoring in SCORINGS
    ] + [("f1", f1_cells)]
    for name, matrix_cells in matrices:
        matrix_path = results_dir / f"ts_matrix_{name}.csv"
        with open(matrix_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                ["ontology/task"] + [f"{m}|{fmt}" for m in models for fmt in formats]
            )
            for ot in onto_tasks:
                writer.writerow(
                    [ot]
                    + [
                        fmt_cell(matrix_cells.get((ot, m, fmt)))
                        for m in models
                        for fmt in formats
                    ]
                )
        outputs[f"ts_matrix_{name}"] = matrix_path

        # LaTeX version of each matrix
        tex_path = results_dir / f"ts_matrix_{name}.tex"
        tex_path.write_text(
            latex_matrix(onto_tasks, models, formats, matrix_cells), encoding="utf-8"
        )
        outputs[f"latex_{name}"] = tex_path

    return outputs
