"""Numbers of Sections sec:results-web, sec:results-web-sources and sec:limitations: gpt-5.6-luna with web search"""
import collections
import re
import statistics

from analysis.common import FORMATS, ONTOLOGIES, SHORT, TIERS, number
from analysis.web import CONDITIONS, web_records

WEB = ["1 call", "3 calls"]  # the conditions with web search
ARMS = {"ts-guessing": [""], "guided-prompting": ["_normal", "_guided"]}  # field suffixes of the answers of each method
PUBLISHER = {"FOAF": "xmlns.com", "Dublin Core Terms": "dublincore.org", "schema.org": "schema.org", "GoodRelations": "heppnetz.de",
             "NEPOMUK File Ontology": "semanticdesktop.org", "W3C Organization Ontology": "w3.org", "Cinelab": "advene.org",
             "EP-Plan": "trustlens.github.io", "Urban IoT Electric Mobility": "comune-milano.github.io"}
GROUPED = 0.03  # websites below this share of the documents of an ontology form its grey segment in Figure fig:web-sources
# second level labels under which a registrable domain has three labels
SHARED_SUFFIXES = {"github.io", "gitlab.io", "readthedocs.io", "blogspot.com", "wordpress.com", "appspot.com", "pages.dev",
                   "herokuapp.com", "netlify.app", "vercel.app"}
COUNTRY_SECOND_LEVEL = {"ac", "co", "com", "edu", "gov", "org", "net", "go", "or", "ne", "nic", "gc", "res"}

# {(method, condition, ontology): {(task, format): records}}
records = {(m, c, o): web_records(m, c, o) for m in ARMS for c in CONDITIONS for o in ONTOLOGIES}


def answers(c: str, ontologies: list[str] = ONTOLOGIES, arms: tuple[str, ...] = ("", "_normal", "_guided"),
            formats: list[str] = FORMATS):
    """(ontology, task, format, record, field suffix) of every answer of a condition"""
    for o in ontologies:
        for m, suffixes in ARMS.items():
            for (t, f), rs in records[(m, c, o)].items():
                for r in rs:
                    for s in suffixes:
                        if s in arms and f in formats:
                            yield o, t, f, r, s


def calls(r: dict, s: str) -> list[dict]:
    """Completed tool calls of one answer"""
    return [a for a in r.get(f"web_search_actions{s}") or [] if a["status"] == "completed"]


def plain_mean(c: str, o: str, value) -> float:
    """Mean of value over the plain answers of each task, then over the tasks"""
    runs = records[("guided-prompting", c, o)]
    return statistics.mean(statistics.mean(value(r) for r in rs) for (_, f), rs in runs.items() if f == "plain")


def address(kind: str, result: dict) -> str:
    """Address of a returned document, for an opened page the redirect target in its header line"""
    redirect = re.search(r"Redirected to URL: (\S+?);", str(result.get("snippet") or "").split("\n", 1)[0])
    url = redirect.group(1) if kind != "search" and redirect else result.get("url") or ""
    return re.sub(r"[?#].*$", "", url)


def text(kind: str, result: dict) -> str:
    """Text of a returned document, for an opened page without its header line and without a notice that nothing was found"""
    snippet = str(result.get("snippet") or "")
    if kind == "search":
        return snippet
    body = snippet.split("\n", 1)[1] if "\n" in snippet else ""
    return "" if body.startswith("No matching text found") else body


def website(url: str) -> str:
    """Registrable domain, en.wikipedia.org gives wikipedia.org and trustlens.github.io stays itself"""
    labels = re.sub(r"^https?://", "", url).split("/")[0].split(":")[0].lower().split(".")
    if len(labels) > 2 and (".".join(labels[-2:]) in SHARED_SUFFIXES or (len(labels[-1]) == 2 and labels[-2] in COUNTRY_SECOND_LEVEL)):
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def documents(r: dict, s: str):
    """(address, text) of every document returned to one answer"""
    for a in calls(r, s):
        for x in a.get("results") or []:
            body = text(a["type"], x)
            if a["type"] == "search" or body.strip():
                yield address(a["type"], x), body


