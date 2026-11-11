"""Table tab:mink-formats: Min-20% score per open-weight model and format, mean over the ontologies"""
import statistics

from analysis.common import FORMATS, MAKI, ONTOLOGIES, number, read_matrix

score = read_matrix("mink_matrix.csv")
for model in MAKI:
    means = [statistics.mean(score[(o, "all", model, fmt)] for o in ONTOLOGIES) for fmt in FORMATS]
    print(f"{model} & " + " & ".join(number(x) for x in means) + r" \\")
