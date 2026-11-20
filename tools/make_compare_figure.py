"""Comparison figure for the README and the model card: UGPhysics held-out test and MATH-500 for every model.

    python tools/make_compare_figure.py --ug results/compare/summary_compare_ugphysics.json \
        --math results/compare/summary_compare_math500.json --out docs/assets

Writes compare_light.png and compare_dark.png (transparent, for GitHub's <picture>) and compare_card.png
(white background, for the Hugging Face model card). Without the JSON files it uses the published numbers.
"""
import argparse
import json
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

THEMES = {
    "light": {"ours": "#2a78d6", "other": "#b9b8b2", "text": "#0b0b0b", "text2": "#52514e", "grid": "#e4e3df", "bg": None},
    "dark": {"ours": "#3987e5", "other": "#5f5e5a", "text": "#f0efec", "text2": "#c3c2b7", "grid": "#30302e", "bg": None},
    "card": {"ours": "#2a78d6", "other": "#b9b8b2", "text": "#0b0b0b", "text2": "#52514e", "grid": "#e4e3df", "bg": "#ffffff"},
}
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11})

# (label, UGPhysics test run, MATH-500 run, footnote mark)
MODELS = [
    ("This model", "ft-qwen-v1.2-lora-s647-x50-test", "ft-qwen-v1.2-lora-s647-x50", ""),
    ("Qwen3.5-2B (base)", "qwen35-2b-nothink-test", "qwen35-2b-nothink", ""),
    ("MegaScience Qwen3-1.7B", "cmp-qwen3-1.7b-megascience", "cmp-qwen3-1.7b-megascience", ""),
    ("DeepSeek-R1-Distill-Qwen-1.5B", "cmp-r1-distill-qwen-1.5b", "cmp-r1-distill-qwen-1.5b", "*"),
    ("OpenReasoning-Nemotron-1.5B", "cmp-openreasoning-nemotron-1.5b", "cmp-openreasoning-nemotron-1.5b", "*"),
]
PUBLISHED = {  # (accuracy, low, high) in %, from results/compare/compare_leaderboard.md
    "ugphysics": [(18.9, 16.3, 21.7), (15.9, 13.6, 18.5), (12.6, 10.5, 15.0), (9.8, 7.8, 11.9), (5.0, 3.5, 6.5)],
    "math500": [(63.5, 56.6, 69.9), (73.0, 67.3, 78.7), (63.0, 56.5, 69.1), (78.2, 73.0, 83.7), (54.7, 47.8, 61.4)],
}


def load(path, bench, col):
    if path and os.path.exists(path):
        js = json.load(open(path))
        out = []
        for m in MODELS:
            r = js["runs"][m[col]]["benchmarks"][bench]["rule"]
            out.append((100 * r["weighted"], 100 * r["ci"][0], 100 * r["ci"][1]))
        return out, js["runs"][MODELS[0][col]]["benchmarks"][bench]["n"]
    return PUBLISHED[bench], {"ugphysics": 1142, "math500": 210}[bench]


def figure(ug, math, n_ug, n_math, path, mode):
    t = THEMES[mode]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.0), dpi=160, gridspec_kw={"width_ratios": [1, 1], "wspace": 0.18})
    if t["bg"]:
        fig.patch.set_facecolor(t["bg"])
    else:
        fig.patch.set_alpha(0)
    labels = [m[0] + m[3] for m in MODELS]
    y = list(range(len(MODELS)))[::-1]
    for k, (ax, vals, title, xmax) in enumerate(((axes[0], ug, "UGPhysics, held-out test (n = {:,})".format(n_ug), 30),
                                                  (axes[1], math, "MATH-500 (n = {:,})".format(n_math), 100))):
        ax.set_facecolor(t["bg"] or "none")
        for s in ("top", "right", "left", "bottom"):
            ax.spines[s].set_visible(False)
        ax.tick_params(colors=t["text2"], length=0)
        ax.grid(axis="x", color=t["grid"], linewidth=1)
        ax.set_axisbelow(True)
        ax.set_xlim(0, xmax)
        ax.set_xticks([0, 10, 20, 30] if xmax == 30 else [0, 25, 50, 75, 100])
        ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: "%d%%" % v))
        ax.set_title(title, color=t["text"], fontsize=12, loc="left", pad=8)
        for i, (v, lo, hi) in enumerate(vals):
            ours = i == 0
            ax.barh(y[i], v, height=0.62, color=t["ours"] if ours else t["other"], linewidth=0)
            ax.plot([lo, hi], [y[i], y[i]], color=t["text2"], linewidth=1)
            ax.text(hi + xmax * 0.015, y[i], "%.1f%%" % v, va="center", ha="left", color=t["text"], fontsize=10.5,
                    fontweight="bold" if ours else "normal")
        ax.set_yticks(y)
        if k == 0:
            ax.set_yticklabels(labels, color=t["text"])
            ax.get_yticklabels()[0].set_fontweight("bold")
        else:
            ax.set_yticklabels([])
    fig.text(0.01, 0.015, "Same questions, prompts and rule judge for every model. Greedy decoding, 4,096 new tokens;"
             " * sampled (T 0.6, top-p 0.95), 8,192 tokens. Lines: 95% intervals.", color=t["text2"], fontsize=8.5)
    fig.subplots_adjust(left=0.235, right=0.98, top=0.88, bottom=0.14)
    fig.savefig(path, transparent=t["bg"] is None, facecolor=t["bg"] or "none")
    plt.close(fig)


def make(ug_json, math_json, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    ug, n_ug = load(ug_json, "ugphysics", 1)
    math, n_math = load(math_json, "math500", 2)
    files = []
    for mode in THEMES:
        p = os.path.join(out_dir, "compare_%s.png" % mode)
        figure(ug, math, n_ug, n_math, p, mode)
        files.append(p)
    return files, ug, math


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--ug", default="results/compare/summary_compare_ugphysics.json")
    ap.add_argument("--math", default="results/compare/summary_compare_math500.json")
    ap.add_argument("--out", default="docs/assets")
    a = ap.parse_args()
    print(make(a.ug, a.math, a.out)[0])
