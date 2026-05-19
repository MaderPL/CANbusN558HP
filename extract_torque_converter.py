#!/usr/bin/env python3
"""
Extract torque converter signals from candump log.

Signals:
  0x08F  offset 48 len 8  (byte 6)     - transmission reinforcement signal  (uint8)
  0x0A5  offset 40 len 16 (bytes 5-6)  - engine speed [RPM * 4]             (uint16 LE)
  0x1AF  offset 24 len 16 (bytes 3-4)  - turbine speed [RPM + 2000]         (uint16 LE)
  0x1AF  offset 40 len 16 (bytes 5-6)  - tailshaft speed [RPM + 2000]       (uint16 LE)
"""

import sys
import csv
import re
from pathlib import Path


def decode_frame(hex_data: str, byte_offset: int, length_bits: int) -> int:
    data = bytes.fromhex(hex_data)
    if length_bits == 8:
        return data[byte_offset]
    elif length_bits == 16:
        # Little-endian (Intel byte order)
        return data[byte_offset] | (data[byte_offset + 1] << 8)
    raise ValueError(f"Unsupported length: {length_bits}")


def extract(candump_path: str, output_path: str) -> None:
    target_ids = {"08f", "0a5", "1af"}

    # Latest value of each signal (held until next update)
    latest = {"reinf": None, "engine_rpm": None, "turbine_rpm": None, "tailshaft_rpm": None}

    rows = []
    line_re = re.compile(r"^\(([0-9.]+)\)\s+\S+\s+([0-9A-Fa-f]+)#([0-9A-Fa-f]+)")

    with open(candump_path) as f:
        for line in f:
            m = line_re.match(line)
            if not m:
                continue
            ts, frame_id, hex_data = m.group(1), m.group(2).lower(), m.group(3).lower()
            frame_id = frame_id.zfill(3)

            if frame_id not in target_ids:
                continue

            if frame_id == "08f" and len(hex_data) >= 14:  # 7+ bytes
                latest["reinf"] = decode_frame(hex_data, 6, 8)

            elif frame_id == "0a5" and len(hex_data) >= 14:  # 7+ bytes
                raw = decode_frame(hex_data, 5, 16)
                latest["engine_rpm"] = round(raw / 4.0, 2)

            elif frame_id == "1af" and len(hex_data) >= 14:  # 7+ bytes
                latest["turbine_rpm"]   = decode_frame(hex_data, 3, 16) - 2000
                latest["tailshaft_rpm"] = decode_frame(hex_data, 5, 16) - 2000

            # Emit a row when all four signals have been seen at least once
            if all(v is not None for v in latest.values()):
                eng  = latest["engine_rpm"]
                tur  = latest["turbine_rpm"]
                tail = latest["tailshaft_rpm"]
                tc_slip    = round(eng / tur,  4) if tur  > 0 else None
                gear_ratio = round(tur / tail, 4) if tail > 0 else None
                rows.append((
                    ts,
                    latest["reinf"],
                    eng,
                    tur,
                    tail,
                    tc_slip,
                    gear_ratio,
                ))

    with open(output_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "timestamp_s",
                "reinf_signal",
                "engine_rpm",
                "turbine_rpm",
                "tailshaft_rpm",
                "tc_slip_ratio",
                "gear_ratio",
            ]
        )
        writer.writerows(rows)

    print(f"Written {len(rows):,} rows → {output_path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: extract_torque_converter.py <candump.log> [output.csv]")
        sys.exit(1)
    inp = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else Path(inp).stem + "_torque_converter.csv"
    extract(inp, out)
