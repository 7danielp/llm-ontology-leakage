"""Helpers for the run directories of all three methods"""

import json
from pathlib import Path

from dataclasses import replace
from typing import Any, Callable

from .config import IdFormat, RunConfig

# Settings that uniquely define a run (written to run_meta.json)
RUN_IDENTITY_FIELDS = (
    "task",
    "model",
    "id_format",
    "ontology_source",
    "ontology_name",
    "ontology_namespace",
    "temperature",
)


METHOD_DIRS = {"TS": "ts-guessing", "GP": "guided-prompting", "MK": "min-k"}


def run_dir_for(cfg: RunConfig, method_prefix: str) -> Path:
    """Build the path to the run directory (stores records.jsonl, run_meta.json, summary.json)"""
    name = f"{cfg.ontology_name.replace(' ', '-')}__{cfg.task}__{cfg.model}__{cfg.id_format}"
    return cfg.results_dir / "runs" / METHOD_DIRS[method_prefix] / f"{method_prefix}__{name}"


def write_meta(
    run_dir: Path, cfg: RunConfig, method: str, client_name: str,
    sampled_keys: list[str] | None = None, sampled_from: str | None = None,
) -> None:
    """Write run_meta.json with the settings of the run, plus a sample block for sampled runs"""
    meta = {
        "method": method,
        "client": client_name,
        "identity": {f: getattr(cfg, f) for f in RUN_IDENTITY_FIELDS},
        "prefix_map": cfg.prefix_map,
        "format_example_iris": None if method == "min-k" else cfg.format_examples.get(cfg.task),
        "axiom_predicates": cfg.axiom_predicates,
        "limit": cfg.limit,
    }
    if cfg.sample is not None:
        meta["sample"] = {"n": cfg.sample, "seed": cfg.seed, "keys": sampled_keys}
        if sampled_from is not None:
            meta["sample"]["from"] = sampled_from
    (run_dir / "run_meta.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def read_records(run_dir: Path) -> list[dict]:
    """Read the records.jsonl of a run"""
    lines = (run_dir / "records.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def load_runs(results_dir: Path) -> list[dict]:
    """Load all completed runs under results/runs (one dict per run with dir, meta and records)"""
    runs = []
    for meta_file in sorted((results_dir / "runs").rglob("run_meta.json")):
        run_dir = meta_file.parent
        records_file = run_dir / "records.jsonl"
        if not records_file.is_file():
            continue
        # summary.json is written last (crashed or still running directories are skipped with a notice)
        if not (run_dir / "summary.json").is_file():
            print(f"  (skipping incomplete run {run_dir.name}: no summary.json)")
            continue
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
        runs.append({"dir": run_dir, "meta": meta, "records": read_records(run_dir)})
    clients = {r["meta"].get("client", "MakiClient") for r in runs}
    if "MockClient" in clients and len(clients) > 1:
        raise RuntimeError(
            f"{results_dir / 'runs'} mixes mock and real runs! "
            "Delete the mock directories first."
        )
    return runs


def run_grid(
    base_cfg: RunConfig,
    client,
    tasks: list[str],
    models: list[str],
    formats: list[IdFormat],
    runner: Callable,
) -> list[dict[str, Any]]:
    """Run every task x model x format combination with a given runner (from main.py)"""
    combos = [(t, m, f) for t in tasks for m in models for f in formats]
    results = []
    for i, (task, model, fmt) in enumerate(combos, start=1):
        print(f"\n=== run {i}/{len(combos)}: task={task} model={model} format={fmt} ===")
        cfg = replace(base_cfg, task=task, model=model, id_format=fmt)
        results.append(runner(cfg, client))
    return results
