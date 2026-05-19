# BMW N558HP CAN Signal Documentation

Vehicle: BMW F30 3-series, VIN WBA3A9C5XFKW74642  
Engine: N55/N558HP (Bosch ME17.2 DME)  
Encoding: Little-endian (Intel byte order), ARM Cortex-M7 GCC bitfield-compatible

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
| RPM             | 40          | 16           | rpm = raw × 0.25  | rpm  | Engine speed |

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

---

## Frame 0x0A7 — Air-Fuel Management

Rate: ~50 Hz

| Signal   | Offset (bit) | Length (bit) | Scaling                    | Unit | Description |
|----------|-------------|--------------|----------------------------|------|-------------|
| T_Demand | 12          | 12           | Nm = (raw−1999)/2          | Nm   | Driver demand torque (Fahrerwunschmoment). The raw pedal-derived torque request before coordinator limits are applied. Pearson r = 0.866 with pedal position. Runs 5–10 Nm above T_Act at mid-to-high load; lower than T_Act at idle (idle speed controller manages independently). |
| Lambda   | 32          | 16           | λ = raw / 32768 (Q1.15)    | —    | Wideband lambda. Stoichiometric = 0x8000 = 32768 → λ = 1.000. AFR = λ × 14.7. |

### Lambda encoding

```
lambda = raw / 32768          # Q1.15 fixed-point
AFR    = lambda × 14.7        # gasoline
```

The high byte (bits 40–47 of the frame) is the integer part of λ×128, restricted to values 123–137 (0x7B–0x89). This brackets 0x80 = stoichiometric, confirming Q1.15.

### Observed lambda values

| Condition        | λ           | AFR         |
|-----------------|-------------|-------------|
| Idle             | 0.987       | 14.51       |
| Light cruise     | 1.007–1.021 | 14.80–15.01 |
| WOT              | 0.973–0.980 | 14.30–14.41 |
| Max observed     | 1.077       | 15.83       |

Pearson(Pedal, λ) = +0.634: the N558HP map runs lean at medium throttle (efficiency lean-burn zone) and enriches only modestly at WOT below ~4500 RPM.

### T_Demand vs T_Act comparison

| Pedal bin | T_Demand (Nm) | T_Act (Nm) | Δ (Nm) |
|-----------|--------------|------------|--------|
| 0–9%      | 6            | 12         | −6     |
| 40–49%    | 68           | 68         | 0      |
| 60–69%    | 127          | 124        | +3     |
| 80–89%    | 190          | 185        | +5     |
| 90–99%    | 171          | 166        | +5     |

At high load, T_Demand slightly exceeds T_Act — the driver requests slightly more than the coordinator delivers after applying T_Cut and T_Loss constraints.

---

## Frame 0x8F — Lambda Setpoint

Rate: ~200 Hz (highest rate frame observed)

| Signal     | Offset (bit) | Length (bit) | Scaling                 | Unit | Description |
|------------|-------------|--------------|-------------------------|------|-------------|
| Lambda_Soll | 16         | 16           | λ = raw / 32768 (Q1.15) | —    | Commanded lambda setpoint (λ_soll). The target mixture ratio that the closed-loop fuel controller is chasing. Near-identical to A7 Lambda at idle (diff < 2 counts); diverges slightly at high load where open-loop enrichment creates a small offset between command and measurement. |

### Lambda_Soll vs Lambda (A7) comparison

| Condition     | λ_soll (0x8F) | λ_meas (A7) | Δ      |
|--------------|--------------|-------------|--------|
| Idle (0% ped) | 0.978        | 0.978       | ≈ 0    |
| 50% pedal    | 0.985        | 0.987       | −0.002 |
| 80% pedal    | 1.001        | 1.006       | −0.005 |
| WOT 4000 RPM | 1.002        | 1.008       | −0.006 |

Pearson r(λ_soll, λ_meas) = 0.955. The small positive offset of λ_meas over λ_soll at high load reflects the open-loop fuelling region where the ECU enriches beyond the closed-loop target during transients.

Encoding is identical to A7 Lambda: Q1.15 fixed-point, stoichiometric = 0x8000 = 32768 → λ = 1.000. Range observed: 0.962–1.032.

---

## Frame 0x0A0 — Transmission Frame A (DME → TCU torque broadcast)

