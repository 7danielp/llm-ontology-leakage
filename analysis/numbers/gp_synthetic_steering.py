"""Numbers of Section sec:results-gp-models: plain answers of llama-3.3-70b on the synthetic tier that follow the ontology name"""
import collections

from rdflib import URIRef

from analysis.common import RESULTS, TIERS, load_records

from llm_ontology_leakage.core.config import ONTOLOGY_PRESETS, build_run_config
from llm_ontology_leakage.core.ontology import EntityResolver, deprecated_entities, load_graph
from llm_ontology_leakage.core.parsing import parse_elements

MODEL = "llama-3.3-70b"
PRESET = {p["ontology_name"]: key for key, p in ONTOLOGY_PRESETS.items()}
TOPIC = {"Weather Patterns": ("weather", "pattern"), "Coffee Brewing": ("coffee", "brew"), "Waste Management": ("waste", "manag")}

counts = collections.Counter()
for o in TIERS["Synthetic"]:
    cfg = build_run_config(PRESET[o], task="domain", model=MODEL, id_format="plain")
    graph = load_graph(cfg.ontology_source, cfg.prefix_map)
    resolver = EntityResolver(graph, cfg.ontology_namespace)
    current = {str(e) for e in graph.subjects() if isinstance(e, URIRef)} - {str(d) for d in deprecated_entities(graph)}
    for t in ("taxonomy", "domain", "range"):
        for r in load_records(RESULTS / "runs" / "guided-prompting" / f"GP__{o.replace(' ', '-')}__{t}__{MODEL}__plain"):
            counts["answers"] += 1
            for arm in ("normal", "guided"):
                # a word of the ontology name anywhere in the answer, the entity and gold as the scoring resolves them
                parsed = parse_elements(r[f"raw_{arm}"], False)
                iri = resolver.resolve(parsed[0]) if parsed and parsed[0] else None
                counts[f"word {arm}"] += any(word in r[f"raw_{arm}"].lower() for word in TOPIC[o])
                counts[f"entity {arm}"] += iri in current
                counts[f"gold {arm}"] += iri in r["gold_iris"]

print(f"{MODEL}, synthetic tier: {counts['answers']} answers per arm; word of the ontology name normal {counts['word normal']}, "
      f"guided {counts['word guided']}; entity normal {counts['entity normal']}, guided {counts['entity guided']}; "
      f"gold normal {counts['gold normal']}, guided {counts['gold guided']}")
