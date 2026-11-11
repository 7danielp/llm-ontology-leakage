"""Appendix app:results: numbered examples of TS-Guessing, Guided Prompting and Min-K% records as LaTeX"""
import json
import statistics

from analysis.common import ONTOLOGIES, ROOT, SHORT, number

FOLDER = {"TS": "ts-guessing", "GP": "guided-prompting", "MK": "min-k"}
METHOD = {"TS": "TS-Guessing", "GP": "Guided Prompting", "MK": "Min-K\\% Prob"}


def path(run: str) -> str:
    """Records file of a run, relative to the repository root"""
    return f"results/full-no-web-search/runs/{FOLDER[run.split('__')[0]]}/{run}/records.jsonl"


def lines(run: str) -> list[str]:
    return [l for l in (ROOT / path(run)).read_text(encoding="utf-8").split("\n") if l.strip()]


def find(run: str, field: str, value: str) -> tuple[int, dict]:
    """Line number and parsed record of the only record whose field has the value"""
    hits = [(i, json.loads(l)) for i, l in enumerate(lines(run), 1) if json.loads(l)[field] == value]
    assert len(hits) == 1, (run, value)
    return hits[0]


def tex(text: str) -> str:
    """Text with the LaTeX special characters escaped"""
    return text.replace("\\", "\\textbackslash{}").replace("_", "\\_").replace("#", "\\#").replace("%", "\\%").replace("&", "\\&")


def tt(text: str) -> str:
    return "\\texttt{" + tex(text) + "}"


def run_line(run: str) -> str:
    """Method, ontology, task, model and format of a run, from its folder name"""
    method, ontology, task, model, fmt = run.split("__")
    name = next(o for o in ONTOLOGIES if o.replace(" ", "-") == ontology)
    return f"{METHOD[method]}, {SHORT.get(name, name)}, {task} task, {model}, {fmt} format"


def table(rows: list[tuple], header: list[str] | None = None) -> str:
    """Field names in the first column, one column per record"""
    spec = "@{}l" + ">{\\raggedright\\arraybackslash}X" * (len(rows[0]) - 1) + "@{}"
    body = ([" & ".join([""] + header) + " \\\\", "\\midrule"] if header else []) + [" & ".join(row) + " \\\\" for row in rows]
    return "{\\small\\begin{tabularx}{\\linewidth}{" + spec + "}\n\\toprule\n" + "\n".join(body) + "\n\\bottomrule\n\\end{tabularx}}"


def ts_rows(records: list[dict], format_example: bool = False) -> list[tuple]:
    def answer(r: dict) -> str:
        return ", ".join(tt(p) for p in r["parsed"]) if r["task"] == "property" else tt(r["raw_output"].strip())
    rows = [("Masked axiom", *(tt(r["prompt"].split("\n")[1]) for r in records))]
    if format_example:
        rows.append(("Format example", *(tt(r["prompt"].rsplit("format: ", 1)[1].strip()) for r in records)))
    return rows + [("Gold", *(", ".join(tt(g) for g in r["gold"]) for r in records)),
                   ("Answer", *(answer(r) for r in records)),
                   ("Exact match", *("yes" if r["strict_match"] else "no" for r in records))]


def gp_rows(r: dict) -> list[tuple]:
    return [("Masked axiom", tt(r["prompt_normal"].split("AXIOM:\n")[1].split("\n")[0])),
            ("Gold", ", ".join(tt(g) for g in r["gold"])),
            ("Normal answer", tt(r["raw_normal"].strip())),
            ("Guided answer", tt(r["raw_guided"].strip())),
            ("Wu and Palmer", f"normal {number(r['sim_normal']['wup'])}, guided {number(r['sim_guided']['wup'])}")]


def mk_rows(r: dict, text: bool = False) -> list[tuple]:
    return ([("Block text", tt(r["text"]))] if text else []) + [("Axiom lines in the block", str(r["n_axioms"])), ("Min-20\\,\\% score", number(r["scores"]["min_20"]))]


def line_means(r: dict) -> list[tuple[float, float]]:
    """Mean log probability per token of the subject and of the whole line, per line of a Min-K% block"""
    result, current = [], []
    for token, logprob in zip(r["tokens"], r["token_logprobs"]):
        if logprob is None:  # begin-of-text token
            continue
        current.append((token, logprob))
        if "\n" in token:
            result.append(current)
            current = []
    if current:
        result.append(current)
    means = []
    for tokens in result:
        n = next(i for i, (t, _) in enumerate(tokens) if " " in t or "\n" in t)  # the subject ends at the first space
        means.append((statistics.mean(lp for _, lp in tokens[:n]), statistics.mean(lp for _, lp in tokens)))
    return means


