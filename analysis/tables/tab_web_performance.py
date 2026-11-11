"""Table tab:web-performance: TS-Guessing F1 and Guided Prompting gap of gpt-5.6-luna without and with web search"""
import statistics

from analysis.common import ONTOLOGIES, SHORT, TASKS, TIERS, number
from analysis.web import CONDITIONS, SPECS, confusion_counts, f1, parse_elements, ts_counts, web_records

ts = {(c, o): web_records("ts-guessing", c, o) for c in CONDITIONS for o in ONTOLOGIES}
gp = {(c, o): web_records("guided-prompting", c, o) for c in CONDITIONS for o in ONTOLOGIES}


WRONG_NAMESPACE = {"dcterms:Collection", "http://purl.org/dc/terms/Collection"}  # the gold class of the Dublin Core Terms domain task in the dcterms namespace


def macro_f1(c: str, o: str, counts=ts_counts) -> float:
    """Micro F1 per task and format, mean over the twelve runs"""
    return float(statistics.mean(f1(*map(sum, zip(*map(counts, rs)))) for rs in ts[(c, o)].values()))


def namespace_counts(r: dict) -> tuple[int, int, int]:
    """(tp, fp, fn) with a domain answer in WRONG_NAMESPACE counted as the gold"""
    if r["task"] != "domain":
        return ts_counts(r)
    spec = SPECS[r["task"]]
    answer = [r["gold"][0] if a.strip() in WRONG_NAMESPACE else a for a in parse_elements(r["raw_output"], spec.list_valued)]
    return confusion_counts(answer, r["gold"], spec.match)


def macro_em(c: str, o: str) -> float:
    """Share of exact matches per task and format, mean over the twelve runs"""
    return statistics.mean(sum(r["strict_match"] for r in rs) / len(rs) for rs in ts[(c, o)].values())


def plain_gap(c: str, o: str) -> float:
    """Gap (Wu and Palmer) in the plain format, mean over the four tasks"""
    return statistics.mean(statistics.mean(r["sim_guided"]["wup"] - r["sim_normal"]["wup"] for r in rs)
                           for (_, fmt), rs in gp[(c, o)].items() if fmt == "plain")


# entries per ontology and condition
stats = {o: {c: {"f1": macro_f1(c, o), "gap": plain_gap(c, o)} for c in CONDITIONS} for o in ONTOLOGIES}


def row(label: str, ontologies: list[str]) -> str:
    n = sum(len(ts[("no web", o)][(t, "plain")]) for o in ontologies for t in TASKS)  # sampled questions
    f1s = [number(statistics.mean(stats[o][c]["f1"] for o in ontologies)) for c in CONDITIONS]
    gaps = [number(statistics.mean(stats[o][c]["gap"] for o in ontologies), signed=True) for c in CONDITIONS]
    return f"{label} & {n:,} & " + " & ".join(f1s + gaps) + r" \\"


if __name__ == "__main__":
    for tier, ontologies in TIERS.items():
        print(r"\rowcolor{tierrow}" + row(rf"\textbf{{{tier}}}", ontologies))
        for o in ontologies:
            print(row(rf"\quad {SHORT.get(o, o)}", [o]))
    print(r"\midrule")
    print(row(r"\textbf{All}", ONTOLOGIES))

    print("% F1 change no web to 3 calls: " + "; ".join(
        f"{tier} {number(statistics.mean(stats[o]['3 calls']['f1'] - stats[o]['no web']['f1'] for o in ontologies), True)}"
        for tier, ontologies in TIERS.items()))
    groups = [TIERS["Popular"], [o for o in TIERS["Popular"] if o != "Dublin Core Terms"], TIERS["Medium"]]
    print("% exact match averaged like the F1 score, popular / popular without Dublin Core Terms / medium: " + "; ".join(
        f"{c} " + ", ".join(number(statistics.mean(macro_em(c, o) for o in group)) for group in groups) for c in CONDITIONS))
    dc = "Dublin Core Terms"
    print("% Dublin Core Terms with dcterms:Collection counted as correct: " + "; ".join(
        f"{c} Dublin Core Terms {number(macro_f1(c, dc, namespace_counts))}, popular "
        + number(statistics.mean(macro_f1(c, o, namespace_counts if o == dc else ts_counts) for o in TIERS["Popular"]))
        + f", medium {number(statistics.mean(stats[o][c]['f1'] for o in TIERS['Medium']))}" for c in ["1 call", "3 calls"]))
