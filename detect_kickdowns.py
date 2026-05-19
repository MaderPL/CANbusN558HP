#!/usr/bin/env python3
"""
Detect kickdown events in torque-converter CSV logs (BMW F30 335i, ZF 8HP45).

A "kickdown" is the driver flooring the pedal in an automatic to force a
power downshift while already driving. The CSVs have no pedal channel, so
kickdown is inferred kinematically from gear ratio, engine RPM, and tailshaft
RPM (and contextually from the 0x08F transmission reinforcement signal).

Criteria
========

A candidate event must satisfy:

  - Vehicle moving (tailshaft_rpm >= 400 at start and end of the shift).
  - One or more rapid downshifts: smoothed gear ratio steps from a lower-
    ratio gear to a higher-ratio one. Consecutive downshifts within 2 s are
    merged into a single event — the TCU often cascades 7→6→5→4 under one
    pedal command.
  - Tailshaft accelerates during the event (Δtail >= 100 rpm in a 2.5 s
    window after shift end) — this rejects coast-down / deceleration
    downshifts, which are by far the most common downshift type on the bus.

The candidate is then classified by intensity:

  HIGH confidence (kickdown):
      gears_skipped >= 2  AND  eng_rpm peak >= 3000

  MEDIUM confidence (likely kickdown / hard tip-in):
      gears_skipped >= 2  AND  eng_rpm peak >= 2200
      OR  gears_skipped == 1 AND eng_rpm peak >= 3500 AND reinf_peak >= 70

  LOW confidence (firm tip-in / part-throttle downshift):
      everything else that still passed the candidate criteria

8HP / 8HP45 gear ratios:
  1: 4.71, 2: 3.14, 3: 2.10, 4: 1.67, 5: 1.29, 6: 1.00, 7: 0.84, 8: 0.67
"""

import csv
import sys
from pathlib import Path

GEAR_RATIOS = {
    1: 4.71, 2: 3.14, 3: 2.10, 4: 1.67,
    5: 1.29, 6: 1.00, 7: 0.84, 8: 0.67,
}

# Candidate gates
TAIL_MOVING_MIN     = 400
RATIO_TOL           = 0.08
RUN_MIN_SAMPLES     = 15
SHIFT_MAX_GAP_S     = 4.0
MERGE_GAP_S         = 5.0  # kickdown cascades can pause briefly in an intermediate gear
ACCEL_WINDOW_S      = 2.5
# A kickdown leaves tailshaft at least as high as it was before the shift,
# unlike a coast-down downshift where tailshaft is monotonically falling.
TAIL_NOT_DECEL_MIN  = -50   # rpm — tail_after_peak − tail_before must exceed this

# Tier thresholds (intensity classification)
HIGH_SKIP, HIGH_ENG = 2, 3000      # multi-gear cascade pulling to a high peak
MED_SKIP,  MED_ENG  = 2, 2200      # multi-gear cascade, moderate peak
SINGLE_SKIP_ENG     = 3500         # single-gear kickdown when revs are high


def gear_for_ratio(ratio):
    if ratio is None or ratio <= 0:
        return None
    best_g, best_err = None, 1e9
    for g, r in GEAR_RATIOS.items():
        err = abs(ratio - r) / r
        if err < best_err:
            best_err, best_g = err, g
    return best_g if best_err < RATIO_TOL else None


def load(csv_path):
    rows = []
    with open(csv_path) as f:
        r = csv.DictReader(f)
        for row in r:
            try:
                t = float(row["timestamp_s"])
                reinf = int(row["reinf_signal"])
                eng = float(row["engine_rpm"])
                tail = int(row["tailshaft_rpm"])
                gr = float(row["gear_ratio"]) if row["gear_ratio"] else None
            except (ValueError, KeyError):
                continue
            rows.append((t, reinf, eng, tail, gr))
    return rows


def stable_runs(gears):
    n = len(gears)
    i = 0
    while i < n:
        g = gears[i]
        if g is None:
            i += 1
            continue
        j = i
        while j < n and gears[j] == g:
            j += 1
        if j - i >= RUN_MIN_SAMPLES:
            yield (g, i, j - 1)
        i = j


def classify(skip, eng_pk, reinf_pk):
    if skip >= HIGH_SKIP and eng_pk >= HIGH_ENG:
        return "HIGH"
    if skip >= MED_SKIP and eng_pk >= MED_ENG:
        return "MED"
    if skip == 1 and eng_pk >= SINGLE_SKIP_ENG:
        return "MED"
    return "LOW"


