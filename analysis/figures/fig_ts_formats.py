"""Figure fig:ts-formats: TS-Guessing micro F1 and correct form per model and identifier format"""
from decimal import ROUND_HALF_UP, Decimal

from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle

from analysis import figstyle as fs
from analysis.common import FIGURES, FORMATS, MODELS, model_name
from analysis.tables.tab_ts_formats import values

YLABEL, ROW_LABEL = "TS-Guessing micro F1", "Correct form (%)"
STEP, WIDTH = 0.15, 0.115  # bar slot and bar width in category units
NUM_DY = 12.0  # pt between the axis line and the top of the number row
ROW_GAP = 3.0  # pt between the number row and the format names
NAME_DY = NUM_DY + fs.SMALL * 1.2 + ROW_GAP  # pt between the axis line and the top of the format names
TICK_OFF = (2.5 + 2) / 72  # in, so the row label ends where the y tick numbers end
SQUARE = 6.0  # pt, legend squares


def pct(x: float) -> str:
    """Whole percent, rounded half up"""
    return str(Decimal(repr(100 * x)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def under_axis(ax, x: float, text: str, dy: float, *, size: float, colour: str, xcoords: str = "data", ha: str = "center",
               dx: float = 0.0):
    """Text whose top stands dy pt under the axis line, centred under the data position x (or as ha says)"""
    ax.annotate(text, xy=(x, 0), xycoords=(xcoords, "axes fraction"), xytext=(dx, -dy), textcoords="offset points",
                ha=ha, va="top", color=colour, fontsize=size, annotation_clip=False)


table = values()  # {model: {format: (F1 score, form-independent F1 score, correct form)}}
fs.setup()
fs.LEFT = round(fs.text_width(ROW_LABEL, fs.SMALL) + TICK_OFF + 0.06, 2)  # the row label stands in the left margin
fig, (ax,) = fs.panels(1, legend_rows=2, notes=True, tiers=None)
# room at the bottom for the number row
extra = (NUM_DY - 6.0) / 72
width, height = fig.get_size_inches()
left, bottom, plot_width, plot_height = ax.get_position().bounds
fig.set_size_inches(width, height + extra)
ax.set_position((left, (bottom * height + extra) / (height + extra), plot_width, plot_height * height / (height + extra)))
fs.y_axis(ax, 0, 0.3, 0.1, label=YLABEL)
xs = list(range(len(FORMATS)))
ax.set_xlim(-0.5, len(FORMATS) - 0.5)
ax.set_xticks(xs, [""] * len(xs))
ax.tick_params(axis="x", length=0)
for x, f in zip(xs, FORMATS):
    for m, dx in zip(MODELS, fs.dodge(len(MODELS), STEP)):
        f1, form, correct = table[m][f]
        colour = fs.MODEL_RAMP[m]
        # open bar up to the form-independent F1 score, filled bar up to the F1 score on top of it
        ax.add_patch(Rectangle((x + dx - WIDTH / 2, 0), WIDTH, form, facecolor="white", edgecolor=colour, lw=fs.OPEN_EDGE,
                               zorder=fs.Z_LINE))
        ax.add_patch(Rectangle((x + dx - WIDTH / 2, 0), WIDTH, f1, facecolor=colour, edgecolor=colour, lw=fs.OPEN_EDGE,
                               zorder=fs.Z_LINE + 0.1))
        under_axis(ax, x + dx, pct(correct), NUM_DY, size=fs.SMALL, colour=fs.MUTED)
under_axis(ax, 0, ROW_LABEL, NUM_DY, size=fs.SMALL, colour=fs.MUTED, xcoords="axes fraction", ha="right", dx=-TICK_OFF * 72)
for x, f in zip(xs, FORMATS):
    under_axis(ax, x, f"{f.capitalize()} format", NAME_DY, size=fs.FONT, colour=fs.INK)
fs.legend_top(fig, [Line2D([], [], ls="none", marker="s", ms=SQUARE, mfc=fs.MODEL_RAMP[m], mec=fs.MODEL_RAMP[m], mew=0)
                    for m in MODELS], [model_name(m) for m in MODELS])
fs.legend_top(fig, [Line2D([], [], ls="none", marker="s", ms=SQUARE, mfc=fs.KEY, mec=fs.KEY, mew=0),
                    Line2D([], [], ls="none", marker="s", ms=SQUARE - fs.OPEN_EDGE, mfc="white", mec=fs.KEY, mew=fs.OPEN_EDGE)],
              ["F1 score", "form-independent F1 score"], row=1)
fs.save(fig, "ts_formats", FIGURES)
