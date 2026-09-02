"""One time generation of a synthetic ontology (GET methodology, Paulheim 2025)"""

import argparse
import json
import re
import statistics
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import OWL, RDF, RDFS

from llm_ontology_leakage.core.config import ONTOLOGY_PRESETS
from llm_ontology_leakage.core.clients import MakiClient
from llm_ontology_leakage.core.ontology import load_graph, local_name

GENERATOR_MODEL = "gemma4-26b"
# temperature taken from the paper, system prompt from its code repository (Paulheim 2025)
TEMPERATURE = 0.5
SYSTEM_PROMPT = "You are an ontology engineer"
OUT_DIR = Path("ressources/ontologies/synthetic")

# domains of the nine benchmark ontologies, the generator must pick a different one
BENCHMARK_DOMAINS = [
    "people and social networks (FOAF)",
    "general web content markup (schema.org)",
    "document and resource metadata (Dublin Core Terms)",
    "e-commerce offers and products (GoodRelations)",
    "desktop files and documents (NEPOMUK File Ontology)",
    "organizational structures (W3C Organization Ontology)",
    "film and video annotation (Cinelab)",
    "scientific workflow plans (EP-Plan)",
    "electric mobility and charging infrastructure (Urban IoT)",
]

DOMAIN_PROMPT = (
    "We are building a benchmark of ontologies covering the following domains:\n"
    + "\n".join(f"- {d}" for d in BENCHMARK_DOMAINS)
    + "\n\nName ONE everyday domain for a new ontology that is unrelated to all "
    "of the domains above. Reply with the domain name only (one or two words)."
)

# generation prompt taken from the paper's code repository (Paulheim 2025)
GENERATION_PROMPT = """Build me an ontology of {domain} with {N} Classes and {M} ObjectProperties, please. Provide the result as
1. List of Classes (one per line)
2. List of ObjectProperties (one per line)
3. List of subclass axioms in the format "A,B" (one per line, where A is a subclass of B)
4. List of domain axioms in the format P,D (one per line, where P is a property, D is its domain - leave empty if there is no suitable class)
5. List of range axioms in the format P,R (one per line, where P is a property, R is its range - leave empty if there is no suitable class)"""


def median_characteristics() -> tuple[int, int, list[dict]]:
    """Extract N (classes) and M (properties) as the median over the nine evaluated ontologies"""
    rows = []
    for name, preset in ONTOLOGY_PRESETS.items():
        graph = load_graph(preset["ontology_source"], preset["prefix_map"])
        classes = {s for t in (OWL.Class, RDFS.Class) for s in graph.subjects(RDF.type, t)
                   if isinstance(s, URIRef)}  # all IRIs typed as OWL or RDFS class
        props = {s for t in (OWL.ObjectProperty, OWL.DatatypeProperty, RDF.Property)
                 for s in graph.subjects(RDF.type, t) if isinstance(s, URIRef)}  # all IRIs typed as OWL or RDF property
        rows.append({
            "ontology": name,
            "classes": len(classes),
            "properties": len(props),
            # names without namespace (kept for the Jaccard freshness check after generation)
            "class_names": {local_name(str(c)).casefold() for c in classes},
            "prop_names": {local_name(str(p)).casefold() for p in props},
        })
    # median instead of mean, a few very large ontologies (e.g. schema.org) would otherwise dominate N and M
    n = round(statistics.median(r["classes"] for r in rows))
    m = round(statistics.median(r["properties"] for r in rows))
    return n, m, rows


def jaccard_freshness(graph: Graph, rows: list[dict]) -> list[dict]:
    """Jaccard overlap of the generated names against every benchmark ontology"""
    def jaccard(a: set[str], b: set[str]) -> float:
        return len(a & b) / len(a | b) if a | b else 0.0  # values near 0 support the guaranteed unseen assumption

    syn_classes = {local_name(str(s)).casefold() for s in graph.subjects(RDF.type, OWL.Class)}
    syn_props = {local_name(str(s)).casefold() for s in graph.subjects(RDF.type, OWL.ObjectProperty)}
    return [
        {
            "ontology": r["ontology"],
            "jaccard_classes": round(jaccard(syn_classes, r["class_names"]), 3),
            "jaccard_properties": round(jaccard(syn_props, r["prop_names"]), 3),
        }
        for r in rows
    ]


