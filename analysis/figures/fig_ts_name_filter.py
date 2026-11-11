"""Figure fig:ts-name-filter: TS-Guessing micro F1 per tier and model, with and without the name-inferable questions"""
import statistics

from matplotlib.lines import Line2D
from matplotlib.text import Text

from analysis import figstyle as fs
from analysis.common import FIGURES, MODELS, TASKS, TIERS, model_name
from analysis.ts_filtered import ontology_f1, questions_left

MARKER = "o"
OPEN_MS = 3.6  # pt, open marker for all questions
FILLED_MS = OPEN_MS + fs.OPEN_EDGE - fs.EDGE  # filled marker, with its white ring as large as the open marker
STEM = 0.8  # pt, line between the two markers of a model
DODGE = 0.15  # five dumbbells side by side within a tier
MEAN_SIGN = "⌀"


def removed_share(ontology: str) -> float:
    """Share of the questions of an ontology that the name filter removes"""
    left = [questions_left(ontology, t) for t in TASKS]  # (questions left, all questions) per task
    total = sum(n for _, n in left)
    return (total - sum(k for k, _ in left)) / total


# (all questions, without the name-inferable questions) per tier and model, mean of the ontologies of a tier
values = {t: {m: [statistics.mean(ontology_f1(o, m, filtered) for o in os) for filtered in (False, True)] for m in MODELS}
          for t, os in TIERS.items()}
removed = {t: round(100 * statistics.mean(removed_share(o) for o in os)) for t, os in TIERS.items()}  # percent

fs.setup()
fig, (ax,) = fs.panels(1, legend_rows=2, notes=True, tiers=None)
fs.y_axis(ax, 0, 0.5, 0.1, label="TS-Guessing micro F1")
xs = fs.category_axis(ax, list(TIERS), notes=[f"{MEAN_SIGN} {removed[t]} % removed" for t in TIERS])
for text in fig.findobj(Text):
    if text.get_text().startswith(MEAN_SIGN):
        text.set_fontfamily(["cmr10", "DejaVu Sans"])  # cmr10 has no diameter sign


def dumbbell(x: float, y_open: float, y_filled: float, colour: str) -> None:
    """Stem, open marker for all questions and filled marker on top for the filtered questions"""
    ax.plot([x, x], [y_open, y_filled], color=colour, lw=STEM, solid_capstyle="butt", zorder=fs.Z_LINE)
    ax.plot(x, y_open, ls="none", marker=MARKER, ms=OPEN_MS, mfc="white", mec=colour, mew=fs.OPEN_EDGE, zorder=fs.Z_MARK)
    ax.plot(x, y_filled, ls="none", marker=MARKER, ms=FILLED_MS, mfc=colour, mec="white", mew=fs.EDGE, zorder=fs.Z_MARK + 1)


for x, t in zip(xs, TIERS):
    for m, dx in zip(MODELS, fs.dodge(len(MODELS), DODGE)):
        dumbbell(x + dx, *values[t][m], fs.MODEL_RAMP[m])

# legend markers as in the plot, the key in neutral grey
model_handles = [Line2D([], [], ls="none", marker=MARKER, color=fs.MODEL_RAMP[m], ms=FILLED_MS, mec="white", mew=fs.EDGE)
                 for m in MODELS]
key_handles = [Line2D([], [], ls="none", marker=MARKER, ms=OPEN_MS, mfc="white", mec=fs.KEY, mew=fs.OPEN_EDGE),
               Line2D([], [], ls="none", marker=MARKER, ms=FILLED_MS, mfc=fs.KEY, mec="white", mew=fs.EDGE)]
fs.legend_top(fig, model_handles, [model_name(m) for m in MODELS])
fs.legend_top(fig, key_handles, ["all questions", "without name-inferable questions"], row=1)
fs.save(fig, "ts_name_filter", FIGURES)
