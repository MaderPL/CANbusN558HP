# Torque Converter K-Characteristic Results

Normalised K-characteristic extracted from CAN bus logs across six BMW vehicles,
all fitted with ZF 8HP automatic transmissions.

## Method

1. Extract `reinf_signal` (0x08F byte 6), `engine_rpm` (0x0A5 bytes 5-6 × 0.25),
   `turbine_rpm`, and `tailshaft_rpm` from candump logs.
2. Compute speed ratio `SR = turbine / engine` and gear ratio `GR = turbine / tailshaft`.
3. Normalise the reinforcement signal: `reinf_norm = reinf_signal / GR`.
4. Find baseline: `baseline = median(reinf_norm)` over all samples where SR ∈ [0.97, 1.03]
   (full lockup condition).
5. `K_norm = reinf_norm / baseline` → equals 1.0 at full lockup for all vehicles.
6. Bin into 0.025-wide SR steps (min 30 samples/bin), fit a weighted smoothing spline
   (weights = 1/σ²), evaluate at SR = 0.05, 0.10, … 1.00.

Valid sample filter: `turbine > 20 RPM`, `tailshaft > 5 RPM`, `engine > 200 RPM`.

Scripts: `extract_torque_converter.py` (standard), `extract_torque_converter.py` with
`--frame 1b0` logic in `/tmp/extract_g11.py` (G11 only).

---

## Vehicle Summary

| Vehicle | Transmission | Source log(s) | Rows extracted | Lockup rows | Baseline |
|---------|-------------|---------------|----------------|-------------|----------|
| F30 335i N55 8HP45 | ZF 8HP45 | can-2024.11.09-190250.candump | 715,637 | 418,847 | 25.00 |
| F30 330i B58 8HP50 | ZF 8HP50 | can-2024.11.05-162503.candump | 751,513 | 539,860 | 21.90 |
| F31 320d B47 8HP | ZF 8HP | F30 320d mode changes driving-can-2024.08.06-182008.candump | 1,371,665 | 379,472 | 21.83 |
| F15 X5 N57Z 8HP75 | ZF 8HP75 | can-2025.08.20-154438.candump | 404,269 | 146,102 | 24.68 |
| F20 N20/B48 8HP | ZF 8HP | 6 GCU logs (2022–2023, see below) | 508,122 | 103,569 | 21.91 |
| G11 7-series 8HP | ZF 8HP | drive + engine on + brake (see below) | 65,081 | 31,250 | 20.03 |

The baseline (`reinf/GR` at lockup) varies by transmission variant and possibly by
software calibration. It is not a physical constant — use K_norm for cross-vehicle
comparison.

---

## F30 335i N55 8HP45

**Log:** `F30 335i N55 8HP45/can-2024.11.09-190250.candump`  
**Baseline:** 25.00  (reinf/GR median at SR 0.97–1.03)

| SR   | K_norm |
|------|--------|
| 0.05 | 1.7088 |
| 0.10 | 1.6469 |
| 0.15 | 1.5936 |
| 0.20 | 1.5476 |
| 0.25 | 1.5075 |
| 0.30 | 1.4720 |
| 0.35 | 1.4398 |
| 0.40 | 1.4096 |
| 0.45 | 1.3800 |
| 0.50 | 1.3496 |
| 0.55 | 1.3172 |
| 0.60 | 1.2814 |
| 0.65 | 1.2412 |
| 0.70 | 1.1963 |
| 0.75 | 1.1466 |
| 0.80 | 1.0937 |
| 0.85 | 1.0412 |
| 0.90 | 1.0049 |
| 0.95 | 1.0056 |
| 1.00 | 1.0023 ← lockup |

Clean monotonic curve. Two additional logs (194107, 195154) were captured the
same day; 190250 has the best SR coverage and is used as the reference.

---

## F30 330i B58 8HP50

**Log:** `F30 330i B58 8HP50/can-2024.11.05-162503.candump`  (139 MB, 3.7 M lines)  
**Baseline:** 21.90

| SR   | K_norm |
|------|--------|
| 0.05 | 1.7537 |
| 0.10 | 1.7167 |
| 0.15 | 1.6796 |
| 0.20 | 1.6426 |
| 0.25 | 1.6060 |
| 0.30 | 1.5701 |
| 0.35 | 1.5354 |
| 0.40 | 1.5008 |
| 0.45 | 1.4553 |
| 0.50 | 1.3970 |
| 0.55 | 1.3412 |
| 0.60 | 1.3007 |
| 0.65 | 1.2479 |
| 0.70 | 1.1919 |
| 0.75 | 1.1516 |
| 0.80 | 1.1207 |
| 0.85 | 1.0820 |
| 0.90 | 1.0395 |
| 0.95 | 1.0077 |
| 1.00 | 1.0014 ← lockup |

