"""Runner for the Guided Prompting method (Golchin & Surdeanu 2024)"""

import json
from dataclasses import asdict, dataclass
from typing import Any

from rdflib import URIRef

from ..core.config import RunConfig
from ..core.clients import CompletionClient
from ..core.ontology import EntityResolver, load_graph, render_identifier
from ..core.parsing import matches_format, parse_elements
from .similarity import MEASURES, ClassSimilarity, PropertySimilarity, set_similarity
from ..core.tasks import TASKS, TaskSpec
from ..core.runs import run_dir_for, write_meta

METHOD = "guided-prompting"

# blank in the axiom line is the part to complete
AXIOM_TEMPLATES = {
    "taxonomy": "{given} {predicate} ___",
    "domain": "{given} {predicate} ___",
    "range": "{given} {predicate} ___",
    "property": "___ {predicate} {given}",
}

# prompt structure and wording follow the guided instruction templates from the paper
NORMAL_TEMPLATE = (
    "INSTRUCTION:\n"
    "Complete the following axiom in a sensible way.\n"
    "{reply_clause}\n\n"
    "AXIOM:\n{axiom}\n\n"
    "COMPLETION:"
)

GUIDED_TEMPLATE = (
    "INSTRUCTION:\n"
    "You are given an axiom from the {ontology} ontology. "
    "Complete it EXACTLY as it appears in {ontology}.\n"
    "ONLY rely on the original form of the axiom in the ontology.\n"
    "{reply_clause}\n\n"
    "AXIOM:\n{axiom}\n\n"
    "COMPLETION:"
)


@dataclass
class GPRecord:
    """Two logged model calls (normal and guided) from a Guided Prompting run"""

    key: str  # IRI of the given entity
    task: str
    given: str
    given_iri: str  # IRI of the given entity
    gold: list[str]  # rendered in the run's id_format
    gold_iris: list[str]  # IRI(s) of the gold(s)
    prompt_normal: str
    prompt_guided: str
    raw_normal: str
    raw_guided: str
    finish_reason_normal: str | None  # "length" = truncated at max_tokens
    finish_reason_guided: str | None
    gold_in_ontology_namespace: bool  # basis for the internal/external gold segments
    # check if answer written in the run's id_format (similarity ignores the format and checks for semantics)
    format_match_normal: bool
    format_match_guided: bool
    # check if the answer is the given entity itself
    self_echo_normal: bool
    self_echo_guided: bool
    # completions are scored with ontology similarity from similarity.py
    sim_normal: dict[str, float]
    sim_guided: dict[str, float]


def build_gp_prompts(
    spec: TaskSpec, ontology_name: str, given_id: str, example_ids: list[str],
    predicate_label: str,
) -> tuple[str, str]:
    """Build the normal and the guided prompt for one axiom (same axiom line and reply clause, only instruction differs)"""
    axiom = AXIOM_TEMPLATES[spec.name].format(given=given_id, predicate=predicate_label)
    reply = spec.reply_clause.format(example=", ".join(example_ids))
    return (
        NORMAL_TEMPLATE.format(reply_clause=reply, axiom=axiom),
        GUIDED_TEMPLATE.format(ontology=ontology_name, reply_clause=reply, axiom=axiom),
    )


def echoes_given(raw: str, given_iri: str, spec: TaskSpec, resolver: EntityResolver) -> bool:
    """Check if the answer contains the given entity itself"""
    return given_iri in {resolver.resolve(e) for e in parse_elements(raw, spec.list_valued)}


def gp_score(
    raw: str,
    gold_iris: list[str],
    spec: TaskSpec,
    resolver: EntityResolver,
    class_sim: ClassSimilarity,
    prop_sim: PropertySimilarity,
) -> dict[str, float]:
    """Similarity between the answer and the golds"""
    parsed = parse_elements(raw, spec.list_valued)
    if spec.name == "property":
        predicted = [resolver.resolve(e) for e in parsed]
        return {m: set_similarity(m, predicted, gold_iris, prop_sim) for m in MEASURES}  # symmetric best match mean of the two sets
    predicted_iri = resolver.resolve(parsed[0]) if parsed else None
    if predicted_iri is None:
        return {m: 0.0 for m in MEASURES}
    return {
        m: max(class_sim.sim(m, predicted_iri, g) for g in gold_iris) for m in MEASURES  # with several golds the best match counts
    }


def _summarize_gp(records, cfg, spec, resolver, class_sim, prop_sim) -> dict:
    """Build the summary of a Guided Prompting run (similarities recomputed from the logged raw answers)"""
    per_measure: dict[str, dict[str, list[float]]] = {
        m: {"normal": [], "guided": []} for m in MEASURES
    }
    for r in records:
        for variant, raw in (("normal", r["raw_normal"]), ("guided", r["raw_guided"])):
            sims = gp_score(raw, r["gold_iris"], spec, resolver, class_sim, prop_sim)
            for m in MEASURES:
                per_measure[m][variant].append(sims[m])
    gap = {}
    for m in MEASURES:
        normal, guided = per_measure[m]["normal"], per_measure[m]["guided"]
        n = len(normal)
        gap[m] = {
            "n": n,
            "mean_normal": sum(normal) / n if n else None,
            "mean_guided": sum(guided) / n if n else None,
            "gap": (sum(guided) - sum(normal)) / n if n else None,
        }
    return {
        "method": METHOD,
        "task": cfg.task,
        "model": cfg.model,
        "id_format": cfg.id_format,
        "ontology_source": cfg.ontology_source,
        "ontology_name": cfg.ontology_name,
        "temperature": cfg.temperature,
        "n_records": len(records),
        "n_format_match_normal": sum(r["format_match_normal"] for r in records),
        "n_format_match_guided": sum(r["format_match_guided"] for r in records),
        "n_self_echo_normal": sum(r["self_echo_normal"] for r in records),
        "n_self_echo_guided": sum(r["self_echo_guided"] for r in records),
        "gap": gap,
    }


