"""Records of the web search runs of gpt-5.6-luna on the sampled questions, shared by the web search scripts"""
from fractions import Fraction

from analysis.common import ROOT, load_records

from llm_ontology_leakage.core.parsing import parse_elements
from llm_ontology_leakage.core.tasks import TASKS as SPECS
from llm_ontology_leakage.ts_guessing.scoring import confusion_counts

WEB_1 = ROOT / "results" / "sampled-web-search-1call" / "runs"
WEB_3 = ROOT / "results" / "sampled-web-search-3calls" / "runs"
# (runs folder, run, model) per condition, no web = the answers of the main run to the sampled questions
CONDITIONS = {"no web": (WEB_1, "sample-reference", "gpt-5.6-luna"),
              "1 call": (WEB_1, "sample-web", "gpt-5.6-luna+web"),
              "3 calls": (WEB_3, "sample-web", "gpt-5.6-luna+web3")}


def web_records(method: str, condition: str, ontology: str) -> dict[tuple[str, str], list[dict]]:
    """Records of one condition per (task, format), method is ts-guessing or guided-prompting"""
    base, sub, model = CONDITIONS[condition]
    prefix = "TS" if method == "ts-guessing" else "GP"
    found = {}
    for run_dir in (base / method / sub).glob(f"{prefix}__{ontology.replace(' ', '-')}__*__{model}__*"):
        _, _, task, run_model, fmt = run_dir.name.split("__")
        if run_model == model:  # the glob for +web also matches +web3
            found[(task, fmt)] = load_records(run_dir)
    return found


def completed(actions: list[dict] | None) -> int:
    """Number of completed web calls of one answer"""
    return sum(a["status"] == "completed" for a in actions or [])


def blocked(actions: list[dict] | None) -> bool:
    """Model asked for a call beyond its limit"""
    return any(a["status"] != "completed" for a in actions or [])


def ts_counts(record: dict) -> tuple[int, int, int]:
    """(tp, fp, fn) of one TS-Guessing answer, scored again from its raw output"""
    spec = SPECS[record["task"]]
    return confusion_counts(parse_elements(record["raw_output"], spec.list_valued), record["gold"], spec.match)


def f1(tp: int, fp: int, fn: int) -> Fraction:
    """Exact F1 from summed counts, 2tp / (2tp + fp + fn)"""
    return Fraction(2 * tp, 2 * tp + fp + fn)
