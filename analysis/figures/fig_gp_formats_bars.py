"""Figure fig:gp-formats: Guided Prompting gap and share of identical answers per tier and identifier format"""
import collections
import statistics

from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle

from analysis import figstyle as fs
from analysis.common import FIGURES, FORMATS, MODELS, ONTOLOGIES, RESULTS, TASKS, TIERS, load_records, read_gaps

STEP, WIDTH = 0.24, 0.184  # bar slot and bar width in tier units
SQUARE = 6.0  # pt, legend squares
SLUG = {o.replace(" ", "-"): o for o in ONTOLOGIES}  # ontology name in the run folders

# gap of each run, mean over the 60 runs of a tier (three ontologies, four tasks, five models)
gaps = {run: gap for run, (gap, _) in read_gaps().items()}
gap_by_tier = {t: {f: statistics.mean(gaps[(o, k, m, f)] for o in os for k in TASKS for m in MODELS) for f in FORMATS}
               for t, os in TIERS.items()}

# share of questions whose normal and guided answer are the same text, per run, then mean over the runs of a tier
identical, questions = collections.Counter(), collections.Counter()
for run_dir in (RESULTS / "runs" / "guided-prompting").glob("GP__*"):
    _, slug, task, model, fmt = run_dir.name.split("__")
    run = (SLUG[slug], task, model, fmt)
    for r in load_records(run_dir):
        identical[run] += r["raw_normal"].strip() == r["raw_guided"].strip()
        questions[run] += 1
share_by_run = {run: identical[run] / questions[run] for run in questions}
share_by_tier = {t: {f: statistics.mean(share_by_run[(o, k, m, f)] for o in os for k in TASKS for m in MODELS) for f in FORMATS}
                 for t, os in TIERS.items()}

print("gap per tier (plain, prefix, full): "
      + "; ".join(f"{t} " + ", ".join(f"{gap_by_tier[t][f]:+.4f}" for f in FORMATS) for t in TIERS))
print("identical answers per tier (plain, prefix, full): "
      + "; ".join(f"{t} " + ", ".join(f"{share_by_tier[t][f]:.4f}" for f in FORMATS) for t in TIERS))

COLOUR = fs.FORMAT_COLOUR
DODGE = fs.dodge(len(FORMATS), STEP)
fs.setup()
fig, (ax_gap, ax_share) = fs.panels(2)
fs.y_axis(ax_gap, -0.1, 0.3, 0.1, label="Gap (Wu and Palmer)", zero=True)
fs.y_axis(ax_share, 0, 0.6, 0.1, label="Share of identical answers")
for ax, values in ((ax_gap, gap_by_tier), (ax_share, share_by_tier)):
    xs = fs.tier_axis(ax, list(TIERS))
    for f, dx in zip(FORMATS, DODGE):
        for x, t in zip(xs, TIERS):
            ax.add_patch(Rectangle((x + dx - WIDTH / 2, 0), WIDTH, values[t][f], facecolor=COLOUR[f], edgecolor=COLOUR[f],
                                   lw=fs.OPEN_EDGE, zorder=fs.Z_LINE))
fs.legend_top(fig, [Line2D([], [], ls="none", marker="s", ms=SQUARE, mfc=COLOUR[f], mec=COLOUR[f], mew=0) for f in FORMATS],
              [f"{f} format" for f in FORMATS])
fs.save(fig, "gp_formats", FIGURES)
