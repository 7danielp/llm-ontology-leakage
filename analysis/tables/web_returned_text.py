"""Table tab:web-returned-full and Appendix app:web-examples: text the web search returned to the TS-Guessing answers"""
import collections
import json
import re
import statistics
from typing import NamedTuple

from analysis.common import ONTOLOGIES, RESULTS, ROOT, SHORT, TASKS, TIERS, iri_name, load_records, name_words, number
from analysis.numbers.web_numbers import PUBLISHER, address, text, website
from analysis.web import WEB_3, blocked, f1, ts_counts, web_records

from llm_ontology_leakage.core.config import ONTOLOGY_PRESETS

LIMIT = 3  # tool calls allowed per answer
NAMESPACE = {p["ontology_name"]: p["ontology_namespace"] for p in ONTOLOGY_PRESETS.values()}
NFO = "NEPOMUK File Ontology"
MARKER = re.compile(r"\ue200cite\ue202(turn\d+[a-z]+\d+)\ue201")  # reference of a returned document, at the start of its text
LINK = re.compile(r"\ue200cite\ue202(\d+)\u2020([^\u2020\ue201]*)[^\ue201]*\ue201")  # a link of an opened page: its number and text
TEX = {"\\": r"\textbackslash{}", "_": r"\_", "#": r"\#", "%": r"\%", "&": r"\&", "$": r"\$", "{": r"\{", "}": r"\}",
       "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}
CALL = {"search": "search", "open_page": "page opening", "find_in_page": "search within a page"}

records = {o: web_records("ts-guessing", "3 calls", o) for o in ONTOLOGIES}  # only this run stored the returned text
n_answers = {o: sum(len(rs) for rs in records[o].values()) for o in ONTOLOGIES}


def completed_calls(r: dict) -> list[dict]:
    return [a for a in r["web_search_actions"] or [] if a["status"] == "completed"]


def documents(r: dict) -> list[tuple[dict, dict, str]]:
    """(call, document, title and text) of every document that the completed calls of an answer returned"""
    return [(a, x, str(x.get("title") or "") + "\n" + text(a["type"], x)) for a in completed_calls(r) for x in a.get("results") or []]


def page_text(x: dict) -> str | None:
    """Title and text of an opened page, None if it returned no text"""
    body = text("open_page", x)
    return (str(x.get("title") or "") + "\n" + body) if body.strip() else None


class Words:
    """Names in a text as whole words, no letter, digit or underscore directly before or after them"""

    def __init__(self, body: str, ignore_case: bool = True):
        self.ignore_case = ignore_case
        self.body = body.lower() if ignore_case else body
        self.words = set(re.findall(r"[A-Za-z0-9_]+", self.body))

    def __contains__(self, name: str) -> bool:
        name = name.lower() if self.ignore_case else name
        if re.fullmatch(r"[A-Za-z0-9_]+", name):
            return name in self.words
        return re.search(rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])", self.body) is not None  # as hasEAN_UCC-13


# one entry per answer with returned text, "both" = the text names the given entity and a gold
answers = []
for o in ONTOLOGIES:
    for (t, f), rs in records[o].items():
        for r in rs:
            docs = documents(r)
            if docs:
                words = Words("\n".join(body for *_, body in docs))
                gold = any(iri_name(g) in words for g in r["gold_iris"])
                answers.append({"ontology": o, "task": t, "format": f, "key": r["key"], "counts": ts_counts(r),
                                "both": gold and iri_name(r["given_iri"]) in words})


def selected(ontologies: list[str], key: str | None = None, value: bool = True) -> list[dict]:
    """Answers with returned text of the ontologies, if key is given only those whose key has this value"""
    return [x for x in answers if x["ontology"] in ontologies and (key is None or x[key] == value)]


def mean_share(ontologies: list[str], key: str) -> float:
    """Share of the answers with returned text for which key holds, mean of the ontologies"""
    return statistics.mean(sum(x[key] for x in selected([o])) / len(selected([o])) for o in ontologies)


