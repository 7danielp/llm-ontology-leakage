"""Extract the runs of the plain model with the sampled questions for comparison"""

import argparse
import json
from dataclasses import replace
from pathlib import Path

from rdflib import URIRef

from llm_ontology_leakage.core.config import RunConfig, base_model
from llm_ontology_leakage.core.ontology import EntityResolver, load_graph
from llm_ontology_leakage.core.runs import METHOD_DIRS, read_records, run_dir_for, write_meta
from llm_ontology_leakage.core.tasks import TASKS
from llm_ontology_leakage.guided_prompting.runner import _summarize_gp
from llm_ontology_leakage.guided_prompting.similarity import ClassSimilarity, PropertySimilarity
from llm_ontology_leakage.ts_guessing.runner import _summarize as _summarize_ts

METHOD_PREFIX = {method: prefix for prefix, method in METHOD_DIRS.items()}


def extract_sampled_runs(results_dir: Path, source_dir: Path) -> list[Path]:
    """For every sampled run under results_dir, cut the same questions from the full run under source_dir into sample-reference"""
    written = []
    for meta_file in sorted((results_dir / "runs").rglob("run_meta.json")):
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
        if "sample" not in meta or "from" in meta["sample"]:  # only sampled runs, not the extracted ones
            continue
        cfg = _config_from_meta(meta, results_dir)
        prefix = METHOD_PREFIX[meta["method"]]
        source_run = run_dir_for(replace(cfg, results_dir=source_dir, sample=None), prefix)  # the full run has no sample folder
        target = run_dir_for(cfg, prefix, reference=True)
        if not (source_run / "summary.json").is_file():
            raise FileNotFoundError(f"no complete full run for {meta_file.parent.name} at {source_run}")
        keys = set(meta["sample"]["keys"])
        picked = [r for r in read_records(source_run) if r["key"] in keys]  # both runs are ordered by IRI
        missing = keys - {r["key"] for r in picked}
        if missing:
            raise ValueError(f"{len(missing)} sampled questions are not in {source_run}: {sorted(missing)[:3]}")

        target.mkdir(parents=True, exist_ok=True)
        (target / "summary.json").unlink(missing_ok=True)
        source_meta = json.loads((source_run / "run_meta.json").read_text(encoding="utf-8"))
        write_meta(
            target, cfg, method=meta["method"], client_name=source_meta["client"],
            sampled_keys=meta["sample"]["keys"], sampled_from=str(source_run),
        )
        (target / "records.jsonl").write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in picked), encoding="utf-8"
        )
        summary = _summarize(picked, cfg, meta["method"])
        (target / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
        written.append(target)
    if not written:
        raise RuntimeError(f"No sampled runs found under {results_dir / 'runs'}")
    return written


def _config_from_meta(meta: dict, results_dir: Path) -> RunConfig:
    """Rebuild the RunConfig of a run from its run_meta.json, for the model without web search"""
    ident = meta["identity"]
    return RunConfig(
        ontology_source=ident["ontology_source"],
        ontology_name=ident["ontology_name"],
        ontology_namespace=ident["ontology_namespace"],
        prefix_map=meta["prefix_map"],
        format_examples={ident["task"]: meta["format_example_iris"]},
        task=ident["task"],
        id_format=ident["id_format"],
        model=base_model(ident["model"]),
        temperature=ident["temperature"],
        max_tokens=None,
        axiom_predicates=meta["axiom_predicates"],
        limit=None,
        results_dir=results_dir,
        sample=meta["sample"]["n"],
        seed=meta["sample"]["seed"],
    )


def _summarize(records: list[dict], cfg: RunConfig, method: str) -> dict:
    """The method's own summary of the picked records (the same code as after a run)"""
    spec = TASKS[cfg.task]
    if method == "ts-guessing":
        return _summarize_ts(records, cfg, spec)
    graph = load_graph(cfg.ontology_source, cfg.prefix_map)
    resolver = EntityResolver(graph, cfg.ontology_namespace)
    class_sim = ClassSimilarity(graph, URIRef(cfg.axiom_predicates["taxonomy"]))
    prop_sim = PropertySimilarity(
        graph, class_sim, URIRef(cfg.axiom_predicates["domain"]), URIRef(cfg.axiom_predicates["range"])
    )
    return _summarize_gp(records, cfg, spec, resolver, class_sim, prop_sim)


def main() -> None:
    """Parse the arguments and write the extracted runs"""
    parser = argparse.ArgumentParser(description="Cut the sampled questions out of the full runs")
    parser.add_argument("--results-dir", type=Path, required=True, help="results dir of the sampled runs")
    parser.add_argument("--source", type=Path, default=Path("results"), help="results dir of the full runs")
    args = parser.parse_args()
    for run_dir in extract_sampled_runs(args.results_dir, args.source):
        print(f"  {run_dir}")


if __name__ == "__main__":
    main()