def _identifier(label: str, kind: str) -> str:
    """Turn a generated label into a valid identifier (classes CamelCase, properties lowerCamelCase)"""
    parts = [p for p in re.split(r"[^0-9A-Za-z]+", label) if p]
    if not parts:
        return ""
    camel = "".join(p[:1].upper() + p[1:] for p in parts)
    return camel if kind == "class" else camel[:1].lower() + camel[1:]


def _section_lines(raw: str) -> list[list[str]]:
    """Split the generator's answer into the five numbered list sections"""
    headers = [
        re.compile(r"(list of )?classes", re.I),  # section 0: class names
        re.compile(r"(list of )?(object)?properties", re.I),  # section 1: property names
        re.compile(r"subclass", re.I),  # section 2: subclass axioms (class,superclass)
        re.compile(r"domain", re.I),  # section 3: domain axioms (property,class)
        re.compile(r"range", re.I),  # section 4: range axioms (property,class)
    ]
    sections: list[list[str]] = [[] for _ in headers]
    current = -1
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("```"):
            continue
        bare = re.sub(r"[*_#`]", "", line).strip()
        # headers have no comma, axiom lines always do
        header_like = (
            (re.match(r"^\d+[.)]\s", bare) or bare.lower().startswith("list of"))
            and "," not in bare
        )
        if header_like and current < len(headers) - 1 and headers[current + 1].search(bare):
            current += 1
            continue
        if current < 0 or not bare:
            continue
        item = re.sub(r"^[-*•]\s*", "", bare)
        item = re.sub(r"^\d+[.)]\s*", "", item)
        if item:
            sections[current].append(item)
    return sections


def build_ontology(raw: str, namespace: str) -> tuple[Graph, dict]:
    """Turn the generator's list answer into an RDF graph"""
    cls_lines, prop_lines, sub_lines, dom_lines, rng_lines = _section_lines(raw)
    ns = Namespace(namespace)

    classes: dict[str, str] = {}  # label in lowercase -> identifier
    for label in cls_lines:
        ident = _identifier(label, "class")
        if ident and ident not in classes.values():
            classes[label.casefold()] = ident

    props: dict[str, str] = {}
    for label in prop_lines:
        ident = _identifier(label, "property")
        if ident and ident not in props.values():
            props[label.casefold()] = ident

    def lookup(label: str, table: dict[str, str], kind: str) -> str | None:
        """Find the identifier of a label (by lowercase text or already as identifier)"""
        return table.get(label.casefold()) or (
            _identifier(label, kind) if _identifier(label, kind) in table.values() else None
        )

    graph = Graph()
    graph.bind(namespace.rstrip("#/").rsplit("/", 1)[-1], ns)  # short prefix instead of the full IRI in the ttl file
    # declare classes
    for ident in classes.values():
        graph.add((ns[ident], RDF.type, OWL.Class))
    # declare properties
    for ident in props.values():
        graph.add((ns[ident], RDF.type, OWL.ObjectProperty))

    stats = {"dropped": [], "empty": 0}

    def add_axioms(lines: list[str], predicate, subject_table, subject_kind, object_table, object_kind):
        n = 0
        for line in lines:
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 2 or not parts[1]:
                stats["empty"] += 1  # empty second field, no axiom can be built
                continue
            if len(parts) > 2 and parts[2]:
                stats["dropped"].append(line)  # not the two-field format the prompt demands
                continue
            s = lookup(parts[0], subject_table, subject_kind)
            o = lookup(parts[1], object_table, object_kind)
            if s is None or o is None:
                stats["dropped"].append(line)  # class or property not in the generated lists
                continue
            graph.add((ns[s], predicate, ns[o]))
            n += 1
        return n

    stats["subclass"] = add_axioms(sub_lines, RDFS.subClassOf, classes, "class", classes, "class")
    stats["domain"] = add_axioms(dom_lines, RDFS.domain, props, "property", classes, "class")
    stats["range"] = add_axioms(rng_lines, RDFS.range, props, "property", classes, "class")
    stats["classes"] = len(classes)
    stats["properties"] = len(props)
    return graph, stats


