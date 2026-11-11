"""Numbers of Section sec:results-web: why the medium tier lies above the popular tier in the TS-Guessing F1 with web search"""
import collections
import functools
import re
import statistics
from fractions import Fraction

from rdflib import URIRef

from analysis.common import FORMATS, ONTOLOGIES, ROOT, SHORT, TASKS, TIERS, number
from analysis.numbers.web_numbers import text
from analysis.ts_wrong_answers import additional, setup
from analysis.web import WEB_3, completed, f1, ts_counts, web_records

POPULAR, MEDIUM = TIERS["Popular"], TIERS["Medium"]
SINGLE = ["taxonomy", "domain", "range"]  # tasks with a single gold
DC, GR, SCHEMA = "Dublin Core Terms", "GoodRelations", "schema.org"


def name(p: str) -> str:
    """Part after the last #, / or :"""
    return re.split(r"[#/:]", p.rstrip("/"))[-1]


def as_written(body: str, word: str) -> bool:
    """Word appears as written as a whole word in body"""
    return re.search(rf"(?<![A-Za-z0-9_]){re.escape(word)}(?![A-Za-z0-9_])", body) is not None


def documents(r: dict) -> list[tuple[dict, dict, str]]:
    """(call, returned document, title and text) of every document that the completed calls of an answer returned"""
    return [(a, x, str(x.get("title") or "") + "\n" + text(a["type"], x))
            for a in r.get("web_search_actions") or [] if a["status"] == "completed" for x in a.get("results") or []]


def has_call(r: dict) -> bool:
    return completed(r.get("web_search_actions")) > 0


def right(rs: list[dict]) -> str:
    """Exact answers among rs, with their share"""
    k = sum(r["strict_match"] for r in rs)
    return f"{k} of {len(rs)} ({number(k / len(rs))})"


records = {c: {o: web_records("ts-guessing", c, o) for o in ONTOLOGIES} for c in ["1 call", "3 calls"]}

# F1 and share of exact matches per run (condition, ontology, task, format)
cell_f1, cell_em = {}, {}
for c, runs in records.items():
    for o in ONTOLOGIES:
        for (t, f), rs in runs[o].items():
            cell_f1[(c, o, t, f)] = f1(*map(sum, zip(*map(ts_counts, rs))))
            cell_em[(c, o, t, f)] = Fraction(sum(r["strict_match"] for r in rs), len(rs))


def task_mean(cells: dict, c: str, o: str, t: str) -> Fraction:
    """Value of an ontology and task, the mean over the three formats"""
    return sum((cells[(c, o, t, f)] for f in FORMATS), Fraction(0)) / len(FORMATS)


def mean(cells: dict, c: str, ontologies: list[str], tasks: list[str] = TASKS) -> float:
    """Mean over the formats and tasks of each ontology, then over the ontologies, as in tab:web-performance"""
    return statistics.mean(float(statistics.mean(task_mean(cells, c, o, t) for t in tasks)) for o in ontologies)


# tiers
popular, medium = mean(cell_f1, "3 calls", POPULAR), mean(cell_f1, "3 calls", MEDIUM)
prop = (mean(cell_f1, "3 calls", MEDIUM, ["property"]) - mean(cell_f1, "3 calls", POPULAR, ["property"])) / len(TASKS)
print(f"F1 medium minus popular, 3 calls: {medium - popular:+.3f} (popular {popular:.3f}, medium {medium:.3f}), "
      f"property task {prop:+.3f}, taxonomy, domain and range {medium - popular - prop:+.3f}")
print("property task F1, popular and medium: " + "; ".join(
    f"{c} {number(mean(cell_f1, c, POPULAR, ['property']))} and {number(mean(cell_f1, c, MEDIUM, ['property']))}"
    for c in records))
print(f"property task EM, popular and medium, 3 calls: {number(mean(cell_em, '3 calls', POPULAR, ['property']))} and "
      f"{number(mean(cell_em, '3 calls', MEDIUM, ['property']))}")
