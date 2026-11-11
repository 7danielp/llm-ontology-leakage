"""Figure fig:heatmap: score of each method per ontology and model"""
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import TwoSlopeNorm

from analysis.common import FIGURES, MAKI, MODELS, ONTOLOGIES, SHORT, TIERS, model_name, number
from analysis.tables.tab_methods import methods

plt.switch_backend("Agg")  # no window, the same drawing on every computer
FIGURES.mkdir(parents=True, exist_ok=True)

# one row per ontology, one column per model
TS = np.array([[methods["TS"][(o, m)] for m in MODELS] for o in ONTOLOGIES])
GP = np.array([[methods["GP"][(o, m)] for m in MODELS] for o in ONTOLOGIES])
MK = np.array([[methods["MK"][(o, m)] for m in MAKI] for o in ONTOLOGIES])
MK_TOP = MK.min() + 1.15 * (MK.max() - MK.min())  # upper end of the Min-K% Prob scale, the highest score lies at 1/1.15 of it

plt.rcParams.update({"font.family": "serif", "font.size": 7.5, "axes.linewidth": 0})
fig, axes = plt.subplots(1, 3, figsize=(6.5, 4.3), gridspec_kw={"width_ratios": [5, 5, 4], "wspace": 0.08})
panels = [  # title, values, colour map, colour scale, number format, models
    ("TS-Guessing\nF1", TS, plt.get_cmap("Blues"), dict(vmin=0, vmax=TS.max()), "{:.2f}", MODELS),
    ("Guided Prompting\ngap, plain format", GP, plt.get_cmap("RdBu_r"), dict(norm=TwoSlopeNorm(vcenter=0, vmin=-0.5, vmax=0.5)), "{:+.2f}", MODELS),
    ("Min-K% Prob\nMin-20% score", MK, plt.get_cmap("Blues"), dict(vmin=MK.min(), vmax=MK_TOP), "{:.2f}", MAKI),
]
labels = [SHORT.get(o, o) for o in ONTOLOGIES]
for i, (ax, (title, values, cmap, scale, fmt, models)) in enumerate(zip(axes, panels)):
    image = ax.imshow(values, cmap=cmap, aspect="auto", **scale)
    for r in range(values.shape[0]):
        for c in range(values.shape[1]):
            rgba = image.cmap(image.norm(values[r, c]))
            light = 0.299 * rgba[0] + 0.587 * rgba[1] + 0.114 * rgba[2] > 0.55  # luminance: black numbers on light squares
            text = fmt.format(values[r, c]).replace("-", "−")
            ax.text(c, r, text, ha="center", va="center", fontsize=6.3, color="black" if light else "white")
    for boundary in (2.5, 5.5, 8.5):  # white gaps between the tiers
        ax.axhline(boundary, color="white", linewidth=3)
    ax.set_xticks(range(len(models)), [model_name(m) for m in models], rotation=40, ha="right", rotation_mode="anchor")
    ax.set_yticks(range(len(labels)), labels if i == 0 else [""] * len(labels))
    ax.tick_params(length=0)
    ax.set_title(title, fontsize=8, pad=6)
for k, tier in enumerate(TIERS):  # tier names right of the last panel
    axes[-1].text(1.04, 3 * k + 1, tier, transform=axes[-1].get_yaxis_transform(), rotation=270, ha="center", va="center", fontsize=7.5, fontweight="bold")
fig.savefig(FIGURES / "heatmap_methods.pdf", bbox_inches="tight", dpi=200, metadata={"CreationDate": None})  # no time stamp in the PDF
fig.savefig(FIGURES / "heatmap_methods.png", bbox_inches="tight", dpi=200)
row, col = np.unravel_index(TS.argmax(), TS.shape)
print(f"TS-Guessing panel without the name-inferable questions, scale 0 to its maximum {number(float(TS.max()))} "
      f"({SHORT.get(ONTOLOGIES[row], ONTOLOGIES[row])}, {model_name(MODELS[col])})")
print(f"Min-K% Prob panel, one scale from {MK.min():.2f} (palest) to {MK.max():.2f} (darkest)")
