#!/usr/bin/env python3
"""
Plot and tabulate torque converter K-parameter (speed ratio) from extracted CSV.

Speed ratio SR = turbine_rpm / engine_rpm  (the K-line X-axis).
Bins SR into ranges and reports statistics per bin.
Produces a 3-panel figure:
  1. Engine & turbine RPM vs time
  2. Speed ratio vs time (with lockup region highlighted)
  3. Scatter: turbine vs engine RPM coloured by reinf_signal
"""

import csv
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np


def load(path: str):
    rows = list(csv.DictReader(open(path)))
    t   = np.array([float(r["timestamp_s"])  for r in rows])
    eng = np.array([float(r["engine_rpm"])   for r in rows])
    tur = np.array([float(r["turbine_rpm"])  for r in rows])
    rei = np.array([int(r["reinf_signal"])   for r in rows])
    # speed ratio only where both shafts are turning
    moving = (eng > 200) & (tur >= 0)
    sr = np.where(moving & (eng > 0), tur / eng, np.nan)
    return t, eng, tur, rei, sr


def print_table(t, eng, tur, rei, sr):
    bins = [0.0, 0.10, 0.20, 0.40, 0.60, 0.75, 0.85, 0.93, 0.97, 1.03, 1.10]
    labels = [
        "stall      (0.00–0.10)",
        "low accel  (0.10–0.20)",
        "accel      (0.20–0.40)",
        "mid accel  (0.40–0.60)",
        "high accel (0.60–0.75)",
        "conv exit  (0.75–0.85)",
        "near-lock  (0.85–0.93)",
        "pre-lock   (0.93–0.97)",
        "locked     (0.97–1.03)",
        "over-lock  (1.03–1.10)",
    ]
    print(f"\n{'Speed ratio range':<26}  {'Rows':>7}  {'Avg eng RPM':>11}  {'Avg tur RPM':>11}  {'Avg reinf':>9}")
    print("-" * 72)
    for i, label in enumerate(labels):
        lo, hi = bins[i], bins[i + 1]
        mask = (~np.isnan(sr)) & (sr >= lo) & (sr < hi)
        n = mask.sum()
        if n == 0:
            continue
        print(
            f"{label:<26}  {n:>7,}  {eng[mask].mean():>11.0f}  "
            f"{tur[mask].mean():>11.0f}  {rei[mask].mean():>9.1f}"
        )
    # lockup fraction
    lock = (~np.isnan(sr)) & (sr >= 0.97) & (sr <= 1.03)
    valid = ~np.isnan(sr)
    pct = 100 * lock.sum() / valid.sum() if valid.sum() else 0
    print(f"\nLockup fraction (SR 0.97–1.03): {pct:.1f}% of time with engine running")


def plot(t, eng, tur, rei, sr, out_path: str):
    fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharex=False)
    fig.suptitle("Torque Converter K-Parameter Analysis", fontsize=13, fontweight="bold")

    # ── panel 1: RPM vs time ──────────────────────────────────────────────────
    ax = axes[0]
    ax.plot(t, eng, color="#e05c2a", linewidth=0.4, label="Engine RPM")
    ax.plot(t, tur, color="#2a7be0", linewidth=0.4, label="Turbine RPM", alpha=0.8)
    ax.set_ylabel("RPM")
    ax.set_xlabel("Time (s)")
    ax.legend(loc="upper right", fontsize=8)
    ax.set_title("Engine vs Turbine Speed")
    ax.grid(True, linewidth=0.3)

    # ── panel 2: speed ratio vs time ─────────────────────────────────────────
    ax = axes[1]
    ax.plot(t, sr, color="#333333", linewidth=0.3, label="Speed ratio")
    ax.axhspan(0.97, 1.03, color="#aaddaa", alpha=0.4, label="Lockup band (0.97–1.03)")
    ax.axhline(1.0, color="green", linewidth=0.6, linestyle="--")
    ax.set_ylim(-0.05, 1.15)
    ax.set_ylabel("SR = turbine / engine")
    ax.set_xlabel("Time (s)")
    ax.legend(loc="upper right", fontsize=8)
    ax.set_title("Speed Ratio (K-Line) over Time")
    ax.grid(True, linewidth=0.3)

    # ── panel 3: turbine vs engine scatter coloured by reinf ─────────────────
    ax = axes[2]
    valid = (~np.isnan(sr)) & (eng > 200)
    # thin to max 80 000 pts for speed
    idx = np.where(valid)[0]
    if len(idx) > 80_000:
        idx = np.random.choice(idx, 80_000, replace=False)
    sc = ax.scatter(
        eng[idx], tur[idx],
        c=rei[idx], cmap="plasma",
        s=0.8, alpha=0.5, linewidths=0,
    )
    # ideal lockup diagonal
    rmax = max(eng[valid].max(), tur[valid].max())
    ax.plot([0, rmax], [0, rmax], "g--", linewidth=0.8, label="SR = 1.0 (lockup)")
    cbar = fig.colorbar(sc, ax=ax, pad=0.01)
    cbar.set_label("Reinf signal", fontsize=8)
    ax.set_xlabel("Engine RPM")
    ax.set_ylabel("Turbine RPM")
    ax.set_title("Turbine vs Engine RPM (colour = reinf signal)")
    ax.legend(fontsize=8)
    ax.grid(True, linewidth=0.3)

    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    print(f"Plot saved → {out_path}")


if __name__ == "__main__":
    csv_path = sys.argv[1] if len(sys.argv) > 1 else "torque_converter_190250.csv"
    out_png  = sys.argv[2] if len(sys.argv) > 2 else Path(csv_path).stem + "_kplot.png"

    np.random.seed(0)
    data = load(csv_path)
    print_table(*data)
    plot(*data, out_path=out_png)
