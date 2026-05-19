#!/usr/bin/env python3
"""
Extract torque converter K-characteristic from 1st gear takeup events.

K-factor (capacity factor):  K = N_engine / sqrt(reinf_signal)
TC speed ratio:              SR = turbine_rpm / engine_rpm

Filters:
  - 1st gear (gear_ratio 4.0–5.5)
  - Takeup phase: tailshaft rising, SR < 1.05
  - reinf_signal > 10 (avoid division artefacts)
  - engine_rpm > 400

Outputs:
  - k_characteristic_<stem>.png  — scatter of all events + binned mean K-line
  - k_characteristic_<stem>.csv  — binned K vs SR summary table
"""

import csv
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def load(path: str):
    rows = list(csv.DictReader(open(path)))
    t    = np.array([float(r["timestamp_s"])   for r in rows])
    eng  = np.array([float(r["engine_rpm"])    for r in rows])
    tur  = np.array([float(r["turbine_rpm"])   for r in rows])
    tail = np.array([float(r["tailshaft_rpm"]) for r in rows])
    rei  = np.array([int(r["reinf_signal"])    for r in rows])
    gr   = np.array([float(r["gear_ratio"]) if r["gear_ratio"] else 0.0 for r in rows])
    return t, eng, tur, tail, rei, gr


def find_1st_gear_events(t, eng, tur, tail, rei, gr):
    """Return list of (slice, sr_array, k_array) for each 1st-gear block."""
    in_1st = (gr >= 4.0) & (gr <= 5.5) & (tail > 5) & (eng > 400) & (rei > 10)
    changes = np.diff(in_1st.astype(int))
    starts  = list(np.where(changes == 1)[0] + 1)
    ends    = list(np.where(changes == -1)[0] + 1)
    if in_1st[0]:  starts.insert(0, 0)
    if in_1st[-1]: ends.append(len(t))

    events = []
    for s, e in zip(starts, ends):
        sl = slice(s, e)
        e_rpm = eng[sl]
        t_rpm = tur[sl]
        r_sig = rei[sl].astype(float)

        sr = np.where(e_rpm > 0, t_rpm / e_rpm, np.nan)

        # Keep only the ascending (takeup) phase: SR < 1.05 & reinf > 10
        valid = (~np.isnan(sr)) & (sr < 1.05) & (r_sig > 10) & (e_rpm > 400)
        if valid.sum() < 30:
            continue

        k = np.where(valid & (r_sig > 0), e_rpm / np.sqrt(r_sig), np.nan)

        # Require at least 0.15 SR range
        sr_valid = sr[valid]
        if sr_valid.max() - sr_valid.min() < 0.15:
            continue

        events.append({
            "t_start": t[s],
            "sr":      sr,
            "k":       k,
            "valid":   valid,
            "eng":     e_rpm,
            "rei":     r_sig,
        })

    return events


def bin_k_vs_sr(events, n_bins=20):
    """Bin all valid (SR, K) pairs and return mean ± std per bin."""
    all_sr, all_k = [], []
    for ev in events:
        v = ev["valid"]
        all_sr.extend(ev["sr"][v].tolist())
        all_k.extend(ev["k"][v].tolist())

    all_sr = np.array(all_sr)
    all_k  = np.array(all_k)

    # Remove NaN/inf
    ok = np.isfinite(all_sr) & np.isfinite(all_k) & (all_k > 0)
    all_sr, all_k = all_sr[ok], all_k[ok]

    edges  = np.linspace(0.0, 1.05, n_bins + 1)
    centres, means, stds, counts = [], [], [], []
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (all_sr >= lo) & (all_sr < hi)
        n = mask.sum()
        if n < 5:
            continue
        centres.append((lo + hi) / 2)
        means.append(all_k[mask].mean())
        stds.append(all_k[mask].std())
        counts.append(n)

    return np.array(centres), np.array(means), np.array(stds), np.array(counts)


