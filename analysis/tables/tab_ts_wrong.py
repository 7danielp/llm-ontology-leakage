"""Table tab:ts-wrong-full and Figure fig:ts-wrong: wrong TS-Guessing answers that name an existing entity"""
import functools
import statistics
from collections.abc import Iterable
from decimal import ROUND_HALF_UP, Decimal

from rdflib import URIRef

from analysis.common import FORMATS, MODELS, ONTOLOGIES, SHORT, TASKS, TIERS, name_inferable, number
from analysis.ts_wrong_answers import additional, records, setup

from llm_ontology_leakage.core.ontology import EntityResolver

SINGLE = ["taxonomy", "domain", "range"]  # one answer per question
setup_once = functools.cache(setup)


def percent(x: float) -> str:
    """Whole percent, rounded half up"""
    return str(Decimal(repr(100 * x)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def entry(x: float | None) -> str:
    return "--" if x is None else number(x)


def mean(xs: Iterable[float | None]) -> float | None:
    """Mean of the values that are not None, None if there is none"""
    kept = [x for x in xs if x is not None]
    return statistics.mean(kept) if kept else None


@functools.cache
def share(ontology: str, task: str) -> float | None:
    """Share of the wrong answers (property task: additional properties) naming an existing entity, None if no question is left"""
    _, _, exists = setup_once(ontology)
    existing = wrong = questions = 0
    for m in MODELS:
        for f in FORMATS:
            for r in records(ontology, m, f, task):
                if name_inferable(r):
                    continue
                questions += 1
                if task == "property":
                    extra = additional(r, exists)
                    existing += sum(p is not None for p in extra)
                    wrong += len(extra)
                elif not r["strict_match"]:
                    existing += bool(r["parsed"] and r["parsed"][0] and exists(r["parsed"][0]))
                    wrong += 1
    return existing / wrong if questions else None


def figure_values() -> dict[str, dict[str, float]]:
    """{task: {tier: mean share of its ontologies}}"""
    return {t: {tier: mean(share(o, t) for o in ontologies) for tier, ontologies in TIERS.items()} for t in TASKS}


@functools.cache
def superclasses(cls: str) -> frozenset[str]:
    """Transitive superclasses of a schema.org class"""
    cfg, graph, _ = setup_once("schema.org")
    subclass_of = URIRef(cfg.axiom_predicates["taxonomy"])
    seen, todo = set(), [URIRef(cls)]
    while todo:
        for parent in graph.objects(todo.pop(), subclass_of):
            if isinstance(parent, URIRef) and parent not in seen:
                seen.add(parent)
                todo.append(parent)
    return frozenset(str(c) for c in seen if str(c) != cls)


def schema_indirect() -> tuple[int, int]:
    """(wrong schema.org taxonomy answers that name a superclass other than the gold, wrong answers)"""
    cfg, graph, _ = setup_once("schema.org")
    resolver = EntityResolver(graph, cfg.ontology_namespace)
    indirect = wrong = 0
    for m in MODELS:
        for f in FORMATS:
            for r in records("schema.org", m, f, "taxonomy"):
                if r["strict_match"] or name_inferable(r):
                    continue
                wrong += 1
                answer = resolver.resolve(r["parsed"][0]) if r["parsed"] else None
                indirect += bool(answer and answer not in r["gold_iris"] and answer in superclasses(r["given_iri"]))
    return indirect, wrong


def schema_inherited() -> tuple[int, int]:
    """(additional schema.org properties whose domain is a superclass of the given class, additional properties)"""
    cfg, graph, exists = setup_once("schema.org")
    domain = URIRef(cfg.axiom_predicates["domain"])
    inherited = extra = 0
    for m in MODELS:
        for f in FORMATS:
            for r in records("schema.org", m, f):
                if name_inferable(r):
                    continue
                for p in additional(r, exists):
                    extra += 1
                    if p is not None:
                        inherited += bool({str(d) for d in graph.objects(URIRef(p), domain)} & superclasses(r["given_iri"]))
    return inherited, extra


if __name__ == "__main__":
    means = figure_values()
    for tier, ontologies in TIERS.items():
        print(rf"\rowcolor{{tierrow}}\textbf{{{tier}}} & " + " & ".join(entry(means[t][tier]) for t in TASKS) + r" \\")
        for o in ontologies:
            print(rf"\quad {SHORT.get(o, o)} & " + " & ".join(entry(share(o, t)) for t in TASKS) + r" \\")

    print("% fig:ts-wrong, tier means per task, popular to synthetic, three decimals: "
          + "; ".join(f"{t} " + ", ".join(f"{v:.3f}" for v in means[t].values()) for t in TASKS))
    tiers = list(TIERS)
    for t in SINGLE:
        v = [means[t][tier] for tier in tiers]
        steps = [f"{a.lower()} > {b.lower()} {'holds' if x > y else 'breaks'}" for a, b, x, y in zip(tiers, tiers[1:], v, v[1:])]
        print(f"% {t}: " + ", ".join(number(x) for x in v) + "; " + ", ".join(steps))
    popular, synthetic = [means[t]["Popular"] for t in SINGLE], [means[t]["Synthetic"] for t in SINGLE]
    print("% popular to synthetic per task: " + ", ".join(
        f"{t} {number(p)} to {number(s)} ({percent(p)} % to {percent(s)} %)" for t, p, s in zip(SINGLE, popular, synthetic)))
    print(f"% popular tier per task between {number(min(popular))} and {number(max(popular))}, "
          f"synthetic tier between {number(min(synthetic))} and {number(max(synthetic))}")

    prop = {o: share(o, "property") for o in ONTOLOGIES}
    prop_popular = [prop[o] for o in TIERS["Popular"]]
    rest = {o: prop[o] for o in ONTOLOGIES if o not in TIERS["Popular"]}
    most = max(rest, key=rest.get)
    print(f"% additional properties that exist: popular ontologies {percent(min(prop_popular))} % to {percent(max(prop_popular))} % ("
          + ", ".join(f"{SHORT.get(o, o)} {number(prop[o])}" for o in TIERS["Popular"])
          + f"), all other ontologies at most {percent(rest[most])} % ({SHORT.get(most, most)} {number(rest[most])})")
    indirect, wrong = schema_indirect()
    inherited, extra = schema_inherited()
    print(f"% schema.org: {indirect:,} of {wrong:,} wrong taxonomy answers ({percent(indirect / wrong)} %) name an indirect "
          f"superclass, {inherited:,} of {extra:,} additional properties ({percent(inherited / extra)} %) have a superclass of the "
          "given class as domain")
