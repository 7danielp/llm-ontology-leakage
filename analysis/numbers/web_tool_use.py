"""Numbers of Section sec:results-web: TS-Guessing F1 of the answers with and without a tool call, run with up to three calls"""
import statistics

from analysis.common import ONTOLOGIES, TASKS, number
from analysis.web import completed, f1, ts_counts, web_records

# (tp, fp, fn) and completed tool calls of every TS-Guessing answer by (ontology, task, format, question)
answers = {c: {(o, t, f, r["key"]): (ts_counts(r), completed(r.get("web_search_actions")))
               for o in ONTOLOGIES for (t, f), rs in web_records("ts-guessing", c, o).items() for r in rs}
           for c in ["no web", "3 calls"]}


def group_f1(condition: str, keys: list[tuple]) -> float:
    """Micro F1 per task over the answers of keys, pooled over ontologies and formats, then the mean over the tasks"""
    per_task = []
    for t in TASKS:
        counts = [answers[condition][k][0] for k in keys if k[1] == t]
        if counts:
            per_task.append(f1(*map(sum, zip(*counts))))
    return float(statistics.mean(per_task))


with_call = [k for k, (_, calls) in answers["3 calls"].items() if calls > 0]
without = [k for k, (_, calls) in answers["3 calls"].items() if calls == 0]
print(f"All, 3 calls: with a tool call {len(with_call):,}, {number(group_f1('no web', with_call))} to "
      f"{number(group_f1('3 calls', with_call))}; without {len(without):,}, {number(group_f1('no web', without))} to "
      f"{number(group_f1('3 calls', without))}")
