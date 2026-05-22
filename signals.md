# BMW PT-CAN Signal Documentation

**Primary vehicle:** WBA3A9C5XFKW74642 (F30 BMW 3-series, N55/N558HP engine, ZF 8HP45 transmission)  
**DME:** Bosch ME17.2  
**Encoding:** Little-endian (Intel byte order), ARM Cortex-M7 GCC bitfield-compatible  
**Differential ratio:** 3.15 (F30 335i N55 — see measured values in 0x254 section)  
**Wheel circumference:** ~2.09 m (225/45R17)  
**Bus:** PT-CAN (powertrain CAN)

## Cross-vehicle validation summary

| Vehicle | Engine | Trans | 0x0A5–0x0A7 | 0x145 | 0x1AF/0x1B0 | CAN ID format |
|---------|--------|-------|------------|-------|-------------|---------------|
| F30 335i N55 (primary) | N55 petrol | ZF 8HP45 | ✓ | active | 0x1AF ✓ 6-gear | 3-digit padded (0A6) |
| F30 335i N55 8HP45 | N55 petrol | ZF 8HP45 | ✓ | active | 0x1AF ✓ 8-gear | 3-digit padded |
| F30 330i B58 | B58 petrol | ZF 8HP50 | ✓ | active | 0x1AF ✓ 8-gear | 3-digit padded |
| F15 X5 N57Z | N57Z diesel | ZF 8HP | ✓ | **SNA (0xFFFF)** | 0x1AF ✓ | 3-digit padded |
| F20 | petrol | — | ✓ (can1) | active | 0x1AF (can2) | **unpadded (A6)** |
| F31 320d | N47 diesel | ZF 8HP | ✓ | **SNA (0xFFFF)** | 0x1AF ✓ 8-gear | **unpadded (A6)** |
| G11 7-series | diesel | ZF 8HP | ✓ | **SNA (0xFFFF)** | **0x1B0** ✓ | 3-digit padded |

Signal presence by frame:

| Frame | F30 N55 | F30 B58 | F31 320d | F15 N57Z | F20 | G11 |
|-------|---------|---------|----------|----------|-----|-----|
| 0x08F (reinf/output torque) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 0x0A5 (engine RPM/torque) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 0x0A6 (torque coord) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 0x0A7 (demand/drivetrain torque) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 0x145 (EGS shift ref) | ✓ active | ✓ active | **SNA** | **SNA** | ✓ active | **SNA** |
| 0x1AF (turbine/tailshaft) | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| 0x1B0 (turbine/tailshaft) | — | — | — | — | — | ✓ |

**Key cross-vehicle findings:**
- 0x145 is **petrol-only** — all diesel vehicles (N57Z, N47, G11) send 0xFFFF (SNA).
- F20 bus assignment depends on recording setup: in single-bus captures all PT signals (0x0A5–0x0A7, 0x145, 0x1AF) appear on can1; in multi-bus captures 0x145 and torque frames appear on can2, with can1 carrying a different bus. Some 2023.03.13 F20 files contain no PT-CAN IDs at all (K-CAN/body bus only).
- F20 and F31 320d candumps use **unpadded hex frame IDs** (e.g. `A6` not `0A6`) — parsers must normalise both formats.
- G11 uses **0x1B0** instead of 0x1AF, with tailshaft and turbine signals in reversed byte order.

Signal extraction formula:
```python
def le_bits(data: bytes, start_bit: int, length: int) -> int:
    return (int.from_bytes(data, 'little') >> start_bit) & ((1 << length) - 1)
```

---

## Torque encoding (shared by 0x0A5, 0x0A6, 0x0A7)

All torque signals use unsigned 12-bit raw values with a common offset:

```
Nm = (raw_unsigned − 1999) / 2
raw_unsigned = Nm × 2 + 1999
```

Offset 1999 is derived from the idle constraint: `T_Act + T_Loss ≈ 0 Nm` at idle,  
giving `mean(T_Act_raw + T_Loss_raw) = 3998 → offset = 1999`.

| Raw value | Nm    | Meaning |
|-----------|-------|---------|
| 1999      | 0     | Zero torque |
| 2867      | 434   | Max engine torque (calibration ceiling) |
| 2097      | +49   | T_Act at idle (~650 RPM) |
| 1901      | −49   | T_Loss at idle (friction) |
| ~2200–2400 | 100–200 | Typical part-load to full-load range |

---

## Frame 0x0A5 — Engine Speed & Torque

Rate: ~100 Hz

| Signal          | Offset (bit) | Length (bit) | Scaling           | Unit | Description |
|-----------------|-------------|--------------|-------------------|------|-------------|
| T1_Torque_Actual | 16         | 12           | Nm = (raw−1999)/2 | Nm   | Actual indicated engine torque. Matches A6 T_Act closely (r = 0.971). |
| T2_Torque_Setpoint | 28      | 12           | Nm = (raw−1999)/2 | Nm   | Rate-limited torque setpoint. Identical to T1 in 95.6% of frames; lags behind T1 during rapid transients. During torque-coordination interventions T2 can diverge widely from T1. |
| RPM             | 40          | 16           | rpm = raw × 0.25  | rpm  | Engine speed. Confirmed on N55 and B58. |

---

## Frame 0x0A6 — Torque Coordination

Rate: ~100 Hz

| Signal  | Offset (bit) | Length (bit) | Scaling           | Unit | Description |
|---------|-------------|--------------|-------------------|------|-------------|
| T_Loss  | 12          | 12           | Nm = (raw−1999)/2 | Nm   | Friction and pumping loss torque. Always negative. Minimum magnitude ≈ −17 Nm at 2000–3000 RPM; increases to −49 Nm at idle and −26 Nm at high RPM. |
| T_Max   | 24          | 12           | Nm = (raw−1999)/2 | Nm   | Maximum engine torque calibration limit. Constant at 434 Nm (raw 2867) during normal operation; reduces to ≈383 Nm at idle. |
| T_Cut   | 36          | 12           | Nm = (raw−1999)/2 | Nm   | Torque cut / limiter setpoint. Near 0 Nm at light load; rises to +40–50 Nm at high pedal during active torque coordination; negative values indicate active cut intervention. |
| T_Act   | 48          | 12           | Nm = (raw−1999)/2 | Nm   | Actual indicated engine torque. Primary torque output signal; equals A5 T1 (r = 0.971). |

