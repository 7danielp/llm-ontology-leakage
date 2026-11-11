"""Figure fig:web-returned: share of the TS-Guessing answers whose returned text names given entity and gold, per tier"""
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

from analysis import figstyle as fs
from analysis.common import FIGURES, TIERS
from analysis.tables.web_returned_text import mean_share

RUN = "3 calls"  # the run with up to three calls, drawn as in Figure fig:web-calls
COPPER = fs.WEB_COLOUR[RUN]
TOP = 0.10  # inches above the plot area, room for the tick number 1.0
WIDTH = 0.287  # bar width in tier units, as in fig_web_calls_bars.py

values = {t: mean_share(os, "both") for t, os in TIERS.items()}

fs.setup()
probe, (probe_ax, _) = fs.panels(2, titles=True)  # the panels of Figure fig:web-calls
panel_w = probe_ax.get_position().width * fs.TEXTWIDTH  # inches
plt.close(probe)
fig, (ax,) = fs.panels(1)
# no legend row, plot area as wide as a panel of Figure fig:web-calls
bottom = ax.get_position().y0 * fig.get_figheight()
fig.set_size_inches(fs.TEXTWIDTH, bottom + fs.PLOT_H + TOP)
x0 = (fs.TEXTWIDTH - fs.LEFT - panel_w) / 2 + fs.LEFT
ax.set_position((x0 / fs.TEXTWIDTH, bottom / fig.get_figheight(), panel_w / fs.TEXTWIDTH, fs.PLOT_H / fig.get_figheight()))
fs.y_axis(ax, 0, 1.0, 0.2, label="Share with given and gold in the text")
for x, t in zip(fs.tier_axis(ax, list(TIERS)), TIERS):
    ax.add_patch(Rectangle((x - WIDTH / 2, 0), WIDTH, values[t], facecolor=COPPER, edgecolor=COPPER, lw=fs.OPEN_EDGE,
                           zorder=fs.Z_LINE))
fs.save(fig, "web_returned", FIGURES)
