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
- F20 uses **two buses**: can1 carries PT signals (0x0A5–0x0A7, 0x145), can2 carries 0x1AF.
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

## Frame 0x0A0 — Transmission Frame A (DME → TCU torque broadcast)

Rate: ~100 Hz

| Signal       | Offset (bit) | Length (bit) | Scaling            | Unit | Description |
|--------------|-------------|--------------|---------------------|------|-------------|
| Counter      | 0           | 16           | —                   | —    | Rolling message counter (16-bit LE, monotonically increasing). Not a sensor signal. |
| T_Coord      | 16          | 12           | Nm = (raw−1999)/2   | Nm   | Torque coordination signal broadcast from DME to TCU. Small range ≈ −7 to +0.5 Nm centered near 0 Nm. Slightly negative at cruise/WOT; briefly relaxes toward 0 during a shift event then returns negative. Exact role (shaft net trim or coordination headroom) unconfirmed. |
| TurbineSpeed | 48          | 16           | rpm = raw − 2000    | rpm  | Torque converter turbine shaft speed. At idle/stall: raw ≈ 2000 → 0 rpm. At lockup (engine ≈ 3300 rpm): raw ≈ 5300 → turbine ≈ 3300 rpm. Slip ratio = TurbineSpeed / EngineRPM rises from 0 (stall) to ≈ 0.98+ (lockup). Staircase pattern during WOT upshifts: turbine drops at each shift and recovers in the new gear ratio. |

### Turbine speed at key operating points

| Condition       | Engine RPM | Raw value | Turbine RPM | Slip ratio |
|----------------|-----------|-----------|-------------|------------|
| Idle / stall    | 650       | ~2000     | 0           | 0.00       |
| Light cruise    | 1500      | ~3100     | 1100        | 0.73       |
| 2nd gear WOT   | 3300      | ~5263     | 3263        | 0.99       |
| Lockup (cruise) | 2400      | ~4400     | 2400        | 1.00       |

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

| Signal | Offset (bit) | Length (bit) | Formula | Notes |
|--------|-------------|--------------|---------|-------|
| EGS shift load ref (ch1) | 16 | 16 | See below | Redundant pair with O32; used by EGS for shift scheduling |
| EGS shift load ref (ch2) | 32 | 16 | Identical to O16 | Safety redundancy |

**SNA value:** 0xFFFF (65535) — transmitted by all diesel DMEs.

**Function:** Higher values → upshift sooner (lower RPM, economy zone). Lower values → hold gear (high-load zone).

```python
raw145 = le_bits(data, 16, 16)   # O16 L16 Intel LE (ch1)
```

**Formula — per-gear (best accuracy):**

```
raw145 = a × T_Loss + b × T_Act + c
```

Where `T_Loss` and `T_Act` are in Nm from 0x0A6.

| Gear | a      | b      | c     | R²    | RMS (counts) |
|------|--------|--------|-------|-------|--------------|
| 1st  | +62.49 | −5.628 | 33977 | 0.733 | 185          |
| 2nd  | +20.59 | −2.149 | 32396 | 0.637 |  67          |
| 3rd  |  +5.03 | −0.288 | 31823 | 0.608 |  19          |
| 4th  |  +4.14 | −0.133 | 31819 | 0.843 |  10          |
| 5th  |  +3.84 | −0.222 | 31882 | 0.864 |   9          |
| 6th  |  +2.56 | −0.172 | 31895 | 0.792 |   7          |

**Formula — global (cross-gear, TC-locked, kph > 5):**

```python
gear_ratio = turbine_RPM / tailshaft_RPM    # from 0x1AF
raw145 ≈ -268.4 × gear_ratio + 4.30 × T_Loss - 0.28 × T_Act + 32340
# R² = 0.88, RMS = 79 counts (n = 35,115 TC-locked points)
```

**Observed mean per gear (N55 primary):**

| Gear | mean raw145 | typical kph |
|------|------------|-------------|
| P/N  | ~29,381    | 0           |
| 1st  | ~30,680    | 5–32        |
| 2nd  | ~31,301    | 5–52        |
| 3rd  | ~31,623    | 17–92       |
| 4th  | ~31,729    | 33–95       |
| 5th  | ~31,786    | 43–92       |
| 6th  | ~31,839    | 46–92       |
| 7th  | ~31,822    | (from N55 8HP data) |
| 8th  | ~31,840    | (from N55 8HP data) |

**Cross-vehicle validation:**
- **F30 B58 8HP50 (petrol):** same structure. 1st gear produces *highest* signal (32,135 mean) vs N55 where 1st is *lowest* (30,680).
- **F15 X5 N57Z / F31 320d / G11 (diesel):** `raw = 0xFFFF` — SNA. Confirmed petrol-specific.

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

| Signal         | Offset (bit) | Length (bit) | Scaling                | Unit   | Description |
|----------------|-------------|--------------|------------------------|--------|-------------|
| WheelSpeed_FL  | 0           | 15           | rpm = raw × 60 / 400   | grad/s | Front-left wheel  |
| Valid_FL       | 15          | 1            | —                      | —      | 1 = signal valid  |
| WheelSpeed_FR  | 16          | 15           | rpm = raw × 60 / 400   | grad/s | Front-right wheel |
| Valid_FR       | 31          | 1            | —                      | —      | 1 = signal valid  |
| WheelSpeed_RL  | 32          | 15           | rpm = raw × 60 / 400   | grad/s | Rear-left wheel   |
| Valid_RL       | 47          | 1            | —                      | —      | 1 = signal valid  |
| WheelSpeed_RR  | 48          | 15           | rpm = raw × 60 / 400   | grad/s | Rear-right wheel  |
| Valid_RR       | 63          | 1            | —                      | —      | 1 = signal valid  |

```python
def wheel_speeds(data: bytes):
    out = []
    for i in (0, 2, 4, 6):
        w = data[i] | (data[i+1] << 8)
        valid = bool(w & 0x8000)
        raw   = w & 0x7FFF
        rpm   = raw * 60.0 / 400.0    # gradians/s -> rpm
        out.append((valid, rpm))
    return out  # [(valid, rpm) for FL, FR, RL, RR]
```

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

# 0x0A0
t_coord      = nm(le_bits(raw, 16, 12))        # coordination trim to TCU
turbine_rpm  = le_bits(raw, 48, 16) - 2000     # turbine speed (0 at stall)

# 0x0B0
b0_t1        = nm(le_bits(raw, 12, 12))   # normally 1048 Nm (unlimited)
b0_shift_ceil = nm(le_bits(raw, 24, 12))  # shift torque ceiling (drops during shifts)
b0_t3        = nm(le_bits(raw, 36, 12))   # ~26–43 Nm, load-dependent

# 0x0D9
pedal_raw = le_bits(raw, 16, 12)
pedal_pct = pedal_raw / 4095 * 100

# 0x254 (4 wheels, gradians/s, 400 grad = 1 rev)
wheels = []
for i in (0, 2, 4, 6):
    w = data[i] | (data[i+1] << 8)
    valid = bool(w & 0x8000)
    rpm   = (w & 0x7FFF) * 60.0 / 400.0
    wheels.append((valid, rpm))
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
