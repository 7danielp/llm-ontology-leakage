"""Table tab:gp-full-maki: Guided Prompting gap per ontology, task, model and format of the four open-weight models"""
from analysis.common import FORMATS, MAKI, full_rows, gap_entry, read_gaps

gaps = read_gaps()  # (ontology, task, model, format) -> (gap, significant)
columns = [(m, f) for m in MAKI for f in FORMATS]
print(full_rows(lambda o, t, column: gap_entry(gaps[(o, t, *column)]), columns))