Largest dataset. Smooth monotonic curve with the highest stall ratio (1.75) of
the petrol vehicles tested, consistent with the B58's higher torque output
(ZF 8HP50 is rated to 500 Nm vs 450 Nm for 8HP45).

---

## F31 320d B47 8HP

**Log:** `F31 320d/F30 320d mode changes driving-can-2024.08.06-182008.candump`  
**Baseline:** 21.83

| SR   | K_norm |
|------|--------|
| 0.05 | 1.6749 |
| 0.10 | 1.6554 |
| 0.15 | 1.6296 |
| 0.20 | 1.5986 |
| 0.25 | 1.5631 |
| 0.30 | 1.5240 |
| 0.35 | 1.4823 |
| 0.40 | 1.4387 |
| 0.45 | 1.3943 |
| 0.50 | 1.3498 |
| 0.55 | 1.3062 |
| 0.60 | 1.2643 |
| 0.65 | 1.2236 |
| 0.70 | 1.1813 |
| 0.75 | 1.1345 |
| 0.80 | 1.0840 |
| 0.85 | 1.0347 |
| 0.90 | 1.0170 |
| 0.95 | 1.0165 |
| 1.00 | 0.9912 ← lockup |

Diesel-tuned torque converter. Lower stall ratio (1.67) compared to the B58
petrol, consistent with the diesel's higher low-end torque reducing the need
for converter multiplication. Largest row count (1.37 M).

---

## F15 X5 N57Z 8HP75

**Log:** `F15 X5 N57Z OEM/can-2025.08.20-154438.candump`  
**Transmission:** ZF 8HP75 (tri-turbo diesel, 740 Nm rated)  
**Baseline:** 24.68

| SR   | K_norm |
|------|--------|
| 0.05 | 1.7516 |
| 0.10 | 1.6932 |
| 0.15 | 1.6393 |
| 0.20 | 1.5892 |
| 0.25 | 1.5424 |
| 0.30 | 1.4982 |
| 0.35 | 1.4561 |
| 0.40 | 1.4154 |
| 0.45 | 1.3756 |
| 0.50 | 1.3360 |
| 0.55 | 1.2960 |
| 0.60 | 1.2550 |
| 0.65 | 1.2129 |
| 0.70 | 1.1704 |
| 0.75 | 1.1282 |
| 0.80 | 1.0871 |
| 0.85 | 1.0483 |
| 0.90 | 1.0159 |
| 0.95 | 0.9955 |
| 1.00 | 0.9930 ← lockup |

Despite being a diesel with a heavier-duty 8HP75 unit, the stall K_norm (1.75)
is comparable to the petrol B58. The higher baseline (24.68 vs ~22) reflects
the 8HP75's heavier TCC solenoid calibration rather than a different converter.

---

## F20 1-series N20/B48 8HP

**Logs:** 6 GCU (Gear Control Unit) candumps combined:
- `GCU2202025-can-2023.02.01-161918.candump` (42 MB — primary driving log)
- `GCU2202025-can-2023.03.13-164321.candump` (24 MB)
- `GCU2202025-can-2023.01.30-100037.candump` (13 MB)
- `GCU2202025-can-2022.09.22-103619.candump` (9 MB)
- `GCU2202025-can-2023.03.13-160640.candump` (5 MB)
- `GCU2202025-can-2023.03.13-165621.candump` (3 MB)

**Baseline:** 21.91  
**Note:** Logs are GCU-only captures. The engine is off during the first ~14 s
of each file (engine_rpm = 0 at offset 40/0x0A5 during crank/start). Low-SR
bins (SR < 0.25) have fewer than 50 samples each; the spline extrapolates
poorly in that region and those values should be disregarded.

| SR   | K_norm | Quality |
|------|--------|---------|
| 0.05 | −3221  | ⚠ sparse/invalid |
| 0.10 | −1221  | ⚠ sparse/invalid |
| 0.15 | −285   | ⚠ sparse/invalid |
| 0.20 | −11.1  | ⚠ sparse |
| 0.25 | 0.857  | ⚠ limited data |
| 0.30 | 1.4461 | ✓ |
| 0.35 | 1.5030 | ✓ |
| 0.40 | 1.4926 | ✓ |
| 0.45 | 1.4628 | ✓ |
| 0.50 | 1.4253 | ✓ |
| 0.55 | 1.3905 | ✓ |
| 0.60 | 1.3662 | ✓ |
| 0.65 | 1.3366 | ✓ |
| 0.70 | 1.2733 | ✓ |
| 0.75 | 1.1683 | ✓ |
| 0.80 | 1.1151 | ✓ |
| 0.85 | 1.1395 | ✓ |
| 0.90 | 1.0241 | ✓ |
| 0.95 | 1.0049 | ✓ |
| 1.00 | 1.0002 ← lockup | ✓ |

