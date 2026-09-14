"""Runner for the TS-Guessing method (Deng et al. 2024)"""

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from rdflib import URIRef

from ..core.config import RunConfig
from ..core.clients import CompletionClient
from ..core.ontology import load_graph, render_identifier, sample_items
from ..core.parsing import matches_format
from ..core.runs import run_dir_for, write_meta
from .scoring import confusion_counts, metrics_table, score
from ..core.tasks import TASKS, TaskSpec

METHOD = "ts-guessing"

QUESTION_TEMPLATES = {
    "taxonomy": "Complete the following axiom so that it holds in the {ontology} ontology.",
    "domain": "Complete the following axiom so that it holds in the {ontology} ontology.",
    "range": "Complete the following axiom so that it holds in the {ontology} ontology.",
    "property": "Complete the following axiom with every property for which it holds in the {ontology} ontology.",
}
# blank in the axiom line is the masking
AXIOM_TEMPLATES = {
    "taxonomy": "{given} {predicate} ___",
    "domain": "{given} {predicate} ___",
    "range": "{given} {predicate} ___",
    "property": "___ {predicate} {given}",
}


def build_prompt(
    spec: TaskSpec, ontology_name: str, given_id: str, example_ids: list[str], predicate_label: str
) -> str:
    """Build final prompt for TS-Guessing"""
    question = QUESTION_TEMPLATES[spec.name].format(ontology=ontology_name)
    axiom = AXIOM_TEMPLATES[spec.name].format(given=given_id, predicate=predicate_label)
    reply = spec.reply_clause.format(example=", ".join(example_ids))
    return f"{question}\n{axiom}\n{reply}"

@dataclass
class Record:
    """One logged model call from a TS-Guessing run"""

    key: str  # IRI of the given entity
    task: str
    given: str
    given_iri: str  # IRI of the given entity
    gold: list[str]  # rendered in the run's id_format
    gold_iris: list[str]  # IRI(s) of the gold(s)
    prompt: str
    raw_output: str
    finish_reason: str | None  # "length" = truncated at max_tokens
    gold_in_ontology_namespace: bool  # basis for the internal/external gold segments
    format_match: bool  # check if answer written in the run's id_format
    parsed: list[str]
    strict_match: bool


def _summarize(records: list[dict], cfg: RunConfig, spec: TaskSpec) -> dict:
    """Build the summary of a TS-Guessing run (scoring recomputed from the logged raw answers)"""
    scored = []
    for r in records:
        parsed, strict = score(
            r["raw_output"],
            r["gold"],
            list_valued=spec.list_valued,
            match_mode=spec.match,
        )
        # F1 inputs for the property task (on the single answer tasks F1 equals EM)
        tp, fp, fn = confusion_counts(parsed, r["gold"], spec.match)
        scored.append(
            {
                "gold_in_ns": r["gold_in_ontology_namespace"],
                "strict": strict,
                "tp": tp,
                "fp": fp,
                "fn": fn,
            }
        )
    return {
        "method": METHOD,
        "task": cfg.task,
        "model": cfg.model,
        "id_format": cfg.id_format,
        "ontology_source": cfg.ontology_source,
        "ontology_name": cfg.ontology_name,
        "temperature": cfg.temperature,
        "n_records": len(records),
        "n_format_match": sum(r["format_match"] for r in records),
        "n_truncated": sum(r["finish_reason"] == "length" for r in records),  # answers cut off at max_tokens
        "metrics": metrics_table(scored),  # EM and pooled precision/recall/F1 per segment
    }


def run_ts_guessing(cfg: RunConfig, client: CompletionClient) -> dict[str, Any]:
    """Execute TS-Guessing run"""
    spec = TASKS[cfg.task]
    graph = load_graph(cfg.ontology_source, cfg.prefix_map)

    # extract task's axioms from the graph
    items = spec.extract(graph, cfg)
    if not items:
        raise ValueError(
            f"Task {cfg.task!r} extracted 0 axioms from {cfg.ontology_name}! "
            "Check the preset's axiom_predicates mapping."
        )
    if cfg.limit is not None:
        items = items[: cfg.limit]  # test runs: the first N questions
    if cfg.sample is not None:
        items = sample_items(items, cfg.sample, cfg.seed)  # experiments: random N per task, the same draw in every run of the cell
        if cfg.model.endswith("+web"):
            client.allow_web_search(len(items))  # one request per question

    example_iris = cfg.format_examples[cfg.task]
    example_ids = [render_identifier(URIRef(iri), graph, cfg.id_format) for iri in example_iris]

    predicate_key = "domain" if spec.name == "property" else spec.name  # property task asks for subjects of domain axioms
    predicate_label = render_identifier(
        URIRef(cfg.axiom_predicates[predicate_key]), graph, "prefix"
    )

    # render all givens and golds in the run's id_format
    prepared = [
        (
            item,
            render_identifier(item.given, graph, cfg.id_format),
            [render_identifier(g, graph, cfg.id_format) for g in item.gold],
        )
        for item in items
    ]

    run_dir = run_dir_for(cfg, method_prefix="TS")
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "summary.json").unlink(missing_ok=True)  # drop a stale summary so a crashed rerun cannot look complete
    sampled_keys = [str(item.given) for item in items] if cfg.sample is not None else None
    write_meta(run_dir, cfg, method=METHOD, client_name=type(client).__name__, sampled_keys=sampled_keys)

    max_tokens = cfg.max_tokens if cfg.max_tokens is not None else spec.default_max_tokens
    ns = cfg.ontology_namespace
    records: list[dict] = []
    with open(run_dir / "records.jsonl", "w", encoding="utf-8") as records_file:
        for i, (item, given_id, gold_ids) in enumerate(prepared, start=1):
            prompt = build_prompt(spec, cfg.ontology_name, given_id, example_ids, predicate_label)
            # one model call per axiom
            completion = client.complete(
                prompt, model=cfg.model, temperature=cfg.temperature, max_tokens=max_tokens
            )
            raw = completion.text
            gold_iris = [str(g) for g in item.gold]
            parsed, strict = score(
                raw,
                gold_ids,
                list_valued=spec.list_valued,
                match_mode=spec.match,
            )
            record = Record(
                key=str(item.given),
                task=cfg.task,
                given=given_id,
                given_iri=str(item.given),
                gold=gold_ids,
                gold_iris=gold_iris,
                prompt=prompt,
                raw_output=raw,
                finish_reason=completion.finish_reason,
                gold_in_ontology_namespace=(
                    any(g.startswith(ns) for g in gold_iris)
                    if spec.match == "any_of"
                    else str(item.given).startswith(ns)
                ),
                format_match=matches_format(raw, spec.list_valued, cfg.id_format),
                parsed=parsed,
                strict_match=strict,
            )
            records.append(asdict(record))
            records_file.write(json.dumps(records[-1], ensure_ascii=False) + "\n")
            shown = ", ".join(parsed)
            if len(shown) > 60:
                shown = shown[:57] + "..."
            print(f"  [{i}/{len(prepared)}] {given_id} -> {shown!r} strict={int(strict)}")

    summary = _summarize(records, cfg, spec)
    (run_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return {"summary": summary, "run_dir": str(run_dir)}