def main() -> None:
    """Parse the arguments and run the generation"""
    parser = argparse.ArgumentParser(description="Generate a synthetic ontology")
    parser.add_argument("--dry-run", action="store_true", help="only print the N/M statistics")
    args = parser.parse_args()
    load_dotenv()

    n, m, rows = median_characteristics()
    print("Key characteristics of the nine benchmark ontologies:")
    for r in rows:
        print(f"  {r['ontology']:>14}: {r['classes']:>5} classes, {r['properties']:>5} properties")
    print(f"  -> median: N={n} classes, M={m} properties")
    if args.dry_run:
        return

    # get the domain name from the generator
    client = MakiClient()
    domain_answer = client.complete(
        DOMAIN_PROMPT, model=GENERATOR_MODEL, temperature=TEMPERATURE,
        max_tokens=32, system=SYSTEM_PROMPT,
    ).text
    domain = (domain_answer.strip().splitlines() or [""])[0].strip(" .\"'")
    if not domain or not re.search(r"[A-Za-z]", domain):
        sys.exit(f"Generator returned no usable domain (answer: {domain_answer!r}) --> rerun.")
    print(f"\nGenerator-chosen domain: {domain}")

    slug = re.sub(r"[^a-z0-9]+", "-", domain.lower()).strip("-")
    if not slug:
        sys.exit(f"Domain {domain!r} yields no usable namespace slug --> rerun.")

    onto_dir = OUT_DIR / slug
    if onto_dir.exists():
        sys.exit(f"{onto_dir}/ already exists --> delete the folder to regenerate.")

    # generate the ontology
    prompt = GENERATION_PROMPT.format(domain=domain, N=n, M=m)
    answer = client.complete(
        prompt, model=GENERATOR_MODEL, temperature=TEMPERATURE,
        max_tokens=8192, system=SYSTEM_PROMPT,
    )
    namespace = f"http://example.org/{slug}#"
    graph, stats = build_ontology(answer.text, namespace)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    # too few classes, properties or axioms means a broken answer, nothing is written then
    if (stats["classes"] < 5 or stats["properties"] < 3
            or min(stats["subclass"], stats["domain"], stats["range"]) < 1):
        (OUT_DIR / "failed-generation.txt").write_text(answer.text, encoding="utf-8")
        sys.exit(
            f"Generation looks degenerate ({stats['classes']} classes, "
            f"{stats['properties']} properties, axioms {stats['subclass']}/"
            f"{stats['domain']}/{stats['range']}). Raw answer saved to "
            "failed-generation.txt; nothing was written, rerun."
        )
    onto_dir.mkdir()
    ttl_path = onto_dir / f"{slug}.ttl"
    graph.serialize(destination=ttl_path, format="turtle")  # write the graph as .ttl file

    freshness = jaccard_freshness(graph, rows)
    print("\nFreshness check (Jaccard overlap of names, near 0 = unseen):")
    for f in freshness:
        print(f"  {f['ontology']:>14}: classes {f['jaccard_classes']:.3f}, "
              f"properties {f['jaccard_properties']:.3f}")

    log = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "generator_model": GENERATOR_MODEL,
        "temperature": TEMPERATURE,
        "system_prompt": SYSTEM_PROMPT,
        "requested": {"N_classes": n, "M_properties": m},
        "characteristics_table": [
            {k: v for k, v in r.items() if not k.endswith("_names")} for r in rows
        ],
        "domain_prompt": DOMAIN_PROMPT,
        "domain_answer_raw": domain_answer,
        "domain": domain,
        "generation_prompt": prompt,
        "generation_answer_raw": answer.text,
        "generation_finish_reason": answer.finish_reason,
        "namespace": namespace,
        "parse_stats": stats,
        "jaccard_freshness": freshness,
    }
    (onto_dir / "generation-log.json").write_text(
        json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(f"\nWritten: {ttl_path} ({len(graph)} triples)")
    print(f"  classes={stats['classes']} properties={stats['properties']} "
          f"subclass={stats['subclass']} domain={stats['domain']} range={stats['range']}")
    print(f"  dropped axioms (unknown elements): {len(stats['dropped'])}, empty fields: {stats['empty']}")
    print(f"Provenance: {onto_dir / 'generation-log.json'}")


if __name__ == "__main__":
    main()
