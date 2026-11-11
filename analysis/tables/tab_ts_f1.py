"""Table tab:ts-f1: TS-Guessing micro F1 per ontology and model with all questions"""
import statistics

from analysis.common import FORMATS, MODELS, ONTOLOGIES, TASKS, read_matrix, tier_rows

run_f1 = read_matrix("ts_matrix_f1.csv")  # {(ontology, task, model, format): micro F1}
# mean over the four tasks and three formats
values = {o: [statistics.mean(run_f1[(o, t, m, f)] for t in TASKS for f in FORMATS) for m in MODELS] for o in ONTOLOGIES}

print(tier_rows(values))
