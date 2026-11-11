"""Table tab:ts-full-maki (--names: tab:ts-full-maki-names): TS-Guessing micro F1 of the open-weight models per run"""
import sys

from analysis.common import FORMATS, MAKI, full_rows, number, read_matrix
from analysis.ts_filtered import matrix

# --names: without the name-inferable questions, None where the filter leaves no question
cells = matrix(True) if "--names" in sys.argv else read_matrix("ts_matrix_f1.csv")


def entry(o: str, t: str, column: tuple[str, str]) -> str:
    """Run F1 of column = (model, format), -- where no question is left"""
    value = cells[(o, t, *column)]
    return "--" if value is None else number(value)


print(full_rows(entry, [(m, f) for m in MAKI for f in FORMATS]))
