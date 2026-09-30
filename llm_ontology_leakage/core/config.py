"""Experiment configuration (ontology x task x model x format) used to build a RunConfig"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

IdFormat = Literal["plain", "prefix", "full"]
TaskName = Literal["taxonomy", "domain", "range", "property"]

GRID_TASKS: list[TaskName] = ["taxonomy", "domain", "range", "property"]
GRID_MODELS: list[str] = ["qwen3.5-122b", "llama-3.3-70b", "qwen3.6-36b", "ministral-3-14b"]
GRID_FORMATS: list[IdFormat] = ["plain", "prefix", "full"]

OPENAI_MODELS: list[str] = ["gpt-5.6-luna", "gpt-5.6-luna+web", "gpt-5.6-luna+web3"]

FULL_RUN_DIR = Path("results/full-no-web-search")  # full runs of all questions and their tables, sampled web runs go to their own --results-dir


def web_tool_calls(model: str) -> int:
    """Web tool calls a model name allows (0 without web search, +web allows 1, +webN allows N)"""
    match = re.search(r"\+web(\d*)$", model)
    return int(match.group(1) or 1) if match else 0


def base_model(model: str) -> str:
    """Model name without the web search suffix (for the API)"""
    return re.sub(r"\+web\d*$", "", model)


# Predicate per task, overridable per preset (the property task reuses the domain predicate)
DEFAULT_AXIOM_PREDICATES: dict[TaskName, str] = {
    "taxonomy": "http://www.w3.org/2000/01/rdf-schema#subClassOf",
    "domain": "http://www.w3.org/2000/01/rdf-schema#domain",
    "range": "http://www.w3.org/2000/01/rdf-schema#range",
}

# One preset per ontology
# prefix_map covers namespaces the file leaves undeclared (else prefix rendering raises a ValueError that names the missing namespace)
# ontology_namespace is the boundary for the internal/external gold flag
# ontology_domain is a short topic description, generate_synthetic.py uses it to pick an unrelated domain
ONTOLOGY_PRESETS: dict[str, dict] = {
    "FOAF": {
        "ontology_source": "ressources/ontologies/popular/foaf.rdf",
        "ontology_name": "FOAF",
        "ontology_domain": "people and social networks",
        "ontology_namespace": "http://xmlns.com/foaf/0.1/",
        "prefix_map": {
            "geo": "http://www.w3.org/2003/01/geo/wgs84_pos#",
            "skos": "http://www.w3.org/2004/02/skos/core#",
        },
        "format_examples": {
            "taxonomy": ["http://xmlns.com/foaf/0.1/ExampleClass"],
            "domain": ["http://xmlns.com/foaf/0.1/ExampleClass"],
            "range": ["http://xmlns.com/foaf/0.1/ExampleClass"],
            "property": ["http://xmlns.com/foaf/0.1/exampleProperty", "http://xmlns.com/foaf/0.1/otherExampleProperty"],
        },
        "tasks": GRID_TASKS,
    },
    "SCHEMA": {
        "ontology_source": "ressources/ontologies/popular/schemaorg-all-http.ttl",
        "ontology_name": "schema.org",
        "ontology_domain": "general web content markup",
        "ontology_namespace": "http://schema.org/",
        "prefix_map": {},
        # schema.org words domain and range as domainIncludes and rangeIncludes
        "axiom_predicates": {
            "domain": "http://schema.org/domainIncludes",
            "range": "http://schema.org/rangeIncludes",
        },
        "format_examples": {
            "taxonomy": ["http://schema.org/ExampleClass"],
            "domain": ["http://schema.org/ExampleClass"],
            "range": ["http://schema.org/ExampleClass"],
            "property": ["http://schema.org/exampleProperty", "http://schema.org/otherExampleProperty"],
        },
        "tasks": GRID_TASKS,
    },
    "DCTERMS": {
        "ontology_source": "ressources/ontologies/popular/dublin_core_terms.ttl",
        "ontology_name": "Dublin Core Terms",
        "ontology_domain": "document and resource metadata",
        # DCMI sibling vocabularies (dcmitype, dcam, elements) also count as internal
        "ontology_namespace": "http://purl.org/dc/",
        "prefix_map": {"dcmitype": "http://purl.org/dc/dcmitype/"},
        # dcterms words range as rangeIncludes
        "axiom_predicates": {"range": "http://purl.org/dc/dcam/rangeIncludes"},
        "format_examples": {
            "taxonomy": ["http://purl.org/dc/terms/ExampleClass"],
            "domain": ["http://purl.org/dc/terms/ExampleClass"],
            "range": ["http://purl.org/dc/terms/ExampleClass"],
            "property": ["http://purl.org/dc/terms/exampleProperty", "http://purl.org/dc/terms/otherExampleProperty"],
        },
        "tasks": GRID_TASKS,
    },
    "GOODRELATIONS": {
        "ontology_source": "ressources/ontologies/medium/goodrelations.rdf",
        "ontology_name": "GoodRelations",
        "ontology_domain": "e-commerce offers and products",
        "ontology_namespace": "http://purl.org/goodrelations/v1#",
        "prefix_map": {"schema": "http://schema.org/"},
        "format_examples": {
            "taxonomy": ["http://purl.org/goodrelations/v1#ExampleClass"],
            "domain": ["http://purl.org/goodrelations/v1#ExampleClass"],
            "range": ["http://purl.org/goodrelations/v1#ExampleClass"],
            "property": ["http://purl.org/goodrelations/v1#exampleProperty", "http://purl.org/goodrelations/v1#otherExampleProperty"],
        },
        "tasks": GRID_TASKS,
    },
    "NFO": {
        "ontology_source": "ressources/ontologies/medium/nfo.rdf",
        "ontology_name": "NEPOMUK File Ontology",
        "ontology_domain": "desktop files and documents",
        # NEPOMUK sibling modules (nie, nco) also count as internal
        "ontology_namespace": "http://www.semanticdesktop.org/ontologies/",
        "prefix_map": {},
        "format_examples": {
            "taxonomy": ["http://www.semanticdesktop.org/ontologies/2007/03/22/nfo#ExampleClass"],
            "domain": ["http://www.semanticdesktop.org/ontologies/2007/03/22/nfo#ExampleClass"],
            "range": ["http://www.semanticdesktop.org/ontologies/2007/03/22/nfo#ExampleClass"],
            "property": ["http://www.semanticdesktop.org/ontologies/2007/03/22/nfo#exampleProperty", "http://www.semanticdesktop.org/ontologies/2007/03/22/nfo#otherExampleProperty"],
        },
        "tasks": GRID_TASKS,
    },
    "ORG": {
        "ontology_source": "ressources/ontologies/medium/org.ttl",
        "ontology_name": "W3C Organization Ontology",
        "ontology_domain": "organizational structures",
        "ontology_namespace": "http://www.w3.org/ns/org#",
        "prefix_map": {"org": "http://www.w3.org/ns/org#"},
        "format_examples": {
            "taxonomy": ["http://www.w3.org/ns/org#ExampleClass"],
            "domain": ["http://www.w3.org/ns/org#ExampleClass"],
            "range": ["http://www.w3.org/ns/org#ExampleClass"],
            "property": ["http://www.w3.org/ns/org#exampleProperty", "http://www.w3.org/ns/org#otherExampleProperty"],
        },
        "tasks": GRID_TASKS,
    },
    "CINELAB": {
        "ontology_source": "ressources/ontologies/unpopular/cinelab.ttl",
        "ontology_name": "Cinelab",
        "ontology_domain": "film and video annotation",
        "ontology_namespace": "http://advene.org/ns/cinelab/ld#",
        "prefix_map": {"cl": "http://advene.org/ns/cinelab/ld#"},
        "format_examples": {
            "taxonomy": ["http://advene.org/ns/cinelab/ld#ExampleClass"],
            "domain": ["http://advene.org/ns/cinelab/ld#ExampleClass"],
            "range": ["http://advene.org/ns/cinelab/ld#ExampleClass"],
            "property": ["http://advene.org/ns/cinelab/ld#exampleProperty", "http://advene.org/ns/cinelab/ld#otherExampleProperty"],
        },
        "tasks": GRID_TASKS,
    },
    "EPPLAN": {
        "ontology_source": "ressources/ontologies/unpopular/ep-plan.ttl",
        "ontology_name": "EP-Plan",
        "ontology_domain": "scientific workflow plans",
        "ontology_namespace": "https://w3id.org/ep-plan#",
        "prefix_map": {
            "ep-plan": "https://w3id.org/ep-plan#",
            "prov": "http://www.w3.org/ns/prov#",
        },
        "format_examples": {
            "taxonomy": ["https://w3id.org/ep-plan#ExampleClass"],
            "domain": ["https://w3id.org/ep-plan#ExampleClass"],
            "range": ["https://w3id.org/ep-plan#ExampleClass"],
            "property": ["https://w3id.org/ep-plan#exampleProperty", "https://w3id.org/ep-plan#otherExampleProperty"],
        },
        "tasks": GRID_TASKS,
    },
    "URBANIOT": {
        "ontology_source": "ressources/ontologies/unpopular/urban-iot_electric.rdf",
        "ontology_name": "Urban IoT Electric Mobility",
        "ontology_domain": "electric mobility and charging infrastructure",
        "ontology_namespace": "http://www.w3id.org/urban-iot/electric#",
        "prefix_map": {
            "uiote": "http://www.w3id.org/urban-iot/electric#",
            "uiot": "http://www.w3id.org/urban-iot/core#",
            "schema": "https://schema.org/",
            "sosa": "http://www.w3.org/ns/sosa/",
            "mv": "http://schema.mobivoc.org/#",
        },
        "format_examples": {
            "taxonomy": ["http://www.w3id.org/urban-iot/electric#ExampleClass"],
            "domain": ["http://www.w3id.org/urban-iot/electric#ExampleClass"],
            "range": ["http://www.w3id.org/urban-iot/electric#ExampleClass"],
            "property": ["http://www.w3id.org/urban-iot/electric#exampleProperty", "http://www.w3id.org/urban-iot/electric#otherExampleProperty"],
        },
        "tasks": GRID_TASKS,
    },
    "SYNTH-1": {
        "ontology_source": "ressources/ontologies/synthetic/weather-patterns/weather-patterns.ttl",
        "ontology_name": "Weather Patterns",
        "ontology_domain": "weather patterns",
        "ontology_namespace": "http://example.org/weather-patterns#",
        "prefix_map": {"weather-patterns": "http://example.org/weather-patterns#"},
        "format_examples": {
            "taxonomy": ["http://example.org/weather-patterns#ExampleClass"],
            "domain": ["http://example.org/weather-patterns#ExampleClass"],
            "range": ["http://example.org/weather-patterns#ExampleClass"],
            "property": ["http://example.org/weather-patterns#exampleProperty", "http://example.org/weather-patterns#otherExampleProperty"],
        },
        "tasks": GRID_TASKS,
    },
    "SYNTH-2": {
        "ontology_source": "ressources/ontologies/synthetic/coffee-brewing/coffee-brewing.ttl",
        "ontology_name": "Coffee Brewing",
        "ontology_domain": "coffee brewing",
        "ontology_namespace": "http://example.org/coffee-brewing#",
        "prefix_map": {"coffee-brewing": "http://example.org/coffee-brewing#"},
        "format_examples": {
            "taxonomy": ["http://example.org/coffee-brewing#ExampleClass"],
            "domain": ["http://example.org/coffee-brewing#ExampleClass"],
            "range": ["http://example.org/coffee-brewing#ExampleClass"],
            "property": ["http://example.org/coffee-brewing#exampleProperty", "http://example.org/coffee-brewing#otherExampleProperty"],
        },
        "tasks": GRID_TASKS,
    },
    "SYNTH-3": {
        "ontology_source": "ressources/ontologies/synthetic/waste-management/waste-management.ttl",
        "ontology_name": "Waste Management",
        "ontology_domain": "waste management",
        "ontology_namespace": "http://example.org/waste-management#",
        "prefix_map": {"waste-management": "http://example.org/waste-management#"},
        "format_examples": {
            "taxonomy": ["http://example.org/waste-management#ExampleClass"],
            "domain": ["http://example.org/waste-management#ExampleClass"],
            "range": ["http://example.org/waste-management#ExampleClass"],
            "property": ["http://example.org/waste-management#exampleProperty", "http://example.org/waste-management#otherExampleProperty"],
        },
        "tasks": GRID_TASKS,
    },
}


@dataclass
class RunConfig:
    """All settings of a single run"""

    ontology_source: str
    ontology_name: str
    ontology_namespace: str  # for gold_in_ontology_namespace
    prefix_map: dict[str, str]
    format_examples: dict[str, list[str]]
    task: TaskName
    id_format: IdFormat
    model: str
    temperature: float
    max_tokens: int | None
    axiom_predicates: dict[str, str]
    limit: int | None # only the first N questions (used for test runs)
    results_dir: Path
    sample: int | None = None  # random sample of at most N questions per task (TS and GP, made for the web search runs), None = all questions
    seed: int = 42  # default seed (same seed = same sample)


def build_run_config(
    preset_name: str, *, task: TaskName, model: str, id_format: IdFormat
) -> RunConfig:
    """Build the RunConfig from a preset plus the task, model and format"""
    preset = ONTOLOGY_PRESETS[preset_name]
    return RunConfig(
        ontology_source=preset["ontology_source"],
        ontology_name=preset["ontology_name"],
        ontology_namespace=preset["ontology_namespace"],
        prefix_map=dict(preset["prefix_map"]),
        format_examples={k: list(v) for k, v in preset["format_examples"].items()},
        task=task,
        id_format=id_format,
        model=model,
        temperature=0.0,
        max_tokens=None,
        axiom_predicates={**DEFAULT_AXIOM_PREDICATES, **preset.get("axiom_predicates", {})},  # preset entries overwrite the defaults
        limit=None,
        results_dir=FULL_RUN_DIR,
    )