def example(title: str, label: str, run: str, line_numbers: list[int], body: str, note: str) -> str:
    where = f"line {line_numbers[0]}" if len(line_numbers) == 1 else "lines " + " and ".join(str(n) for n in line_numbers)
    # the minipage keeps the run line and the table of fields on one page
    return (f"\\example{{{title}}}{{{label}}}%\n\\begin{{minipage}}{{\\linewidth}}\\raggedright\n"
            f"{run_line(run)}. Full record{'s' if len(line_numbers) > 1 else ''} in \\url{{{path(run)}}}, {where}.\\par\\smallskip\n"
            f"{body}\n\\end{{minipage}}\\par\\smallskip\n{note}\n")


out = ["% built by analysis/app_examples.py", "\\begingroup\\raggedright  % long identifiers and paths, ragged right avoids overfull lines",
       "All file paths are relative to the root of the repository (Appendix~\\ref{app:code}). "
       "Each example shows only the fields of a record that matter for the observation, and names the file and line of the full record.", "",
       "\\section{Examples of TS-Guessing Answers}", "\\label{app:ts-examples}", ""]

# two records of one run, plus counts over its three formats
run = "TS__Coffee-Brewing__domain__llama-3.3-70b__plain"
pairs = sorted([find(run, "given", "affects"), find(run, "given", "follows")], key=lambda p: p[0])
answers = [json.loads(l) for f in ("plain", "prefix", "full") for l in lines(run.replace("__plain", f"__{f}"))]
brewing_answers = sum(r["raw_output"].strip().split(":")[-1].split("#")[-1] == "BrewingMethod" for r in answers)  # without prefix or namespace
brewing_golds = sum(r["gold"] == ["BrewingMethod"] for r in (json.loads(l) for l in lines(run)))
out.append(example("Default answer that exists in the ontology", "ex:coffee-default", run, [p[0] for p in pairs],
                   table(ts_rows([p[1] for p in pairs]), [tt(p[1]["given"]) for p in pairs]),
                   f"The model llama-3.3-70b gives the same answer \\texttt{{BrewingMethod}} to both properties. It is a hit for \\texttt{{follows}} and a miss for \\texttt{{affects}}. "
                   f"Over the three formats the model answers \\texttt{{BrewingMethod}} to {brewing_answers} of its {len(answers)} domain questions, and the class is the gold of {brewing_golds} properties (Section~\\ref{{sec:results-ts}})."))

TS = [
    ("Right datatype, wrong namespace", "ex:nfo-datatype", "TS__NEPOMUK-File-Ontology__range__llama-3.3-70b__prefix", "nfo:aspectRatio", True,
     "The model names the right datatype, but in the namespace of NFO (\\texttt{nfo:Float} instead of \\texttt{xsd:float}), as the format example \\texttt{nfo:ExampleClass} in the prompt suggests (Section~\\ref{sec:results-ts})."),
    ("Answer in the property name", "ex:epplan-name", "TS__EP-Plan__range__qwen3.5-122b__prefix", "ep-plan:hasConstraint", False,
     "The gold class \\texttt{ep-plan:Constraint} can be read off the property name \\texttt{ep-plan:hasConstraint} (Section~\\ref{sec:results-ts})."),
    ("Superclass further up the hierarchy", "ex:schema-ancestor", "TS__schema.org__taxonomy__llama-3.3-70b__prefix", "schema:3DModel", False,
     "The answer \\texttt{schema:CreativeWork} is the superclass of the gold \\texttt{schema:MediaObject}, so the axiom holds, but the ontology does not state it directly (Section~\\ref{sec:results-ts-tasks})."),
    ("Inherited properties listed", "ex:schema-inherited", "TS__schema.org__property__gpt-5.6-luna__prefix", "schema:Book", False,
     "The answer holds all 6 gold properties and 5 further properties, such as \\texttt{schema:author}, that have the superclass \\texttt{schema:CreativeWork} as domain, so \\texttt{schema:Book} only inherits them (F1 0.71, Section~\\ref{sec:results-ts-tasks})."),
    ("Right name, wrong form", "ex:foaf-form", "TS__FOAF__domain__ministral-3-14b__plain", "familyName", True,
     "The class is right, but the answer carries a prefix that the format example does not have, so \\texttt{foaf:Person} counts as a miss (Section~\\ref{sec:results-ts-formats})."),
]
for title, label, run, given, format_example, note in TS:
    n, r = find(run, "given", given)
    out.append(example(title, label, run, [n], table(ts_rows([r], format_example)), note))

