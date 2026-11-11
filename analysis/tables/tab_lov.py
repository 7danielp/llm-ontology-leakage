"""Table tab:lov: occurrences and rank in LOV of the nine real ontologies"""
import csv

from analysis.common import ROOT, SHORT, TIERS

# namespace of each ontology in the LOV query (column s)
NAMESPACES = {
    "FOAF": "http://xmlns.com/foaf/0.1/",
    "Dublin Core Terms": "http://purl.org/dc/terms/",
    "schema.org": "http://schema.org/",
    "GoodRelations": "http://purl.org/goodrelations/v1",
    "NEPOMUK File Ontology": "http://www.semanticdesktop.org/ontologies/2007/03/22/nfo",
    "W3C Organization Ontology": "http://www.w3.org/ns/org#",
    "Cinelab": "http://advene.org/ns/cinelab/ld",
    "EP-Plan": "https://w3id.org/ep-plan",
    "Urban IoT Electric Mobility": "http://www.w3id.org/urban-iot/electric",
}

with open(ROOT / "ressources" / "ontologies" / "lov_query.csv", newline="", encoding="utf-8") as f:
    occurrences = {row["s"]: int(row["c"]) for row in csv.DictReader(f)}

for tier in ["Popular", "Medium", "Unpopular"]:  # the synthetic ontologies are not in LOV
    print(rf"\rowcolor{{tierrow}}\multicolumn{{3}}{{l}}{{\textbf{{{tier}}}}} \\")
    for o in TIERS[tier]:
        count = occurrences[NAMESPACES[o]]
        rank = 1 + sum(other > count for other in occurrences.values())  # equal counts share a rank
        print(rf"\quad {SHORT.get(o, o)} & {count:,} & {rank} \\")
print(f"% vocabularies in the query: {len(occurrences)}, without occurrence: {sum(c == 0 for c in occurrences.values())}")