### Representative Nm values

| Condition     | RPM  | T_Loss | T_Max | T_Cut | T_Act | Net shaft |
|--------------|------|--------|-------|-------|-------|-----------|
| Idle         | 660  | −49    | 383   | −2    | 49    | 0         |
| Light cruise | 2000 | −17    | 434   | +2    | 80    | 64        |
| WOT 3000 RPM | 3000 | −18    | 434   | +28   | 149   | 134       |
| 80% pedal    | 2600 | −23    | 434   | +44   | 185   | 163       |

Net shaft torque = T_Act + T_Loss (T_Loss is already negative).

### Friction model (T_Loss vs RPM)

| RPM range  | Mean T_Loss (Nm) |
|-----------|-----------------|
| 500–999   | −49             |
| 1000–1499 | −34             |
| 1500–1999 | −26             |
| 2000–2999 | −17             |
| 3000–3499 | −18             |
| 3500–3999 | −21             |
| 4000–4999 | −26             |

**Cross-vehicle notes:**
- **F30 B58 (petrol):** identical decoding; T_Max mode = 445 Nm (vs 434 Nm on N55). Peaks seen at 649 Nm suggest a tuned engine.
- **F31 320d (diesel):** T_Loss range −66 to −22.5 Nm; T_Max bimodal at ~236 Nm and ~390–400 Nm. T_Act peaks at 403 Nm. Decoding formula valid.
- **F15 X5 N57Z (diesel):** T_Max bimodal at ~322 Nm and ~750 Nm. Treat T_Max / T_Cut with caution for N57Z.

---

## Frame 0x0A7 — Torque & Drivetrain Signal

Rate: ~50 Hz  
Frame length: 7 bytes.

| Signal   | Offset (bit) | Length (bit) | Scaling                | Unit | Description |
|----------|-------------|--------------|------------------------|------|-------------|
| T_Demand | 12          | 12           | Nm = (raw−1999)/2      | Nm   | Driver demand torque (Fahrerwunschmoment). The raw pedal-derived torque request before coordinator limits are applied. Pearson r = 0.866 with pedal position. Runs 5–10 Nm above T_Act at mid-to-high load; lower than T_Act at idle (idle speed controller manages independently). |
| A7_Sig2  | 32          | 16           | Nm = (raw−31932)/8     | Nm   | 16-bit drivetrain torque signal. 0.125 Nm/count (4× finer resolution than 12-bit signals; offset 31932 ≈ 16 × 1999, same physical zero). Raw range observed: 31577–43242. At TC lockup, A7_dec ≈ T_Act × GR_current_gear: per-gear OLS slopes match ZF 8HP45 ratios (GR4=1.667→slope=1.713, GR8=0.667→slope=0.628) with per-gear R²=0.96–0.98 and RMSE=4–11 Nm. WOT spot-check in 4th gear shows ratio error ≤1.5%. Consistent with transmission output shaft torque or TCU wheel-side torque estimate. Shows sharp step-down transients coinciding with every upshift event. Non-zero OLS intercept at mid-load indicates an additive baseline component beyond the pure T_Act×GR product. |

### T_Demand vs T_Act comparison

| Pedal bin | T_Demand (Nm) | T_Act (Nm) | Δ (Nm) |
|-----------|--------------|------------|--------|
| 0–9%      | 6            | 12         | −6     |
| 40–49%    | 68           | 68         | 0      |
| 60–69%    | 127          | 124        | +3     |
| 80–89%    | 190          | 185        | +5     |
| 90–99%    | 171          | 166        | +5     |

At high load, T_Demand slightly exceeds T_Act — the driver requests slightly more than the coordinator delivers after applying T_Cut and T_Loss constraints.

### A7_Sig2 gear-ratio validation (TC-locked, cross-log)

Per-gear OLS of A7_dec ~ T_Act at TC lockup (slip ≥ 0.95). Slopes closely track ZF 8HP45 ratios.

| Gear | ZF GR  | Fitted slope | Mean A7/T_Act | R²     | RMSE   |
|------|--------|-------------|---------------|--------|--------|
| 4    | 1.667  | 1.713       | 1.604         | 0.976  | 7.8 Nm |
| 5    | 1.285  | 1.101       | 1.231         | 0.960  | 11.1 Nm|
| 6    | 1.000  | 1.148       | 1.077         | 0.969  | 7.1 Nm |
| 7    | 0.839  | 0.787       | 0.788         | 0.966  | 5.4 Nm |
| 8    | 0.667  | 0.628       | 0.628         | 0.980  | 4.1 Nm |

Mean A7/T_Act tracks GR to within 4–8%. At WOT in 4th gear the ratio converges to GR₄=1.667 within 0–1.5%.

### A7_Sig2 per-gear raw statistics (N55 8HP45, 49K frames)

| Gear | n     | mean raw | range         | mean decoded (Nm) |
|------|-------|----------|---------------|-------------------|
| 1st  | 1400  | 33589    | 32243–35212   | 207               |
| 2nd  | 1325  | 33016    | 31712–33805   | 136               |
| 3rd  | 6546  | 32274    | 31577–33402   | 43                |
| 4th  | 3406  | 32222    | 31670–32949   | 36                |
| 5th  | 10666 | 32129    | 31742–32816   | 25                |
| 6th  | 12485 | 32129    | 31807–32644   | 25                |
| 7th  | 1493  | 32195    | 31842–32565   | 33                |
| 8th  | 2258  | 32045    | 31872–32253   | 14                |

