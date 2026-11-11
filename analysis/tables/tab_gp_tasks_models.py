"""Table tab:gp-tasks-models: Guided Prompting tier means per task and model in the plain format"""
from analysis.common import MODELS, TASKS, TIERS, number
from analysis.tables.tab_tasks_methods import per_model

keeps = {}  # task -> models with popular > medium > unpopular
for task in TASKS:
    tier_means = per_model("GP", task)  # model -> tier means in the order of TIERS
    print(rf"\multicolumn{{6}}{{l}}{{\textbf{{{task.capitalize()}}}}} \\")
    for i, tier in enumerate(TIERS):
        print(rf"\quad {tier} & " + " & ".join(number(tier_means[m][i], True) for m in MODELS) + r" \\")
    print(r"\addlinespace")
    keeps[task] = sum(tier_means[m][0] > tier_means[m][1] > tier_means[m][2] for m in MODELS)
print("% models with popular > medium > unpopular (of 5): " + ", ".join(f"{t} {n}" for t, n in keeps.items()))