def f1_text(xs: list[dict]) -> str:
    """Micro F1 per task, mean over the tasks with answers"""
    per_task = [f1(*map(sum, zip(*[x["counts"] for x in xs if x["task"] == t]))) for t in TASKS if any(x["task"] == t for x in xs)]
    return number(float(statistics.mean(per_task))) if per_task else "--"


def share_row(label: str, ontologies: list[str]) -> str:
    return (f"{label} & {sum(n_answers[o] for o in ontologies):,} & {len(selected(ontologies)):,} & "
            f"{number(mean_share(ontologies, 'both'))} & {f1_text(selected(ontologies, 'both'))} & "
            f"{f1_text(selected(ontologies, 'both', False))}" + r" \\")


class Page(NamedTuple):
    record: dict
    url: str
    lines: int | None  # total lines, None if nothing returned
    body: str | None  # title and text, None if no text
    named: bool  # the text names an entity of the ontology in any case


def entity_names(o: str) -> set[str]:
    """Names of the given and gold IRIs of all questions of o in the main run that lie in its namespace"""
    iris = set()
    for run_dir in (RESULTS / "runs" / "ts-guessing").glob(f"TS__{o.replace(' ', '-')}__*__gpt-5.6-luna__*"):
        for r in load_records(run_dir):
            iris.update([r["given_iri"], *r["gold_iris"]])
    return {iri_name(i) for i in iris if i.startswith(NAMESPACE[o])}


def has_entity(body: str | None, names: set[str]) -> bool:
    if body is None:
        return False
    words = Words(body)
    return any(n in words for n in names)


def header(result: dict) -> str:
    """First line of a returned document, for an opened page the line with its source and redirect"""
    return str(result.get("snippet") or "").split("\n", 1)[0]


def total_lines(result: dict) -> int | None:
    found = re.search(r"Total lines: (\d+)", header(result))
    return int(found.group(1)) if found else None


def publisher_pages(o: str, names: set[str]) -> list[Page]:
    """Every completed page opening of a TS-Guessing answer on the publishing website of o"""
    pages = []
    for rs in records[o].values():
        for r in rs:
            for a in completed_calls(r):
                if a["type"] != "open_page":
                    continue
                results = a.get("results") or []
                if not results and website(a.get("url") or "") == PUBLISHER[o]:
                    pages.append(Page(r, re.sub(r"[?#].*$", "", a.get("url") or ""), None, None, False))
                for x in results:
                    if website(address("open_page", x)) == PUBLISHER[o]:
                        body = page_text(x)
                        pages.append(Page(r, address("open_page", x), total_lines(x), body, has_entity(body, names)))
    return pages


def opening_counts(pages: list[Page]) -> str:
    named = collections.defaultdict(bool)  # per answer: one of its pages names an entity
    for p in pages:
        named[(p.record["task"], p.record["key"], p.record["prompt"])] |= p.named
    return (f"{len(pages)}, no text {sum(p.body is None for p in pages)}, without entity name "
            f"{sum(p.body is not None and not p.named for p in pages)}; answers {len(named)}, of them without entity name "
            f"{sum(not v for v in named.values())}")


def page_list(pages: list[Page], names: set[str]) -> str:
    """Openings of each page and the entity names on it as written"""
    found = {}
    for p in pages:
        if p.body is not None and (p.url, p.lines) not in found:
            words = Words(p.body, False)
            found[(p.url, p.lines)] = (sum(n in words for n in names), sum(n in words for n in names if len(name_words(n)) > 1))
    entries = []
    for (url, lines), k in collections.Counter((p.url, p.lines) for p in pages).most_common():
        if (url, lines) in found:
            n, compound = found[(url, lines)]
            entries.append(f"{url} ({lines} lines): openings {k}, entity names {n} of {len(names)}, compound {compound}")
        else:
            entries.append(f"{url} ({'nothing returned' if lines is None else f'{lines} lines, no text'}): openings {k}")
    return "; ".join(entries)