def documents_per_website(c: str = "3 calls") -> dict[str, collections.Counter]:
    """Returned documents per ontology and website"""
    sites = collections.defaultdict(collections.Counter)
    for o, _, _, r, s in answers(c):
        for url, _ in documents(r, s):
            sites[o][website(url)] += 1
    return sites


if __name__ == "__main__":
    print("sec:results-web")
    questions = {(o, t, r["key"]) for o, t, _, r, _ in answers("no web", arms=("",))}
    for (_, _, o), runs in records.items():  # every condition asks the same questions in every format and method
        asked = {(t, f, r["key"]) for (t, f), rs in runs.items() for r in rs}
        assert asked == {(t, f, k) for x, t, k in questions if x == o for f in FORMATS}
    per_task = collections.Counter((o, t) for o, t, _ in questions)
    print(f"sampled questions: {len(questions)}, at most {max(per_task.values())} per ontology and task, "
          f"{len(questions) * len(FORMATS):,} TS-Guessing answers per condition")
    with_call = {(c, f): sum(bool(calls(r, s)) for *_, r, s in answers(c, arms=("_normal",), formats=[f])) for c in WEB for f in FORMATS}
    print("normal answers of Guided Prompting with a tool call: "
          + ", ".join(f"{c} " + ", ".join(f"{f} {with_call[(c, f)]}" for f in FORMATS) for c in WEB))
    for arm in ("guided", "normal"):
        medium = [statistics.mean(plain_mean(c, o, lambda r: r[f"sim_{arm}"]["wup"]) for o in TIERS["Medium"]) for c in CONDITIONS]
        print(f"medium tier, plain format, mean Wu and Palmer similarity of the {arm} answers, no web, 1 call, 3 calls: "
              + " ".join(number(x) for x in medium))

    print("sec:results-web-sources")
    sites = documents_per_website()  # run with up to three calls
    found = collections.Counter()  # documents that name the address of a synthetic ontology
    namespaces = {o: "example.org/" + o.lower().replace(" ", "-") for o in TIERS["Synthetic"]}
    for *_, r, s in answers("3 calls"):
        for url, body in documents(r, s):
            for x, ns in namespaces.items():
                found[x] += ns in url or ns in body
    n_documents = {o: sum(sites[o].values()) for o in ONTOLOGIES}
    per_tier = {tier: sum(n_documents[o] for o in os) for tier, os in TIERS.items()}
    print("documents: " + ", ".join(f"{tier} {n:,}" for tier, n in per_tier.items()) + f", all {sum(per_tier.values()):,}")
    print("share of the documents from the publishing websites: " + ", ".join(
        f"{tier} {sum(sites[o][PUBLISHER[o]] for o in os) / per_tier[tier]:.0%}" for tier, os in list(TIERS.items())[:3]))
    print("share of the documents of an ontology from its publishing website: " + ", ".join(
        f"{SHORT.get(o, o)} {w} {sites[o][w] / n_documents[o]:.0%}" for o, w in PUBLISHER.items()))
    print("websites: " + ", ".join(f"{SHORT.get(o, o)} {len(sites[o])}" for o in TIERS["Unpopular"] + TIERS["Synthetic"]))
    print("share of the documents in the grey segment: " + ", ".join(
        f"{o} {sum(k for k in sites[o].values() if k / n_documents[o] < GROUPED) / n_documents[o]:.1%}" for o in TIERS["Synthetic"]))
    print("documents naming the address of a synthetic ontology: " + ", ".join(f"{x} {n}" for x, n in found.items()))

    print("sec:limitations")
    tokens = collections.defaultdict(list)  # reasoning tokens of each answer per (condition, with a tool call)
    for c in WEB:
        for *_, r, s in answers(c):
            tokens[(c, bool(calls(r, s)))].append(r[f"usage{s}"]["reasoning_tokens"] or 0)
    for has_call, label in ((True, "with"), (False, "without")):
        print(f"reasoning tokens {label} a tool call: " + ", ".join(
            f"{c} {min(v)} to {max(v)} (mean {statistics.mean(v):.2f})" for c in WEB for v in [tokens[(c, has_call)]]))
