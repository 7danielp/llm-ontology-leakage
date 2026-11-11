"""Constants and helpers shared by the analysis scripts"""
import csv
import json
import re
import statistics
from collections.abc import Callable
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results" / "full-no-web-search"  # main run
FIGURES = ROOT / "ressources" / "figures"  # output of the scripts in analysis/figures

MAKI = ["ministral-3-14b", "qwen3.6-36b", "llama-3.3-70b", "qwen3.5-122b"]
MODELS = MAKI + ["gpt-5.6-luna"]
MODEL_NAME = {"qwen3.6-36b": "qwen3.6-35b"} # fix


def model_name(model: str) -> str:
    """Name of a model as printed in the thesis"""
    return MODEL_NAME.get(model, model)

FORMATS = ["plain", "prefix", "full"]
TASKS = ["taxonomy", "domain", "range", "property"]

# tiers in table order, names as in the result files, popular and medium tier sorted by LOV rank
TIERS = {
    "Popular": ["Dublin Core Terms", "schema.org", "FOAF"],
    "Medium": ["GoodRelations", "NEPOMUK File Ontology", "W3C Organization Ontology"],
    "Unpopular": ["Cinelab", "EP-Plan", "Urban IoT Electric Mobility"],
    "Synthetic": ["Weather Patterns", "Coffee Brewing", "Waste Management"],
}
ONTOLOGIES = [o for ontologies in TIERS.values() for o in ontologies]
SHORT = {"NEPOMUK File Ontology": "NFO", "W3C Organization Ontology": "W3C Organization",
         "Urban IoT Electric Mobility": "Urban IoT"}


def read_matrix(name: str, folder: Path = RESULTS) -> dict[tuple[str, str, str, str], float]:
    """Matrix CSV as {(ontology, task, model, format): value}"""
    cells = {}
    with open(folder / name, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            ontology, task = row.pop("ontology/task").split("/")
            for column, value in row.items():
                model, fmt = column.split("|")
                cells[(ontology, task, model, fmt)] = float(value)
    return cells


def read_aggregate(name: str, folder: Path = RESULTS) -> list[dict]:
    with open(folder / name, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def read_gaps(folder: Path = RESULTS) -> dict[tuple[str, str, str, str], tuple[float, bool]]:
    """Guided Prompting gap (Wu and Palmer, all questions) and significance per (ontology, task, model, format)"""
    runs = {d.name: d for d in (folder / "runs" / "guided-prompting").rglob("GP__*") if d.is_dir()}
    gaps = {}
    for r in read_aggregate("gp_aggregate.csv", folder):
        if r["measure"] != "wup" or r["segment"] != "all":
            continue
        records = load_records(runs["__".join(["GP", r["ontology"].replace(" ", "-"), r["task"], r["model"], r["id_format"]])])
        # from the records (to avoid double rounding)
        gap = statistics.mean(x["sim_guided"]["wup"] for x in records) - statistics.mean(x["sim_normal"]["wup"] for x in records)
        gaps[(r["ontology"], r["task"], r["model"], r["id_format"])] = (round(gap, 9), r["significant"] == "1")
    return gaps


def gap_entry(gap: tuple[float, bool]) -> str:
    """Signed gap, on a grey background if significant"""
    text = number(gap[0], signed=True)
    return rf"\cellcolor{{tierrow}}{text}" if gap[1] else text


def iri_name(iri: str) -> str:
    """Local name of an IRI, the part after the last # or /"""
    return re.split(r"[#/]", iri.rstrip("/"))[-1]


def name_words(name: str) -> list[str]:
    """Lowercase words of a camel case name, hasEVSEChargeCategory gives has evse charge category"""
    return [w.lower() for w in re.findall(r"[A-Z]+(?![a-z])|[A-Z]?[a-z]+|\d+", name)]


def name_inferable(record: dict) -> bool:
    """Gold name appears as whole words in the given name, as Constraint in hasConstraint"""
    given = name_words(iri_name(record["given_iri"]))
    for gold in record["gold_iris"]:
        w = name_words(iri_name(gold))
        if w and any(given[i:i + len(w)] == w for i in range(len(given) - len(w) + 1)):
            return True
    return False


def outside_namespace(run_dir: Path) -> str:
    """Namespace of the run as the main code sets it (core/config.py), sibling vocabularies such as dcmitype count as inside"""
    identity = json.loads((run_dir / "run_meta.json").read_text(encoding="utf-8"))["identity"]
    return identity["ontology_namespace"]


def golds_outside(record: dict, namespace: str) -> bool:
    """All golds of a question lie outside the namespace"""
    return all(not g.startswith(namespace) for g in record["gold_iris"])


def load_records(run_dir: Path) -> list[dict]:
    lines = (run_dir / "records.jsonl").read_text(encoding="utf-8").split("\n")  # not splitlines, web snippets may hold U+2028
    return [json.loads(line) for line in lines if line.strip()]


def number(x: float, signed: bool = False) -> str:
    """Two decimals with a real minus sign, and an explicit plus if signed"""
    # half up on the shortest decimal form, so 0.075 (stored as 0.07499...) gives 0.08
    text = str(Decimal(repr(abs(x))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    if text == "0.00":
        return text
    if x < 0:
        return f"$-${text}"
    return f"$+${text}" if signed else text


def tier_rows(values: dict[str, list[float]]) -> str:
    """Grey tier row with the mean of its ontologies, then one row per ontology"""
    lines = []
    for tier, ontologies in TIERS.items():
        columns = len(values[ontologies[0]])
        means = [statistics.mean(values[o][i] for o in ontologies) for i in range(columns)]
        lines.append(rf"\rowcolor{{tierrow}}\textbf{{{tier}}} & " + " & ".join(number(m) for m in means) + r" \\")
        for o in ontologies:
            lines.append(rf"\quad {SHORT.get(o, o)} & " + " & ".join(number(v) for v in values[o]) + r" \\")
    return "\n".join(lines)


def full_rows(cell: Callable[[str, str, object], str], columns: list, tasks: list[str] = TASKS) -> str:
    """One row per ontology and task, cell(ontology, task, column) gives one entry"""
    lines = []
    for o in ONTOLOGIES:
        for k, t in enumerate(tasks):
            lines.append(f"{SHORT.get(o, o) if k == 0 else ''} & {t} & " + " & ".join(cell(o, t, c) for c in columns) + r" \\")
        lines.append(r"\addlinespace")
    return "\n".join(lines[:-1])