def unmarked(body: str) -> str:
    """Text without the markers of the tool (private use characters), a link keeps its text"""
    body = LINK.sub(r"\2", MARKER.sub("", body))
    return re.sub(r"[\ue000-\uf8ff]", "", body)


def marks(body: str) -> list[re.Match]:
    """The markers L0:, L1:, ... with which the tool numbers the lines of an opened page"""
    found = []
    for m in re.finditer(r"(?:(?<=\s)|^)L(\d+):", body):
        if int(m.group(1)) == len(found):
            found.append(m)
    return found


def numbered_lines(body: str) -> list[str]:
    found = marks(body)
    ends = [m.start() for m in found[1:]] + [len(body)]
    return [body[m.end():end].strip() for m, end in zip(found, ends)]


def link_on(body: str, n: int) -> tuple[str, int]:
    """Text of the link with number n on an opened page and the number of its line"""
    found = [m for m in LINK.finditer(body) if int(m.group(1)) == n]
    assert len({m.group(2) for m in found}) == 1, n
    return found[0].group(2), sum(m.start() < found[0].start() for m in marks(body)) - 1


def plain(url: str) -> str:
    """Address without scheme, www, fragment and trailing slash"""
    return re.sub(r"^(https?://)?(www\.)?", "", url).split("#")[0].rstrip("/")


def opened(x: dict) -> str | None:
    """Address that the model asked to open, None for a followed link"""
    found = re.search(r'Source: open\(\{"ref_id":"([^"]+)"', header(x))
    return found.group(1) if found and re.match(r"https?://", found.group(1)) else None


def located(o: str, t: str, f: str, key: str) -> tuple[str, int, dict]:
    """Path, line number in the file and record of one answer"""
    path = WEB_3 / "ts-guessing" / "sample-web" / f"TS__{o.replace(' ', '-')}__{t}__gpt-5.6-luna+web3__{f}" / "records.jsonl"
    lines = path.read_text(encoding="utf-8").split("\n")  # not splitlines, web snippets may hold U+2028
    hits = [(n, json.loads(line)) for n, line in enumerate(lines, 1) if line.strip() and json.loads(line)["key"] == key]
    assert len(hits) == 1, (o, t, f, key)
    return str(path.relative_to(ROOT)), *hits[0]


def contained(r: dict) -> tuple[bool, bool]:
    """Whether the returned text of an answer names a gold and the given entity"""
    words = Words("\n".join(body for *_, body in documents(r)))
    return any(iri_name(g) in words for g in r["gold_iris"]), iri_name(r["given_iri"]) in words


def escaped(s: str, breaks: bool = True) -> str:
    """LaTeX special characters escaped, with breaks a line break allowed after / and after # in an IRI, else repeated spaces kept"""
    assert s.isascii(), s
    out = []
    for k, ch in enumerate(s):
        out.append(r"\ " if not breaks and ch == " " and s[k - 1:k] == " " else TEX.get(ch, ch))
        if breaks and ((ch == "/" and s[k + 1:k + 2] not in ("/", "")) or (ch == "#" and k > 0 and s[k - 1].isalnum() and s[k + 1:k + 2].isalnum())):
            out.append(r"\allowbreak{}")
    return "".join(out)


def tt(s: str) -> str:
    return r"\texttt{" + escaped(s) + "}"


def link(s: str) -> str:
    """An address as \\url, which cannot take # or % inside a table cell"""
    assert s.isascii() and not set(s) & set("#%{}\\^~ "), s
    return r"\url{" + s + "}"


def marked(line: str, given: str | None, golds: list[str], breaks: bool = False) -> str:
    """A line escaped, the given entity marked by \\givenname and every gold by \\goldname, as whole words in any case"""
    names = {n.lower(): "given" for n in ([given] if given else [])} | {g.lower(): "gold" for g in golds}
    if not names:
        return escaped(line, breaks=breaks)
    pattern = re.compile(r"(?<![A-Za-z0-9_])(" + "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True)) + r")(?![A-Za-z0-9_])", re.I)
    out, at = [], 0
    for m in pattern.finditer(line):
        out.append(escaped(line[at:m.start()], breaks=breaks))
        word = escaped(m.group(1), breaks=False)
        out.append((r"\givenname{" if names[m.group(1).lower()] == "given" else r"\goldname{") + word + "}")
        at = m.end()
    out.append(escaped(line[at:], breaks=breaks))
    return "".join(out)