---

## Frame 0x8F — Effective Drivetrain Output Torque

Rate: ~200 Hz (highest rate frame observed)  
Frame structure: 8 bytes. b0 = CRC/checksum (rapidly varying). b1 = alive counter (upper nibble fixed at 0x10, lower nibble cycles). b4–b7 = constant (0x22 0x00 0x20 0x10 — likely protocol/version bytes). Only b2–b3 carry live data.

| Signal   | Offset (bit) | Length (bit) | Scaling             | Unit | Description |
|----------|-------------|--------------|---------------------|------|-------------|
| X8F_Sig1 | 16          | 16           | Nm = (raw−31932)/8  | Nm   | Effective drivetrain output torque including all active interventions. 0.125 Nm/count; same zero as A7_Sig2. Raw range: 30800–36297. At TC lockup in gears 6–8 (GR ≤ 1.0): X8F_dec ≈ T_Net × GR_current_gear within 5–9% (per-gear R²=0.91–0.95). At WOT in gear 4, WOT spot-check confirms X8F ≈ T_Net×GR to within ~10 Nm. During active torque interventions (T_Cut < −10 Nm): X8F collapses to floor (raw 32000 = 8.5 Nm) while A7_Sig2 and T_Act remain elevated — X8F reflects transmitted rather than produced torque. Floor value (raw 32000) also appears at TC stall (zero turbine speed). In gears 4–5, mean X8F/T_Net is 20–25% below GR, likely due to mixed-slip and part-load frames within each gear band. Relationship to A7_Sig2: X8F = A7_Sig2 − T_Loss×GR (i.e. A7 carries indicated engine torque×GR, X8F subtracts friction×GR to give net transmitted torque). |

### X8F_Sig1 gear-ratio validation (TC-locked, cross-log)

Per-gear mean ratio X8F_dec / T_Net vs ZF 8HP45 GR. Relationship holds tightest in overdrive/direct gears.

| Gear | ZF GR  | X8F/T_Net (194107) | X8F/T_Net (190250) | X8F~T_Net R² | Notes |
|------|--------|--------------------|--------------------|-------------|-------|
| 4    | 1.667  | 1.246              | 1.342              | 0.71–0.72   | 20–25% below GR; WOT spot-check +9 Nm of T_Net×GR |
| 5    | 1.285  | 1.008              | 1.042              | 0.82–0.95   | 19–22% below GR |
| 6    | 1.000  | 0.917              | 0.994              | 0.68–0.69   | within 0.6–8% of GR |
| 7    | 0.839  | 0.763              | 0.801              | 0.93–0.93   | within 4.5–9% of GR |
| 8    | 0.667  | 0.697              | 0.673              | 0.91–0.92   | within 0.9–4.5% of GR |

### Intervention behaviour

During active T_Cut events (torque coordination / shift clutch overlap):
- X8F_Sig1 collapses to floor (raw 32000 = 8.5 Nm), indicating zero net transmitted torque
- A7_Sig2 remains above zero, reflecting engine-side indicated torque still present
- T_Act remains elevated throughout; X8F is the only signal showing the transmission-side effect

### Observed X8F_Sig1 values

| Condition                          | Raw    | Decoded (Nm) | T_Net×GR (Nm) | Notes |
|-----------------------------------|--------|-------------|--------------|-------|
| Floor / TC stall / full torque cut | 32000  | 8.5         | —            | Default / no-transmission state |
| Idle lockup (194107, 650 RPM)      | ~32390 | ~48         | ~0 (G—)      | TC slip; tracks T_Act at stall |
| Cruise, gear 8 (~100 Nm T_Act)    | ~32580 | ~81         | ~81          | X8F ≈ T_Net×GR₈ |
| Cruise, gear 7 (~100 Nm T_Act)    | ~32720 | ~98         | ~97          | X8F ≈ T_Net×GR₇ |
| WOT, gear 4 (T_Act=101, T_Net=60) | ~32930 | ~108        | 100          | X8F ≈ T_Net×GR₄ +9 Nm |
| WOT, gear 4 (T_Act=165, T_Net=149)| ~33450 | ~183        | 248          | Partially limited; ~80% of T_Net×GR |

X8F_Sig1 is always smaller than A7_Sig2 at the same operating point. The difference A7−X8F represents the friction torque component scaled by gear ratio (T_Loss×GR).

---

## Frame 0x0A0 — Transmission Frame A (TCU → DME torque broadcast)

Rate: ~100 Hz
Direction: ZF 8HP TCU → Bosch DME (companion frame to 0x0B0).

| Signal       | Offset (bit) | Length (bit) | Scaling            | Unit | Description |
|--------------|-------------|--------------|---------------------|------|-------------|
| Counter      | 0           | 16           | —                   | —    | Rolling message counter (16-bit LE, monotonically increasing). Not a sensor signal. |
| T_Coord      | 16          | 12           | Nm = (raw−1999)/2   | Nm   | Torque coordination signal from TCU. Small range ≈ −7 to +0.5 Nm centered near 0 Nm. Slightly negative at cruise/WOT; briefly relaxes toward 0 during a shift event then returns negative. Exact role (shaft net trim or coordination headroom) unconfirmed. |
| T_SlipCap    | 32          | 12           | Nm = (raw−1999)/2   | Nm   | **TCU steady-state torque ceiling**, lowered as the torque-converter slips. High at TCC lockup (full mechanical clutch path), drops monotonically as slip ratio increases. Universal negative correlation with TC slip across F30/F31/F15/G11/F20 captures (r = −0.36 to −0.92 with slip ratio). The saturation level is vehicle-specific and matches the gearbox/clutch torque rating: 468 Nm (F31 320d 8HP45), 579 Nm (F30 N55 8HP45), 784 Nm (F15 X5, G11 8HP70), 1024 Nm (B58, F20 — i.e. saturated at 12-bit Nm max = "unlimited" flag, same pattern as B0_T1). Behaves as the steady-state companion to B0_ShiftCeil (which drops only during shifts); together they form the TCU's complete torque-coordination handshake to the DME. Independent of A5 T1 actual engine torque (r ≈ 0). |
| flag         | 44          | 4            | constant            | —    | Bits always 0xF in observed data; likely padding / "sign-extended" marker. |
| TurbineSpeed | 48          | 16           | rpm = raw − 2000    | rpm  | Torque converter turbine shaft speed. At idle/stall: raw ≈ 2000 → 0 rpm. At lockup (engine ≈ 3300 rpm): raw ≈ 5300 → turbine ≈ 3300 rpm. Slip ratio = TurbineSpeed / EngineRPM rises from 0 (stall) to ≈ 0.98+ (lockup). Staircase pattern during WOT upshifts: turbine drops at each shift and recovers in the new gear ratio. |

