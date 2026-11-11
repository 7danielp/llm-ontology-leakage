"""Table tab:ts-full-luna (--names: tab:ts-full-luna-names): TS-Guessing micro F1 of gpt-5.6-luna per run"""
import sys

from analysis.common import FORMATS, ROOT, full_rows, number, read_matrix
from analysis.ts_filtered import matrix

if "--names" in sys.argv:  # main run without the name-inferable questions
    columns = [(matrix(True), "gpt-5.6-luna", f) for f in FORMATS]
else:  # main run, then the sampled questions without web search, with one and with up to three web calls
    full = read_matrix("ts_matrix_f1.csv")
    web_1 = read_matrix("ts_matrix_f1.csv", ROOT / "results" / "sampled-web-search-1call")
    web_3 = read_matrix("ts_matrix_f1.csv", ROOT / "results" / "sampled-web-search-3calls")
    blocks = [(full, "gpt-5.6-luna"), (web_1, "gpt-5.6-luna sample-reference"),  # model names as in the CSV columns
              (web_1, "gpt-5.6-luna+web sample-web"), (web_3, "gpt-5.6-luna+web3 sample-web")]
    columns = [(source, model, f) for source, model in blocks for f in FORMATS]


def entry(o: str, t: str, column: tuple[dict, str, str]) -> str:
    """Run F1 of column = (run F1 per (ontology, task, model, format), model, format), -- where no question is left"""
    source, model, f = column
    value = source[(o, t, model, f)]
    return "--" if value is None else number(value)


print(full_rows(entry, columns))
