"""Table tab:gp-plain: Guided Prompting gap in the plain format per ontology and model, mean over the four tasks"""
import statistics

from analysis.common import MODELS, ONTOLOGIES, SHORT, TASKS, TIERS, number, read_aggregate, read_gaps

gap = {(r["ontology"], r["task"], r["model"], r["id_format"]): float(r["gap"])
       for r in read_aggregate("gp_aggregate.csv") if r["measure"] == "wup" and r["segment"] == "all"}
significant = {run: is_significant for run, (_, is_significant) in read_gaps().items()}

# per ontology one entry per model, in the order of MODELS
values = {o: [statistics.mean(gap[(o, t, m, "plain")] for t in TASKS) for m in MODELS] for o in ONTOLOGIES}
count = {o: [sum(significant[(o, t, m, "plain")] for t in TASKS) for m in MODELS] for o in ONTOLOGIES}  # significant tasks


def entry(mean_gap: float, significant_tasks: int) -> str:
    """Signed gap, bold if significant in all four tasks"""
    text = number(mean_gap, True)
    return rf"\textbf{{{text}}}" if significant_tasks == len(TASKS) else text


for tier, ontologies in TIERS.items():
    tier_means = [statistics.mean(values[o][i] for o in ontologies) for i in range(len(MODELS))]
    print(rf"\rowcolor{{tierrow}}\textbf{{{tier}}} & " + " & ".join(number(v, True) for v in tier_means) + r" \\")
    for o in ontologies:
        print(rf"\quad {SHORT.get(o, o)} & " + " & ".join(entry(v, n) for v, n in zip(values[o], count[o])) + r" \\")