### Turbine speed at key operating points

| Condition       | Engine RPM | Raw value | Turbine RPM | Slip ratio |
|----------------|-----------|-----------|-------------|------------|
| Idle / stall    | 650       | ~2000     | 0           | 0.00       |
| Light cruise    | 1500      | ~3100     | 1100        | 0.73       |
| 2nd gear WOT   | 3300      | ~5263     | 3263        | 0.99       |
| Lockup (cruise) | 2400      | ~4400     | 2400        | 1.00       |

### T_SlipCap vs TC slip — cross-vehicle correlation

Pearson r between T_SlipCap and `slip_ratio = 1 − turbine/engine_rpm`:

| Vehicle              | r(T_SlipCap, slip_ratio) | mean@lockup (Nm) | mean@stall (Nm) | saturation (Nm) |
|----------------------|--------------------------|------------------|-----------------|-----------------|
| F30 N55 8HP45 335i   | −0.36                    | 531              | 334             | 579             |
| F30 B58 8HP50 340i   | −0.59                    | 972              | 308             | 1024 (max)      |
| F31 320d 8HP45       | **−0.92**                | 468              | 280             | 468             |
| F15 X5 N57Z (AWD)    | −0.78                    | 774              | 414             | 784             |
| G11 7-series         | −0.69                    | 777              | 339             | 784             |
| F20 1-series (dyno)  | −0.44                    | 885              | 299             | 1024 (max)      |

The 1024 Nm saturation in B58/F20 captures equals the 12-bit Nm encoding
ceiling (`raw=4095 → Nm=1048` saturated to display 1024) — same "unlimited"
flag pattern as `B0_T1` in frame 0x0B0.

---

## Frame 0x0B0 — Transmission Frame B (TCU → DME torque management)

Rate: ~100 Hz  
Direction: ZF 8HP45 TCU → Bosch ME17.2 DME

All torque signals use the same encoding as 0x0A5/0x0A6: `Nm = (raw − 1999) / 2`.

| Signal       | Offset (bit) | Length (bit) | Scaling           | Unit | Description |
|--------------|-------------|--------------|-------------------|------|-------------|
| AliveCounter | 0           | 16           | —                 | —    | Rolling alive counter (bytes 0–1). Confirms frame is live. |
| B0_T1        | 12          | 12           | Nm = (raw−1999)/2 | Nm   | Torque signal. Saturated at 1048 Nm (raw = 4095, bytes 2–3 = 0xFF) during normal operation — effectively an "unlimited" flag. Exact role unconfirmed. |
| B0_ShiftCeil | 24          | 12           | Nm = (raw−1999)/2 | Nm   | **TCU shift torque ceiling.** Normally 1048 Nm (unlimited). During clutch-to-clutch upshifts, drops to 108–216 Nm for the duration of the overlap phase, limiting engine torque while the outgoing clutch releases and the incoming clutch engages. Returns to 1048 Nm at the instant T_Act spikes (clutch fully locked). This is the primary torque coordination signal from TCU to DME during gear changes. |
| B0_T3        | 36          | 12           | Nm = (raw−1999)/2 | Nm   | Torque signal. Ranges from ≈ 43 Nm at idle to ≈ 26 Nm at WOT; decreases with increasing engine load. Constant across shift events (not the shift ceiling). Exact role unconfirmed. |

### B0_ShiftCeil during WOT upshifts (example: t = 1197–1215 s)

| Shift event | Pre-shift RPM | Ceiling during shift | Duration | Post-shift T_Act spike |
|-------------|--------------|----------------------|----------|------------------------|
| 2→3         | ~3300        | ~216 Nm              | ~80 ms   | yes                    |
| 3→4         | ~3200        | ~108 Nm              | ~80 ms   | yes                    |
| 4→5         | ~3000        | ~108–162 Nm          | ~80 ms   | yes                    |

The DME's T_Cut on 0x0A6 mirrors the B0_ShiftCeil request: when the ceiling drops, T_Cut also drops by a corresponding amount, confirming this is a live torque-coordination handshake.

---

## Frame 0x0D9 — Pedal Position

Rate: ~50 Hz

| Signal    | Offset (bit) | Length (bit) | Scaling        | Unit | Description |
|-----------|-------------|--------------|----------------|------|-------------|
| Pedal_Raw | 16          | 12           | % = raw/max×100 | —    | Accelerator pedal position. 0 = fully released. Max observed raw ≈ 4095. |

---

## Frame 0x145 — EGS Shift Load Reference (DME)

Frame length: 8 bytes. Rate: ~100 Hz (same as 0x0A6).

