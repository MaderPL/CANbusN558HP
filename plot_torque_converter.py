#!/usr/bin/env python3
"""
Plot and tabulate torque converter K-parameter from extracted CSV.

TC speed ratio  SR  = turbine_rpm / engine_rpm   (converter slip)
Gear ratio      GR  = turbine_rpm / tailshaft_rpm (transmission gear)

Produces a 4-panel figure:
  1. Engine, turbine & tailshaft RPM vs time
  2. TC speed ratio vs time (lockup band highlighted)
  3. Gear ratio vs time (ZF 8HP reference lines)
  4. Scatter: turbine vs engine RPM coloured by reinf_signal
"""

import csv
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

# ZF 8HP gear ratios (nominal)
ZF8HP_GEARS = {
    "1st": 4.714, "2nd": 3.143, "3rd": 2.106, "4th": 1.667,
    "5th": 1.285, "6th": 1.000, "7th": 0.839, "8th": 0.667,
}


def load(path: str):
    rows = list(csv.DictReader(open(path)))
    t    = np.array([float(r["timestamp_s"])    for r in rows])
    eng  = np.array([float(r["engine_rpm"])     for r in rows])
    tur  = np.array([float(r["turbine_rpm"])    for r in rows])
    tail = np.array([float(r["tailshaft_rpm"])  for r in rows])
    rei  = np.array([int(r["reinf_signal"])     for r in rows])
    sr   = np.where((eng > 200) & (eng > 0), tur / eng,   np.nan)
    gr   = np.where((tail > 20),              tur / tail, np.nan)
    return t, eng, tur, tail, rei, sr, gr


def print_table(t, eng, tur, tail, rei, sr, gr):
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
    hdr = f"\n{'TC speed ratio range':<26}  {'Rows':>7}  {'Avg eng':>7}  {'Avg tur':>7}  {'Avg tail':>8}  {'Avg reinf':>9}"
    print(hdr)
    print("-" * 74)
    for i, label in enumerate(labels):
        lo, hi = bins[i], bins[i + 1]
        mask = (~np.isnan(sr)) & (sr >= lo) & (sr < hi)
        n = mask.sum()
        if n == 0:
            continue
        print(
            f"{label:<26}  {n:>7,}  {eng[mask].mean():>7.0f}  "
            f"{tur[mask].mean():>7.0f}  {tail[mask].mean():>8.0f}  {rei[mask].mean():>9.1f}"
        )
    lock  = (~np.isnan(sr)) & (sr >= 0.97) & (sr <= 1.03)
    valid = ~np.isnan(sr)
    pct = 100 * lock.sum() / valid.sum() if valid.sum() else 0
    print(f"\nLockup fraction (SR 0.97–1.03): {pct:.1f}% of engine-on time")

    print(f"\n{'Gear (ZF 8HP)':<10}  {'Nominal GR':>10}  {'Rows in ±5%':>11}  {'Avg eng RPM':>11}  {'Avg tail RPM':>12}")
    print("-" * 60)
    for name, nominal in ZF8HP_GEARS.items():
        lo, hi = nominal * 0.95, nominal * 1.05
        mask = (~np.isnan(gr)) & (gr >= lo) & (gr < hi)
        n = mask.sum()
        if n == 0:
            continue
        print(f"{name:<10}  {nominal:>10.3f}  {n:>11,}  {eng[mask].mean():>11.0f}  {tail[mask].mean():>12.0f}")


def plot(t, eng, tur, tail, rei, sr, gr, out_path: str):
    fig, axes = plt.subplots(4, 1, figsize=(14, 14), sharex=False)
    fig.suptitle("Torque Converter K-Parameter Analysis", fontsize=13, fontweight="bold")

    # ── panel 1: all three RPM traces ─────────────────────────────────────────
    ax = axes[0]
    ax.plot(t, eng,  color="#e05c2a", linewidth=0.4, label="Engine RPM")
    ax.plot(t, tur,  color="#2a7be0", linewidth=0.4, label="Turbine RPM", alpha=0.85)
    ax.plot(t, tail, color="#9b30d0", linewidth=0.4, label="Tailshaft RPM", alpha=0.85)
    ax.set_ylabel("RPM")
    ax.set_xlabel("Time (s)")
    ax.legend(loc="upper right", fontsize=8)
    ax.set_title("Engine / Turbine / Tailshaft Speed")
    ax.grid(True, linewidth=0.3)

    # ── panel 2: TC speed ratio ────────────────────────────────────────────────
    ax = axes[1]
    ax.plot(t, sr, color="#333333", linewidth=0.3, label="TC speed ratio (tur/eng)")
    ax.axhspan(0.97, 1.03, color="#aaddaa", alpha=0.4, label="Lockup band (0.97–1.03)")
    ax.axhline(1.0, color="green", linewidth=0.6, linestyle="--")
    ax.set_ylim(-0.05, 1.15)
    ax.set_ylabel("SR = turbine / engine")
    ax.set_xlabel("Time (s)")
    ax.legend(loc="upper right", fontsize=8)
    ax.set_title("Torque Converter Speed Ratio (K-Line)")
    ax.grid(True, linewidth=0.3)

    # ── panel 3: gear ratio with ZF 8HP reference lines ───────────────────────
    ax = axes[2]
    ax.plot(t, gr, color="#555555", linewidth=0.3, label="Gear ratio (tur/tail)", zorder=2)
    colors = plt.cm.tab10(np.linspace(0, 1, len(ZF8HP_GEARS)))
    for (name, nominal), col in zip(ZF8HP_GEARS.items(), colors):
        ax.axhline(nominal, color=col, linewidth=0.7, linestyle="--", alpha=0.8, label=f"{name} ({nominal:.3f})")
    ax.set_ylim(0, 5.2)
    ax.set_ylabel("GR = turbine / tailshaft")
    ax.set_xlabel("Time (s)")
    ax.legend(loc="upper right", fontsize=7, ncol=2)
    ax.set_title("Gear Ratio with ZF 8HP Reference Lines")
    ax.grid(True, linewidth=0.3)

    # ── panel 4: turbine vs engine scatter coloured by reinf ──────────────────
    ax = axes[3]
    valid = (~np.isnan(sr)) & (eng > 200)
    idx = np.where(valid)[0]
    if len(idx) > 80_000:
        idx = np.random.choice(idx, 80_000, replace=False)
    sc = ax.scatter(eng[idx], tur[idx], c=rei[idx], cmap="plasma",
                    s=0.8, alpha=0.5, linewidths=0)
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
