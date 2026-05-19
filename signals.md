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

| Signal     | Offset (bit) | Length (bit) | Scaling              | Unit | Description |
|------------|-------------|--------------|----------------------|------|-------------|
| T_Demand   | 12          | 12           | Nm = (raw−1999)/2    | Nm   | Driver demand torque (Fahrerwunschmoment). The raw pedal-derived torque request before coordinator limits are applied. Pearson r = 0.866 with pedal position. Runs 5–10 Nm above T_Act at mid-to-high load; lower than T_Act at idle (idle speed controller manages independently). |
| Phi_Demand | 32          | 16           | φ = raw / 32768      | —    | **Fuel-air equivalence ratio demand** (φ = 1/λ). The unconstrained fuel enrichment target from the load map. φ = 1.0 → stoichiometric; φ > 1.0 → rich; φ < 1.0 → lean. Actual lambda = 32768 / raw. This signal responds immediately to throttle changes and can exceed the commanded value (0x8F Phi_Soll) at low RPM where injector duty cycle limits delivery. |

### Phi encoding (both 0x0A7 and 0x8F)

```
phi   = raw / 32768        # Q1.15, fuel-air equivalence ratio (= 1/lambda)
lambda = 32768 / raw       # actual lambda: <1.0 = rich, >1.0 = lean
AFR   = lambda × 14.7      # gasoline stoich AFR
```

Stoichiometric: raw = 32768 → φ = 1.0 → λ = 1.0. Rich mixture: raw > 32768. Lean mixture: raw < 32768.

### Observed Phi_Demand (0x0A7) values

| Condition                    | raw   | φ      | λ     | AFR   |
|-----------------------------|-------|--------|-------|-------|
| Light cruise (15% pedal)    | ~32000 | 0.977 | 1.024 | 15.06 |
| Moderate load (40% pedal)   | ~33000 | 1.007 | 0.993 | 14.60 |
| WOT 97.7% ped, 3000 RPM    | ~38400 | 1.172 | 0.853 | 12.54 |
| WOT 97.7% ped, 2000 RPM    | ~43200 | 1.318 | 0.759 | 11.16 |
| WOT 97.7% ped, 7000 RPM    | ~36600 | 1.117 | 0.895 | 13.16 |

At low RPM WOT (2000 rpm), the map demands very rich mixture (λ ≈ 0.76) during boost build-up. As RPM rises, demand moderates (λ ≈ 0.85–0.90 at 3000–6000 RPM). Light cruise uses lean-burn (λ > 1.0).

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

## Frame 0x8F — Fuel-Air Ratio Setpoint

Rate: ~200 Hz (highest rate frame observed)  
Frame structure: 8 bytes. b0 = CRC/checksum (rapidly varying). b1 = alive counter (0x1X). b4–b7 = constant protocol bytes (0x22 0x00 0x20 0x10).

| Signal    | Offset (bit) | Length (bit) | Scaling          | Unit | Description |
|-----------|-------------|--------------|------------------|------|-------------|
| Phi_Soll  | 16          | 16           | φ = raw / 32768  | —    | **Commanded fuel-air equivalence ratio** (φ_soll = 1/λ). The actual fuel enrichment command sent to the injectors, after any delivery constraints are applied. φ = 1.0 = stoichiometric (raw = 32768). Rich (WOT): raw > 32768 (φ > 1.0 → λ < 1.0). Lean cruise: raw < 32768 (φ < 1.0 → λ > 1.0). At high pedal + low RPM, limited below Phi_Demand (0x0A7) by injector capacity. |

### Phi_Soll (0x8F) vs Phi_Demand (0x0A7) — fuel delivery constraint

| Condition                    | Phi_Soll (8F) λ=32768/r | Phi_Demand (A7) λ=32768/r | Injector-limited? |
|-----------------------------|------------------------|--------------------------|------------------|
| Light cruise (15% pedal)    | 0.977 → λ = 1.024      | 0.977 → λ = 1.024         | No (equal)       |
| WOT 97.7% ped, 3000 RPM    | 1.074 → λ = 0.931      | 1.172 → λ = 0.853         | Yes              |
| WOT 97.7% ped, 2000 RPM    | 1.039 → λ = 0.963      | 1.319 → λ = 0.758         | Yes (heavily)    |
| WOT 97.7% ped, 4500 RPM    | 1.049 → λ = 0.953      | 1.063 → λ = 0.941         | Marginal         |

At low RPM the injectors reach duty-cycle limits — the map demands λ ≈ 0.76 but the commanded injection quantity only achieves λ ≈ 0.96. As RPM rises, the injectors have more time per cycle to open and the two signals converge. This gap represents the fuel delivery deficit under the N558HP tune at low-RPM WOT.

Observed range: raw 30800–36297 → φ 0.940–1.108 → λ 0.903–1.064.

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
t_demand_nm = nm(le_bits(raw, 12, 12))       # driver demand torque
phi_demand  = le_bits(raw, 32, 16) / 32768   # fuel-air equivalence ratio demand (phi = 1/lambda)
lam_demand  = 32768 / le_bits(raw, 32, 16)   # lambda = 1/phi (<1.0 = rich at WOT)
afr_demand  = lam_demand * 14.7

# 0x8F
phi_soll   = le_bits(raw, 16, 16) / 32768    # commanded phi (1/lambda) sent to injectors
lam_soll   = 32768 / le_bits(raw, 16, 16)    # commanded lambda (<1.0 = rich at WOT)

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
```