Rate: ~100 Hz

| Signal        | Offset (bit) | Length (bit) | Description |
|---------------|-------------|--------------|-------------|
| Counter       | 0           | 16           | Rolling message counter (16-bit LE, monotonically increasing). Not a sensor signal. |
| T_Net         | 16          | 12           | Net / trim torque in Nm encoding (offset 1999, ×0.5 Nm/LSB). Small range ≈ ±15 Nm centered near 0; likely shaft net torque or coordination trim broadcast to TCU. |
| ShiftStatus   | 24          | 8            | Byte[3]. Two observed values: **0x87** (normal coordination) / **0x88** (shift torque-cut active). The single-bit transition (low nibble 7→8) flags an active transmission torque intervention. Occurs at light pedal (<5%), mid RPM (~1800), and coincides with T_Cut ≈ −30 Nm on 0x0A6. |
| CalibConst    | 32          | 16           | Near-constant value (~64400 raw, Q0.16 ≈ 0.982). Low entropy at high RPM (single unique value). Likely a calibration reference or fixed-point constant, not a live sensor. |
| SubCounter    | 40          | 8            | Byte[5] cycles 0xFA→0xFB→0xFC (3 values). Sub-counter or frame type indicator. |
| MsgCounter    | 48          | 16           | Second counter field (confirmed constant delta = 0 between consecutive frames in the initial segment, behaves as a timestamp). |

---

## Frame 0x0B0 — Transmission Frame B (TCU → DME lambda permission)

Rate: ~100 Hz

| Signal        | Offset (bit) | Length (bit) | Scaling                 | Description |
|---------------|-------------|--------------|-------------------------|-------------|
| AliveCounter  | 0           | 16           | —                       | Rolling alive counter (bytes 0–1). Confirms frame is live. |
| Lambda_Max    | 32          | 16           | λ = raw / 32768 (Q1.15) | **TCU lean-burn permission ceiling.** Maximum lambda the TCU allows the DME to target. Always slightly above stoich (1.0017–1.0185). At idle/light load the TCU permits lean-burn (≤1.010); as load or shift probability increases it tightens toward stoich (≤1.002), ensuring full torque is available for clutch engagement. Negative Pearson r with both RPM (−0.62) and pedal (−0.51). |
| Mode_Status   | 32          | 8            | —                       | Byte[4]. 16 unique values combining an upper nibble (operating mode) and lower nibble alive counter. Dominant values: **0x5F** (idle, RPM≈692, ped≈0%) and **0x3F** (normal driving, RPM≈2310, ped≈40%). Value 0x38/0x39 appears at high load (ped>60%). |

### Lambda_Max (0x0B0) vs lambda_soll (0x8F)

| Pedal bin | Lambda_Max (TCU ceiling) | λ_soll (DME target) | Headroom |
|-----------|------------------------|---------------------|----------|
| 0–9%      | 1.010                  | 0.978               | +0.032   |
| 50–59%    | 1.002                  | 0.985               | +0.017   |
| 80–89%    | 1.002                  | 1.001               | +0.001   |
| 90–99%    | 1.002                  | 1.009               | −0.007   |

At very high pedal (90%+) λ_soll briefly exceeds Lambda_Max by 0.007 — open-loop transient enrichment overshoot. The TCU ceiling is the dominant constraint in the lean-burn zone; the DME operates below it at all other times.

---

## Frame 0x0D9 — Pedal Position

Rate: ~50 Hz

| Signal    | Offset (bit) | Length (bit) | Scaling        | Unit | Description |
|-----------|-------------|--------------|----------------|------|-------------|
| Pedal_Raw | 16          | 12           | % = raw/max×100 | —    | Accelerator pedal position. 0 = fully released. Max observed raw ≈ 4095. |

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

# 0x0A7
t_demand_nm = nm(le_bits(raw, 12, 12))      # driver demand torque
lam         = le_bits(raw, 32, 16) / 32768  # lambda (1.0 = stoich)
afr         = lam * 14.7

# 0x8F
lam_soll = le_bits(raw, 16, 16) / 32768   # lambda setpoint (1.0 = stoich)

# 0x0D9
pedal_raw = le_bits(raw, 16, 12)
pedal_pct = pedal_raw / 4095 * 100
```
