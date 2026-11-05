"""Two figures for the report: how long the chimes are, and which scale degrees they use.
Reads analysis/features.csv; writes analysis/fig_length.png and analysis/fig_degrees.png.

    python analysis/charts.py
"""

import collections
import csv
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
ROWS = list(csv.DictReader((REPO / "analysis" / "features.csv").open(encoding="utf-8-sig")))
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
COLORS = {"原创发车铃": "#2a78d6", "改编发车铃": "#eb6834", "车内铃": "#1baf7a"}
plt.rcParams.update({"font.family": ["WenQuanYi Zen Hei", "IPAGothic", "DejaVu Sans"], "font.size": 10,
                     "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
                     "text.color": INK, "figure.facecolor": SURFACE, "axes.facecolor": SURFACE})


def representatives():
    dep = [r for r in ROWS if r["kind"] == "发车铃" and r["transcription"].startswith("自动")]
    fams = collections.OrderedDict()
    for r in dep:
        fams.setdefault(r["family"], []).append(r)
    reps = [next((x for x in g if not x["variant"]), g[0]) for g in fams.values()]
    return {
        "原创发车铃": [r for r in reps if r["origin"] == "原创"],
        "改编发车铃": [r for r in reps if r["origin"] == "改编"],
        "车内铃": [r for r in ROWS if r["kind"] == "车内铃"],
    }


def length_figure(groups) -> None:
    fig, ax = plt.subplots(figsize=(8.2, 3.2))
    rng = np.random.default_rng(1)
    for row, (name, rows) in enumerate(groups.items()):
        y = len(groups) - 1 - row
        spans = np.array([float(r["span_s"]) for r in rows])
        jitter = rng.uniform(-0.18, 0.18, len(spans))
        ax.scatter(spans, y + jitter, s=26, color=COLORS[name], edgecolor=SURFACE, linewidth=1.2, zorder=3)
        med = np.median(spans)
        ax.plot([med, med], [y - 0.3, y + 0.3], color=INK, linewidth=2, zorder=4, solid_capstyle="round")
        ax.text(med, y + 0.36, f"中位数 {med:.1f} 秒", ha="center", va="bottom", fontsize=9, color=INK)
        jr = [float(r["span_s"]) for r in rows if r["source"].startswith("JR-SH")]
        if jr:
            q1, q2, q3 = np.percentile(jr, [25, 50, 75])
            ax.annotate(f"JR-SH 系列 {len(jr)} 首：中位 {q2:.1f} 秒\n半数在 {q1:.1f}–{q3:.1f} 秒之间", xy=(q2, y - 0.2),
                        xytext=(0.4, y - 0.52), fontsize=8.5, color=INK2, va="center", ha="left",
                        arrowprops={"arrowstyle": "-", "color": INK2, "linewidth": 0.8, "relpos": (1.0, 0.5)})
    ax.set_yticks(range(len(groups)))
    ax.set_yticklabels([f"{n}（{len(r)}）" for n, r in reversed(list(groups.items()))])
    ax.set_xlabel("一遍的有效长度（秒，从第一个音到最后一个音结束）")
    # the axis follows the data, so the longest melodies (about 29 s) are never cut off
    longest = max(float(r["span_s"]) for rows in groups.values() for r in rows)
    ax.set_xlim(0, np.ceil(longest) + 1)
    ax.set_xticks(np.arange(0, np.ceil(longest) + 1, 5))
    ax.set_ylim(-0.7, len(groups) - 0.25)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.set_title("发车铃多长？（每个点是一首旋律，变体只取一版）", loc="left", fontsize=11, color=INK)
    fig.tight_layout()
    fig.savefig(REPO / "analysis" / "fig_length.png", dpi=200)


def degree_figure(groups) -> None:
    names = ["1级", "降2", "2级", "降3", "3级", "4级", "升4", "5级", "降6", "6级", "降7", "7级"]
    fig, ax = plt.subplots(figsize=(8.2, 3.4))
    x = np.arange(12)
    width = 0.26
    for k, (name, rows) in enumerate(groups.items()):
        major = [r for r in rows if r["mode"] == "major"]
        share = np.array([np.mean([float(r[f"deg_{d}"]) for r in major]) for d in range(12)])
        ax.bar(x + (k - 1) * (width + 0.02), share, width, color=COLORS[name], label=f"{name}（大调 {len(major)} 首）",
               zorder=3, edgecolor=SURFACE, linewidth=1)
    ax.set_xticks(x)
    ax.set_xticklabels(names)
    ax.set_ylabel("占全部音符时值的比例")
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.legend(frameon=False, fontsize=9, loc="upper right")
    ax.set_title("大调发车铃用哪些音级？（相对主音，按时值加权）", loc="left", fontsize=11, color=INK)
    fig.tight_layout()
    fig.savefig(REPO / "analysis" / "fig_degrees.png", dpi=200)


def main() -> None:
    groups = representatives()
    length_figure(groups)
    degree_figure(groups)
    print("-> analysis/fig_length.png, analysis/fig_degrees.png")


if __name__ == "__main__":
    main()
