"""Numbers of Sections sec:results-gp, sec:results-comparison and sec:limitations: Guided Prompting answer counts and tests"""
import collections
import statistics
from collections.abc import Callable

from rdflib import URIRef
from scipy.stats import false_discovery_control, ttest_rel

from analysis.common import FORMATS, MODELS, ONTOLOGIES, RESULTS, TASKS, TIERS, load_records, name_inferable, number, read_aggregate, read_gaps

from llm_ontology_leakage.core.config import ONTOLOGY_PRESETS, build_run_config
from llm_ontology_leakage.core.ontology import EntityResolver, deprecated_entities, load_graph
from llm_ontology_leakage.core.parsing import parse_elements

RUNS = RESULTS / "runs" / "guided-prompting"
PRESET = {p["ontology_name"]: key for key, p in ONTOLOGY_PRESETS.items()}
TIER = {o: tier for tier, ontologies in TIERS.items() for o in ontologies}
SINGLE = ("taxonomy", "domain", "range")  # the tasks with a single answer
FOAF, W3C, ORG = "http://xmlns.com/foaf/0.1/", "W3C Organization Ontology", "http://www.w3.org/ns/org#Organization"
LLAMA, LUNA, MINISTRAL = "llama-3.3-70b", "gpt-5.6-luna", "ministral-3-14b"


def records(o: str, t: str, m: str, f: str = "plain") -> list[dict]:
    return load_records(RUNS / f"GP__{o.replace(' ', '-')}__{t}__{m}__{f}")


def exact(rs: list[dict], arm: str) -> int:
    """Answers of one arm with similarity 1, the gold itself"""
    return sum(r[f"sim_{arm}"]["wup"] == 1 for r in rs)


def gap(rs: list[dict]) -> float:
    return statistics.mean(r["sim_guided"]["wup"] - r["sim_normal"]["wup"] for r in rs)


def ontology_gap(o: str, m: str, keep: Callable[[dict], bool]) -> float:
    """Mean of the task gaps over the questions that keep accepts"""
    return statistics.mean(gap(rs) for t in TASKS if (rs := [r for r in records(o, t, m) if keep(r)]))


def tier_means(m: str, keep: Callable[[dict], bool]) -> list[float]:
    return [statistics.mean(ontology_gap(o, m, keep) for o in ontologies) for ontologies in TIERS.values()]


def entity_of(ontology: str) -> Callable[[str], str | None]:
    """Maps an answer to the current entity of the ontology that it names, None if invented"""
    cfg = build_run_config(PRESET[ontology], task="domain", model=MODELS[0], id_format="plain")
    graph = load_graph(cfg.ontology_source, cfg.prefix_map)
    resolver = EntityResolver(graph, cfg.ontology_namespace)
    current = {str(e) for e in graph.subjects() if isinstance(e, URIRef)} - {str(d) for d in deprecated_entities(graph)}

    def entity(raw: str) -> str | None:
        parsed = parse_elements(raw, False)
        iri = resolver.resolve(parsed[0]) if parsed and parsed[0] else None
        return iri if iri in current else None
    return entity


gaps = read_gaps()  # (ontology, task, model, format) -> (gap, significant)
entities = {o: entity_of(o) for o in ONTOLOGIES}

print("sec:results-gp-ontologies")
plain_per_tier = collections.Counter(TIER[o] for (o, _, _, f), (_, s) in gaps.items() if f == "plain" and s)
print("significant gaps of 60: " + ", ".join(f"{tier} {plain_per_tier[tier]}" for tier in TIERS))
central = (FOAF + "Person", FOAF + "Agent")
rs = records("FOAF", "domain", LLAMA)
guided, normal = (sum(entities["FOAF"](r[f"raw_{arm}"]) in central for r in rs) for arm in ("guided", "normal"))
print(f"FOAF domain, {LLAMA} answers Person or Agent: guided {guided} of {len(rs)}, normal {normal}")
organization = {m: [sum(entities[W3C](r[f"raw_{arm}"]) == ORG for r in records(W3C, "domain", m)) for arm in ("guided", "normal")]
                for m in MODELS}
print(f"W3C Organization domain, answers Organization guided and normal of {len(records(W3C, 'domain', LLAMA))}: "
      + ", ".join(f"{m} {g} and {n}" for m, (g, n) in organization.items()))

print("sec:results-gp-formats")
per_format = collections.Counter(f for (_, _, _, f), (_, s) in gaps.items() if s)
print("significant tests of 240 per format: " + ", ".join(f"{f} {per_format[f]}" for f in FORMATS))
for m in (LLAMA, LUNA):
    rs = [r for t in SINGLE for r in records("schema.org", t, m, "prefix")]
    ts = [r for t in SINGLE for r in load_records(RESULTS / "runs" / "ts-guessing" / f"TS__schema.org__{t}__{m}__prefix")]
    normal, guided = (sum(entities["schema.org"](r[f"raw_{arm}"]) is None for r in rs) for arm in ("normal", "guided"))
    print(f"schema.org taxonomy, domain and range, prefix, {m}: no entity of schema.org normal {normal}, guided {guided}; "
          f"exact normal {exact(rs, 'normal')}, guided {exact(rs, 'guided')}, TS-Guessing {sum(r['strict_match'] for r in ts)} of {len(rs)}")

print("sec:results-gp-models")
rs = [r for o in ONTOLOGIES for t in TASKS for r in records(o, t, MINISTRAL)]
print(f"{MINISTRAL} answers OntologyClass: normal {sum(r['raw_normal'].strip() == 'OntologyClass' for r in rs):,} of {len(rs):,}, "
      f"guided {sum(r['raw_guided'].strip() == 'OntologyClass' for r in rs)}")
without = tier_means(MINISTRAL, lambda r: "OntologyClass" not in (r["raw_normal"].strip(), r["raw_guided"].strip()))
print(f"{MINISTRAL} tier means without OntologyClass in either answer: " + ", ".join(number(x, True) for x in without))

print("sec:results-comparison")
means = [tier_means(m, lambda r: not name_inferable(r)) for m in MODELS]
names = list(TIERS)
print("tier tests without the name-inferable questions: " + ", ".join(
    f"{names[i]} > {names[i + 1].lower()} p = {ttest_rel([v[i] for v in means], [v[i + 1] for v in means], alternative='greater').pvalue:.3f}"
    for i in range(3)))

print("sec:limitations")
print(f"significant tests over all formats: {sum(s for _, s in gaps.values())} of {len(gaps)}, expected by chance {0.05 * len(gaps):.0f}")
p_values = [float(r["p_value"]) for r in read_aggregate("gp_aggregate.csv") if r["measure"] == "wup" and r["segment"] == "all"]
print(f"kept by Benjamini Hochberg over all formats: {sum(p <= 0.05 for p in false_discovery_control(p_values))}")
shares = []
for m in MODELS:
    rs = [(o, r) for o in ONTOLOGIES for t in SINGLE for r in records(o, t, m, "prefix")]
    normal, guided = (sum(entities[o](r[f"raw_{arm}"]) is None for o, r in rs) / len(rs) for arm in ("normal", "guided"))
    shares.append(f"{m} {normal:.0%} to {guided:.0%}")
print("prefix, invented answers in the single-answer tasks, normal to guided: " + ", ".join(shares))
