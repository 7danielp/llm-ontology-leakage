"""Load ontology, extract per-task items, and render or resolve identifiers"""

from collections import defaultdict
from dataclasses import dataclass

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import OWL

from .config import IdFormat, RunConfig, TaskName

# schema.org marks replaced terms with supersededBy, these are filtered out as deprecated
SUPERSEDED_BY = (
    URIRef("http://schema.org/supersededBy"),
    URIRef("https://schema.org/supersededBy"),
)
# schema.org retires terms into its attic section (not all of them carry supersededBy), those count as deprecated too
IS_PART_OF = (URIRef("http://schema.org/isPartOf"), URIRef("https://schema.org/isPartOf"))
ATTIC = (URIRef("http://attic.schema.org"), URIRef("https://attic.schema.org"))


@dataclass(frozen=True)
class TaskItem:
    """One extracted axiom (given entity plus gold answers) used by TS-Guessing and Guided Prompting"""

    given: URIRef
    gold: tuple[URIRef, ...]


def load_graph(source: str, prefix_map: dict[str, str]) -> Graph:
    """Load ontology file into a graph, with prefix_map filling missing prefix bindings"""
    graph = Graph(bind_namespaces="core")  # "core" binds only standard namespaces (owl, rdf, rdfs, xsd, xml)
    graph.parse(source)
    bound = {str(ns): p for p, ns in graph.namespaces()}
    for prefix, namespace in prefix_map.items():
        if bound.get(namespace) == "":
            # file binds namespace only to ":", replace it with real prefix
            graph.bind(prefix, namespace, override=True, replace=True)
        else:
            # fill missing prefix without changing file's own declarations
            graph.bind(prefix, namespace, override=False, replace=False)
    return graph


def deprecated_entities(graph: Graph) -> set[URIRef]:
    """Set of deprecated/superseded entities (owl:deprecated/schema:supersededBy/schema.org attic)"""
    deprecated = {
        s
        for s, o in graph.subject_objects(OWL.deprecated)
        if isinstance(s, URIRef) and isinstance(o, Literal) and str(o).lower() in ("true", "1")
    }
    for predicate in SUPERSEDED_BY:
        deprecated |= {s for s in graph.subjects(predicate, None) if isinstance(s, URIRef)}
    for predicate in IS_PART_OF:
        for attic in ATTIC:
            deprecated |= {s for s in graph.subjects(predicate, attic) if isinstance(s, URIRef)}
    return deprecated


def union_members(graph: Graph, node) -> list[URIRef]:
    """IRIs of an owl:unionOf class expression"""
    for head in graph.objects(node, OWL.unionOf):
        return [m for m in graph.items(head) if isinstance(m, URIRef)]
    return []


def axiom_pairs(graph: Graph, cfg: RunConfig, task: TaskName) -> list[tuple[URIRef, URIRef]]:
    """Extract all (subject, object) pairs of the task's predicate"""
    predicate = URIRef(cfg.axiom_predicates[task])  # mapped via preset (e.g. schema:domainIncludes instead of rdfs:domain)
    deprecated = deprecated_entities(graph)  # drop axioms with deprecated/superseded entities
    pairs = []
    for s, o in graph.subject_objects(predicate):
        if not isinstance(s, URIRef) or s in deprecated:
            continue
        if isinstance(o, URIRef):
            objects = [o]
        else:
            # unionOf members are (disjunctive) golds, other complex structures are dropped
            objects = union_members(graph, o)
        pairs.extend((s, m) for m in objects if m not in deprecated)
    return pairs


def _grouped_by_subject(pairs: list[tuple[URIRef, URIRef]]) -> list[TaskItem]:
    """Build TaskItem per subject with all its objects as gold"""
    by_subject: dict[URIRef, set[URIRef]] = defaultdict(set)
    for s, o in pairs:
        by_subject[s].add(o)
    return sorted(
        (TaskItem(s, tuple(sorted(golds, key=str))) for s, golds in by_subject.items()),
        key=lambda item: str(item.given),
    )


def extract_taxonomy_items(graph: Graph, cfg: RunConfig) -> list[TaskItem]:
    """Per class, its direct superclass(es)"""
    return _grouped_by_subject(axiom_pairs(graph, cfg, "taxonomy"))


def extract_domain_items(graph: Graph, cfg: RunConfig) -> list[TaskItem]:
    """Per property, its domain class(es)"""
    return _grouped_by_subject(axiom_pairs(graph, cfg, "domain"))


def extract_range_items(graph: Graph, cfg: RunConfig) -> list[TaskItem]:
    """Per property, its range class(es)"""
    return _grouped_by_subject(axiom_pairs(graph, cfg, "range"))


def extract_property_items(graph: Graph, cfg: RunConfig) -> list[TaskItem]:
    """Per class, the set of properties that have it as their domain"""
    by_class: dict[URIRef, set[URIRef]] = defaultdict(set)
    for p, c in axiom_pairs(graph, cfg, "domain"):
        by_class[c].add(p)  # grouped by the class instead of the property
    return sorted(
        (TaskItem(c, tuple(sorted(props, key=str))) for c, props in by_class.items()),
        key=lambda item: str(item.given),
    )


def render_identifier(iri: URIRef, graph: Graph, fmt: IdFormat) -> str:
    """Render an IRI in a specific identifier format (plain, prefix, full)"""
    if fmt == "full":
        return str(iri)
    if fmt == "plain":
        return local_name(str(iri))
    try:
        prefix, _, local = graph.namespace_manager.compute_qname(iri, generate=False)  
    except (KeyError, ValueError) as e:
        raise ValueError(
            f"Cannot render {iri} in {fmt!r} format: {e}. Add a prefix for its namespace to RunConfig.prefix_map."
        ) from e
    return f"{prefix}:{local}"


def local_name(iri: str) -> str:
    """Return part of an IRI after the last '#' or '/'"""
    if "#" in iri:
        return iri.rsplit("#", 1)[1]
    if "/" in iri:
        return iri.rsplit("/", 1)[1]
    return iri


class EntityResolver:
    """Resolve model-written identifier to an IRI (used by Guided Prompting for similarity calculations)"""

    def __init__(self, graph: Graph, ontology_namespace: str) -> None:
        """Collect the ontology's prefixes, local names and deprecated entities"""
        self._namespace = ontology_namespace
        self._deprecated = {str(d) for d in deprecated_entities(graph)}  # not part of the ontology
        self._prefixes = {prefix: str(ns) for prefix, ns in graph.namespaces()}
        self._by_local: dict[str, set[str]] = defaultdict(set)
        for triple in graph.triples((None, None, None)):
            for term in triple:
                if isinstance(term, URIRef):
                    self._by_local[local_name(str(term))].add(str(term))

    def resolve(self, identifier: str) -> str | None:
        """Resolve identifier to an IRI"""
        if "://" in identifier:  # full format, already an IRI
            iri = identifier
        elif ":" in identifier:  # prefix format to IRI
            prefix, _, local = identifier.partition(":")
            namespace = self._prefixes.get(prefix)
            iri = namespace + local if namespace else None
        else:  # plain format to IRI
            candidates = self._by_local.get(identifier, set())
            in_target = {c for c in candidates if c.startswith(self._namespace)}
            if len(in_target) == 1:
                iri = next(iter(in_target))  # internal ontology entity
            elif len(candidates) == 1:
                iri = next(iter(candidates))  # external ontology entity
            else:
                iri = None  # unknown
        return None if iri in self._deprecated else iri  # deprecated counts as unknown