def names_of(r: dict) -> tuple[str, list[str]]:
    return iri_name(r["given_iri"]), [iri_name(g) for g in r["gold_iris"]]


def ttm(s: str, r: dict) -> str:
    return r"\texttt{" + marked(s, *names_of(r), breaks=True) + "}"


def quoted(lines: list[str], given: str | None = None, golds: list[str] = ()) -> str:
    """Lines of returned text in typewriter type, one per line, every space kept"""
    shown = [marked(line, given, list(golds)) if line else r"\mbox{}" for line in lines]
    return r"\par\smallskip{\ttfamily " + r"\newline ".join(shown) + r"\par}\vspace{2pt}"


def axiom(r: dict) -> str:
    """Masked axiom of the prompt, the placeholder bound to the word before it"""
    line = r["prompt"].split("\n")[1]
    assert line.endswith(" ___"), line
    return ttm(line, r).replace(r" \_\_\_}", r"~\_\_\_}")


def call_rows(r: dict) -> list[tuple[str, str]]:
    """(field, value) per tool call of an answer: what the call asked for and what came back"""
    rows, views = [], {}  # views: reference of a returned page to the number of its call and the page
    for k, a in enumerate(r["web_search_actions"] or [], 1):
        results = a.get("results") or []
        if a["status"] != "completed":
            assert k == LIMIT + 1 and not results
            rows.append((f"Tool call {k}", f"{CALL[a['type']]} beyond the limit of three calls, blocked by the interface"))
        elif a["type"] == "search":
            sites = {website(address("search", x)) for x in results}
            # a site: filter with a path under which no result lies
            paths = [p for q in a.get("queries") or [] for p in re.findall(r"site:(\S+/\S+)", q)]
            outside = [p for p in paths if not any(plain(address("search", x)).startswith(plain(p)) for x in results)]
            rows.append((f"Tool call {k}", f"search for {ttm('; '.join(a.get('queries') or []), r)}, {len(results)}~results"
                         + (f", all from {tt(sites.pop())}" if len(sites) == 1 else "") + "".join(f", none under {tt(plain(p))}" for p in outside)))
        else:
            assert a["type"] == "open_page" and len(results) == 1
            x = results[0]
            views[MARKER.match(str(x.get("snippet") or "")).group(1)] = (k, x)
            asked, final = opened(x), address(a["type"], x)
            if asked:
                step = f"opened {link(asked)}"
            else:  # a link of an earlier page, named as written on that page
                source = re.search(r'Source: click\(\{"ref_id":"([^"]+)","id":(\d+)', header(x))
                k_page, x_page = views[source.group(1)]
                asked, at = link_on(text("open_page", x_page), int(source.group(2)))
                assert re.match(r"https?://", asked) and plain(asked) == plain(x.get("url") or "")
                step = f"followed the link {link(asked)} in L{at} of the page of call {k_page}"
            rows.append((f"Tool call {k}", step + (f", redirected to {link(final)}" if plain(final) != plain(asked) else "")
                         + f", a~page~of~{total_lines(x)}~lines"))
    return rows


def answer_rows(r: dict) -> list[tuple[str, str]]:
    return [("Answer", ttm(r["raw_output"].strip(), r)), ("Exact match", "yes" if r["strict_match"] else "no")]


def returned(rank: int, results: list, url: str) -> str:
    return f"result {rank} of {len(results)}, {link(url)}"


def head(o: str, t: str, f: str, path: str, line: int) -> str:
    """Line above the table, the path may break only after its folders"""
    folder, run, file = path.rsplit("/", 2)
    return (f"TS-Guessing, {SHORT.get(o, o)}, {t} task, gpt-5.6-luna with up to three web tool calls, {f} format. Full record in "
            f"\\url{{{folder}/}}\\allowbreak\\url{{{run}/}}\\allowbreak\\mbox{{\\url{{{file}}}, line~{line}}}.")


