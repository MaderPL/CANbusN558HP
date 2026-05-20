# BMW CAN Signal Documentation

Primary vehicle: BMW F30 3-series, VIN WBA3A9C5XFKW74642  
Engine: N55/N558HP (Bosch ME17.2 DME)  
Encoding: Little-endian (Intel byte order), ARM Cortex-M7 GCC bitfield-compatible

Signal presence across captured vehicles:

| Frame | F30 N55 | F30 B58 | F31 320d | F15 X5 N57Z | F20 | G11 |
|-------|---------|---------|----------|-------------|-----|-----|
| 0x08F (reinf) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 0x0A5 (engine RPM) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 0x1AF (turbine/tailshaft) | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| 0x1B0 (turbine/tailshaft) | — | — | — | — | — | ✓ |

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

## Frame 0x0A7 — Torque & Unknown Signal

Rate: ~50 Hz  
Frame length: 7 bytes.

| Signal   | Offset (bit) | Length (bit) | Scaling           | Unit | Description |
|----------|-------------|--------------|-------------------|------|-------------|
| T_Demand | 12          | 12           | Nm = (raw−1999)/2 | Nm   | Driver demand torque (Fahrerwunschmoment). The raw pedal-derived torque request before coordinator limits are applied. Pearson r = 0.866 with pedal position. Runs 5–10 Nm above T_Act at mid-to-high load; lower than T_Act at idle (idle speed controller manages independently). |
| A7_Sig2  | 32          | 16           | TBD               | TBD  | 16-bit torque-related signal. Raw range observed: 31000–43242. At moderate cruise the value is close to T_Demand (O12 L12) within ~20–50 raw counts. At WOT/boost it significantly exceeds T_Demand and T_Act. Encoding and exact physical quantity not yet confirmed. |

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

## Frame 0x8F — Unknown Torque Signal

Rate: ~200 Hz (highest rate frame observed)  
Frame structure: 8 bytes. b0 = CRC/checksum (rapidly varying). b1 = alive counter (upper nibble fixed at 0x10, lower nibble cycles). b4–b7 = constant (0x22 0x00 0x20 0x10 — likely protocol/version bytes). Only b2–b3 carry live data.

| Signal   | Offset (bit) | Length (bit) | Scaling | Unit | Description |
|----------|-------------|--------------|---------|------|-------------|
| X8F_Sig1 | 16          | 16           | TBD     | TBD  | 16-bit torque-related signal. Raw range observed: 30800–36297. Correlates positively with engine load and torque. At moderate cruise, approximately tracks T_Act; at WOT/boost the value significantly exceeds T_Act. The RPM-dependent zero offset and the boost-related excursion suggest this is a different torque quantity than T_Act. Encoding and exact physical quantity not yet confirmed. |

### Observed X8F_Sig1 raw values

| Condition                  | Raw    | Notes |
|---------------------------|--------|-------|
| Key-on, engine off         | 32000  | Initialization default |
| Idle (~780 RPM)            | ~32000 | Near default |
| Light cruise (2000 RPM, 15% ped) | 31760–32000 | Tracks T_Act closely |
| Moderate load (2050 RPM, 23% ped) | 32300–32350 | Tracks T_Act closely |
| WOT 39% ped, 3300 RPM     | 33000–33850 | Significantly above T_Act |
| WOT 97.7% ped, 3000 RPM   | ~35200 | Further above T_Act |
| WOT 97.7% ped, 2000 RPM   | ~34050 | Above T_Act but less than 3000 RPM value |

The 0x8F signal is always smaller than A7_Sig2 (0x0A7 O32) at the same operating point. Both signals converge toward T_Act at moderate cruise and diverge increasingly at WOT/high boost.

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

# 0x0A7
t_demand_nm = nm(le_bits(raw, 12, 12))   # driver demand torque
a7_sig2     = le_bits(raw, 32, 16)       # 16-bit torque-related signal (TBD encoding)

# 0x8F
x8f_sig1 = le_bits(raw, 16, 16)          # 16-bit torque-related signal (TBD encoding)

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