def save_table(centres, means, stds, counts, out_csv: str):
    with open(out_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["sr_centre", "k_mean", "k_std", "n_points"])
        for c, m, s, n in zip(centres, means, stds, counts):
            w.writerow([f"{c:.4f}", f"{m:.3f}", f"{s:.3f}", n])
    print(f"K-table saved → {out_csv}")


def print_table(centres, means, stds, counts):
    print(f"\n{'SR centre':>10}  {'K mean':>8}  {'K std':>7}  {'N pts':>7}")
    print("-" * 40)
    for c, m, s, n in zip(centres, means, stds, counts):
        print(f"{c:>10.3f}  {m:>8.2f}  {s:>7.2f}  {n:>7,}")


def plot(events, centres, means, stds, out_png: str):
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle(
        "Torque Converter K-Characteristic  (1st gear takeup events)",
        fontsize=12, fontweight="bold"
    )

    cmap   = plt.cm.viridis
    colors = [cmap(i / max(len(events) - 1, 1)) for i in range(len(events))]

    # ── left: K vs SR scatter for every event ─────────────────────────────────
    ax = axes[0]
    for ev, col in zip(events, colors):
        v = ev["valid"]
        ax.scatter(ev["sr"][v], ev["k"][v],
                   s=1.5, alpha=0.25, color=col, linewidths=0)

    # Mean K-line with ±1σ band
    ax.fill_between(centres, means - stds, means + stds,
                    alpha=0.25, color="red", label="±1σ band")
    ax.plot(centres, means, "r-", linewidth=2.0, label="Mean K-line")

    ax.set_xlabel("Speed ratio  SR = turbine / engine", fontsize=10)
    ax.set_ylabel("K = engine_rpm / √reinf_signal", fontsize=10)
    ax.set_title(f"K vs SR  ({len(events)} events)")
    ax.legend(fontsize=9)
    ax.grid(True, linewidth=0.3)
    ax.set_xlim(0, 1.05)

    # ── right: a handful of individual events coloured by engine RPM ──────────
    ax = axes[1]
    # Pick the events with widest SR range for illustration
    top = sorted(events,
                 key=lambda e: (e["sr"][e["valid"]].max() - e["sr"][e["valid"]].min()),
                 reverse=True)[:12]
    for i, ev in enumerate(top):
        v  = ev["valid"]
        sc = ax.scatter(ev["sr"][v], ev["k"][v],
                        c=ev["eng"][v], cmap="plasma",
                        s=2, alpha=0.6, linewidths=0,
                        vmin=500, vmax=4000)
    ax.plot(centres, means, "r-", linewidth=2.0, label="Mean K-line", zorder=5)
    cbar = fig.colorbar(sc, ax=ax, pad=0.02)
    cbar.set_label("Engine RPM", fontsize=8)
    ax.set_xlabel("Speed ratio  SR = turbine / engine", fontsize=10)
    ax.set_ylabel("K = engine_rpm / √reinf_signal", fontsize=10)
    ax.set_title("Top 12 events by SR coverage  (colour = engine RPM)")
    ax.legend(fontsize=9)
    ax.grid(True, linewidth=0.3)
    ax.set_xlim(0, 1.05)

    fig.tight_layout()
    fig.savefig(out_png, dpi=150)
    print(f"Plot saved → {out_png}")


if __name__ == "__main__":
    csv_path = sys.argv[1] if len(sys.argv) > 1 else "torque_converter_190250.csv"
    stem     = Path(csv_path).stem
    out_png  = f"k_characteristic_{stem}.png"
    out_csv  = f"k_characteristic_{stem}.csv"

    t, eng, tur, tail, rei, gr = load(csv_path)
    events = find_1st_gear_events(t, eng, tur, tail, rei, gr)
    print(f"1st gear takeup events used: {len(events)}")

    centres, means, stds, counts = bin_k_vs_sr(events)
    print_table(centres, means, stds, counts)
    save_table(centres, means, stds, counts, out_csv)
    plot(events, centres, means, stds, out_png)