def example(title: str, label: str, head_line: str, rows: list[tuple[str, str]]) -> None:
    print(f"\\example{{{title}}}{{{label}}}%\n\\begin{{minipage}}{{\\linewidth}}\\raggedright\n{head_line}\\par\\smallskip")
    print("{\\small\\begin{tabularx}{\\linewidth}{@{}l>{\\raggedright\\arraybackslash}X@{}}\n\\toprule")
    for field, value in rows:
        print(f"{field} & {value} \\\\")
    print("\\bottomrule\n\\end{tabularx}}\n\\end{minipage}\\par\\smallskip")


def nfo_example() -> None:
    """Example ex:web-nfo: the entry of height in the first search result, from its heading to the next heading"""
    path, line, record = located(NFO, "domain", "prefix", "http://www.semanticdesktop.org/ontologies/2007/03/22/nfo#height")
    (call,) = record["web_search_actions"]
    result = call["results"][0]
    url = address("search", result)
    assert record["strict_match"] and website(url) == PUBLISHER[NFO]
    lines = (str(result.get("title") or "") + "\n" + text("search", result)).split("\n")
    first = next(k for k, x in enumerate(lines) if re.fullmatch(r"#+ " + re.escape(iri_name(record["given_iri"])), unmarked(x)))
    end = next(k for k in range(first + 1, len(lines)) if lines[k].startswith("#"))
    while not lines[end - 1].strip():
        end -= 1
    shown = [unmarked(x) for x in lines[first:end]]
    whole, joined = unmarked(text("search", result)), "\n".join(shown)
    assert whole[:whole.index(joined)].strip() and whole[whole.index(joined) + len(joined):].strip()  # text left out before and after
    assert [" ".join(x.split()) for x in shown if x.startswith(("#", "Domain"))] == ["### height", "Domain | nfo:Visual"]
    rows = [("Masked axiom", axiom(record)), ("Gold", ", ".join(ttm(g, record) for g in record["gold"])), *call_rows(record),
            ("Returned text", returned(1, call["results"], url) + quoted(["[...]", *shown, "[...]"], *names_of(record))),
            *answer_rows(record)]
    example("Search result that states the axiom", "ex:web-nfo", head(NFO, "domain", "prefix", path, line), rows)


def goodrelations_example() -> None:
    """Example ex:web-goodrelations: the answer copies the first list of properties of the search result"""
    path, line, record = located("GoodRelations", "property", "plain", "http://purl.org/goodrelations/v1#ProductOrService")
    (call,) = record["web_search_actions"]
    result = call["results"][0]
    lines = [x.rstrip() for x in unmarked(text("search", result)).split("\n")]
    prefix = "Properties (rdfs:domain) : "
    lists = [(k, x) for k, x in enumerate(lines) if prefix in x]
    listed = [[n.removeprefix("gr:") for n in x.split(prefix, 1)[1].split()] for _, x in lists]
    heading = lines.index("### gr:ProductOrService (rdf:type owl:Class)")
    gold_list = next(k for k, _ in lists if k > heading)
    # a list of 27, then the gold list of 22 under the heading of the given class, later the list of 27 again
    assert [len(n) for n in listed] == [27, 22, 27] and listed[0] == listed[2]
    assert lists[0][0] < heading < gold_list == lists[1][0] < lists[2][0]
    assert sorted(listed[1]) == sorted(record["gold"]) and record["parsed"] == listed[0]
    extra = [n for n in listed[0] if n not in record["gold"]]
    tp, fp, fn = ts_counts(record)
    assert not record["strict_match"] and website(result["url"]) == PUBLISHER["GoodRelations"]
    tokens = lines[gold_list].split(prefix, 1)[1].split()
    assert lines[gold_list] == prefix + " ".join(tokens)
    start = lists[0][1]
    shown = ["[...] " + start[start.index(prefix):], lines[heading], "[...]", prefix + " ".join(tokens[:2]) + " [...] " + " ".join(tokens[-2:]), "[...]"]
    masked = record["prompt"].split("\n")[1]
    rows = [("Masked axiom", ttm(masked, record).replace(r"\_\_\_ ", r"\_\_\_~")),
            ("Gold", f"the 22 properties of the list under the heading {ttm('gr:ProductOrService', record)}"), *call_rows(record),
            ("Returned text", returned(1, call["results"], result["url"]) + quoted(shown, *names_of(record))),
            ("Answer", "the 27 properties of the first list, the 22 gold properties and " + ", ".join(tt(n) for n in extra[:-1]) + f" and {tt(extra[-1])}"),
            ("Exact match", "no"), ("F1 score", number(float(f1(tp, fp, fn))))]
    example("Answer that copies a list of properties", "ex:web-goodrelations", head("GoodRelations", "property", "plain", path, line), rows)
    print(f"% ex:web-goodrelations: lists of {', '.join(str(len(n)) for n in listed)} properties in lines "
          f"{', '.join(str(k) for k, _ in lists)} of the search result; tp {tp}, fp {fp}, fn {fn}")