out += ["\\section{Examples of Guided Prompting Answers}", "\\label{app:gp-examples}", ""]
GP = [
    ("Central class instead of the gold", "ex:foaf-gp", "GP__FOAF__domain__llama-3.3-70b__plain", "icqChatID",
     "The guided answer \\texttt{Person} is not the gold \\texttt{Agent}, but as a subclass of it still scores 0.80, while the normal answer \\texttt{UserAccount} is not a class of FOAF and scores 0 (Section~\\ref{sec:results-gp})."),
    ("Name of a synthetic ontology helps", "ex:weather-gp", "GP__Weather-Patterns__domain__llama-3.3-70b__plain", "hasEye",
     "The ontology cannot be part of the training data, yet the guided prompt, which names it, leads to the answer \\texttt{TropicalCyclone} close to the gold \\texttt{Hurricane} (similarity 0.89, Section~\\ref{sec:results-gp-synthetic})."),
    ("Guessed class exists", "ex:coffee-gp", "GP__Coffee-Brewing__domain__llama-3.3-70b__plain", "follows",
     "The class \\texttt{BrewingMethod}, guessed with the guided prompt that names the ontology, exists and is the gold (Section~\\ref{sec:results-gp-synthetic})."),
    ("Normal answer invents a class", "ex:schema-gp", "GP__schema.org__taxonomy__gpt-5.6-luna__prefix", "schema:Apartment",
     "The normal answer \\texttt{schema:Building} is not a class of schema.org and scores 0, while the guided answer is the gold (Section~\\ref{sec:results-gp-formats})."),
    ("Ontology name answered as a class", "ex:org-gp", "GP__W3C-Organization-Ontology__domain__ministral-3-14b__plain", "headOf",
     "The guided answer is \\texttt{Organization}, the class after which the ontology is named. It is not the gold \\texttt{Agent} but lies close to it in the class hierarchy (similarity 0.80, Section~\\ref{sec:results-gp-models})."),
    ("Placeholder as answer", "ex:epplan-gp", "GP__EP-Plan__range__ministral-3-14b__plain", "includesStep",
     "The normal answer is the placeholder \\texttt{OntologyClass}, which scores 0 and inflates the gap (Section~\\ref{sec:results-gp-models})."),
]
for title, label, run, given, note in GP:
    n, r = find(run, "given", given)
    out.append(example(title, label, run, [n], table(gp_rows(r)), note))

out += ["\\section{Examples of Min-K\\% Blocks}", "\\label{app:mink-examples}", "",
        "The records of Min-K\\% Prob also hold the tokens of a block and one log probability per token. The examples show the text of the block, the number of its axiom lines and its Min-20\\,\\% score. "
        "The first token of a record has no log probability and is not scored. For llama-3.3-70b and ministral-3-14b this is the begin-of-text token of the model, for qwen3.5-122b and qwen3.6-36b the first token of the block itself.", ""]

run = "MK__W3C-Organization-Ontology__range__llama-3.3-70b__prefix"
n, rec = find(run, "key", "range-003")
ten_axiom_scores = [json.loads(l)["scores"]["min_20"] for l in lines(run) if json.loads(l)["n_axioms"] == 10]
out.append(example("Remainder block with a single axiom line", "ex:org-remainder", run, [n], table(mk_rows(rec, text=True)),
                   f"The block holds a single axiom line and scores {number(rec['scores']['min_20'])}, compared with {number(min(ten_axiom_scores))} to {number(max(ten_axiom_scores))} for the three blocks of ten lines of the same task (Table~\\ref{{tab:questions}} and Section~\\ref{{sec:results-mink-ontologies}})."))
run = "MK__EP-Plan__domain__llama-3.3-70b__prefix"
n, rec = find(run, "key", "domain-005")
rows = "\\\\\n".join(f"\\texttt{{{tex(l)}}} & {number(s)} & {number(w)}" for l, (s, w) in zip(rec["text"].split("\n"), line_means(rec)))
lines_table = f"{{\\scriptsize\\begin{{tabular}}{{@{{}}lrr@{{}}}}\n\\toprule\nAxiom line & Property & Whole line \\\\\n\\midrule\n{rows}\\\\\n\\bottomrule\n\\end{{tabular}}}}"
out.append(example("Repeated subject from a union", "ex:epplan-union", run, [n], table(mk_rows(rec)) + "\\par\\medskip\n" + lines_table,
                   "The second table gives, for each line of the block, the mean log probability per token of the property at its start and of the whole line, computed from the tokens of the record. "
                   "The property \\texttt{ep-plan:isElementOfPlan} scores much lower in its first line than in the six lines that repeat it. "
                   "The whole first line is lower mainly because of its class \\texttt{ep-plan:CommunicationSpecification}, whose tokens the model predicts poorly (Section~\\ref{sec:results-mink})."))
out.append("\\endgroup")
print("\n".join(out))
