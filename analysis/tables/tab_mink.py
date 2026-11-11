"""Table tab:mink: Min-20% score per ontology and open-weight model, mean over the formats"""
import statistics

from analysis.common import FORMATS, MAKI, ONTOLOGIES, read_matrix, tier_rows

scores = read_matrix("mink_matrix.csv")
# row all = mean over all blocks of the three tasks
values = {o: [statistics.mean(scores[(o, "all", m, f)] for f in FORMATS) for m in MAKI] for o in ONTOLOGIES}
print(tier_rows(values))