def schema_example() -> None:
    """Example ex:web-schema: the answer copies the properties that Clip inherits"""
    path, line, record = located("schema.org", "property", "plain", "http://schema.org/Clip")
    (call,) = record["web_search_actions"]
    rank, result = next((k, x) for k, x in enumerate(call["results"], 1) if x.get("url") == "https://schema.org/Clip")
    lines = [x.rstrip() for x in unmarked(text("search", result)).split("\n")]
    heads = [k for k, x in enumerate(lines) if x.startswith("Properties from ")]
    end = next(k for k, x in enumerate(lines) if x.startswith("Property  | On Types"))
    sections = {lines[a]: re.findall(r"` (\w+)`", "\n".join(lines[a:b])) for a, b in zip(heads, heads[1:] + [end])}
    assert list(sections) == ["Properties from Clip", "Properties from CreativeWork", "Properties from Thing"]
    assert sorted(sections["Properties from Clip"]) == sorted(record["gold"])
    listed = [n for v in sections.values() for n in v]
    extra = [n for n in record["parsed"] if n not in listed]
    assert len(record["parsed"]) == 96 and set(listed) <= set(record["parsed"]) and extra == ["offer"]
    tp, fp, fn = ts_counts(record)
    assert not record["strict_match"] and website(result["url"]) == PUBLISHER["schema.org"]
    chain = lines.index("Thing > CreativeWork > Clip")
    own_rows = [x for x in lines[heads[0]:heads[1]] if re.match(r"` \w+`", x)]
    assert [re.match(r"` (\w+)`", x).group(1) for x in own_rows] == sections["Properties from Clip"]
    own_names = [x[:x.index("`", 2) + 1] + " [...]" for x in own_rows]  # the name of each row, the rest left out
    shown = ["[...]", lines[chain], "[...]", lines[heads[0]], "[...]", *own_names[:3], "[...]", lines[heads[1]], "[...]",
             lines[heads[2]], "[...]"]
    masked = record["prompt"].split("\n")[1]
    rows = [("Masked axiom", ttm(masked, record).replace(r"\_\_\_ ", r"\_\_\_~")),
            ("Gold", f"the 9 properties under the heading Properties from {marked('Clip', *names_of(record))}"), *call_rows(record),
            ("Returned text", returned(rank, call["results"], result["url"]) + quoted(shown, *names_of(record))),
            ("Answer", f"96 properties, the {len(listed)} listed under the three headings and {tt(extra[0])}"),
            ("Exact match", "no"), ("F1 score", number(float(f1(tp, fp, fn))))]
    example("Answer that copies inherited properties", "ex:web-schema", head("schema.org", "property", "plain", path, line), rows)
    print(f"% ex:web-schema: properties from Clip, CreativeWork and Thing {', '.join(str(len(v)) for v in sections.values())}; "
          f"tp {tp}, fp {fp}, fn {fn}")