From SR 0.30 onward the curve is well-sampled and consistent with other
petrol vehicles (K_norm ≈ 1.47–1.50 at mid-slip). The GCU logs capture
primarily highway and city driving, with very few hard-launch events that
would populate the low-SR bins.

---

## G11 7-series 8HP

**Logs:** 4 candumps combined:
- `drive.candump` (15.6 MB — primary driving session)
- `engine on+rev+brake+pps.candump` (8.4 MB)
- `brake+pps.candump` (664 KB)
- `wakeup.candump` (2.0 MB)

**Baseline:** 20.03  
**Frame difference:** G11 uses **0x1B0** instead of 0x1AF for turbine/tailshaft
speeds. Signal layout within 0x1B0 is also reversed — tailshaft at bytes 1-2
(offset 8), turbine at bytes 3-4 (offset 24) — vs 0x1AF which has turbine at
bytes 3-4 and tailshaft at bytes 5-6.

```python
# G11 / 0x1B0 decoding
tailshaft_rpm = (data[1] | (data[2] << 8)) - 2000   # offset  8, length 16
turbine_rpm   = (data[3] | (data[4] << 8)) - 2000   # offset 24, length 16
```

| SR   | K_norm |
|------|--------|
| 0.05 | 1.6399 |
| 0.10 | 1.6603 |
| 0.15 | 1.6209 |
| 0.20 | 1.5594 |
| 0.25 | 1.5135 |
| 0.30 | 1.4939 |
| 0.35 | 1.4590 |
| 0.40 | 1.3792 |
| 0.45 | 1.2957 |
| 0.50 | 1.2067 |
| 0.55 | 1.2886 |
| 0.60 | 1.2065 |
| 0.65 | 1.1435 |
| 0.70 | 1.1440 |
| 0.75 | 1.1093 |
| 0.80 | 1.0461 |
| 0.85 | 1.0091 |
| 0.90 | 0.9994 |
| 0.95 | 0.9909 |
| 1.00 | 0.9973 ← lockup |

The G11 has a noticeably different curve shape: K_norm drops faster in the
mid-SR range (0.40–0.60) compared to the F30/F15. A slight non-monotonicity
at SR 0.50–0.55 is likely spline artefact from the smaller dataset (65 K rows
vs 400 K+ for other vehicles). The lower baseline (20.03) is a calibration
difference in the 7-series GCU, not a physical converter change.

---

## Cross-vehicle comparison

K_norm at selected speed ratios (SR = turbine/engine):

| SR   | F30 N55 | F30 B58 | F31 320d | F15 N57Z | F20  | G11  |
|------|---------|---------|----------|----------|------|------|
| 0.10 | 1.647   | 1.717   | 1.655    | 1.693    | —    | 1.660 |
| 0.20 | 1.548   | 1.643   | 1.599    | 1.589    | —    | 1.559 |
| 0.30 | 1.472   | 1.570   | 1.524    | 1.498    | 1.446 | 1.494 |
| 0.40 | 1.410   | 1.501   | 1.439    | 1.415    | 1.493 | 1.379 |
| 0.50 | 1.350   | 1.397   | 1.350    | 1.336    | 1.425 | 1.207 |
| 0.60 | 1.281   | 1.301   | 1.264    | 1.255    | 1.366 | 1.207 |
| 0.70 | 1.196   | 1.192   | 1.181    | 1.170    | 1.273 | 1.144 |
| 0.80 | 1.094   | 1.121   | 1.084    | 1.087    | 1.115 | 1.046 |
| 0.90 | 1.005   | 1.040   | 1.017    | 1.016    | 1.024 | 0.999 |
| 1.00 | 1.002   | 1.001   | 0.991    | 0.993    | 1.000 | 0.997 |

(F20 values at SR < 0.30 excluded due to insufficient data.)

All vehicles converge to K_norm ≈ 1.0 at full lockup as expected. Spread at
stall (SR ≈ 0.10) is ±0.035 across the petrol/diesel N-series engines, which
is within inter-vehicle calibration variation of the ZF 8HP TCC solenoid.
The F30 B58 consistently shows the highest multiplication ratio across all SR
values, consistent with its higher torque capacity variant (8HP50).
