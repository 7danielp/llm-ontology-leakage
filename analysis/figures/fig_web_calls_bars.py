"""Figure fig:web-calls: tool calls of gpt-5.6-luna per tier, one bar per run with web search"""
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle

from analysis import figstyle as fs
from analysis.common import FIGURES, TIERS
from analysis.numbers.tab_web_calls import RUNS, mean_share

STEP, WIDTH = 0.374, 0.287  # bar slot and bar width in tier units
SQUARE = 6.0  # pt, legend squares
COLOUR = fs.WEB_COLOUR
LABEL = {"1 call": "one tool call allowed", "3 calls": "up to three tool calls allowed"}

# left panel completed calls per answer, right panel share of answers that asked for more calls than allowed
values = {panel: {run: {t: mean_share(run, key, os) for t, os in TIERS.items()} for run in RUNS}
          for panel, key in (("left", "calls"), ("right", "blocked"))}

fs.setup()
fig, (ax_a, ax_b) = fs.panels(2, titles=True)
fs.y_axis(ax_a, 0, 2.0, 0.5, label="Calls per answer")
fs.y_axis(ax_b, 0, 0.7, 0.1, label="Share of answers")
fs.panel_title(ax_a, "Tool calls made")
fs.panel_title(ax_b, "Asked for more calls than allowed")
for ax, panel in ((ax_a, "left"), (ax_b, "right")):
    xs = fs.tier_axis(ax, list(TIERS))
    for run, dx in zip(RUNS, fs.dodge(len(RUNS), STEP)):
        for x, t in zip(xs, TIERS):
            ax.add_patch(Rectangle((x + dx - WIDTH / 2, 0), WIDTH, values[panel][run][t], facecolor=COLOUR[run],
                                   edgecolor=COLOUR[run], lw=fs.OPEN_EDGE, zorder=fs.Z_LINE))
fs.legend_top(fig, [Line2D([], [], ls="none", marker="s", ms=SQUARE, mfc=COLOUR[run], mec=COLOUR[run], mew=0) for run in RUNS],
              [LABEL[run] for run in RUNS])
fs.save(fig, "web_calls", FIGURES)
