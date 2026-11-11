"""Numbers of Sections sec:results-web and sec:results-web-sources: plain Guided Prompting answers and the Urban IoT page"""
import statistics

from analysis.common import ONTOLOGIES, TASKS, TIERS
from analysis.web import completed, web_records


def plain_records(c: str, o: str) -> dict[str, dict[str, dict]]:
    """Plain Guided Prompting records per task and question"""
    runs = web_records("guided-prompting", c, o)
    return {t: {r["key"]: r for r in runs[(t, "plain")]} for t in TASKS}


plain = {(c, o): plain_records(c, o) for c in ["no web", "1 call"] for o in ONTOLOGIES}


def mean_similarity(c: str, ontologies: list[str], arm: str) -> float:
    """Mean Wu and Palmer similarity of the guided or normal answers, over the answers of a task, the tasks and the ontologies"""
    return statistics.mean(statistics.mean(statistics.mean(r[f"sim_{arm}"]["wup"] for r in task.values())
                                           for task in plain[(c, o)].values()) for o in ontologies)


print("sec:results-web")
for arm in ["guided", "normal"]:
    print(f"popular tier, Wu and Palmer of the {arm} answers, no web and 1 call: "
          + " ".join(f"{mean_similarity(c, TIERS['Popular'], arm):.4f}" for c in ["no web", "1 call"]))
# the same question without web search and with one call
pairs = [(plain[("no web", o)][t][k], r) for o in ONTOLOGIES for t in TASKS for k, r in plain[("1 call", o)][t].items()]
changed = sum(a["raw_normal"].strip() != b["raw_normal"].strip() for a, b in pairs)
with_tool = sum(bool(completed(r.get("web_search_actions_normal"))) for pair in pairs for r in pair)
print(f"normal answers with a changed text, no web to 1 call: {changed} of {len(pairs)}, with a tool call {with_tool}")

print("sec:results-web-sources")
record = next(r for r in web_records("ts-guessing", "3 calls", "Urban IoT Electric Mobility")[("domain", "full")]
              if r["key"] == "http://www.w3id.org/urban-iot/electric#floorLevel")
page = str(record["web_search_actions"][1]["results"][0].get("snippet") or "")  # page of the second call, a header line first
print("Urban IoT page text, domain of floorLevel, full format, 3 calls: "
      + " | ".join(line.strip() for line in page.split("\n")[1:] if line.strip())[:1500])