| Signal | Offset (bit) | Length (bit) | Formula | Notes |
|--------|-------------|--------------|---------|-------|
| Counter | 0 | 16 | — | Rolling 16-bit counter (bytes 0–1) |
| ShiftRef_A | 16 | 16 | See below | Primary EGS shift load reference (bytes 2–3) |
| ShiftRef_B | 32 | 16 | Identical to ShiftRef_A | Safety-redundant copy (bytes 4–5). On B58/F20 lags ShiftRef_A by exactly one CAN frame (~10 ms) during rapid deceleration — EGS firmware write-order artifact. On N55 the two are always frame-synchronous. |
| ShiftRef_C | 48 | 16 | See below | Third reference signal (bytes 6–7). Exact alias of ShiftRef_A on B58/F20; independent engine-torque-based computation on N55 F30. |

**SNA value:** 0xFFFF (65535) — transmitted by all diesel DMEs.  
**Standby/engine-off default:** ~32,000 (0x7D00) — broadcast when DME is not actively computing (engine off, fuel cut).

**Function:** Higher values → upshift sooner (economy/part-load). Lower values → hold gear (high-load/kick-down inhibit).

```python
raw145  = le_bits(data, 16, 16)   # ShiftRef_A
raw145b = le_bits(data, 32, 16)   # ShiftRef_B (redundant copy, lag possible on B58)
raw145c = le_bits(data, 48, 16)   # ShiftRef_C (alias on B58/F20, independent on N55)
```

---

### ShiftRef_A — Friction/drag-based shift reference

**Formula (per gear):**

```
ShiftRef_A = a × T_Loss + b × T_Act + c
```

`T_Loss` and `T_Act` in Nm from 0x0A6. `T_Loss` dominates; `b` is small and negative.  
All coefficients are positive for `a`; `c` increases monotonically from 1st to 8th gear (lower gear → lower base value → EGS more likely to upshift under load).

**Global cross-gear formula (TC-locked points, kph > 5):**

```python
gear_ratio = turbine_RPM / tailshaft_RPM    # from 0x1AF
ShiftRef_A ≈ -268.4 × gear_ratio + 4.30 × T_Loss - 0.28 × T_Act + 32340
# R² = 0.88, RMS = 79 counts (n = 35,115 TC-locked)
```

#### Per-gear OLS coefficients — N55/8HP45 primary log (`can-2024.11.09-194107`)

| Gear | N      | a (T_Loss) | b (T_Act) | c (intercept) | R²    | σ (counts) |
|------|--------|-----------|-----------|--------------|-------|-----------|
| 1st  | 1,368  | +56.83    | −6.95     | 32,764        | 0.763 | 231       |
| 2nd  | 1,404  | +27.50    | −2.87     | 32,314        | 0.643 |  99       |
| 3rd  | 6,825  |  +4.80    | −0.25     | 31,753        | 0.553 |  22       |
| 4th  | 3,829  |  +3.93    | −0.11     | 31,813        | 0.759 |  14       |
| 5th  | 11,024 |  +3.77    | −0.21     | 31,880        | 0.843 |   9       |
| 6th  | 12,707 |  +2.56    | −0.17     | 31,899        | 0.778 |   7       |
| 7th  | 1,677  |  +2.22    | −0.10     | 31,902        | 0.744 |   9       |
| 8th  | 2,345  |  +1.59    | −0.14     | 31,914        | 0.787 |   4       |

#### Per-gear OLS coefficients — N55/8HP45 extended log (`can-2024.11.09-190250`)

| Gear | N      | a      | b     | c      | R²    | σ  |
|------|--------|--------|-------|--------|-------|----|
| 1st  | 10,565 | +16.22 | −2.03 | 31,315 | 0.324 | 382|
| 2nd  | 10,790 | +12.48 | −0.09 | 31,634 | 0.573 | 172|
| 3rd  | 12,552 |  +5.29 | −0.18 | 31,748 | 0.606 |  44|
| 4th  | 12,527 |  +5.13 | −0.16 | 31,837 | 0.886 |  20|
| 5th  | 27,636 |  +3.51 | −0.12 | 31,863 | 0.825 |  14|
| 6th  | 29,426 |  +2.89 | −0.14 | 31,898 | 0.864 |  10|
| 7th  | 12,031 |  +1.85 | −0.05 | 31,883 | 0.790 |   8|
| 8th  | 28,192 |  +2.01 | −0.13 | 31,929 | 0.491 |  12|

#### Per-gear OLS coefficients — B58/8HP50 (`can-2024.11.05-162503`)

| Gear | N      | a      | b     | c      | R²    | σ   |
|------|--------|--------|-------|--------|-------|-----|
| 1st  | 14,902 | +12.89 | −3.10 | 31,761 | 0.923 | 112 |
| 2nd  | 24,698 |  +8.37 | −0.45 | 31,758 | 0.946 |  44 |
| 3rd  |  4,592 |  +5.29 | +0.03 | 31,837 | 0.912 |  35 |
| 4th  |  5,429 |  +3.61 | +0.01 | 31,890 | 0.271 |  40 |
| 5th  |  3,307 |  +4.35 | +0.07 | 31,952 | 0.243 |  28 |
| 6th  | 11,966 |  +1.01 | −0.03 | 31,901 | 0.115 |  12 |
| 7th  | 41,052 |  +2.18 | +0.02 | 31,948 | 0.319 |   7 |
| 8th  | 28,507 |  +1.53 | +0.01 | 31,951 | 0.863 |   6 |

#### Per-gear OLS coefficients — F20/N55 8HP (`GCU2202025-can-2023.02.01-161918`)

| Gear | N     | a      | b     | c      | R²    | σ   |
|------|-------|--------|-------|--------|-------|-----|
| 1st  | 2,235 | +13.83 | −3.53 | 31,730 | 0.941 | 111 |
| 2nd  | 2,945 |  +7.27 | −1.55 | 31,793 | 0.908 |  80 |
| 3rd  | 2,582 |  +4.05 | −0.49 | 31,858 | 0.622 | 101 |
| 4th  | 2,498 |  +3.90 | −0.18 | 31,915 | 0.432 |  60 |
| 5th  | 1,240 |  +3.11 | −0.01 | 31,896 | 0.372 |  34 |
| 6th  | 1,046 |  +3.40 | +0.07 | 31,956 | 0.099 |  27 |
| 7th  | 3,083 |  +0.09 | +0.03 | 31,875 | 0.060 |  17 |
| 8th  | 8,382 |  +1.01 | +0.10 | 31,922 | 0.841 |   5 |

