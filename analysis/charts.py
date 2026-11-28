import argparse
import csv
import os
import statistics

import matplotlib
matplotlib.use("Agg")  # draw to files, no window needed
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter

TEXT = "#191919"
MUTED = "#666666"
GRID = "#e5e5e5"
BLUE = "#257de0"    # bots, or the main measure
ORANGE = "#f47230"  # rendezvous peers, or the second measure
AQUA = "#00b894"    # ordinary benign peers, or a third series
MARKERS = ["o", "s", "^"]

DILUTION_NETWORK = 360  # benign peers in the dilution sweep
RATIO_PREFERENCE = 0.8  # rendezvous_preference used in the network ratio sweep


def load(path):
    with open(path) as f:
        return list(csv.DictReader(f))


def averages(rows, column, benign=None, preference=None):
    # Average a column over repeats. Returns {(benign, preference): average},
    # optionally only for one network size or one preference.
    groups = {}
    for r in rows:
        b, p = int(r["benign"]), float(r["rendezvous_preference"])
        if (benign is None or b == benign) and (preference is None or p == preference):
            groups.setdefault((b, p), []).append(float(r[column]))
    return {key: statistics.mean(values) for key, values in groups.items()}


def style(ax, title, xlabel, ylabel):
    ax.set_title(title, color=TEXT, fontsize=13)
    ax.set_xlabel(xlabel, color=MUTED)
    ax.set_ylabel(ylabel, color=MUTED)
    ax.grid(color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=MUTED)


def lines(ax, series, end_labels=True, gap=None):
    # series: list of (label, colour, [(x, y), ...]). Draws each line, labels
    # its right end (nudged apart so labels never overlap), and adds a legend.
    ends = []
    for i, (label, colour, points) in enumerate(series):
        points = sorted(points)
        ax.plot([x for x, _ in points], [y for _, y in points], color=colour, linewidth=2,
                marker=MARKERS[i % len(MARKERS)], markersize=6, label=label)
        ends.append([points[-1][1], label, points[-1][0]])
    if end_labels and len(series) > 1:
        ends.sort()
        gap = gap or 0.05 * (ax.get_ylim()[1] - ax.get_ylim()[0])
        for i in range(1, len(ends)):
            ends[i][0] = max(ends[i][0], ends[i - 1][0] + gap)
        for y, label, x in ends:
            ax.annotate(label, (x, y), xytext=(8, 0), textcoords="offset points",
                        va="center", color=MUTED, fontsize=9)


def guessing(ax):
    ax.axhline(50, color=MUTED, linewidth=1, linestyle="--", label="Guessing (50%)")


def legend_below(ax, columns, offset=-0.17):
    ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, offset),
              ncol=columns, fontsize=9, labelcolor=TEXT)


def save(fig, out):
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)


def dilution_points(rows, column, scale=100):
    dilution = averages(rows, "dilution", benign=DILUTION_NETWORK)
    values = averages(rows, column, benign=DILUTION_NETWORK)
    return [(100 * dilution[k], scale * values[k]) for k in dilution]


def ratio_points(rows, column, preference, scale=100):
    values = averages(rows, column, preference=preference)
    return [(b / 40, scale * v) for (b, _), v in values.items()]


# 1. The main result.
def dilution_vs_detection(rows, out):
    fig, ax = plt.subplots(figsize=(7, 4.5))
    guessing(ax)
    lines(ax, [("Mutual contacts detection", BLUE, dilution_points(rows, "mutual_contacts_auc"))],
          end_labels=False)
    style(ax, f"Dilution vs Detection (40 bots, {DILUTION_NETWORK} benign peers)",
          "Dilution: ordinary benign peers among the bots' neighbours", "Detection (AUC)")
    ax.set_xlim(40, 90)
    ax.set_ylim(0, 105)
    ax.xaxis.set_major_formatter(PercentFormatter())
    ax.yaxis.set_major_formatter(PercentFormatter())
    legend_below(ax, 2)
    save(fig, out)


# 2. Why detection fails: the bots' overlap sinks to the ordinary peers' level.
def overlap_vs_dilution(rows, out):
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.set_ylim(0, 0.36)
    lines(ax, [
        ("Bots", BLUE, dilution_points(rows, "bot_overlap", scale=1)),
        ("Rendezvous peers", ORANGE, dilution_points(rows, "rendezvous_overlap", scale=1)),
        ("Ordinary benign peers", AQUA, dilution_points(rows, "ordinary_overlap", scale=1)),
    ], end_labels=False)
    style(ax, f"Neighbour Overlap vs Dilution (40 bots, {DILUTION_NETWORK} benign peers)",
          "Dilution: ordinary benign peers among the bots' neighbours",
          "Average mutual contacts score")
    ax.set_xlim(40, 90)
    ax.xaxis.set_major_formatter(PercentFormatter())
    legend_below(ax, 3)
    save(fig, out)


# 3. Network size: detection at each network ratio, with the control.
def ratio_vs_detection(rows, out):
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.set_ylim(0, 105)
    guessing(ax)
    lines(ax, [
        (f"Bots favour rendezvous peers ({RATIO_PREFERENCE:g})", BLUE,
         ratio_points(rows, "mutual_contacts_auc", RATIO_PREFERENCE)),
        ("Bots pick at random (control)", ORANGE, ratio_points(rows, "mutual_contacts_auc", 0.0)),
    ], end_labels=False)
    style(ax, "Network Ratio vs Detection (40 bots)",
          "Network benign-to-bot ratio (benign peers per bot)", "Detection (AUC)")
    ratios = sorted({x for x, _ in ratio_points(rows, "mutual_contacts_auc", 0.0)})
    ax.set_xticks(ratios)
    ax.set_xticklabels([f"{r:g}\n({int(r * 40)} benign)" for r in ratios])
    ax.set_xlim(1, 10)
    ax.yaxis.set_major_formatter(PercentFormatter())
    legend_below(ax, 3, offset=-0.25)
    save(fig, out)


