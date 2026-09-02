"""Semantic similarity of classes and properties, following Meng, Huang & Gu (2013)"""

# Path Length Formula: sim = 2*deep_max - len(c1, c2)
# Wu & Palmer Formula: sim = 2*depth(lso) / (len(c1, c2) + 2*depth(lso))

from collections import defaultdict, deque
from statistics import mean

from rdflib import Graph, URIRef
from rdflib.namespace import RDFS

from ..core.ontology import union_members

OWL_THING = "http://www.w3.org/2002/07/owl#Thing"  # universal superclass (used as global root of every class hierarchy)

MEASURES = ("path", "wup")


class ClassSimilarity:
    """Similarity of two classes over the subclass hierarchy (Path Length and Wu & Palmer, Meng et al.)"""

    def __init__(self, graph: Graph, subclass_predicate: URIRef = RDFS.subClassOf) -> None:
        """Read the subclass edges from the graph and precompute all depths"""
        self._parents: dict[str, set[str]] = defaultdict(set)
        nodes: set[str] = set()
        for s, o in graph.subject_objects(subclass_predicate):
            # IRI to IRI axioms only
            if not (isinstance(s, URIRef) and isinstance(o, URIRef)):
                continue
            if str(s) == OWL_THING:
                continue
            nodes.add(str(s))
            if str(o) != OWL_THING:
                nodes.add(str(o))
            self._parents[str(s)].add(str(o))
        self._nodes = nodes
        self._depth: dict[str, int] = {OWL_THING: 1}  # universal root has depth 1
        for c in nodes:
            self._compute_depth(c, ())
        self.deep_max = max(self._depth.values())

    def _compute_depth(self, c: str, visiting: tuple) -> int:
        """Compute the depth (node count of the shortest path from the root)"""
        if c in self._depth:  # already computed
            return self._depth[c]
        parents = [p for p in self._parents.get(c, ()) if p not in visiting]
        depth = 2 if not parents else 1 + min(
            self._compute_depth(p, visiting + (c,)) for p in parents
        )
        if c not in visiting:  # save depth of class
            self._depth[c] = depth
        return depth

    def in_hierarchy(self, c: str) -> bool:
        """Check whether the class occurs in the hierarchy (owl:Thing always counts because it is the root)"""
        return c == OWL_THING or c in self._nodes

    def _ancestor_distances(self, c: str) -> dict[str, int]:
        """Shortest upward distance from c to every ancestor (c itself at 0)"""
        dist = {c: 0}
        queue = deque([c])
        while queue:
            x = queue.popleft()
            parents = self._parents.get(x) or ({OWL_THING} if x != OWL_THING else set())  # classes without parents hang directly below the root
            for p in parents:
                if p not in dist:
                    dist[p] = dist[x] + 1
                    queue.append(p)
        return dist

    def len_and_lso(self, c1: str, c2: str) -> tuple[int, str]:
        """Return the shortest distance between the two classes (len) and their deepest shared ancestor (lso)"""
        if c1 == c2:
            return 0, c1
        d1, d2 = self._ancestor_distances(c1), self._ancestor_distances(c2)
        common = set(d1) & set(d2)
        lso = min(common, key=lambda a: (-self._depth.get(a, 1), d1[a] + d2[a]))  # if two ancestors are equally deep, the closer one wins
        length = min(d1[a] + d2[a] for a in common)
        return length, lso

    def path(self, c1: str, c2: str) -> float:
        """Path Length, Formula: 2*deep_max - len (Meng et al.)"""
        # identical IRIs are maximally similar even outside the hierarchy (e.g. rdfs:Literal), anything else outside scores 0
        if c1 == c2:
            return 2.0 * self.deep_max
        if not (self.in_hierarchy(c1) and self.in_hierarchy(c2)):
            return 0.0
        length, _ = self.len_and_lso(c1, c2)
        return 2.0 * self.deep_max - length

    def wup(self, c1: str, c2: str) -> float:
        """Wu & Palmer, Formula: 2*depth(lso) / (len + 2*depth(lso)) (Meng et al.)"""
        if c1 == c2:
            return 1.0
        if not (self.in_hierarchy(c1) and self.in_hierarchy(c2)):
            return 0.0
        length, lso = self.len_and_lso(c1, c2)
        lso_depth = self._depth.get(lso, 1)
        return 2.0 * lso_depth / (length + 2.0 * lso_depth)

    def sim(self, measure: str, c1: str, c2: str) -> float:
        """Dispatch to the requested measure by name ("path" or "wup")"""
        return getattr(self, measure)(c1, c2)


class PropertySimilarity:
    """Similarity of two properties, the mean of domain and range similarity"""

    def __init__(
        self,
        graph: Graph,
        class_sim: ClassSimilarity,
        domain_predicate: URIRef = RDFS.domain,
        range_predicate: URIRef = RDFS.range,
    ) -> None:
        """Read the domain and range classes of all properties from the graph"""
        self._domains: dict[str, set[str]] = defaultdict(set)
        self._ranges: dict[str, set[str]] = defaultdict(set)
        for pred, store in ((domain_predicate, self._domains), (range_predicate, self._ranges)):
            for s, o in graph.subject_objects(pred):
                if not isinstance(s, URIRef):
                    continue
                targets = [o] if isinstance(o, URIRef) else union_members(graph, o)
                for t in targets:
                    store[str(s)].add(str(t))
        self._class_sim = class_sim

    def sim(self, measure: str, p1: str, p2: str) -> float:
        """Mean of domain and range similarity"""
        parts = []
        for store in (self._domains, self._ranges):
            v1, v2 = store.get(p1), store.get(p2)
            if v1 and v2:  # defined on both sides
                # compare class(es) of p1 with class(es) of p2 (the best pair counts)
                parts.append(max(self._class_sim.sim(measure, a, b) for a in v1 for b in v2))
        if not parts:
            return 0.0
        return mean(parts)


def set_similarity(
    measure: str,
    predicted: list[str | None],
    gold: list[str],
    prop_sim: PropertySimilarity,
) -> float:
    """Symmetric best match mean between prediction and gold (property task)"""
    if not predicted or not gold:
        return 0.0  # empty answer scores 0
    resolved = [p for p in predicted if p is not None]

    # each gold takes its best answer, missing golds lower the score
    per_gold = [
        max((prop_sim.sim(measure, g, p) for p in resolved), default=0.0) for g in gold
    ]
    # each answer takes its best gold, invented answers lower the score (not in the ontology counts 0)
    per_pred = [
        0.0 if p is None else max(prop_sim.sim(measure, p, g) for g in gold)
        for p in predicted
    ]
    # average of both directions (too little and too much answered both lower the score)
    return (mean(per_gold) + mean(per_pred)) / 2.0