#### Coefficient scaling law

The `a` coefficient scales with gear ratio as a power law: **`a ∝ gear_ratio^α`**.

Fitting `log(a) = α × log(ratio) + const` over gears 1–8:

| Log | α exponent | Pearson r |
|-----|-----------|-----------|
| N55 extended (190250) | 1.17 | 0.983 |
| B58 (162503)          | 1.17 | 0.917 |
| N55 primary (194107)  | 1.80 | 0.953 |
| F20 (161918)          | 1.74 | 0.761 |

**Interpretation:** `a` scales approximately as `1/gear_ratio` (α ≈ 1.2 in the larger N55 and B58 logs). This means `a × gear_ratio` is roughly constant — consistent with the DME applying T_Loss on the input-shaft (not the output-shaft) side: input-shaft torque = output torque / gear_ratio, so the sensitivity of the shift reference to T_Loss is inversely proportional to gear ratio.

The intercept `c` rises monotonically from ~31,750 (3rd) to ~31,950 (8th). Physical meaning: at zero T_Loss and T_Act the shift reference converges to a gear-dependent base level. Higher gears have higher base values → EGS is biased toward upshifting.

**Cross-vehicle per-gear means at cruise/steady-state:**

| Gear | N55 ref | N55 8HP ext | B58 8HP50 | F20 petrol |
|------|---------|-------------|-----------|------------|
| P/N  | ~29,381 | —           | —         | —          |
| 1st  | ~30,680 | 31,702      | 31,848    | 31,871     |
| 2nd  | ~31,301 | 31,575      | 31,865    | 31,803     |
| 3rd  | ~31,623 | 31,630      | 31,671    | 31,810     |
| 4th  | ~31,729 | 31,675      | 31,776    | 31,839     |
| 5th  | ~31,786 | 31,676      | 31,789    | 31,834     |
| 6th  | ~31,839 | 31,791      | 31,831    | 31,828     |
| 7th  | ~31,822 | 31,693      | 31,777    | 31,818     |
| 8th  | ~31,840 | 31,615      | 31,863    | 31,808     |

Gears 3–8 agree within ±250 across all petrol engines; gears 1–2 show +500–1200 counts driven by higher clutch/launch loads.

---

### ShiftRef_B — Redundant copy with write-lag

ShiftRef_B (bytes 4–5) carries the same value as ShiftRef_A and is decoded identically. Its purpose is to provide a duplicate for EGS cross-check (safety validation).

On B58/F20 firmware a write-order artifact causes ShiftRef_B to lag ShiftRef_A by **exactly one CAN frame (~10 ms)** during rapid deceleration. The EGS compares both fields; if they differ by more than a threshold the frame is considered corrupted. The 1-frame lag is within this tolerance and does not trigger a fault.

On N55 F30 both fields are written synchronously within the same DME task cycle.

---

### ShiftRef_C — Vehicle-dependent third reference

ShiftRef_C (bytes 6–7) encodes different information depending on the DME software:

#### B58/8HP50 and F20/N55: exact alias of ShiftRef_A

On these vehicles ShiftRef_C **= ShiftRef_A on every frame** (R² = 1.0, difference always 0). It appears the B58/F20 DME uses bytes 6–7 as a second write of the same value, possibly for a different EGS consumer or as a reserved placeholder that received the same assignment.

#### N55 F30: independent engine-torque-based reference

On N55 F30 ShiftRef_C is a **separate computation path** with different coefficients:

```
ShiftRef_C ≈ α × T_Act + β × T_Loss + 31820
```

Key characteristics:
- The intercept (~31,820) is **flat across gears 4–8** (variation < 30 counts), independent of gear ratio — unlike ShiftRef_A whose `c` rises with gear.
- `α ≈ 0.5–0.75` (T_Act dominant, varies by gear/log segment).
- `β` is small (< 0.3), far smaller than the `a` coefficient in ShiftRef_A.
- ShiftRef_C ≥ ShiftRef_A at all times.

**CA_diff = ShiftRef_C − ShiftRef_A** by torque state (N55 F30, gears 4–8):

| Torque state | Approx T_Act (Nm) | Approx T_Loss (Nm) | Typical CA_diff (counts) |
|--------------|------------------|---------------------|--------------------------|
| Coast/overrun | −30              | −30                 | 0                        |
| Light accel   | +63              | −25                 | ~10–30                   |
| Moderate accel| +111             | −20                 | ~30–80                   |

CA_diff is **zero whenever T_Act ≈ T_Loss** (pure coasting, no fuel). It becomes positive and grows proportionally to T_Act when the engine is producing positive torque. The correlation between CA_diff and ShiftRef_A is −0.91: when ShiftRef_A is depressed (low gear, high drag load), CA_diff is largest.

**Physical interpretation:**
- **ShiftRef_A** = drag/friction-based shift reference: primarily driven by T_Loss (internal resistance). Higher T_Loss → lower ShiftRef_A → EGS holds gear longer (transmission under high load).
- **ShiftRef_C** (N55 only) = engine-torque-based shift reference: primarily driven by T_Act (actual delivered torque). The gear-independent intercept suggests a simpler computation than ShiftRef_A. The EGS likely uses both signals for kickdown detection and upshift-inhibit: ShiftRef_A captures drivetrain load state while ShiftRef_C captures driver demand.

