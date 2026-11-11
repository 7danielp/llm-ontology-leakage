"""Table tab:ts-relaxed: TS-Guessing in the strict and the relaxed setting, without the name-inferable questions"""
import functools
import statistics
from collections import defaultdict

from rdflib import URIRef

from analysis.common import FORMATS, MODELS, ONTOLOGIES, ROOT, SHORT, TASKS, TIERS, iri_name, load_records, name_inferable, number
from analysis.ts_filtered import run_dir

from llm_ontology_leakage.core.config import ONTOLOGY_PRESETS, build_run_config
from llm_ontology_leakage.core.ontology import axiom_pairs, load_graph, render_identifier
from llm_ontology_leakage.core.tasks import TASKS as SPECS
from llm_ontology_leakage.guided_prompting.similarity import OWL_THING, ClassSimilarity
from llm_ontology_leakage.ts_guessing.scoring import confusion_counts, score

PRESET = {p["ontology_name"]: key for key, p in ONTOLOGY_PRESETS.items()}
SINGLE = ("taxonomy", "domain", "range")  # the tasks with one answer per question
Counts = tuple[int, int, int]  # tp, fp, fn


class Ontology:
    """Class hierarchy of Guided Prompting and domain axioms of one ontology"""

    def __init__(self, name: str) -> None:
        cfg = build_run_config(PRESET[name], task="taxonomy", model=MODELS[0], id_format="plain")
        self.namespace = cfg.ontology_namespace
        self.graph = load_graph(str(ROOT / cfg.ontology_source), cfg.prefix_map)
        self.classes = ClassSimilarity(self.graph, URIRef(cfg.axiom_predicates["taxonomy"]))
        self.by_domain: dict[str, set[str]] = defaultdict(set)  # {class: properties with this stated domain}
        for p, c in axiom_pairs(self.graph, cfg, "domain"):
            self.by_domain[str(c)].add(str(p))

    @functools.cache
    def superclasses(self, c: str) -> frozenset[str]:
        """Transitive superclasses of c, the virtual root owl:Thing only if the file states it on the way up"""
        above = set(self.classes._ancestor_distances(c)) - {c}
        if not any(OWL_THING in self.classes._parents.get(a, ()) for a in above | {c}):
            above.discard(OWL_THING)
        return frozenset(above)

    def accepted(self, task: str, given: str, golds: list[str]) -> set[str]:
        """IRIs the relaxed setting accepts for one question, the stated golds included"""
        if task == "taxonomy":
            return set(self.superclasses(given))
        if task in ("domain", "range"):
            return set(golds).union(*(self.superclasses(g) for g in golds))
        # property task: every property whose domain is the given class or one of its superclasses
        return set().union(*(self.by_domain.get(c, set()) for c in {given} | self.superclasses(given)))

    @functools.cache
    def identifier(self, iri: str, fmt: str) -> str:
        """IRI written in an identifier format, as in the prompts"""
        return render_identifier(URIRef(iri), self.graph, fmt)


@functools.cache
def ontology(name: str) -> Ontology:
    return Ontology(name)


def rendered(o: Ontology, iris: set[str], fmt: str) -> dict[str, str]:
    """{identifier: IRI}, an IRI in the namespace of the ontology wins a shared name (as in EntityResolver)"""
    return {o.identifier(i, fmt): i for i in sorted(iris, key=lambda i: (i.startswith(o.namespace), i))}


def counts(task: str, parsed: list[str], gold: list[str], accepted: list[str]) -> Counts:
    """tp, fp and fn against the accepted identifiers, in the property task missing are only the stated golds"""
    if task != "property":
        return confusion_counts(parsed, accepted, SPECS[task].match)
    listed = set(parsed) - {""}
    tp = len(listed & set(accepted))
    return tp, len(listed) - tp, len(set(gold) - listed)


@functools.cache
def questions(name: str, task: str, model: str, fmt: str) -> tuple[dict, ...]:
    """Per question of one run: key, name-inferable, strict and relaxed counts, IRI of a single answer only relaxed accepts"""
    o, spec, out = ontology(name), SPECS[task], []
    for r in load_records(run_dir(name, task, model, fmt)):
        parsed, _ = score(r["raw_output"], r["gold"], list_valued=spec.list_valued, match_mode=spec.match)
        relaxed = rendered(o, o.accepted(task, r["given_iri"], r["gold_iris"]), fmt)
        c = {"strict": confusion_counts(parsed, r["gold"], spec.match), "relaxed": counts(task, parsed, r["gold"], list(relaxed))}
        new_hit = task in SINGLE and c["relaxed"][0] > c["strict"][0]
        out.append({"key": r["key"], "inferable": name_inferable(r), "counts": c, "hit": relaxed[parsed[0]] if new_hit else None})
    return tuple(out)


