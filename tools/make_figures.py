"""Figures for the README: light and dark versions with transparent backgrounds (used with <picture>).

    python tools/make_figures.py --final results/final_test/summary.json --dev results/dev/summary.json \
        --log training/qwen-v1.2-lora/log.csv --out docs/assets
"""
import argparse
import csv
import json
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

THEMES = {  # validated categorical slots 1-2 (blue, orange) and text/grid tokens per mode
    "light": {"s1": "#2a78d6", "s2": "#eb6834", "text": "#0b0b0b", "text2": "#52514e", "grid": "#e4e3df"},
    "dark": {"s1": "#3987e5", "s2": "#d95926", "text": "#f0efec", "text2": "#c3c2b7", "grid": "#30302e"},
}
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11})


def _style(ax, t):
    ax.set_facecolor("none")
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(t["grid"])
    ax.tick_params(colors=t["text2"], length=0)
    ax.grid(axis="y", color=t["grid"], linewidth=1)
    ax.set_axisbelow(True)


def _column(ax, x, h, w, color, fig, radius_px=4):
    """Column with a rounded top (radius in pixels) and a square base."""
    fig.canvas.draw()
    x0, y0 = ax.transData.transform((0, 0))
    x1, y1 = ax.transData.transform((1, 1))
    px_x, px_y = (x1 - x0), (y1 - y0)            # pixels per data unit
    r = min(radius_px / px_x, w / 2)              # radius in x data units
    ry = radius_px / px_y                         # the same radius in y data units
    # the box starts below the baseline; the axes clip that part away, so the base is square and the top rounded
    ax.add_patch(FancyBboxPatch((x - w / 2, -ry), w, h + ry, boxstyle="round,pad=0,rounding_size=%f" % r,
                                mutation_aspect=px_x / px_y, linewidth=0, facecolor=color))


def results_figure(rows, path, mode):
    """rows: [(panel title, [(label, value, lo, hi), (label, value, lo, hi)]), ...]; values in %."""
    t = THEMES[mode]
    fig, axes = plt.subplots(1, len(rows), figsize=(9, 4.2), dpi=160)
    fig.patch.set_alpha(0)
    names = [b[0] for b in rows[0][1]]
    for ax, (title, bars) in zip(axes, rows):
        _style(ax, t)
        top = max(b[3] for b in bars) * 1.25
        ax.set_xlim(-0.6, len(bars) - 0.4)
        ax.set_ylim(0, top)
        ax.set_xticks([])
        ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: "%d%%" % v))
        ax.set_title(title, color=t["text"], fontsize=12, loc="left", pad=10)
        for i, (name, v, lo, hi) in enumerate(bars):
            _column(ax, i, v, 0.42, t["s1"] if i == len(bars) - 1 else t["s2"], fig)
            ax.plot([i, i], [lo, hi], color=t["text2"], linewidth=1, solid_capstyle="butt")
            ax.plot([i - 0.05, i + 0.05], [hi, hi], color=t["text2"], linewidth=1)
            ax.plot([i - 0.05, i + 0.05], [lo, lo], color=t["text2"], linewidth=1)
            ax.text(i, hi + top * 0.025, "%.1f%%" % v, ha="center", va="bottom", color=t["text"], fontsize=11,
                    fontweight="bold" if i == len(bars) - 1 else "normal")
    handles = [plt.Rectangle((0, 0), 1, 1, color=t["s2"]), plt.Rectangle((0, 0), 1, 1, color=t["s1"])]
    leg = fig.legend(handles, names, loc="upper left", bbox_to_anchor=(0.01, 1.0), ncol=2, frameon=False,
                     fontsize=11, handlelength=1.0, handleheight=1.0)
    for txt in leg.get_texts():
        txt.set_color(t["text"])
    fig.text(0.01, 0.01, "Greedy decoding, 4,096 new tokens, official UGPhysics rule judge. Whiskers: 95% intervals.",
             color=t["text2"], fontsize=9)
    fig.tight_layout(rect=(0, 0.04, 1, 0.9))
    fig.savefig(path, transparent=True)
    plt.close(fig)


def training_figure(log_csv, path, mode):
    t = THEMES[mode]
    tr, va = {}, {}   # a resumed run logs some steps twice: keep the last value per step
    for r in csv.DictReader(open(log_csv)):
        if r.get("train_loss"):
            tr[int(r["step"])] = float(r["train_loss"])
        if r.get("val_loss"):
            va[int(r["step"])] = float(r["val_loss"])
    steps, vsteps = sorted(tr), sorted(va)
    loss, vloss = [tr[s] for s in steps], [va[s] for s in vsteps]
    fig, ax = plt.subplots(figsize=(9, 3.8), dpi=160)
    fig.patch.set_alpha(0)
    _style(ax, t)
    ax.plot(steps, loss, color=t["s1"], linewidth=2, solid_joinstyle="round", solid_capstyle="round", label="training loss")
    ax.plot(vsteps, vloss, color=t["s2"], linewidth=2, marker="o", markersize=7, markeredgewidth=2,
            markeredgecolor="#ffffff" if mode == "light" else "#0d1117", label="validation loss")
    ax.set_xlabel("optimizer step", color=t["text2"])
    ax.set_ylim(0, max(loss + vloss) * 1.1)
    ax.set_xlim(0, max(steps + vsteps) * 1.02)
    leg = ax.legend(frameon=False, loc="upper right")
    for txt in leg.get_texts():
        txt.set_color(t["text"])
    ax.set_title("LoRA training on 12,000 physics solutions (1 epoch, 647 steps)", color=t["text"], loc="left", fontsize=12)
    fig.tight_layout()
    fig.savefig(path, transparent=True)
    plt.close(fig)


BASE, OURS = "qwen35-2b-nothink", "ft-qwen-v1.2-lora-s647-x50"


def _acc(summary, run, bench):
    b = summary["runs"][run]["benchmarks"][bench]
    r = b["rule"]
    return 100 * r["weighted"], 100 * r["ci"][0], 100 * r["ci"][1], b["n"]


def make_all(final_json, dev_json, log_csv, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    made = []
    if final_json and dev_json and os.path.exists(final_json) and os.path.exists(dev_json):
        fin, dev = json.load(open(final_json)), json.load(open(dev_json))
        ub, uo = _acc(fin, BASE + "-test", "ugphysics"), _acc(fin, OURS + "-test", "ugphysics")
        mb, mo = _acc(dev, BASE, "math500"), _acc(dev, OURS, "math500")
        names = ("Qwen3.5-2B (base, non-thinking)", "this model")
        rows = [("UGPhysics, unseen questions (n = {:,})".format(ub[3]), [(names[0],) + ub[:3], (names[1],) + uo[:3]]),
                ("MATH-500 (n = {:,})".format(mb[3]), [(names[0],) + mb[:3], (names[1],) + mo[:3]])]
        for mode in THEMES:
            results_figure(rows, os.path.join(out_dir, "results_%s.png" % mode), mode)
        made.append("results")
    if log_csv and os.path.exists(log_csv):
        for mode in THEMES:
            training_figure(log_csv, os.path.join(out_dir, "training_%s.png" % mode), mode)
        made.append("training")
    return made


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--final", default="results/final_test/summary.json")
    ap.add_argument("--dev", default="results/dev/summary.json")
    ap.add_argument("--log", default="training/qwen-v1.2-lora/log.csv")
    ap.add_argument("--out", default="docs/assets")
    a = ap.parse_args()
    print("made:", make_all(a.final, a.dev, a.log, a.out))
