"""Shared style of the thesis figures: page size, fonts, colours, panel layout, tier axis, legend and saving"""
import itertools
import logging
from collections.abc import Sequence
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.text import Text
from matplotlib.ticker import FixedLocator, FuncFormatter

plt.switch_backend("Agg")  # no window, the same drawing on every computer
logging.getLogger("fontTools").setLevel(logging.ERROR)  # no font timestamp warnings on PDF export

# page and type
TEXTWIDTH = 418.25555 / 72.27  # inches, \textwidth of the thesis
FONT = 8.0  # pt, all text
SMALL = 7.5  # pt, secondary notes
PLOT_H = 1.85  # inches, height of every plot area

# neutral inks
INK = "#2B2B2B"  # text
MUTED = "#6F6F6F"  # secondary text
AXIS = "#9A9A9A"  # axis lines and ticks
GRID = "#E6E6E6"  # horizontal grid
ZERO = "#C8C8C8"  # zero line
KEY = "#7A7A7A"  # legend markers that explain a fill

# model colours, light to dark by model size, copper for gpt-5.6-luna
MODEL_RAMP = {
    "ministral-3-14b": "#84A1B9",  # light steel blue
    "qwen3.6-36b": "#58799B",  # steel blue
    "llama-3.3-70b": "#32527D",  # dark slate blue
    "qwen3.5-122b": "#162C55",  # navy
    "gpt-5.6-luna": "#A45934",  # copper
}
FORMAT_COLOUR = {"plain": "#94B3FD", "prefix": "#5C88EA", "full": "#2D3EBD"}  # one blue, light to dark as more of the identifier is written
# runs of gpt-5.6-luna with web search, darker than its copper, up to three calls the darkest
WEB_COLOUR = {"1 call": "#994F2B", "3 calls": "#5C2716"}

# marks
EDGE = 0.5  # pt, white ring around a filled marker
OPEN_EDGE = 0.75  # pt, outline of open markers and bars
Z_LINE, Z_MARK = 3, 10  # every marker above every line

# margins in inches
LEFT = 0.50  # y tick numbers and y label of the first panel
GAP = 0.62  # between panels, room for the y label of the next one
RIGHT = 0.06  # at least, panels() widens it for the last tier name
LEGEND_ROW = 0.30  # legend row on top
LEGEND_ROW2 = 0.17  # second, smaller legend row
TITLE_ROW = 0.20  # panel titles
NAME_ROW = 0.26  # names under the axis
NOTE_ROW = 0.16  # muted line under every name
NAME_DY = 4  # pt between the axis line and the top of a name

# tier axis
TIER_NAMES = ("Popular", "Medium", "Unpopular", "Synthetic")
X_PAD = 0.5  # room left of the first and right of the last tier, in tier steps


def setup() -> None:
    """Matplotlib settings of every figure, cmr10 as in the thesis text"""
    plt.rcParams.update({
        "font.family": "serif", "font.serif": ["cmr10"], "mathtext.fontset": "cm", "axes.formatter.use_mathtext": True,
        "axes.unicode_minus": False, "font.size": FONT, "pdf.fonttype": 42, "text.color": INK, "axes.labelcolor": INK,
        "axes.titlesize": FONT, "axes.labelsize": FONT, "xtick.labelsize": FONT, "ytick.labelsize": FONT,
        "legend.fontsize": FONT, "legend.frameon": False, "axes.linewidth": 0.6, "axes.edgecolor": AXIS,
        "xtick.color": AXIS, "ytick.color": AXIS, "xtick.labelcolor": INK, "ytick.labelcolor": INK,
        "lines.solid_capstyle": "round", "lines.dash_capstyle": "butt", "savefig.dpi": 200,
    })


def text_width(text: str, size: float = FONT) -> float:
    """Width of a text in inches in the figure font"""
    fig = plt.figure(figsize=(1, 1), dpi=600)
    w = fig.text(0, 0, text, fontsize=size).get_window_extent(fig.canvas.get_renderer()).width / fig.dpi
    plt.close(fig)
    return w


def panels(n: int = 1, *, titles: bool = False, legend_rows: int = 1, notes: bool = False,
           tiers: Sequence[str] | None = TIER_NAMES, gap: float = GAP):
    """Figure of text width with n plot areas in a row, room for titles, legend rows, notes and tier names; returns (fig, axes)"""
    top = LEGEND_ROW + (legend_rows - 1) * LEGEND_ROW2 + (TITLE_ROW if titles else 0)
    bottom = NAME_ROW + (NOTE_ROW if notes else 0)
    pw = (TEXTWIDTH - LEFT - (n - 1) * gap - RIGHT) / n
    if tiers:  # the last name, centred on the last tier, may stick out to the right
        overhang = text_width(tiers[-1]) / 2 - X_PAD * pw / (len(tiers) - 1 + 2 * X_PAD)
        pw = (TEXTWIDTH - LEFT - (n - 1) * gap - max(RIGHT, overhang + 0.02)) / n
    height = bottom + PLOT_H + top
    fig = plt.figure(figsize=(TEXTWIDTH, height))
    axes = [fig.add_axes(((LEFT + k * (pw + gap)) / TEXTWIDTH, bottom / height, pw / TEXTWIDTH, PLOT_H / height))
            for k in range(n)]
    return fig, axes


def frame(ax) -> None:
    """Left and bottom axis lines only"""
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(AXIS)
        ax.spines[side].set_linewidth(0.6)


