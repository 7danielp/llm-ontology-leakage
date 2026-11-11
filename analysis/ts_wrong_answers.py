"""Existing entities named in TS-Guessing answers, shared by tab_ts_wrong.py and web_tier_reasons.py"""
import collections

from rdflib import URIRef

from analysis.common import MODELS, RESULTS, ROOT, load_records

from llm_ontology_leakage.core.config import ONTOLOGY_PRESETS, build_run_config
from llm_ontology_leakage.core.ontology import EntityResolver, deprecated_entities, load_graph, local_name

PRESET = {p["ontology_name"]: key for key, p in ONTOLOGY_PRESETS.items()}


def setup(ontology: str):
    """(run configuration, graph, exists) of an ontology, exists(name) gives the existing entity a name stands for, else None"""
    cfg = build_run_config(PRESET[ontology], task="property", model=MODELS[0], id_format="plain")
    graph = load_graph(str(ROOT / cfg.ontology_source), cfg.prefix_map)
    resolver = EntityResolver(graph, cfg.ontology_namespace)
    # current entities of the ontology file
    entities = {str(e) for e in graph.subjects() if isinstance(e, URIRef)} - {str(d) for d in deprecated_entities(graph)}
    by_local = collections.defaultdict(set)
    for e in entities:
        by_local[local_name(e)].add(e)

    def exists(name: str) -> str | None:
        iri = resolver.resolve(name)
        if iri is None and ":" not in name:  # plain name shared by two namespaces, such as creator
            unique = by_local.get(name, set())
            iri = next(iter(unique)) if len(unique) == 1 else None
        return iri if iri in entities else None
    return cfg, graph, exists


def records(ontology: str, model: str, fmt: str, task: str = "property") -> list[dict]:
    return load_records(RESULTS / "runs" / "ts-guessing" / f"TS__{ontology.replace(' ', '-')}__{task}__{model}__{fmt}")


def additional(r: dict, exists) -> list[str | None]:
    """Existing entities of the listed properties that are not gold, None for invented ones"""
    gold = set(r["gold_iris"])
    resolved = [exists(p) for p in dict.fromkeys(r["parsed"] or []) if p]
    return [p for p in resolved if p not in gold]