def urban_iot_example() -> None:
    """Example ex:web-urbaniot: a page of the publishing website without any entity of Urban IoT"""
    o, t, f = "Urban IoT Electric Mobility", "domain", "full"
    path, line, record = located(o, t, f, "http://www.w3id.org/urban-iot/electric#floorLevel")
    assert not record["strict_match"] and contained(record) == (False, False)
    assert len(completed_calls(record)) == LIMIT and blocked(record["web_search_actions"])
    k_page, page = next((k, x) for k, a in enumerate(record["web_search_actions"], 1) if a["status"] == "completed" and a["type"] == "open_page"
                        for x in a.get("results") or [] if website(address("open_page", x)) == PUBLISHER[o])
    assert not has_entity(page_text(page), entity_names(o))
    stored = unmarked(text("open_page", page))
    lines = numbered_lines(stored)
    title = next(k for k, x in enumerate(lines) if x.startswith("#"))
    spec = lines.index("Ontology Specification")
    assert lines[spec + 1].startswith("## Acknowledgements") and len(lines) == total_lines(page) and len(lines) > spec + 2
    title_line, spec_lines = f"L{title}: {lines[title]}", [f"L{k}: {lines[k]}" for k in (spec, spec + 1)]
    assert title_line in stored and "\n".join(spec_lines) in stored and title + 1 < spec
    shown = (["[...]"] if title > 0 else []) + [title_line, "[...]", *spec_lines, "[...]"]
    rows = [("Masked axiom", axiom(record)), ("Gold", ", ".join(ttm(g, record) for g in record["gold"])), *call_rows(record),
            ("Returned text", f"the page of call {k_page}" + quoted(shown, *names_of(record))), *answer_rows(record)]
    example("Documentation page without entities", "ex:web-urbaniot", head(o, t, f, path, line), rows)


if __name__ == "__main__":
    print("% tab:web-returned-full")
    for tier, ontologies in TIERS.items():
        print(share_row(r"\rowcolor{tierrow}\textbf{" + tier + "}", ontologies))
        for o in ontologies:
            print(share_row(rf"\quad {SHORT.get(o, o)}", [o]))
    print(r"\midrule")
    print(share_row(r"\textbf{All}", ONTOLOGIES))

    print("% sec:results-web-calls")
    both = {(x["ontology"], x["task"], x["format"], x["key"]): x["both"] for x in answers}
    group = {"without given and gold": [], "with both": [], "without returned text": []}  # tool calls of the unpopular answers
    for o in TIERS["Unpopular"]:
        for (t, f), rs in records[o].items():
            for r in rs:
                b = both.get((o, t, f, r["key"]))
                group["without returned text" if b is None else "with both" if b else "without given and gold"].append(r["web_search_actions"])
    asked = {k: sum(blocked(a) for a in v) for k, v in group.items()}
    n_asked = sum(asked.values())
    print(f"% unpopular answers that asked for a fourth call: {n_asked} of {sum(len(v) for v in group.values())}, "
          f"{asked['without given and gold']} of them without given and gold ({number(asked['without given and gold'] / n_asked)}); "
          "asked among the answers " + ", ".join(f"{k} {asked[k]} of {len(v)} ({number(asked[k] / len(v))})" for k, v in group.items())
          + f", of the latter {sum(bool(a) for a in group['without returned text'])} with a tool call")

    print("% sec:results-web-sources")
    names = {o: entity_names(o) for o in TIERS["Unpopular"]}
    pages = {o: publisher_pages(o, names[o]) for o in TIERS["Unpopular"]}
    print(f"% openings on the publishing websites of the unpopular tier: {opening_counts([p for o in pages for p in pages[o]])}")
    for o in TIERS["Unpopular"]:
        print(f"% {SHORT.get(o, o)} openings on {PUBLISHER[o]}: {opening_counts(pages[o])}")
        print(f"% {SHORT.get(o, o)} pages: {page_list(pages[o], names[o])}")

    print("% app:web-examples")
    nfo_example()
    goodrelations_example()
    schema_example()
    urban_iot_example()
