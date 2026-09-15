"""Aggregation of the Guided Prompting runs into CSV and LaTeX tables"""

import csv
import json
import random
from pathlib import Path

from rdflib import URIRef

from ..core.reporting import SEGMENTS, fmt_cell, latex_matrix, ordered, model_label, with_run_column
from ..core.runs import load_runs
from ..core.config import (
    DEFAULT_AXIOM_PREDICATES,
    GRID_FORMATS,
    GRID_MODELS,
    GRID_TASKS,
    ONTOLOGY_PRESETS,
)
from .runner import METHOD, gp_score
from ..core.ontology import EntityResolver, load_graph
from .similarity import MEASURES, ClassSimilarity, PropertySimilarity
from ..core.tasks import TASKS

NUM_RESAMPLES = 10_000
BOOTSTRAP_SEED = 42  # fixed seed (for reproducibility)
P_SIGNIFICANT = 0.05


def bootstrap_p_value(
    scores_normal: list[float], scores_guided: list[float], rng: random.Random
) -> float:
    """Compute the one sided bootstrap p value (guided > normal)"""
    count = 0
    # both score lists are resampled independently with replacement, counting how often the guided mean is larger
    for _ in range(NUM_RESAMPLES):
        mean_normal = sum(rng.choices(scores_normal, k=len(scores_normal))) / len(scores_normal)
        mean_guided = sum(rng.choices(scores_guided, k=len(scores_guided))) / len(scores_guided)
        if mean_guided > mean_normal:
            count += 1
    return 1.0 - count / NUM_RESAMPLES


