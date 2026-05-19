#!/usr/bin/env python3
"""
Build the normalised K-characteristic table for the torque converter.

Method:
  1. Compute tc_norm = (reinf / gear_ratio) / baseline  for all valid samples
  2. Bin into 0.025-wide SR steps, weight each bin by 1/std^2
  3. Fit a smoothing spline through the weighted bin means
  4. Evaluate at round SR steps (0.05 … 1.00) for the final table
  5. Plot raw scatter + bin means + fitted K-line
"""

import csv, sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.interpolate import UnivariateSpline


# ── data loading ──────────────────────────────────────────────────────────────
def load(path):
    rows = list(csv.DictReader(open(path)))
    eng  = np.array([float(r["engine_rpm"])    for r in rows])
    tur  = np.array([float(r["turbine_rpm"])   for r in rows])
    tail = np.array([float(r["tailshaft_rpm"]) for r in rows])
    rei  = np.array([int(r["reinf_signal"])    for r in rows])
    return eng, tur, tail, rei


# ── normalised tc signal ──────────────────────────────────────────────────────
def tc_normalised(eng, tur, tail, rei):
    valid    = (tur > 20) & (tail > 5) & (eng > 200)
    gr       = np.where(valid, tur / tail, np.nan)
    raw      = np.where(valid, rei / gr,   np.nan)
    sr       = np.where(valid & (eng > 0), tur / eng, np.nan)
    locked   = valid & (sr >= 0.97) & (sr <= 1.03)
    baseline = np.nanmedian(raw[locked])
    tc       = raw / baseline
    return sr, tc, valid, baseline


# ── bin means with quality filter ────────────────────────────────────────────
def bin_means(sr, tc, valid, bin_width=0.025, min_n=30):
    v          = valid & np.isfinite(sr) & np.isfinite(tc)
    sr_v, tc_v = sr[v], tc[v]
    edges      = np.arange(0.0, 1.076, bin_width)
    centres, means, stds, counts = [], [], [], []
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (sr_v >= lo) & (sr_v < hi)
        n    = mask.sum()
        if n < min_n:
            continue
        centres.append((lo + hi) / 2)
        means.append(tc_v[mask].mean())
        stds.append(max(tc_v[mask].std(), 1e-6))
        counts.append(n)
    return (np.array(centres), np.array(means),
            np.array(stds), np.array(counts))


# ── spline fit ────────────────────────────────────────────────────────────────
def fit_spline(centres, means, stds, sr_fit):
    # Weight bins by inverse variance; down-weight noisy ends
    w = 1.0 / stds ** 2
    # Constrain fit to SR 0.10–1.05 where data is reliable
    mask = (centres >= 0.10) & (centres <= 1.05)
    spl  = UnivariateSpline(centres[mask], means[mask], w=w[mask], s=len(mask) * 0.5)
    return spl(sr_fit)


# ── table output ──────────────────────────────────────────────────────────────
def print_and_save_table(sr_table, k_table, out_csv):
    header = f"{'SR':>6}  {'K (normalised)':>16}  {'Torque ratio interpretation'}"
    print("\n" + "=" * 60)
    print("  Torque Converter Normalised K-Characteristic")
    print("  baseline: reinf/GR at full lockup (SR 0.97–1.03)")
    print("=" * 60)
    print(f"{'SR':>6}  {'K_norm':>8}")
    print("-" * 18)
    for sr, k in zip(sr_table, k_table):
        marker = "  ← lockup" if abs(sr - 1.0) < 0.01 else ""
        print(f"  {sr:.2f}  {k:>8.4f}{marker}")
    print("-" * 18)

    with open(out_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["SR", "K_norm"])
        for sr, k in zip(sr_table, k_table):
            w.writerow([f"{sr:.2f}", f"{k:.4f}"])
    print(f"\nTable saved → {out_csv}")