def y_axis(ax, lo: float, hi: float, step: float, *, label: str | None = None, zero: bool = False) -> None:
    """Fixed y range with a labelled tick every step and a light grid, zero=True adds a zero line"""
    ticks = [round(lo + i * step, 9) for i in range(round((hi - lo) / step) + 1)]
    ax.set_ylim(lo, hi)
    ax.yaxis.set_major_locator(FixedLocator(ticks))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: "0" if abs(v) < 1e-9 else f"${v:.1f}$"))  # real minus sign
    for y in ticks:
        if abs(y - lo) > 1e-9 and not (zero and abs(y) < 1e-9):
            ax.axhline(y, color=GRID, lw=0.5, zorder=1)
    if zero and lo < 0 < hi:
        ax.axhline(0, color=ZERO, lw=0.7, zorder=2)
    ax.tick_params(axis="y", length=2.5, width=0.5, color=AXIS, labelcolor=INK, pad=2)
    if label:
        ax.set_ylabel(label, color=INK, labelpad=5)
    frame(ax)


def panel_title(ax, text: str) -> None:
    ax.set_title(text, color=INK, fontsize=FONT, pad=6)


def _names(ax, xs: Sequence[float], names: Sequence[str], notes: Sequence[str] | None) -> None:
    """Names centred under the x positions, an optional muted note under each"""
    for k, (x, name) in enumerate(zip(xs, names)):
        ax.annotate(name, xy=(x, 0), xycoords=("data", "axes fraction"), xytext=(0, -NAME_DY), textcoords="offset points",
                    ha="center", va="top", color=INK, fontsize=FONT, annotation_clip=False)
        if notes:
            ax.annotate(notes[k], xy=(x, 0), xycoords=("data", "axes fraction"), xytext=(0, -NAME_DY - FONT - 2.5),
                        textcoords="offset points", ha="center", va="top", color=MUTED, fontsize=SMALL, annotation_clip=False)


def tier_axis(ax, tiers: Sequence[str] = TIER_NAMES) -> list[float]:
    """Tier axis without x ticks, the names centred under the tiers; returns the x positions"""
    xs = [float(k) for k in range(len(tiers))]
    ax.set_xlim(xs[0] - X_PAD, xs[-1] + X_PAD)
    ax.tick_params(axis="x", length=0)
    ax.set_xticks(xs, [""] * len(xs))
    _names(ax, xs, tiers, None)
    return xs


def category_axis(ax, names: Sequence[str], *, notes: Sequence[str] | None = None) -> list[float]:
    """Evenly spaced categories with horizontal names and optional notes; returns the x positions"""
    xs = list(range(len(names)))
    ax.set_xlim(-0.5, len(names) - 0.5)
    ax.set_xticks(xs, [""] * len(xs))
    ax.tick_params(axis="x", length=0)
    _names(ax, xs, names, notes)
    return xs


def dodge(n: int, step: float) -> list[float]:
    """Sideways shifts that set n series side by side, centred"""
    return [(k - (n - 1) / 2) * step for k in range(n)]


def legend_top(fig, handles, labels, *, row: int = 0) -> None:
    """Frameless legend in one row on top from the left axis line, row=1 a smaller, muted row under row 0"""
    x0 = min(fig.axes, key=lambda a: a.get_position().x0).get_position().x0
    pad = 0.35  # same border pad in both rows, so the first markers stand under each other
    if row == 0:
        y = 1.0
    else:  # right under row 0
        fig.canvas.draw()
        y = (fig.legends[0].get_window_extent().transformed(fig.transFigure.inverted()).y0 + 0.012
             + pad * SMALL / 72 / fig.get_figheight())
    fig.legend(handles, labels, ncol=len(handles), loc="upper left", bbox_to_anchor=(x0 - 0.012, y), frameon=False,
               fontsize=SMALL if row else FONT, labelcolor=MUTED if row else INK, handlelength=0.8, handletextpad=0.5,
               columnspacing=1.0, borderaxespad=pad)


def check_labels(fig, min_gap: float = 0.03) -> None:
    """Raise if two texts of the figure overlap or come closer than min_gap inches, or if a text leaves the figure"""
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    pad = min_gap * fig.dpi / 2
    boxes = [(t.get_text(), t.get_window_extent(renderer)) for t in fig.findobj(Text)
             if t.get_visible() and t.get_text().strip() and t.get_window_extent(renderer).width > 0]
    w, h = fig.get_figwidth() * fig.dpi, fig.get_figheight() * fig.dpi
    problems = [f"text leaves the figure: {s!r}" for s, b in boxes if b.x0 < -1 or b.x1 > w + 1 or b.y0 < -1 or b.y1 > h + 1]
    problems += [f"texts collide: {sa!r} and {sb!r}" for (sa, a), (sb, b) in itertools.combinations(boxes, 2)
                 if a.x0 - pad < b.x1 + pad and b.x0 - pad < a.x1 + pad and a.y0 < b.y1 and b.y0 < a.y1]
    if problems:
        raise AssertionError("; ".join(problems))


def save(fig, name: str, out: Path) -> None:
    """Write <name>.pdf and <name>.png at the exact figure size, after check_labels"""
    check_labels(fig)
    out.mkdir(parents=True, exist_ok=True)
    fig.savefig(out / f"{name}.pdf", metadata={"CreationDate": None})  # no time stamp in the PDF
    fig.savefig(out / f"{name}.png", dpi=200)