def f1(cs: list[Counts]) -> float | None:
    """Micro F1 of the summed counts, None without questions"""
    tp, fp, fn = (sum(c[i] for c in cs) for i in range(3))
    return 2 * tp / (2 * tp + fp + fn) if cs else None


def run_f1(name: str, task: str, model: str, fmt: str, setting: str, filtered: bool = True) -> float | None:
    """Micro F1 of one run, None if the filter removes all its questions"""
    return f1([q["counts"][setting] for q in questions(name, task, model, fmt) if not (filtered and q["inferable"])])


def mean(xs) -> float | None:
    """Mean of the values that are not None, None if there is none"""
    kept = [x for x in xs if x is not None]
    return statistics.mean(kept) if kept else None


def ontology_f1(name: str, model: str, setting: str, filtered: bool = True) -> float:
    """Mean over the tasks and formats of the runs that still have questions"""
    return mean(run_f1(name, t, model, f, setting, filtered) for t in TASKS for f in FORMATS)


def task_gain(name: str, task: str) -> float | None:
    """Relaxed minus strict F1 of one task, mean over the five models and three formats, None without questions"""
    strict = mean(run_f1(name, task, m, f, "strict") for m in MODELS for f in FORMATS)
    return None if strict is None else mean(run_f1(name, task, m, f, "relaxed") for m in MODELS for f in FORMATS) - strict


def gain(name: str) -> float:
    """Relaxed minus strict ontology score, mean over the five models"""
    return statistics.mean(ontology_f1(name, m, "relaxed") - ontology_f1(name, m, "strict") for m in MODELS)


def tier_means(setting: str, filtered: bool = True) -> dict[str, list[float]]:
    """{model: tier means popular to synthetic}"""
    return {m: [statistics.mean(ontology_f1(o, m, setting, filtered) for o in os) for os in TIERS.values()] for m in MODELS}


def order(values: list[float]) -> str:
    """Relations of neighbouring tiers, popular to synthetic"""
    return " ".join(">" if a > b else "<" if a < b else "=" for a, b in zip(values, values[1:]))


def relaxed_row(label: str, ontologies: list[str]) -> str:
    """Strict and relaxed score (mean over the ontologies and the five models), then the gain per task"""
    overall = [statistics.mean(ontology_f1(o, m, s) for o in ontologies for m in MODELS) for s in ("strict", "relaxed")]
    gains = [mean(task_gain(o, t) for o in ontologies) for t in TASKS]
    return (f"{label} & " + " & ".join(number(x) for x in overall) + " & "
            + " & ".join("--" if x is None else number(x, signed=True) for x in gains) + r" \\")


print("% Table tab:ts-relaxed")
for tier, os in TIERS.items():
    print(relaxed_row(rf"\rowcolor{{tierrow}}\textbf{{{tier}}}", os))
    for o in os:
        print(relaxed_row(rf"\quad {SHORT.get(o, o)}", [o]))

print("% gain relaxed minus strict per ontology: " + ", ".join(
    f"{SHORT.get(o, o)} {gain(o):+.3f}" for o in sorted(ONTOLOGIES, key=lambda o: -gain(o))))
for label, filtered in (("", True), ("all questions, ", False)):
    strict, relaxed = tier_means("strict", filtered), tier_means("relaxed", filtered)
    print(f"% {label}tier means per model, strict -> relaxed")
    for m in MODELS:
        print(f"%   {m}: " + ", ".join(f"{number(a)} -> {number(b)}" for a, b in zip(strict[m], relaxed[m]))
              + f"; order strict {order(strict[m])}, relaxed {order(relaxed[m])}")

# single answers on schema.org that only the relaxed setting accepts
hits = {t: [iri_name(q["hit"]) for m in MODELS for f in FORMATS for q in questions("schema.org", t, m, f)
            if not q["inferable"] and q["hit"]] for t in SINGLE}
print("% newly accepted single answers on schema.org that are Thing: "
      + ", ".join(f"{t} {h.count('Thing')} of {len(h)}" for t, h in hits.items())
      + f", together {sum(h.count('Thing') for h in hits.values())} of {sum(len(h) for h in hits.values())}")

# examples ex:schema-ancestor and ex:schema-inherited, record lines 1 and 30 of the prefix runs
for task, model, line, ex in (("taxonomy", "llama-3.3-70b", 1, "ex:schema-ancestor"),
                              ("property", "gpt-5.6-luna", 30, "ex:schema-inherited")):
    q = questions("schema.org", task, model, "prefix")[line - 1]
    print(f"% {ex} ({iri_name(q['key'])}): " + ", ".join(f"{s} F1 {f1([q['counts'][s]]):.2f}" for s in ("strict", "relaxed")))
