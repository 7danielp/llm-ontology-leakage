"""Table tab:ts-formats and Figure fig:ts-formats: TS-Guessing micro F1 and correct form per model and identifier format"""
import functools
import re
import statistics

from analysis.common import FORMATS, MODELS, ONTOLOGIES, SHORT, TASKS, TIERS, load_records, name_inferable, number
from analysis.ts_filtered import matrix, run_dir

from llm_ontology_leakage.core.tasks import TASKS as SPECS
from llm_ontology_leakage.ts_guessing.scoring import score


def local(name: str) -> str:
    """Local name in lower case, the part after the last colon, # or /"""
    return re.split(r"[:#/]", name.rstrip("/"))[-1].lower()


def in_requested_form(answer: str, fmt: str) -> bool:
    """plain: no prefix or IRI, prefix: a prefix but no IRI, full: an IRI"""
    iri = answer.startswith(("http://", "https://"))
    return {"plain": ":" not in answer, "prefix": ":" in answer and not iri, "full": iri}[fmt]


@functools.cache
def run(o: str, t: str, m: str, f: str) -> tuple[float | None, int, int]:
    """(form-independent micro F1, answers in the requested form, answers) of one run without the name-inferable questions"""
    records = [r for r in load_records(run_dir(o, t, m, f)) if not name_inferable(r)]
    if not records:
        return None, 0, 0
    spec = SPECS[t]
    tp = fp = fn = in_form = answers = 0
    for r in records:
        parsed, _ = score(r["raw_output"], r["gold"], list_valued=spec.list_valued, match_mode=spec.match)
        items = [p for p in parsed or [] if p]
        golds = {local(g) for g in r["gold_iris"]}
        if spec.list_valued:  # property task: answered set against gold set, by local names
            names = {local(p) for p in items}
            hits = len(names & golds)
            tp, fp, fn = tp + hits, fp + len(names) - hits, fn + len(golds) - hits
        elif r["strict_match"] or (items and local(items[0]) in golds):  # one class: the first answered item
            tp += 1
        else:
            fp, fn = fp + bool(items), fn + 1
        if items:
            answers += 1
            in_form += in_requested_form(items[0], f)
    return (2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.0), in_form, answers


def strict_f1(o: str, t: str, m: str, f: str) -> float | None:
    """F1 score of one run, None if no question is left"""
    return matrix()[(o, t, m, f)]


def form_f1(o: str, t: str, m: str, f: str) -> float | None:
    """Form-independent F1 score of one run, None if no question is left"""
    return run(o, t, m, f)[0]


def macro(value, ontologies, m: str, f: str) -> float:
    """Mean over the ontologies of the mean over the tasks that still have questions"""
    return statistics.mean(statistics.mean(v for t in TASKS if (v := value(o, t, m, f)) is not None) for o in ontologies)


def share(m: str, ontologies, f: str) -> float:
    """Answers in the requested form over all answers"""
    runs = [run(o, t, m, f) for o in ontologies for t in TASKS]
    return sum(r[1] for r in runs) / sum(r[2] for r in runs)


def values() -> dict[str, dict[str, tuple[float, float, float]]]:
    """{model: {format: (F1 score, form-independent F1 score, correct form)}}"""
    return {m: {f: (macro(strict_f1, ONTOLOGIES, m, f), macro(form_f1, ONTOLOGIES, m, f), share(m, ONTOLOGIES, f))
                for f in FORMATS} for m in MODELS}


def lowest_in_plain(scores: dict[tuple[str, str], float]) -> str:
    """Models whose score is lower in the plain format than in the prefix and the full format"""
    return ", ".join(m for m in MODELS if scores[(m, "plain")] < min(scores[(m, "prefix")], scores[(m, "full")])) or "none"


if __name__ == "__main__":
    table = values()
    for m in MODELS:
        print(f"{m} & " + " & ".join(f"{number(f1)} & {number(form)} & {round(100 * correct)}"
                                     for f1, form, correct in table[m].values()) + r" \\")
    print("% values with four decimals (F1 score, form-independent F1 score, correct form)")
    for m in MODELS:
        print(f"%   {m}: " + "; ".join(f"{f} {table[m][f][0]:.4f}, {table[m][f][1]:.4f}, {table[m][f][2]:.4f}" for f in FORMATS))

    f1 = {(m, f): table[m][f][0] for m in MODELS for f in FORMATS}
    form = {(m, f): table[m][f][1] for m in MODELS for f in FORMATS}
    correct = {(m, f): table[m][f][2] for m in MODELS for f in FORMATS}
    print(f"% F1 score lowest in the plain format for: {lowest_in_plain(f1)}")
    print("% F1 score, full minus prefix: "
          + ", ".join(f"{m} {number(f1[(m, 'full')] - f1[(m, 'prefix')], signed=True)}" for m in MODELS))
    plain = sorted(MODELS, key=lambda m: correct[(m, "plain")])
    print("% correct form in the plain format: " + ", ".join(f"{m} {round(100 * correct[(m, 'plain')])} %" for m in MODELS)
          + f"; lowest {plain[0]}, highest {plain[-1]}")
    other = {(m, f): round(100 * correct[(m, f)]) for m in MODELS for f in ("prefix", "full")}  # whole percent
    print(f"% correct form in the prefix and the full format: {min(other.values())} % to {max(other.values())} % ("
          + ", ".join(f"{m} {v} %" for (m, f), v in other.items() if v < 100) + " below 100 %)")
    gains = {k: form[k] - f1[k] for k in f1}
    print("% form-independent minus F1 score: "
          + "; ".join(f"{m} " + ", ".join(number(gains[(m, f)], signed=True) for f in FORMATS) for m in MODELS)
          + f"; gain in every format for every model: {all(g > 0 for g in gains.values())}")
    print(f"% form-independent F1 score lowest in the plain format for: {lowest_in_plain(form)}")
    steps = {m: (f1[(m, "prefix")] - f1[(m, "plain")], form[(m, "prefix")] - form[(m, "plain")]) for m in MODELS}
    print("% prefix minus plain, F1 score against form-independent (share explained by the form): "
          + "; ".join(f"{m} {number(a)} and {number(b)} ({1 - b / a:.0%})" for m, (a, b) in steps.items()))

    print("% plain form on FOAF and Dublin Core Terms: "
          + ", ".join(f"{m} {share(m, ['FOAF', 'Dublin Core Terms'], 'plain'):.0%}" for m in MODELS))
    plain_runs = {o: [run(o, t, m, "plain") for m in MODELS for t in TASKS] for o in ONTOLOGIES}
    prefixed = {o: 1 - sum(r[1] for r in runs) / sum(r[2] for r in runs) for o, runs in plain_runs.items()}  # pooled over the models
    print("% plain answers with a prefix, all models: "
          + ", ".join(f"{tier} {statistics.mean(prefixed[o] for o in os):.0%}" for tier, os in TIERS.items())
          + " (" + ", ".join(f"{SHORT.get(o, o)} {prefixed[o]:.0%}" for o in ONTOLOGIES) + ")")