def aggregate_gp(results_dir: Path) -> dict[str, Path]:
    """Collect all Guided Prompting runs and write gp_aggregate.csv plus one gap matrix per measure (CSV and LaTeX)"""
    runs = [r for r in load_runs(results_dir) if r["meta"].get("method") == METHOD]
    if not runs:
        raise RuntimeError(f"No guided-prompting runs found under {results_dir / 'runs'}")

    context: dict[tuple, tuple] = {}  # (source, ns, prefix_map, predicates) -> (resolver, class_sim, prop_sim)
    rows: list[dict] = []
    cells: dict[str, dict[tuple[str, str, str], float | None]] = {m: {} for m in MEASURES}

    for run in runs:
        ident = run["meta"]["identity"]
        spec = TASKS[ident["task"]]
        key = (ident["ontology_source"], ident["ontology_namespace"], json.dumps(run["meta"].get("prefix_map", {}), sort_keys=True), json.dumps(run["meta"].get("axiom_predicates") or {}, sort_keys=True))
        if key not in context:
            graph = load_graph(
                ident["ontology_source"], run["meta"].get("prefix_map", {})
            )
            predicates = {**DEFAULT_AXIOM_PREDICATES, **(run["meta"].get("axiom_predicates") or {})}  # use the predicates from the run's meta
            class_sim = ClassSimilarity(graph, URIRef(predicates["taxonomy"]))
            context[key] = (
                EntityResolver(graph, ident["ontology_namespace"]),
                class_sim,
                PropertySimilarity(
                    graph, class_sim,
                    URIRef(predicates["domain"]), URIRef(predicates["range"]),
                ),
            )
        resolver, class_sim, prop_sim = context[key]

        # recompute the similarities of both completions from raw model output
        scored = []
        for r in run["records"]:
            scored.append(
                {
                    "gold_in_ns": r["gold_in_ontology_namespace"],
                    "truncated_normal": r["finish_reason_normal"] == "length",
                    "truncated_guided": r["finish_reason_guided"] == "length",
                    "normal": gp_score(
                        r["raw_normal"], r["gold_iris"], spec, resolver, class_sim, prop_sim
                    ),
                    "guided": gp_score(
                        r["raw_guided"], r["gold_iris"], spec, resolver, class_sim, prop_sim
                    ),
                }
            )

        # matrix rows carry the ontology in their names so runs on different ontologies do not collide
        run_key = (f"{ident['ontology_name']}/{ident['task']}", model_label(ident["model"], run["meta"]["run"]), ident["id_format"])
        for measure in MEASURES:
            for segment in SEGMENTS:
                if segment == "all":
                    sel = scored
                elif segment == "gold_in_ns":
                    sel = [s for s in scored if s["gold_in_ns"]]
                else:
                    sel = [s for s in scored if not s["gold_in_ns"]]
                n = len(sel)
                if n == 0:
                    mean_normal = mean_guided = gap = p_value = None
                else:
                    normal = [s["normal"][measure] for s in sel]
                    guided = [s["guided"][measure] for s in sel]
                    mean_normal = sum(normal) / n
                    mean_guided = sum(guided) / n
                    gap = mean_guided - mean_normal
                    p_value = bootstrap_p_value(
                        normal, guided, random.Random(BOOTSTRAP_SEED)
                    )
                rows.append(
                    {
                        "method": METHOD,
                        "ontology": ident["ontology_name"],
                        "task": ident["task"],
                        "model": ident["model"],
                        "run": run["meta"]["run"],
                        "id_format": ident["id_format"],
                        "measure": measure,
                        "segment": segment,
                        "n": n,
                        "n_truncated_normal": sum(s["truncated_normal"] for s in sel),
                        "n_truncated_guided": sum(s["truncated_guided"] for s in sel),
                        "mean_normal": fmt_cell(mean_normal),
                        "mean_guided": fmt_cell(mean_guided),
                        "gap": fmt_cell(gap),
                        "p_value": fmt_cell(p_value),
                        "significant": (
                            "" if p_value is None else str(int(p_value <= P_SIGNIFICANT))
                        ),
                    }
                )
                if segment == "all":
                    cells[measure][run_key] = gap

    # row and column order follows the grid configuration
    onto_tasks = ordered(
        {r["ontology"] + "/" + r["task"] for r in rows},
        [f"{p['ontology_name']}/{t}" for p in ONTOLOGY_PRESETS.values() for t in GRID_TASKS],
    )
    models = ordered({model_label(r["model"], r["run"]) for r in rows}, GRID_MODELS)
    formats = ordered({r["id_format"] for r in rows}, list(GRID_FORMATS))

    outputs: dict[str, Path] = {}

    # complete results in one CSV table (one row per run x measure x segment)
    agg_path = results_dir / "gp_aggregate.csv"
    fieldnames = with_run_column([
        "method", "ontology", "task", "model", "run", "id_format", "measure", "segment",
        "n", "n_truncated_normal", "n_truncated_guided", "mean_normal", "mean_guided", "gap", "p_value", "significant",
    ], rows)
    rows.sort(
        key=lambda r: (
            onto_tasks.index(r["ontology"] + "/" + r["task"]),
            models.index(model_label(r["model"], r["run"])),
            formats.index(r["id_format"]),
            MEASURES.index(r["measure"]),
            SEGMENTS.index(r["segment"]),
        )
    )
    with open(agg_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    outputs["gp_aggregate"] = agg_path

    # compact overview matrices, where each cell is the gap of one run (on segment "all")
    for measure in MEASURES:
        matrix_path = results_dir / f"gp_matrix_{measure}.csv"
        with open(matrix_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["ontology/task"] + [f"{m}|{fmt}" for m in models for fmt in formats])
            for ot in onto_tasks:
                writer.writerow(
                    [ot]
                    + [fmt_cell(cells[measure].get((ot, m, fmt))) for m in models for fmt in formats]
                )
        outputs[f"gp_matrix_{measure}"] = matrix_path

        # LaTeX version of each matrix (Path Length and Wu & Palmer)
        tex_path = results_dir / f"gp_matrix_{measure}.tex"
        tex_path.write_text(
            latex_matrix(onto_tasks, models, formats, cells[measure]), encoding="utf-8"
        )
        outputs[f"gp_latex_{measure}"] = tex_path
    return outputs
