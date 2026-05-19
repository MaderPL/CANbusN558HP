#!/usr/bin/env python3
"""
Plot reinf_signal / (turbine_rpm / tailshaft_rpm)  vs time and vs TC speed ratio.

Frame 0x8F offset 48 len 8  = reinf_signal
gear_ratio = turbine_rpm / tailshaft_rpm
normalised = reinf_signal / gear_ratio  =  reinf_signal * tailshaft_rpm / turbine_rpm
"""

import csv, sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def load(path):
    rows = list(csv.DictReader(open(path)))
    t    = np.array([float(r["timestamp_s"])   for r in rows])
    eng  = np.array([float(r["engine_rpm"])    for r in rows])
    tur  = np.array([float(r["turbine_rpm"])   for r in rows])
    tail = np.array([float(r["tailshaft_rpm"]) for r in rows])
    rei  = np.array([int(r["reinf_signal"])    for r in rows])
    return t, eng, tur, tail, rei


def compute(eng, tur, tail, rei):
    valid = (tur > 20) & (tail > 5)
    gr    = np.where(valid, tur / tail, np.nan)
    norm  = np.where(valid, rei / gr,   np.nan)   # = rei * tail / tur
    sr    = np.where((eng > 200) & (tur >= 0) & (eng > 0), tur / eng, np.nan)
    return gr, norm, sr, valid


if __name__ == "__main__":
    csv_path = sys.argv[1] if len(sys.argv) > 1 else "torque_converter_190250.csv"
    out_png  = Path(csv_path).stem + "_reinf_norm.png"

    t, eng, tur, tail, rei = load(csv_path)
    gr, norm, sr, valid    = compute(eng, tur, tail, rei)

    fig, axes = plt.subplots(3, 1, figsize=(14, 11))
    fig.suptitle(
        "8F[O48L8]  /  (turbine / tailshaft)\n"
        r"$\it{reinf\_signal}$  /  gear\_ratio",
        fontsize=12, fontweight="bold"
    )

    # ── panel 1: normalised value over time ───────────────────────────────────
    ax = axes[0]
    ax.plot(t, norm, color="#2255aa", linewidth=0.35, alpha=0.8)
    ax.set_ylabel("reinf / (tur/tail)", fontsize=9)
    ax.set_xlabel("Time (s)")
    ax.set_title("Normalised reinforcement signal over time")
    ax.grid(True, linewidth=0.3)

    # ── panel 2: normalised vs TC speed ratio, coloured by gear ratio ─────────
    ax = axes[1]
    v = valid & np.isfinite(sr) & np.isfinite(norm)
    idx = np.where(v)[0]
    if len(idx) > 100_000:
        idx = np.random.choice(idx, 100_000, replace=False)
    sc = ax.scatter(sr[idx], norm[idx],
                    c=gr[idx], cmap="tab10",
                    s=1.0, alpha=0.4, linewidths=0,
                    vmin=0.5, vmax=5.0)
    cbar = fig.colorbar(sc, ax=ax, pad=0.01)
    cbar.set_label("Gear ratio (tur/tail)", fontsize=8)
    ax.set_xlabel("TC speed ratio  SR = turbine / engine", fontsize=9)
    ax.set_ylabel("reinf / (tur/tail)", fontsize=9)
    ax.set_title("Normalised reinforcement vs TC speed ratio  (colour = gear)")
    ax.set_xlim(-0.05, 1.15)
    ax.grid(True, linewidth=0.3)

    # ── panel 3: binned mean ± 1σ per SR bin ──────────────────────────────────
    ax = axes[2]
    sr_v   = sr[v]
    norm_v = norm[v]
    edges  = np.linspace(0.0, 1.10, 45)
    centres, means, stds = [], [], []
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (sr_v >= lo) & (sr_v < hi)
        if mask.sum() < 20:
            continue
        centres.append((lo + hi) / 2)
        means.append(norm_v[mask].mean())
        stds.append(norm_v[mask].std())
    centres = np.array(centres)
    means   = np.array(means)
    stds    = np.array(stds)

    ax.fill_between(centres, means - stds, means + stds,
                    alpha=0.25, color="red", label="±1σ")
    ax.plot(centres, means, "r-", linewidth=2.0, label="Mean")
    ax.axvline(0.97, color="green", linewidth=0.8, linestyle="--", label="Lockup onset")
    ax.set_xlabel("TC speed ratio  SR = turbine / engine", fontsize=9)
    ax.set_ylabel("reinf / (tur/tail)", fontsize=9)
    ax.set_title("Binned mean  reinf / gear_ratio  vs SR")
    ax.legend(fontsize=9)
    ax.set_xlim(-0.05, 1.15)
    ax.grid(True, linewidth=0.3)

    # print table
    print(f"\n{'SR centre':>10}  {'mean':>8}  {'std':>7}  {'N':>7}")
    print("-" * 38)
    for c, m, s in zip(centres, means, stds):
        print(f"{c:>10.3f}  {m:>8.3f}  {s:>7.3f}")

    fig.tight_layout()
    fig.savefig(out_png, dpi=150)
    print(f"\nPlot saved → {out_png}")