**Cross-vehicle validation:**
- **F30 N55 8HP45, B58 8HP50, F20:** formula structure confirmed across all petrol logs.
- **F20 specific:** 0x145 is on **can2** in multi-bus recordings; on can1 in single-bus captures. ID is unpadded (`145` not `0145`). Only `can-2023.02.01-161918.candump` contains active driving data; all other F20 files with 0x145 present show the engine-off standby constant (~32,000).
- **F15 X5 N57Z / F31 320d / G11 (diesel):** 100% 0xFFFF — SNA confirmed on every frame across all diesel logs.

---

## Frame 0x173 — Brake Pedal Status (DSC)

| Signal | Offset (bit) | Length (bit) | Formula | Unit | Notes |
|--------|-------------|--------------|---------|------|-------|
| Brake pedal status | 56 | 2 | `(byte7) & 0x03` | — | 0 = not pressed, 3 = pressed. |

---

## Frame 0x254 — Wheel Speeds (DSC broadcast)

Rate: ~50 Hz  
Frame length: 8 bytes (4 × 16-bit fields, one per wheel, little-endian).  
Encoding: lower 15 bits = wheel angular velocity in **gradians/second**
(400 gradians = 1 wheel revolution); bit 15 = validity flag (1 = valid).  
Invalid pattern: lower 15 bits all set (0x7FFF), full word 0xFFFF / 0x7FFF.
Field order is **rear-first**: RL, RR, FL, FR.

| Signal         | Offset (bit) | Length (bit) | Scaling                | Unit   | Description |
|----------------|-------------|--------------|------------------------|--------|-------------|
| WheelSpeed_RL  | 0           | 15           | rpm = raw × 60 / 400   | grad/s | Rear-left wheel   |
| Valid_RL       | 15          | 1            | —                      | —      | 1 = signal valid  |
| WheelSpeed_RR  | 16          | 15           | rpm = raw × 60 / 400   | grad/s | Rear-right wheel  |
| Valid_RR       | 31          | 1            | —                      | —      | 1 = signal valid  |
| WheelSpeed_FL  | 32          | 15           | rpm = raw × 60 / 400   | grad/s | Front-left wheel  |
| Valid_FL       | 47          | 1            | —                      | —      | 1 = signal valid  |
| WheelSpeed_FR  | 48          | 15           | rpm = raw × 60 / 400   | grad/s | Front-right wheel |
| Valid_FR       | 63          | 1            | —                      | —      | 1 = signal valid  |

```python
def wheel_speeds(data: bytes):
    out = []
    for i in (0, 2, 4, 6):
        w = data[i] | (data[i+1] << 8)
        valid = bool(w & 0x8000)
        raw   = w & 0x7FFF
        rpm   = raw * 60.0 / 400.0    # gradians/s -> rpm
        out.append((valid, rpm))
    return out  # [(valid, rpm) for RL, RR, FL, FR]
```

The rear-first ordering was confirmed by the F20 dyno capture: on a 2WD
dyno only the driven (rear) wheels turn, so the two front sensors are
marked invalid (0x7FFF) while the two rear fields carry live data. On
road captures (F30, F31, F15, G11) all four wheels remain valid, which
is consistent with — but does not disambiguate — the field order.

Final-drive ratio recovery (paired with 0x1AF tailshaft):

```
FD = tailshaft_rpm / wheel_rpm
```

Measured FD values, robust median over gears 5-8:

| Vehicle              | Measured FD | BMW spec       |
|----------------------|-------------|----------------|
| F30 335i N55 8HP45   | 3.120       | 3.077 / 3.154  |
| F30 340i B58 8HP50   | 2.746       | 2.813          |
| F31 320d 8HP45       | 2.801       | 2.813          |
| F15 X5 N57Z (AWD)    | 3.133       | 3.077–3.154    |
| G11 7-series         | 2.546       | 2.471–2.813    |

Per-gear `tailshaft_rpm / wheel_rpm` is constant within ±0.005 in upper
gears, confirming the gradian-per-second encoding.

---

## Torque Converter Frames

These frames are present on all captured vehicles. Encoding is consistent across
F30, F31, F15, F20, and G11 for 0x08F and 0x0A5. The turbine/tailshaft frame
differs by vehicle generation: 0x1AF on most models, 0x1B0 on the G11 (7-series).

### Frame 0x08F — Transmission Reinforcement Signal

Rate: ~100 Hz

| Signal      | Offset (bit) | Length (bit) | Scaling | Unit | Description |
|-------------|-------------|--------------|---------|------|-------------|
| reinf_signal | 48         | 8            | raw     | —    | TCC solenoid pressure proxy. High at stall (~200+), low at lockup (~25). Integer steps. |

```python
reinf = data[6]   # byte 6, unsigned uint8
```

Typical values by operating condition:

| Condition         | reinf range | Notes |
|-------------------|-------------|-------|
| Stall / low SR    | 180–255     | Maximum converter multiplication |
| Mid SR (0.40–0.75)| 80–150      | Partial slip |
| Near lockup       | 25–60       | Approaching coupled state |
| Full lockup (SR ≥ 0.97) | 20–40 | Baseline region for normalisation |

### Frame 0x1AF — Turbine & Tailshaft Speed (most vehicles)

Present on: F30, F31, F15 X5, F20, and all other non-G11 vehicles tested.  
Rate: ~50 Hz

| Signal        | Offset (bit) | Length (bit) | Scaling         | Unit | Description |
|---------------|-------------|--------------|-----------------|------|-------------|
| turbine_rpm   | 24          | 16           | rpm = raw − 2000 | rpm  | Torque converter turbine speed |
| tailshaft_rpm | 40          | 16           | rpm = raw − 2000 | rpm  | Transmission output / tailshaft speed |

```python
turbine_rpm   = (data[3] | (data[4] << 8)) - 2000
tailshaft_rpm = (data[5] | (data[6] << 8)) - 2000
```

Both signals share the 2000 RPM offset: raw 2000 (0x07D0) = 0 RPM. Negative
decoded values indicate the signal is invalid or the vehicle is stationary.

