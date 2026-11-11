"""Table tab:ontology-stats: classes, properties and subclass, domain and range axioms per ontology as stated in its file"""
import os
import statistics

from rdflib import URIRef
from rdflib.namespace import OWL, RDF, RDFS

from analysis.common import ROOT, SHORT, TIERS
from llm_ontology_leakage.core.config import ONTOLOGY_PRESETS, build_run_config
from llm_ontology_leakage.core.ontology import load_graph

# classes and properties as for the median size of the synthetic ontologies (median_characteristics in generate_synthetic.py)
CLASS_TYPES = (OWL.Class, RDFS.Class)
PROPERTY_TYPES = (OWL.ObjectProperty, OWL.DatatypeProperty, RDF.Property)
TASKS = ("taxonomy", "domain", "range")  # subclass, domain and range axioms with the predicates of each preset (Section sec:extraction)

os.chdir(ROOT)  # the preset sources are relative to the repository root
PRESETS = {preset["ontology_name"]: key for key, preset in ONTOLOGY_PRESETS.items()}


def typed(graph, types: tuple) -> int:
    """Number of IRIs that the file types with one of the types, deprecated ones included"""
    return len({s for t in types for s in graph.subjects(RDF.type, t) if isinstance(s, URIRef)})


def axioms(graph, cfg, task: str) -> int:
    """All triples of the task's predicate in the file, a union of classes counts once (the extraction keeps fewer)"""
    return len(list(graph.subject_objects(URIRef(cfg.axiom_predicates[task]))))


rows = {}
for tier, ontologies in TIERS.items():
    for o in ontologies:
        key = PRESETS[o]
        graph = load_graph(ONTOLOGY_PRESETS[key]["ontology_source"], ONTOLOGY_PRESETS[key]["prefix_map"])
        cfg = build_run_config(key, task="taxonomy", model="none", id_format="plain")
        rows[o] = [typed(graph, CLASS_TYPES), typed(graph, PROPERTY_TYPES)] + [axioms(graph, cfg, t) for t in TASKS]

for tier, ontologies in TIERS.items():
    print(rf"\rowcolor{{tierrow}}\multicolumn{{6}}{{l}}{{\textbf{{{tier}}}}} \\")
    for o in ontologies:
        print(rf"\quad {SHORT.get(o, o)} & " + " & ".join(f"{n:,}" for n in rows[o]) + r" \\")
real = [o for tier in ("Popular", "Medium", "Unpopular") for o in TIERS[tier]]
print(f"% median of the nine real ontologies: {statistics.median(rows[o][0] for o in real)} classes and "
      f"{statistics.median(rows[o][1] for o in real)} properties (Section sec:synthetic)")
