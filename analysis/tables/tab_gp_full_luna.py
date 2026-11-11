"""Table tab:gp-full-luna: Guided Prompting gap of gpt-5.6-luna per ontology, task and format, without and with web search"""
from analysis.common import FORMATS, ROOT, full_rows, gap_entry, read_gaps

full = read_gaps()
web_1 = read_gaps(ROOT / "results" / "sampled-web-search-1call")
web_3 = read_gaps(ROOT / "results" / "sampled-web-search-3calls")

# all questions, then the sampled questions without web search, with one and with up to three tool calls
SOURCES = [(full, "gpt-5.6-luna"), (web_1, "gpt-5.6-luna"), (web_1, "gpt-5.6-luna+web"), (web_3, "gpt-5.6-luna+web3")]
COLUMNS = [(gaps, model, f) for gaps, model in SOURCES for f in FORMATS]


def entry(ontology: str, task: str, column: tuple) -> str:
    gaps, model, fmt = column
    return gap_entry(gaps[(ontology, task, model, fmt)])


print(full_rows(entry, COLUMNS))