**SNA pattern:** raw value 0xD007 (53255) on both channels = signal not available (e.g. EGS not ready). After subtracting offset this decodes to 51255 RPM, giving turbine/tailshaft ratio ≈ 1.0 which falsely classifies as 6th gear. Always filter `raw != 0xD007` before gear identification:

```python
if turbine_raw != 0xD007 and tailshaft_raw != 0xD007:
    turbine_rpm   = turbine_raw - 2000
    tailshaft_rpm = tailshaft_raw - 2000
```

### Frame 0x1B0 — Turbine & Tailshaft Speed (G11 7-series)

Present on: G11 (confirmed). Replaces 0x1AF on this platform.  
Rate: ~50 Hz

| Signal        | Offset (bit) | Length (bit) | Scaling         | Unit | Description |
|---------------|-------------|--------------|-----------------|------|-------------|
| tailshaft_rpm | 8           | 16           | rpm = raw − 2000 | rpm  | Transmission output / tailshaft speed |
| turbine_rpm   | 24          | 16           | rpm = raw − 2000 | rpm  | Torque converter turbine speed |

```python
tailshaft_rpm = (data[1] | (data[2] << 8)) - 2000   # bytes 1-2 (offset 8)
turbine_rpm   = (data[3] | (data[4] << 8)) - 2000   # bytes 3-4 (offset 24)
```

Signal order is reversed compared to 0x1AF: tailshaft precedes turbine.
Same 2000 RPM zero-offset encoding as 0x1AF.

### Derived torque converter quantities

```python
SR  = turbine_rpm / engine_rpm        # speed ratio (0 = stall, 1 = lockup)
GR  = turbine_rpm / tailshaft_rpm     # gear ratio (ZF 8HP: 4.714 … 0.667)
reinf_norm = reinf_signal / GR        # reinf normalised for gear
K_norm = reinf_norm / baseline        # 1.0 at full lockup
```

Where `baseline = median(reinf/GR)` over all samples with SR ∈ [0.97, 1.03].

---

## Decoder snippet (Python)

```python
def le_bits(data: bytes, start_bit: int, length: int) -> int:
    return (int.from_bytes(data, 'little') >> start_bit) & ((1 << length) - 1)

TORQUE_OFFSET = 1999

def nm(raw: int) -> float:
    return (raw - TORQUE_OFFSET) / 2.0

# 0x0A5
t1_nm  = nm(le_bits(raw, 16, 12))   # actual torque
t2_nm  = nm(le_bits(raw, 28, 12))   # smoothed setpoint
rpm    = le_bits(raw, 40, 16) * 0.25

# 0x0A6
t_loss_nm = nm(le_bits(raw, 12, 12))  # friction loss (negative)
t_max_nm  = nm(le_bits(raw, 24, 12))  # calibration ceiling (~434 Nm)
t_cut_nm  = nm(le_bits(raw, 36, 12))  # cut/limit setpoint
t_act_nm  = nm(le_bits(raw, 48, 12))  # actual indicated torque

OFFSET_16 = 31932  # = 16 × 1999 − 52; same physical zero as 12-bit, 0.125 Nm/count

def nm16(raw: int) -> float:
    return (raw - OFFSET_16) / 8.0

# 0x0A7
t_demand_nm = nm(le_bits(raw, 12, 12))   # driver demand torque
a7_sig2_nm  = nm16(le_bits(raw, 32, 16)) # 16-bit torque (T_Act×GR at WOT lockup; step-down at upshifts)

# 0x8F
x8f_sig1_nm = nm16(le_bits(raw, 16, 16)) # 16-bit torque (≈T_Net×GR at lockup; floor at stall/cut)

# 0x0A0 (TCU -> DME)
t_coord      = nm(le_bits(raw, 16, 12))        # coordination trim from TCU
t_slipcap    = nm(le_bits(raw, 32, 12))        # TCU steady-state torque ceiling (drops with TC slip)
turbine_rpm  = le_bits(raw, 48, 16) - 2000     # turbine speed (0 at stall)

# 0x0B0
b0_t1        = nm(le_bits(raw, 12, 12))   # normally 1048 Nm (unlimited)
b0_shift_ceil = nm(le_bits(raw, 24, 12))  # shift torque ceiling (drops during shifts)
b0_t3        = nm(le_bits(raw, 36, 12))   # ~26–43 Nm, load-dependent

# 0x0D9
pedal_raw = le_bits(raw, 16, 12)
pedal_pct = pedal_raw / 4095 * 100

# 0x254 (4 wheels, gradians/s, 400 grad = 1 rev, order RL/RR/FL/FR)
wheels = []
for i in (0, 2, 4, 6):
    w = data[i] | (data[i+1] << 8)
    valid = bool(w & 0x8000)
    rpm   = (w & 0x7FFF) * 60.0 / 400.0
    wheels.append((valid, rpm))   # RL, RR, FL, FR
```

---

## Capture summary — can-2024.11.09-194107.candump (primary)

| Time (s) | Event | Speed | Gear |
|----------|-------|-------|------|
| 0–13.75 | Stationary, brake held | 0 kph | P/N |
| 13.75 | Brake released, pulling away | 0 → | 1st |
| 13.75–22 | Hard acceleration | 0–49 kph | 1st → 2nd |
| 22–27 | Continued acceleration | 49–66 kph | 2nd → 3rd |
| 27–36 | Acceleration to cruise | 66–71 kph | 3rd → 4th |
| 36–36.64 | Throttle lift, engine overrun | 71 → 68 kph | 4th → 5th |
| 36.64 | Brake pressed | 68 kph | 5th |
| 36.64–44.51 | Braking | 68 → 44 kph | 5th |
| 44.51 | Brake released | 44 kph | 5th |
| 44.51–52 | Constant speed / gentle acceleration | 43–47 kph | 5th |
| 52+ | Upshift, gentle acceleration | 47–49+ kph | 6th |