# ── plot ──────────────────────────────────────────────────────────────────────
def plot(sr_all, tc_all, valid, centres, means, stds,
         sr_table, k_table, baseline, out_png):

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle(
        "Torque Converter — Normalised K-Characteristic\n"
        r"$K_{norm}=1.0$ at full lockup  (baseline = " + f"{baseline:.1f})",
        fontsize=12, fontweight="bold"
    )

    for ax in axes:
        ax.axhline(1.0, color="green", linewidth=0.9, linestyle="--",
                   label="Fully coupled = 1.0", zorder=1)
        ax.axvline(0.97, color="gray", linewidth=0.7, linestyle=":",
                   label="Lockup onset SR=0.97", zorder=1)

    # ── left: raw scatter + bins + spline ────────────────────────────────────
    ax = axes[0]
    v   = valid & np.isfinite(sr_all) & np.isfinite(tc_all)
    idx = np.where(v)[0]
    if len(idx) > 80_000:
        idx = np.random.choice(idx, 80_000, replace=False)
    ax.scatter(sr_all[idx], tc_all[idx],
               s=0.8, alpha=0.15, color="#aaaacc", linewidths=0, label="Raw data")
    ax.errorbar(centres, means, yerr=stds,
                fmt="o", color="#2255aa", markersize=3,
                linewidth=0.8, capsize=2, label="Bin mean ±1σ", zorder=3)
    ax.plot(sr_table, k_table, "r-", linewidth=2.2, label="Fitted K-line", zorder=4)
    ax.set_xlabel("Speed ratio  SR = turbine / engine", fontsize=10)
    ax.set_ylabel("K_norm  (1.0 = fully coupled)", fontsize=10)
    ax.set_title("Raw data + bin means + fitted K-line")
    ax.set_xlim(-0.02, 1.10)
    ax.set_ylim(0.8, 2.8)
    ax.legend(fontsize=8)
    ax.grid(True, linewidth=0.3)

    # ── right: clean K-line only ─────────────────────────────────────────────
    ax = axes[1]
    ax.plot(sr_table, k_table, "r-", linewidth=2.5, label="K-characteristic", zorder=3)
    # annotate key points
    for sr_pt, label in [(0.10, "SR 0.10"), (0.50, "SR 0.50"),
                         (0.80, "SR 0.80"), (1.00, "Lockup")]:
        k_pt = np.interp(sr_pt, sr_table, k_table)
        ax.annotate(f"{label}\nK={k_pt:.3f}",
                    xy=(sr_pt, k_pt), xytext=(sr_pt + 0.04, k_pt + 0.05),
                    fontsize=7.5, arrowprops=dict(arrowstyle="-", lw=0.6))
    ax.set_xlabel("Speed ratio  SR = turbine / engine", fontsize=10)
    ax.set_ylabel("K_norm  (1.0 = fully coupled)", fontsize=10)
    ax.set_title("Clean K-characteristic")
    ax.set_xlim(-0.02, 1.10)
    ax.set_ylim(0.8, 2.8)
    ax.legend(fontsize=8)
    ax.grid(True, linewidth=0.3)

    fig.tight_layout()
    fig.savefig(out_png, dpi=150)
    print(f"Plot saved → {out_png}")


# ── main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    csv_path = sys.argv[1] if len(sys.argv) > 1 else "torque_converter_190250.csv"
    stem     = Path(csv_path).stem
    out_png  = f"k_norm_characteristic_{stem}.png"
    out_csv  = f"k_norm_characteristic_{stem}.csv"

    np.random.seed(0)

    eng, tur, tail, rei            = load(csv_path)
    sr, tc, valid, baseline        = tc_normalised(eng, tur, tail, rei)
    centres, means, stds, counts   = bin_means(sr, tc, valid)
    sr_table                       = np.arange(0.05, 1.01, 0.05)
    k_table                        = fit_spline(centres, means, stds, sr_table)

    print(f"Baseline: {baseline:.4f}")
    print_and_save_table(sr_table, k_table, out_csv)
    plot(sr, tc, valid, centres, means, stds, sr_table, k_table, baseline, out_png)