# 4. Why small networks score lower: rendezvous peers overlap as much as bots.
def overlap_vs_ratio(rows, out):
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.set_ylim(0, 0.4)
    lines(ax, [
        ("Bots", BLUE, ratio_points(rows, "bot_overlap", RATIO_PREFERENCE, scale=1)),
        ("Rendezvous peers", ORANGE, ratio_points(rows, "rendezvous_overlap", RATIO_PREFERENCE, scale=1)),
        ("Ordinary benign peers", AQUA, ratio_points(rows, "ordinary_overlap", RATIO_PREFERENCE, scale=1)),
    ])
    style(ax, f"Neighbour Overlap vs Network Ratio (bots favour rendezvous peers, {RATIO_PREFERENCE:g})",
          "Network benign-to-bot ratio (benign peers per bot)", "Average mutual contacts score")
    ax.title.set_fontsize(11)
    ratios = sorted({x for x, _ in ratio_points(rows, "bot_overlap", RATIO_PREFERENCE)})
    ax.set_xticks(ratios)
    ax.set_xticklabels([f"{r:g}\n({int(r * 40)} benign)" for r in ratios])
    ax.set_xlim(1, 11.5)
    legend_below(ax, 3, offset=-0.25)
    save(fig, out)


# 5. The leakage check: counting neighbours does not find the bots.
def degree_vs_dilution(rows, out):
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.set_ylim(0, 105)
    guessing(ax)
    lines(ax, [
        ("Mutual contacts", BLUE, dilution_points(rows, "mutual_contacts_auc")),
        ("Number of neighbours (degree)", ORANGE, dilution_points(rows, "degree_auc")),
    ], end_labels=False)
    style(ax, f"Detection by Measure (40 bots, {DILUTION_NETWORK} benign peers)",
          "Dilution: ordinary benign peers among the bots' neighbours", "Detection (AUC)")
    ax.set_xlim(40, 90)
    ax.xaxis.set_major_formatter(PercentFormatter())
    ax.yaxis.set_major_formatter(PercentFormatter())
    legend_below(ax, 3)
    save(fig, out)


# 6. Method: how the setting translates into measured dilution.
def setting_vs_dilution(rows, out):
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.set_ylim(0, 105)
    series = []
    for (benign, colour) in [(360, BLUE), (160, ORANGE), (80, AQUA)]:
        dilution = averages(rows, "dilution", benign=benign)
        series.append((f"{benign} benign peers", colour,
                       [(p, 100 * d) for (_, p), d in dilution.items()]))
    lines(ax, series, end_labels=False)
    style(ax, "Bot Setting vs Measured Dilution (40 bots)",
          "Bot setting: chance a bot picks a rendezvous peer for a new link",
          "Measured dilution")
    ax.set_xlim(-0.05, 1.05)
    ax.yaxis.set_major_formatter(PercentFormatter())
    legend_below(ax, 3)
    save(fig, out)


# 7. Fidelity check: the peers behaved as configured in every run.
def fidelity(rows, out):
    runs = range(1, len(rows) + 1)
    fig, (top, bottom) = plt.subplots(2, 1, figsize=(7, 5.5), sharex=True)
    top.axhline(5, color=MUTED, linewidth=1, linestyle="--", label="Setting (5 s)")
    top.plot(runs, [float(r["mean_ping_gap"]) for r in rows], "o", color=BLUE, markersize=5,
             label="Measured")
    style(top, "Peers Behaved as Configured (all 36 runs)", "", "Time between PINGs (s)")
    top.set_ylim(4, 6)
    top.legend(frameon=False, loc="upper right", fontsize=9, labelcolor=TEXT)
    bottom.plot(runs, [float(r["mean_neighbours"]) for r in rows], "o", color=BLUE, markersize=5)
    style(bottom, "", "Run", "Average neighbours per peer")
    bottom.set_ylim(0, 30)
    save(fig, out)


CHARTS = {
    "1_dilution_vs_detection": dilution_vs_detection,
    "2_overlap_vs_dilution": overlap_vs_dilution,
    "3_ratio_vs_detection": ratio_vs_detection,
    "4_overlap_vs_ratio": overlap_vs_ratio,
    "5_degree_vs_dilution": degree_vs_dilution,
    "6_setting_vs_dilution": setting_vs_dilution,
    "7_fidelity": fidelity,
}


def main():
    parser = argparse.ArgumentParser(description="Draw the charts from a sweep results file.")
    parser.add_argument("results", help="CSV file from the sweep, e.g. results/sweep2.csv")
    parser.add_argument("--out-dir", default="results/charts")
    args = parser.parse_args()

    rows = load(args.results)
    os.makedirs(args.out_dir, exist_ok=True)
    for name, draw in CHARTS.items():
        out = os.path.join(args.out_dir, f"{name}.png")
        draw(rows, out)
        print(f"Saved {out}")


if __name__ == "__main__":
    main()