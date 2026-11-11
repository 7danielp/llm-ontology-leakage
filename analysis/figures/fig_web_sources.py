"""Figure fig:web-sources: websites of the documents that the web search returned in the run with up to three calls"""
import math
import re

import matplotlib.pyplot as plt
from matplotlib.colors import to_rgb
from matplotlib.patches import Patch, Wedge

from analysis.common import FIGURES, TIERS
from analysis.numbers.web_numbers import GROUPED, PUBLISHER, documents_per_website

plt.switch_backend("Agg")  # no window, the same drawing on every computer
FIGURES.mkdir(parents=True, exist_ok=True)
NAME = "web_search_sources"
TIER_COLOUR = {"Popular": "#2b6cb0", "Medium": "#2f8a6c", "Unpopular": "#b8701a", "Synthetic": "#8456b3"}
OTHER = "#9aa3ab"
INK = "#1e293b"
HIGHLIGHT, HIGHLIGHT_LW = INK, 1.2  # outline of the publishing website, in pt
# ontology names in the middle ring
RING_NAME = {"Dublin Core Terms": "DC Terms", "NEPOMUK File Ontology": "NFO", "W3C Organization Ontology": "W3C Org",
             "Urban IoT Electric Mobility": "Urban IoT", "Waste Management": "Waste Mgmt.", "Weather Patterns": "Weather",
             "Coffee Brewing": "Coffee"}
R0, RING = 0.30, 0.23  # inner radius and ring width (tier, ontology, website)
MIN_LABEL_DEG = 1.5  # outer website labels only for slices at least this wide


def mix(colour: str, weight: float) -> tuple:
    """Colour mixed with white (weight 0 = colour, 1 = white)"""
    return tuple(c + (1 - c) * weight for c in to_rgb(colour))


def radial_text(ax, deg: float, r: float, text: str, size: float, colour, anchor: str = "center", weight: str = "normal"):
    """Text along the radius at compass angle deg (0 = top, clockwise), kept upright"""
    theta = math.radians(90 - deg)
    rot = 90 - deg
    left = 180 < deg < 360
    if left:
        rot += 180
    ha = anchor if anchor == "center" else ({"start": "right", "end": "left"}[anchor] if left else {"start": "left", "end": "right"}[anchor])
    return ax.text(r * math.cos(theta), r * math.sin(theta), text, rotation=rot, rotation_mode="anchor",
                   ha=ha, va="center", fontsize=size, color=colour, fontweight=weight)


def fit_label(ax, renderer, units_per_px, deg, r, span, text, sizes, colour):
    """Radial label in a ring, at the largest size that fits the ring width and the slice height, None if none fits"""
    def extent(size):
        probe = ax.text(0, 0, text, fontsize=size, fontweight="bold")  # unrotated, for the true text size
        bb = probe.get_window_extent(renderer)
        probe.remove()
        return bb.width * units_per_px, bb.height * units_per_px

    arc = math.radians(span) * r
    for size in sizes:
        length, height = extent(size)
        if length <= RING - 0.03 and height <= arc:
            return radial_text(ax, deg, r, text, size, colour, weight="bold")
    return None


def variants(name: str) -> list[str]:
    """Forms of a ring label, longest first: one line, two lines (space, dot or camel case), shortened with a dot"""
    out = [name]
    m = re.match(r"^(\S+) (.+)$", name) or re.match(r"^(.+?)(\.[^.]+)$", name) or re.match(r"^([A-Z]?[a-z]+)([A-Z].*)$", name)
    if m:
        out.append(m.group(1) + "\n" + m.group(2))
    if len(name) > 8:
        out.append(name[:7].rstrip(". ") + ".")
    return out


# tier -> ontology -> websites, those below GROUPED of the documents of an ontology together as one grey slice
sites = documents_per_website()
data = {"documents": sum(sum(c.values()) for c in sites.values()), "children": []}
for tier, ontologies in TIERS.items():
    ontos = []
    for o in sorted(ontologies):
        n = sum(sites[o].values())
        ranked = sorted(sites[o].items(), key=lambda x: (-x[1], x[0]))  # most documents first
        children = [{"name": w, "value": k} for w, k in ranked if k / n >= GROUPED]
        small = [k for _, k in ranked if k / n < GROUPED]
        if small:
            children.append({"name": f"{len(small)} other websites", "other": True, "value": sum(small)})
        ontos.append({"name": o, "children": children})
    data["children"].append({"name": tier, "children": ontos})