print(f"GoodRelations property task, 1 call: EM {number(float(task_mean(cell_em, '1 call', GR, 'property')))}, "
      f"F1 {number(float(task_mean(cell_f1, '1 call', GR, 'property')))}")
print("taxonomy, domain and range answers right, popular and medium, 3 calls: " + " and ".join(
    right([r for o in TIERS[tier] for t in SINGLE for f in FORMATS for r in records["3 calls"][o][(t, f)]])
    for tier in ["Popular", "Medium"]))
rest = [float(task_mean(cell_f1, "3 calls", o, t)) for o in POPULAR for t in SINGLE if (o, t) != (DC, "domain")]
print(f"taxonomy, domain and range F1, popular without the Dublin Core Terms domain task and medium, 3 calls: "
      f"{number(statistics.mean(rest))} and {number(mean(cell_f1, '3 calls', MEDIUM, SINGLE))}")

# property answers
cfg, graph, exists = setup(SCHEMA)
SUB, DOM = URIRef(cfg.axiom_predicates["taxonomy"]), URIRef(cfg.axiom_predicates["domain"])  # domain is schema:domainIncludes


@functools.cache
def ancestors(cls: URIRef) -> frozenset[URIRef]:
    """Transitive superclasses of a schema.org class"""
    seen, todo = set(), [cls]
    while todo:
        for parent in graph.objects(todo.pop(), SUB):
            if isinstance(parent, URIRef) and parent not in seen:
                seen.add(parent)
                todo.append(parent)
    return frozenset(seen)


found_tier = {"Popular": [0, 0], "Medium": [0, 0]}  # named properties found in the returned text, named properties
for o in [*MEDIUM, *POPULAR]:
    rs = [r for f in FORMATS for r in records["3 calls"][o][("property", f)]]
    named = [[p for p in dict.fromkeys(r["parsed"] or []) if p] for r in rs]
    bodies = ["\n".join(d for *_, d in documents(r)) for r in rs]  # returned text of each answer
    found = sum(as_written(body, name(p)) for body, ps in zip(bodies, named) for p in ps)
    tier = "Popular" if o in POPULAR else "Medium"
    found_tier[tier][0] += found
    found_tier[tier][1] += sum(map(len, named))
    gold = statistics.mean(len(r["gold"]) for r in rs)
    line = (f"property answers, 3 calls, {SHORT.get(o, o)}: {len(rs)} answers, gold {gold:.1f} and named "
            f"{statistics.mean(map(len, named)):.1f} per answer, exact {sum(r['strict_match'] for r in rs)} of {len(rs)}, "
            f"named found in the returned text {found} of {sum(map(len, named))}, "
            f"F1 {number(float(task_mean(cell_f1, '3 calls', o, 'property')))}, "
            f"EM {number(float(task_mean(cell_em, '3 calls', o, 'property')))}")
    if o == SCHEMA:
        extra = [(p, r) for r in rs for p in additional(r, exists)]
        inherited = sum(p is not None and bool(set(graph.objects(URIRef(p), DOM)) & ancestors(URIRef(r["given_iri"])))
                        for p, r in extra)
        line += f"; additional {len(extra)}, with a superclass of the given class as domain {inherited}"
    print(line)
print("named properties found in the returned text, 3 calls: " + ", ".join(
    f"{tier.lower()} {a} of {b} ({a / b:.0%})" for tier, (a, b) in found_tier.items()))
top = max(ONTOLOGIES, key=lambda o: mean(cell_f1, "3 calls", [o]))
print(f"highest F1 of an ontology, 3 calls: {SHORT.get(top, top)} {number(mean(cell_f1, '3 calls', [top]))}")