def run_guided_prompting(cfg: RunConfig, client: CompletionClient) -> dict[str, Any]:
    """Execute Guided Prompting run"""
    spec = TASKS[cfg.task]
    graph = load_graph(cfg.ontology_source, cfg.prefix_map)
    resolver = EntityResolver(graph, cfg.ontology_namespace)

    class_sim = ClassSimilarity(graph, URIRef(cfg.axiom_predicates["taxonomy"]))
    prop_sim = PropertySimilarity(
        graph, class_sim,
        URIRef(cfg.axiom_predicates["domain"]), URIRef(cfg.axiom_predicates["range"]),
    )

    # extract the task's axioms from the graph
    items = spec.extract(graph, cfg)
    if not items:
        raise ValueError(
            f"Task {cfg.task!r} extracted 0 axioms from {cfg.ontology_name}! "
            "Check the preset's axiom_predicates mapping."
        )
    if cfg.limit is not None:
        items = items[: cfg.limit]

    predicate_key = "domain" if spec.name == "property" else spec.name  # property task asks for subjects of domain axioms
    predicate_label = render_identifier(
        URIRef(cfg.axiom_predicates[predicate_key]), graph, "prefix"
    )

    example_iris = cfg.format_examples[cfg.task]
    example_ids = [render_identifier(URIRef(iri), graph, cfg.id_format) for iri in example_iris]

    # render all givens and golds in the run's id_format
    prepared = [
        (
            item,
            render_identifier(item.given, graph, cfg.id_format),
            [render_identifier(g, graph, cfg.id_format) for g in item.gold],
        )
        for item in items
    ]

    run_dir = run_dir_for(cfg, method_prefix="GP")
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "summary.json").unlink(missing_ok=True)  # drop stale summary so crashed rerun cannot look complete
    write_meta(run_dir, cfg, method=METHOD, client_name=type(client).__name__)

    max_tokens = cfg.max_tokens if cfg.max_tokens is not None else spec.default_max_tokens
    ns = cfg.ontology_namespace
    records: list[dict] = []
    with open(run_dir / "records.jsonl", "w", encoding="utf-8") as records_file:
        for i, (item, given_id, gold_ids) in enumerate(prepared, start=1):
            prompt_normal, prompt_guided = build_gp_prompts(
                spec, cfg.ontology_name, given_id, example_ids, predicate_label
            )
            # two model calls per axiom (normal and guided)
            completion_normal = client.complete(
                prompt_normal,
                model=cfg.model, temperature=cfg.temperature, max_tokens=max_tokens,
            )
            completion_guided = client.complete(
                prompt_guided,
                model=cfg.model, temperature=cfg.temperature, max_tokens=max_tokens,
            )
            gold_iris = [str(g) for g in item.gold]
            sim_normal = gp_score(
                completion_normal.text, gold_iris, spec, resolver, class_sim, prop_sim
            )
            sim_guided = gp_score(
                completion_guided.text, gold_iris, spec, resolver, class_sim, prop_sim
            )
            record = GPRecord(
                key=str(item.given),
                task=cfg.task,
                given=given_id,
                given_iri=str(item.given),
                gold=gold_ids,
                gold_iris=gold_iris,
                prompt_normal=prompt_normal,
                prompt_guided=prompt_guided,
                raw_normal=completion_normal.text,
                raw_guided=completion_guided.text,
                finish_reason_normal=completion_normal.finish_reason,
                finish_reason_guided=completion_guided.finish_reason,
                gold_in_ontology_namespace=(
                    any(g.startswith(ns) for g in gold_iris)
                    if spec.match == "any_of"
                    else str(item.given).startswith(ns)
                ),
                format_match_normal=matches_format(completion_normal.text, spec.list_valued, cfg.id_format),
                format_match_guided=matches_format(completion_guided.text, spec.list_valued, cfg.id_format),
                self_echo_normal=echoes_given(completion_normal.text, str(item.given), spec, resolver),
                self_echo_guided=echoes_given(completion_guided.text, str(item.given), spec, resolver),
                sim_normal=sim_normal,
                sim_guided=sim_guided,
            )
            records.append(asdict(record))
            records_file.write(json.dumps(records[-1], ensure_ascii=False) + "\n")
            gaps = ", ".join(
                f"{m}: {sim_guided[m]:.2f}-{sim_normal[m]:.2f}" for m in MEASURES
            )
            print(f"  [{i}/{len(prepared)}] {given_id} (guided-normal {gaps})")

    summary = _summarize_gp(records, cfg, spec, resolver, class_sim, prop_sim)
    (run_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return {"summary": summary, "run_dir": str(run_dir)}