total = data["documents"]
fig, ax = plt.subplots(figsize=(7.2, 7.2))
ax.set_xlim(-1.62, 1.62)
ax.set_ylim(-1.62, 1.62)
ax.set_aspect("equal")
ax.axis("off")
fig.subplots_adjust(left=0, right=1, bottom=0, top=1)  # final axes size, so label fitting measures the real ring width
renderer = fig.canvas.get_renderer()
units_per_px = 3.24 / ax.get_window_extent().width

outlined = []  # (ontology, website, wedge) of every publishing website
start = 0.0  # compass degrees, clockwise from the top
for tier in data["children"]:
    base = TIER_COLOUR[tier["name"]]
    ontos = sorted(tier["children"], key=lambda o: -sum(c["value"] for c in o["children"]))
    t_value = sum(c["value"] for o in ontos for c in o["children"])
    t_span = 360 * t_value / total
    ax.add_patch(Wedge((0, 0), R0 + RING, 90 - start - t_span, 90 - start, width=RING, facecolor=base, edgecolor="white", linewidth=0.8))
    for text in variants(tier["name"]):
        if fit_label(ax, renderer, units_per_px, start + t_span / 2, R0 + RING / 2, t_span, text, (8, 7.5, 7, 6.5, 6, 5.5), "white"):
            break
    o_start = start
    for onto in ontos:
        sites = sorted(onto["children"], key=lambda c: (c.get("other", False), -c["value"]))
        o_value = sum(c["value"] for c in sites)
        o_span = 360 * o_value / total
        ax.add_patch(Wedge((0, 0), R0 + 2 * RING, 90 - o_start - o_span, 90 - o_start, width=RING,
                           facecolor=mix(base, 0.3), edgecolor="white", linewidth=0.8))
        for text in variants(RING_NAME.get(onto["name"], onto["name"])):  # longest form that fits
            if fit_label(ax, renderer, units_per_px, o_start + o_span / 2, R0 + 1.5 * RING, o_span, text, (6.5, 6, 5.5, 5), INK):
                break
        s_start = o_start
        for site in sites:
            s_span = 360 * site["value"] / total
            colour = mix(OTHER, 0.35) if site.get("other") else mix(base, 0.56)
            ax.add_patch(Wedge((0, 0), R0 + 3 * RING, 90 - s_start - s_span, 90 - s_start, width=RING,
                               facecolor=colour, edgecolor="white", linewidth=0.5))
            published = not site.get("other") and PUBLISHER.get(onto["name"]) == site["name"]
            if published:  # outline on top of all segments, drawn after the loop
                outlined.append((onto["name"], site["name"], Wedge((0, 0), R0 + 3 * RING, 90 - s_start - s_span, 90 - s_start,
                                                                   width=RING, facecolor="none", edgecolor=HIGHLIGHT,
                                                                   linewidth=HIGHLIGHT_LW, joinstyle="miter", zorder=3)))
            if s_span >= MIN_LABEL_DEG:
                text = site["name"].replace(" other websites", " others") if site.get("other") else site["name"]
                radial_text(ax, s_start + s_span / 2, R0 + 3 * RING + 0.025, text, 5.2,
                            "#64748b" if site.get("other") else INK, anchor="start", weight="bold" if published else "normal")
            s_start += s_span
        o_start += o_span
    start += t_span
for _, _, wedge in outlined:
    ax.add_patch(wedge)
assert sorted((o, w) for o, w, _ in outlined) == sorted(PUBLISHER.items())  # one outline per real ontology

ax.add_patch(plt.Circle((0, 0), R0 - 0.01, facecolor="#f8fafc", edgecolor="#e2e8f0", linewidth=0.8))
ax.text(0, 0.035, "All 12", ha="center", va="center", fontsize=9, fontweight="bold", color=INK)
ax.text(0, -0.06, f"{total:,} documents", ha="center", va="center", fontsize=6.5, color="#64748b")
handles = ([Patch(facecolor=TIER_COLOUR[t], label=t) for t in TIER_COLOUR] + [Patch(facecolor=mix(OTHER, 0.35), label="grouped small websites")]
           + [Patch(facecolor="white", edgecolor=HIGHLIGHT, linewidth=HIGHLIGHT_LW, joinstyle="miter", label="publishing website")])
ax.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, -0.04), ncol=len(handles), frameon=False, fontsize=7.5,
          handlelength=1, columnspacing=1.2)
fig.savefig(FIGURES / f"{NAME}.pdf", bbox_inches="tight", metadata={"CreationDate": None})
fig.savefig(FIGURES / f"{NAME}.png", dpi=200, bbox_inches="tight")
