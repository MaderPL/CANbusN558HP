# BMW N558HP CAN Signal Documentation

Vehicle: BMW F30 3-series, VIN WBA3A9C5XFKW74642  
Engine: N55/N558HP (Bosch ME17.2 DME)  
Encoding: Little-endian (Intel byte order), ARM Cortex-M7 GCC bitfield-compatible

All signals use the extraction formula:
```
value = (int.from_bytes(payload, 'little') >> start_bit) & ((1 << length) - 1)
```

---

## Frame 0x0A5 — Engine Speed & Torque

Rate: ~100 Hz

| Signal | Offset (bit) | Length (bit) | Type     | Scale / Unit | Notes |
|--------|-------------|--------------|----------|--------------|-------|
| T1     | 16          | 12           | signed   | Nm×2 + 1999  | Indicated (actual) torque. Matches A6_tact closely (r=0.971). `Nm = (raw_unsigned − 1999) / 2` |
| T2     | 28          | 12           | signed   | Nm×2 + 1999  | Rate-limited / smoothed torque setpoint. Identical to T1 ~95.6% of time; lags T1 during rapid transients. During torque-coordination interventions T2 can diverge strongly (T2≈+2020 unsigned, T1≈+300 unsigned) |
| RPM    | 40          | 16           | unsigned | × 0.25 RPM   | Engine speed |

### Torque encoding
```
raw_unsigned = Nm × 2 + 1999      (offset derived from idle: tact_raw + loss_raw ≈ 3998)
Nm           = (raw_unsigned − 1999) / 2
```
Idle: T1 ≈ 49 Nm (accessory / idle load)

---

## Frame 0x0A6 — Torque Coordination Signals

Rate: ~100 Hz  
All four torque signals use the same Nm encoding as A5 (offset 1999, scale ×2).

| Signal | Offset (bit) | Length (bit) | Type     | Meaning |
|--------|-------------|--------------|----------|---------|
| t_loss | 12          | 12           | unsigned | Friction / pumping loss torque (negative Nm, opposes crankshaft). Increases in magnitude at low and high RPM. |
| t_max  | 24          | 12           | unsigned | Maximum engine torque calibration limit. Constant at 434 Nm (raw 2867) in 83.7% of frames; drops slightly at idle (≈383 Nm). |
| t_cut  | 36          | 12           | unsigned | Torque cut / limiter setpoint. Near 0 Nm at light load; rises to +40–50 Nm at high pedal indicating active torque coordination. Negative values indicate active cut intervention. |
| t_act  | 48          | 12           | unsigned | Actual indicated engine torque (= A5 T1, Pearson r=0.971). This is the primary torque output signal. |

### Representative values (offset=1999)

| Condition        | RPM  | t_loss (Nm) | t_max (Nm) | t_cut (Nm) | t_act (Nm) | Net shaft (Nm) |
|-----------------|------|-------------|------------|------------|------------|----------------|
| Idle            | ~660 | −49         | 383        | −2         | 49         | ≈ 0            |
| Light cruise    | 2000 | −17         | 434        | +2         | 80         | 64             |
| WOT 3000 RPM    | 3000 | −18         | 434        | +28        | 149        | 134            |
| 80% pedal       | 2600 | −23         | 434        | +44        | 185        | 163            |

**Net shaft torque** = t_act + t_loss (friction is negative, already signed by convention).  
At idle the sum is ≈ 0 Nm — this is the physical constraint used to derive the offset.

### Friction model (t_loss vs RPM)

| RPM range  | Mean loss (Nm) |
|-----------|---------------|
| 500–999   | −49           |
| 1000–1499 | −34           |
| 1500–1999 | −26           |
| 2000–2999 | −17           |
| 3000–3499 | −18           |
| 3500–3999 | −21           |
| 4000–4999 | −26           |

Minimum friction near 2000–3000 RPM (viscous losses at lower RPM dominate; high-RPM mechanical losses increase again).

---

## Frame 0x0A7 — Lambda (Air-Fuel Ratio)

Rate: ~50 Hz

| Signal | Offset (bit) | Length (bit) | Type     | Scale / Unit | Notes |
|--------|-------------|--------------|----------|--------------|-------|
| (TBD)  | 12          | 12           | unknown  | —            | Not yet decoded |
| lambda | 32          | 16           | unsigned | Q1.15 fixed-point: λ = raw / 32768 | Wideband lambda value |

### Lambda encoding
```
lambda = raw / 32768          (Q1.15 fixed-point)
AFR    = lambda × 14.7        (for gasoline)
stoich → raw = 0x8000 = 32768, λ = 1.000
```

### Observed lambda values

| Condition         | λ     | AFR    |
|------------------|-------|--------|
| Idle              | 0.987 | 14.51  |
| Light cruise      | 1.007–1.021 | 14.80–15.01 | (lean-burn economy region) |
| WOT               | 0.973–0.980 | 14.30–14.41 | (mild enrichment) |
| Peak observed     | 1.077 | 15.83  |

Pearson(pedal, lambda) = +0.634: at medium throttle the tune runs lean (λ>1) for efficiency; it does not significantly enrich at WOT below ~4500 RPM (N558HP stage-1 map characteristic).

The high byte of the 16-bit lambda word (bits 40–47) takes only values 123–137 (0x7B–0x89). This is the integer part of λ×128, confirming the Q1.15 interpretation: values straddle 0x80=128 (stoichiometric).

---

## Frame 0x0D9 — Pedal Position

Rate: ~50 Hz

| Signal | Offset (bit) | Length (bit) | Type     | Scale / Unit | Notes |
|--------|-------------|--------------|----------|--------------|-------|
| pedal  | 16          | 12           | unsigned | 0–max raw (max observed ≈ 4096) | Accelerator pedal position sensor. 0 = fully released. |

Pedal % = raw / max_raw × 100

---

## Decoder snippet (Python)

```python
def le_bits(data: bytes, start_bit: int, length: int) -> int:
    return (int.from_bytes(data, 'little') >> start_bit) & ((1 << length) - 1)

def signed12(v: int) -> int:
    return v - 4096 if v >= 2048 else v

def nm(raw_unsigned: int, offset: int = 1999) -> float:
    return (raw_unsigned - offset) / 2.0

# --- 0x0A5 ---
t1_raw  = le_bits(raw, 16, 12)
t2_raw  = le_bits(raw, 28, 12)
rpm     = le_bits(raw, 40, 16) * 0.25
t1_nm   = nm(t1_raw)
t2_nm   = nm(t2_raw)

# --- 0x0A6 ---
t_loss_raw = le_bits(raw, 12, 12)
t_max_raw  = le_bits(raw, 24, 12)
t_cut_raw  = le_bits(raw, 36, 12)
t_act_raw  = le_bits(raw, 48, 12)
t_loss_nm  = nm(t_loss_raw)   # negative at all RPM (friction)
t_max_nm   = nm(t_max_raw)    # ≈ 434 Nm (calibration ceiling)
t_cut_nm   = nm(t_cut_raw)    # torque cut setpoint
t_act_nm   = nm(t_act_raw)    # actual indicated torque

# --- 0x0A7 ---
lambda_raw = le_bits(raw, 32, 16)
lam        = lambda_raw / 32768.0   # λ (1.000 = stoichiometric)
afr        = lam * 14.7

# --- 0x0D9 ---
pedal_raw = le_bits(raw, 16, 12)
```
