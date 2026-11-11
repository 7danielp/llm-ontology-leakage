"""Data file of the project page, docs/data/web_search_sources.csv: every page that the web search returned in the run
with up to three calls, with its ontology, tier, website and counts"""
import collections
import csv
import re

from analysis.common import ROOT, TIERS
from analysis.numbers.web_numbers import answers, calls, text, website

TABLE = ROOT / "docs" / "data" / "web_search_sources.csv"
COLUMNS = ["ontology", "tier", "domain", "page", "count", "search results", "opened pages"]
PERSONAL = re.compile(r"linkedin\.com/(in|pub|posts)/", re.I)  # pages of private persons, listed without their address
TIER_ORDER = [t.lower() for t in TIERS]
TIER = {o: tier.lower() for tier, ontologies in TIERS.items() for o in ontologies}


def page(kind: str, result: dict) -> str:
    """Address of a returned document without its fragment, for an opened page the redirect target in its header line"""
    redirect = re.search(r"Redirected to URL: (\S+?);", str(result.get("snippet") or "").split("\n", 1)[0])
    url = redirect.group(1) if kind != "search" and redirect else result.get("url") or ""
    return url.split("#")[0]


def row(o: str, w: str, name: str, c: collections.Counter) -> dict:
    return {"ontology": o, "tier": TIER[o], "domain": w, "page": name, "count": c["search results"] + c["opened pages"],
            "search results": c["search results"], "opened pages": c["opened pages"]}


counts = collections.defaultdict(collections.Counter)  # (ontology, website, page) -> search results and opened pages
for o, _, _, r, s in answers("3 calls"):
    for a in calls(r, s):
        for x in a.get("results") or []:
            if a["type"] == "search":
                kind = "search results"
            elif text(a["type"], x).strip():  # an opened page without any text returned nothing
                kind = "opened pages"
            else:
                continue
            url = page(a["type"], x)
            counts[(o, website(url), url)][kind] += 1

rows, personal = [], collections.defaultdict(collections.Counter)
for (o, w, url), c in counts.items():
    if PERSONAL.search(url):
        personal[(o, w)].update(c)
        personal[(o, w)]["pages"] += 1
    else:
        rows.append(row(o, w, url, c))
rows += [row(o, w, f"({c['pages']} personal LinkedIn pages, not listed)", c) for (o, w), c in personal.items()]
site_total = collections.Counter()
for r in rows:
    site_total[(r["ontology"], r["domain"])] += r["count"]
rows.sort(key=lambda r: (TIER_ORDER.index(r["tier"]), r["ontology"], -site_total[(r["ontology"], r["domain"])], r["domain"],
                         -r["count"], r["page"]))
with TABLE.open("w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=COLUMNS, lineterminator="\n")  # line ends as in the repository
    writer.writeheader()
    writer.writerows(rows)
print(f"{TABLE.relative_to(ROOT)}: {len(rows):,} pages, {sum(r['count'] for r in rows):,} documents")
