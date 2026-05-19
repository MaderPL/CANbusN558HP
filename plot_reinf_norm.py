#!/usr/bin/env python3
"""
Plot reinf_signal / (turbine_rpm / tailshaft_rpm), normalised to 1.0 at full lockup.

Frame 0x8F offset 48 len 8  = reinf_signal
gear_ratio  = turbine_rpm / tailshaft_rpm
raw_norm    = reinf_signal / gear_ratio
baseline    = median of raw_norm where SR ∈ [0.97, 1.03]  (fully coupled)
tc_norm     = raw_norm / baseline   →  1.0 when engine speed = turbine speed
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
    valid    = (tur > 20) & (tail > 5)
    gr       = np.where(valid, tur / tail, np.nan)
    raw_norm = np.where(valid, rei / gr,   np.nan)
    sr       = np.where((eng > 200) & (eng > 0), tur / eng, np.nan)

    # Baseline: median of raw_norm when fully coupled (SR 0.97–1.03)
    locked   = valid & (sr >= 0.97) & (sr <= 1.03)
    baseline = np.nanmedian(raw_norm[locked])
    tc_norm  = raw_norm / baseline

    return gr, tc_norm, sr, valid, baseline


if __name__ == "__main__":
    csv_path = sys.argv[1] if len(sys.argv) > 1 else "torque_converter_190250.csv"
    out_png  = Path(csv_path).stem + "_tc_norm.png"

    t, eng, tur, tail, rei   = load(csv_path)
    gr, tc_norm, sr, valid, baseline = compute(eng, tur, tail, rei)

    print(f"Normalisation baseline (median reinf/GR at SR 0.97–1.03): {baseline:.4f}")

    fig, axes = plt.subplots(3, 1, figsize=(14, 11))
    fig.suptitle(
        "TC reinforcement  /  gear_ratio  —  normalised to 1.0 at full lockup\n"
        r"$tc\_norm = \frac{reinf\_signal \;/\; (turbine/tailshaft)}{baseline}$",
        fontsize=11, fontweight="bold"
    )

    # ── panel 1: normalised value over time ──────────────────────────────────
    ax = axes[0]
    ax.plot(t, tc_norm, color="#2255aa", linewidth=0.35, alpha=0.8)
    ax.axhline(1.0, color="green", linewidth=0.8, linestyle="--", label="Fully coupled (= 1.0)")
    ax.set_ylabel("tc_norm  (1 = fully coupled)", fontsize=9)
    ax.set_xlabel("Time (s)")
    ax.set_title("Normalised TC reinforcement over time")
    ax.legend(fontsize=9)
    ax.grid(True, linewidth=0.3)

    # ── panel 2: scatter vs TC speed ratio, coloured by gear ratio ───────────
    ax = axes[1]
    v   = valid & np.isfinite(sr) & np.isfinite(tc_norm)
    idx = np.where(v)[0]
    if len(idx) > 100_000:
        idx = np.random.choice(idx, 100_000, replace=False)
    sc = ax.scatter(sr[idx], tc_norm[idx],
                    c=gr[idx], cmap="tab10",
                    s=1.0, alpha=0.4, linewidths=0,
                    vmin=0.5, vmax=5.0)
    ax.axhline(1.0, color="green", linewidth=0.9, linestyle="--", label="Fully coupled (= 1.0)")
    cbar = fig.colorbar(sc, ax=ax, pad=0.01)
    cbar.set_label("Gear ratio (tur/tail)", fontsize=8)
    ax.set_xlabel("TC speed ratio  SR = turbine / engine", fontsize=9)
    ax.set_ylabel("tc_norm  (1 = fully coupled)", fontsize=9)
    ax.set_title("Normalised TC reinforcement vs speed ratio  (colour = gear)")
    ax.legend(fontsize=9)
    ax.set_xlim(-0.05, 1.15)
    ax.grid(True, linewidth=0.3)

    # ── panel 3: binned mean ± 1σ ─────────────────────────────────────────────
    ax = axes[2]
    sr_v    = sr[v]
    norm_v  = tc_norm[v]
    edges   = np.linspace(0.0, 1.10, 45)
    centres, means, stds, counts = [], [], [], []
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (sr_v >= lo) & (sr_v < hi)
        n = mask.sum()
        if n < 20:
            continue
        centres.append((lo + hi) / 2)
        means.append(norm_v[mask].mean())
        stds.append(norm_v[mask].std())
        counts.append(n)
    centres = np.array(centres)
    means   = np.array(means)
    stds    = np.array(stds)

    ax.fill_between(centres, means - stds, means + stds,
                    alpha=0.25, color="red", label="±1σ")
    ax.plot(centres, means, "r-", linewidth=2.0, label="Mean tc_norm")
    ax.axhline(1.0, color="green", linewidth=0.9, linestyle="--", label="Fully coupled (= 1.0)")
    ax.axvline(0.97, color="gray", linewidth=0.7, linestyle=":", label="Lockup onset SR=0.97")
    ax.set_xlabel("TC speed ratio  SR = turbine / engine", fontsize=9)
    ax.set_ylabel("tc_norm  (1 = fully coupled)", fontsize=9)
    ax.set_title(f"Binned mean  tc_norm  vs SR  (baseline = {baseline:.2f})")
    ax.legend(fontsize=9)
    ax.set_xlim(-0.05, 1.15)
    ax.grid(True, linewidth=0.3)

    print(f"\n{'SR centre':>10}  {'tc_norm mean':>13}  {'std':>7}  {'N pts':>8}")
    print("-" * 46)
    for c, m, s, n in zip(centres, means, stds, counts):
        print(f"{c:>10.3f}  {m:>13.4f}  {s:>7.4f}  {n:>8,}")

    fig.tight_layout()
    fig.savefig(out_png, dpi=150)
    print(f"\nPlot saved → {out_png}")
