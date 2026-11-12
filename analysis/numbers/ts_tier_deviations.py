"""Numbers of Section sec:results-ts-ontologies: ontologies that score unlike their tier, TS-Guessing with all questions"""
import re
import statistics

from analysis.common import FORMATS, MAKI, MODELS, RESULTS, TASKS, iri_name, load_records, name_inferable, number, read_matrix

from llm_ontology_leakage.core.tasks import TASKS as SPECS
from llm_ontology_leakage.ts_guessing.scoring import confusion_counts, score

RUNS = RESULTS / "runs" / "ts-guessing"
DC, FOAF, NFO, W3C = "Dublin Core Terms", "FOAF", "NEPOMUK File Ontology", "W3C Organization Ontology"
XSD = "http://www.w3.org/2001/XMLSchema#"
run_f1 = read_matrix("ts_matrix_f1.csv")  # {(ontology, task, model, format): micro F1 of the run}


def records(o: str, t: str, m: str, f: str) -> list[dict]:
    return load_records(RUNS / f"TS__{o.replace(' ', '-')}__{t}__{m}__{f}")


def local(x: str) -> str:
    """Local name of an IRI or a prefixed name"""
    return re.split(r"[#/:]", x.strip().rstrip("/"))[-1]


def span(values: list[float]) -> str:
    return f"{number(min(values))} to {number(max(values))}"


def micro_f1(o: str, m: str) -> float:
    """Micro F1 of a model over all answers of the four tasks and three formats"""
    tp = fp = fn = 0
    for t in TASKS:
        spec = SPECS[t]
        for f in FORMATS:
            for r in records(o, t, m, f):
                parsed, _ = score(r["raw_output"], r["gold"], list_valued=spec.list_valued, match_mode=spec.match)
                a, b, c = confusion_counts(parsed, r["gold"], spec.match)
                tp, fp, fn = tp + a, fp + b, fn + c
    return 2 * tp / (2 * tp + fp + fn)


def other_namespace(r: dict) -> bool:
    """Miss that names the right XML Schema datatype in another namespace, as nfo:Float for xsd:float"""
    answer = r["raw_output"].strip()
    return (not r["strict_match"] and all(g.startswith(XSD) for g in r["gold_iris"]) and ":" in answer
            and not answer.startswith(XSD) and not answer.lower().startswith("xsd:")
            and local(answer).lower() in {local(g).lower() for g in r["gold_iris"]})


def table_value(o: str, m: str) -> float:
    """Value of Table tab:ts-f1, mean run F1 over the four tasks and three formats"""
    return statistics.mean(run_f1[(o, t, m, f)] for t in TASKS for f in FORMATS)


def value_with_other_namespace(o: str, m: str) -> float:
    """Value of Table tab:ts-f1 if these misses counted as hits, the range F1 is the EM rate"""
    values = [run_f1[(o, t, m, f)] for t in TASKS if t != "range" for f in FORMATS]
    for f in FORMATS:
        values.append(statistics.mean(bool(r["strict_match"]) or other_namespace(r) for r in records(o, "range", m, f)))
    return statistics.mean(values)


def is_org(r: dict) -> bool:
    return any(iri_name(g) == "Organization" and "/ns/org" in g for g in r["gold_iris"])


for o in (DC, FOAF):
    print(f"{o} taxonomy max F1 (MAKI): {number(max(run_f1[(o, 'taxonomy', m, f)] for m in MAKI for f in FORMATS))}")
for t in ("domain", "property"):
    rs = [r for m in MODELS for f in FORMATS for r in records(DC, t, m, f)]
    print(f"{DC} {t} questions: {len(records(DC, t, MAKI[0], 'plain'))}, "
          f"exact over all models and formats: {sum(r['strict_match'] for r in rs)}")
for o in (DC, FOAF):
    print(f"{o} micro F1 per model, four tasks together: {span([micro_f1(o, m) for m in MODELS])}")

nfo = records(NFO, "range", MAKI[0], "plain")
datatypes = sum(all(g.startswith(XSD) for g in r["gold_iris"]) for r in nfo)
print(f"NFO range golds that are XML Schema datatypes: {datatypes} of {len(nfo)}")
print(f"NFO with the right datatype in another namespace as hit: {span([value_with_other_namespace(NFO, m) for m in MODELS])} "
      f"instead of {span([table_value(NFO, m) for m in MODELS])}")

for t in ("taxonomy", "domain", "range"):
    questions = records(W3C, t, MAKI[0], "plain")
    n = sum(is_org(r) for r in questions)
    print(f"W3C Organization {t} questions with gold org:Organization: {n} of {len(questions)}, "
          f"F1 of always answering it: {number(n / len(questions))}")
correct = [r for t in ("taxonomy", "domain", "range") for m in MODELS for f in FORMATS for r in records(W3C, t, m, f)
           if r["strict_match"]]
org = sum(map(is_org, correct))
print(f"W3C Organization correct taxonomy, domain and range answers that are org:Organization: {org} of {len(correct)} "
      f"({number(org / len(correct))})")

counts = []
for t in ("taxonomy", "domain", "range"):
    correct = [r for m in MODELS for f in FORMATS for r in records("EP-Plan", t, m, f) if r["strict_match"]]
    counts.append((sum(map(name_inferable, correct)), len(correct)))
    print(f"EP-Plan correct {t} answers with the gold in the given name: {counts[-1][0]} of {counts[-1][1]}")
inferable, total = map(sum, zip(*counts))
print(f"EP-Plan correct taxonomy, domain and range answers with the gold in the given name: {inferable} of {total} "
      f"({number(inferable / total)})")
