"""Figure fig:ts-wrong: wrong TS-Guessing answers that name an existing entity, per tier and task"""
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle

from analysis import figstyle as fs
from analysis.common import FIGURES, TASKS, TIERS
from analysis.tables.tab_ts_wrong import figure_values

YLABEL = "Share naming an existing entity"
LO, HI, TICK = 0, 0.8, 0.2
GAP_PANELS = 0.5  # inches between the two plot areas
STEP, WIDTH = 0.24, 0.184  # bar slot and bar width in tier units
SQUARE = 6.0  # pt, legend squares
TASK_COLOUR = {"taxonomy": "#48C3F5", "domain": "#DEAC0A", "range": "#F37453", "property": "#83C791"}  # sky blue, gold, coral, green

values = figure_values()  # {task: {tier: share}}
fs.setup()
fig, (left, right) = fs.panels(2, titles=True, gap=GAP_PANELS)
for ax, tasks, title in ((left, ["taxonomy", "domain", "range"], "Wrong answers"),
                         (right, ["property"], "Listed properties that are not gold")):
    fs.y_axis(ax, LO, HI, TICK, label=YLABEL if ax is left else None)
    fs.panel_title(ax, title)
    xs = fs.tier_axis(ax, list(TIERS))
    for t, dx in zip(tasks, fs.dodge(3, STEP) if len(tasks) == 3 else [0.0]):
        for x, tier in zip(xs, TIERS):
            ax.add_patch(Rectangle((x + dx - WIDTH / 2, 0), WIDTH, values[t][tier], facecolor=TASK_COLOUR[t],
                                   edgecolor=TASK_COLOUR[t], lw=fs.OPEN_EDGE, zorder=fs.Z_LINE))
fs.legend_top(fig, [Line2D([], [], ls="none", marker="s", ms=SQUARE, mfc=TASK_COLOUR[t], mec=TASK_COLOUR[t], mew=0) for t in TASKS],
              [f"{t} task" for t in TASKS])
fs.save(fig, "ts_wrong", FIGURES)