# examples with up to three calls
for o, given in [(GR, "ProductOrService"), (SCHEMA, "Clip")]:
    r = next(r for r in records["3 calls"][o][("property", "plain")] if r["given"] == given)
    run = f"TS__{o.replace(' ', '-')}__property__gpt-5.6-luna+web3__plain"
    path = WEB_3 / "ts-guessing" / "sample-web" / run / "records.jsonl"
    lines = path.read_text(encoding="utf-8").split("\n")
    line_number = 1 + next(i for i, x in enumerate(lines) if x.strip() and f'"key": "{r["key"]}"' in x)
    tp, fp, fn = ts_counts(r)
    named = [p for p in dict.fromkeys(r["parsed"]) if p]
    docs = documents(r)
    _, best, body = max(docs, key=lambda d: sum(as_written(d[2], name(p)) for p in named))  # document with most named properties
    calls = [a["type"] for a in r["web_search_actions"] if a["status"] == "completed"]
    line = (f"{o} {given}: plain format {path.relative_to(ROOT)}, line {line_number}; gold {len(r['gold'])}, "
            f"named {len(named)}, correct {tp}, F1 {number(float(f1(tp, fp, fn)))}; completed calls {len(calls)} "
            f"({', '.join(calls)}), {len(docs)} documents; {best.get('url')}")
    if o == GR:
        listed = [x[3:] for x in re.search(r"Properties \(rdfs:domain\) : ((?:gr:\S+ ?)+)", body).group(1).split()]
        per_format = [next(x for x in records["3 calls"][o][("property", f)] if x["key"] == r["key"]) for f in FORMATS]
        line += (f" lists {len(listed)} properties on its line 'Properties (rdfs:domain) :', named in the same order: "
                 f"{listed == named}, gold among them {sum(x in set(r['gold']) for x in listed)}; (tp, fp, fn) per format: "
                 + ", ".join(f"{f} {ts_counts(x)}" for f, x in zip(FORMATS, per_format)))
    else:
        heads = list(dict.fromkeys(re.findall(r"Properties from (\w+)", body)))
        own = body.split(f"Properties from {heads[0]}", 1)[1].split(f"Properties from {heads[1]}", 1)[0]
        listed = list(dict.fromkeys(re.findall(r"` (\w+)`", own)))
        page = list(dict.fromkeys(re.findall(r"` (\w+)`", body.split(f"Properties from {heads[0]}", 1)[1])))
        line += (f" groups its properties under 'Properties from' {', '.join(heads)}; the group of {heads[0]} lists "
                 f"{len(listed)}, equal to the gold: {set(listed) == set(r['gold'])}; all groups list {len(page)}, "
                 f"the answer names {len(set(named) & set(page))} of them and {len(set(named) - set(page))} others")
    print(line)

# Dublin Core Terms
dc = records["3 calls"][DC]
print(f"Dublin Core Terms, 3 calls: F1 {number(mean(cell_f1, '3 calls', [DC]))}; per task (sampled questions) " + ", ".join(
    f"{t} {number(float(task_mean(cell_f1, '3 calls', DC, t)))} ({len(dc[(t, 'plain')])})" for t in TASKS)
      + f"; right {right([r for rs in dc.values() for r in rs])}")
rs = [r for f in FORMATS for r in dc[("domain", f)]]
with_call, without = [ts_counts(r) for r in rs if has_call(r)], [ts_counts(r) for r in rs if not has_call(r)]
golds = collections.Counter(name(g) for r in rs for g in r["gold"])
wrong = collections.Counter(r["parsed"][0] for r in rs if r["parsed"] and not r["strict_match"])
print(f"Dublin Core Terms domain task, 3 calls: tool used in {len(with_call)} of {len(rs)} answers, F1 with a call "
      f"{number(float(f1(*map(sum, zip(*with_call)))))} and without {number(float(f1(*map(sum, zip(*without)))))}; "
      f"golds {dict(golds)}; wrong answers {dict(wrong.most_common())}")