def detect(csv_path):
    rows = load(csv_path)
    if not rows:
        return []
    gears = [gear_for_ratio(r[4]) for r in rows]
    runs = list(stable_runs(gears))
    if len(runs) < 2:
        return []

    # Raw downshift transitions
    shifts = []
    for (g_prev, _s_prev, e_prev), (g_next, s_next, _e_next) in zip(runs, runs[1:]):
        if g_next >= g_prev:
            continue
        if rows[s_next][0] - rows[e_prev][0] > SHIFT_MAX_GAP_S:
            continue
        if rows[e_prev][3] < TAIL_MOVING_MIN or rows[s_next][3] < TAIL_MOVING_MIN:
            continue
        shifts.append((g_prev, g_next, e_prev, s_next))
    if not shifts:
        return []

    # Merge consecutive downshifts within MERGE_GAP_S
    merged = []
    cur = list(shifts[0])
    for g_prev, g_next, e_prev, s_next in shifts[1:]:
        last_t_end = rows[cur[3]][0]
        if rows[e_prev][0] - last_t_end <= MERGE_GAP_S and g_next < cur[1]:
            cur[1] = g_next
            cur[3] = s_next
        else:
            merged.append(tuple(cur))
            cur = [g_prev, g_next, e_prev, s_next]
    merged.append(tuple(cur))

    n = len(rows)
    events = []
    for g_from, g_to, idx_from_end, idx_to_start in merged:
        t_start = rows[idx_from_end][0]
        t_end = rows[idx_to_start][0]
        eng_pk = rows[idx_to_start][2]
        tail_pk = rows[idx_to_start][3]
        reinf_pk = 0
        t_lo, t_hi = t_start - 0.5, t_end + ACCEL_WINDOW_S
        k = max(0, idx_from_end - 50)
        while k < n and rows[k][0] < t_lo:
            k += 1
        while k < n and rows[k][0] <= t_hi:
            reinf_pk = max(reinf_pk, rows[k][1])
            if rows[k][0] >= t_end:
                tail_pk = max(tail_pk, rows[k][3])
                eng_pk = max(eng_pk, rows[k][2])
            k += 1
        tail_after = rows[idx_to_start][3]
        tail_delta = tail_pk - tail_after
        # Compare against the pre-shift tailshaft: a kickdown does not
        # decelerate the vehicle, a coast-down does.
        tail_before = rows[idx_from_end][3]
        if (tail_pk - tail_before) < TAIL_NOT_DECEL_MIN:
            continue
        skip = g_from - g_to
        tier = classify(skip, eng_pk, reinf_pk)
        events.append({
            "tier": tier,
            "t_start": t_start,
            "t_end": t_end,
            "duration_s": round(t_end - t_start, 3),
            "gear_from": g_from,
            "gear_to": g_to,
            "gears_skipped": skip,
            "tail_before": rows[idx_from_end][3],
            "tail_after_peak": tail_pk,
            "tail_accel_delta": tail_delta,
            "eng_rpm_before": round(rows[idx_from_end][2], 0),
            "eng_rpm_after_peak": round(eng_pk, 0),
            "reinf_peak": reinf_pk,
        })
    return events


def hhmmss(t_offset, base):
    h, m, s = int(base[0:2]), int(base[2:4]), int(base[4:6])
    total = h*3600 + m*60 + s + int(t_offset)
    return f"{(total//3600)%24:02d}:{(total//60)%60:02d}:{total%60:02d}"


def main():
    files = sys.argv[1:] or [
        "torque_converter_190250.csv",
        "torque_converter_194107.csv",
        "torque_converter_195154.csv",
    ]
    verbose = "--all" in sys.argv
    grand_high = grand_med = grand_low = 0
    for fn in files:
        if fn == "--all":
            continue
        stem = Path(fn).stem
        base = stem.split("_")[-1]
        if not (len(base) == 6 and base.isdigit()):
            base = "000000"
        print(f"\n=== {fn} (log start ≈ {base[:2]}:{base[2:4]}:{base[4:6]}) ===")
        evs = detect(fn)
        # By default only show HIGH and MED (true kickdowns). Pass --all to
        # include LOW candidates (mostly part-throttle / coast-down downshifts).
        shown = [e for e in evs if verbose or e["tier"] in ("HIGH", "MED")]
        if not shown:
            print("  (no kickdowns detected)")
        else:
            print(
                f"  {'#':>3}  {'tier':>4}  {'t(s)':>9}  {'wallclk':>8}  "
                f"{'dur':>5}  {'shift':>5}  {'sk':>3}  "
                f"{'tailB':>5}  {'tailPk':>6}  {'Δtail':>5}  "
                f"{'engB':>5}  {'engPk':>5}  {'reinf':>5}"
            )
            for k, e in enumerate(shown, 1):
                print(
                    f"  {k:>3}  {e['tier']:>4}  {e['t_start']:>9.2f}  "
                    f"{hhmmss(e['t_start'], base):>8}  {e['duration_s']:>5.2f}  "
                    f"{e['gear_from']}→{e['gear_to']:<3}  {e['gears_skipped']:>3}  "
                    f"{e['tail_before']:>5}  {e['tail_after_peak']:>6}  "
                    f"{e['tail_accel_delta']:>5}  "
                    f"{int(e['eng_rpm_before']):>5}  "
                    f"{int(e['eng_rpm_after_peak']):>5}  "
                    f"{e['reinf_peak']:>5}"
                )
        nh = sum(1 for e in evs if e["tier"] == "HIGH")
        nm = sum(1 for e in evs if e["tier"] == "MED")
        nl = sum(1 for e in evs if e["tier"] == "LOW")
        print(f"  summary: {nh} HIGH, {nm} MED, {nl} LOW")
        grand_high += nh; grand_med += nm; grand_low += nl
    print(f"\nTOTAL across files:  {grand_high} HIGH-confidence kickdowns,  "
          f"{grand_med} medium,  {grand_low} low candidates "
          f"(use --all to list LOW candidates).")


if __name__ == "__main__":
    main()
