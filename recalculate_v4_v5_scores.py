#!/usr/bin/env python3
"""Add V4 and V5 final accessibility scores to a completed V3 CSV.

V4 and V5 retain V3's data-confidence adjustment and access safeguards.  Only
the relative weighting of vehicle access and connectivity differs.
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path


V4_V5_FIELDS = [
    "overall_accessibility_score_v4",
    "overall_accessibility_score_v5",
]


def number(value: str | None) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except ValueError:
        return None


def final_score(
    vehicle: float | None,
    connectivity: float | None,
    confidence: float | None,
    status: str,
    vehicle_weight: float,
) -> float | None:
    """Apply V3's confidence adjustment and access safeguards to a new base."""
    if vehicle is None or connectivity is None or confidence is None:
        return None

    base = vehicle_weight * vehicle + (1 - vehicle_weight) * connectivity
    adjusted = base * (0.85 + 0.15 * confidence / 100)
    if status == "Blocked":
        return 0.0
    if status == "Insufficient data":
        return None
    if vehicle < 25:
        return min(adjusted, 35.0)
    if vehicle < 50:
        return min(adjusted, 60.0)
    return adjusted


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", type=Path, help="Optional separate output path; leaves input unchanged.")
    args = parser.parse_args()

    with args.input.open(newline="", encoding="utf-8-sig") as stream:
        rows = list(csv.DictReader(stream))
        fieldnames = list(rows[0]) if rows else []
    for field in V4_V5_FIELDS:
        if field not in fieldnames:
            fieldnames.append(field)

    populated_v4 = populated_v5 = 0
    for row in rows:
        vehicle = number(row.get("vehicle_access_score_v3"))
        connectivity = number(row.get("connectivity_score_v3"))
        confidence = number(row.get("data_confidence_score"))
        status = row.get("accessibility_status_v3", "")
        v4 = final_score(vehicle, connectivity, confidence, status, 0.70)
        v5 = final_score(vehicle, connectivity, confidence, status, 0.80)
        row["overall_accessibility_score_v4"] = "" if v4 is None else f"{v4:.1f}"
        row["overall_accessibility_score_v5"] = "" if v5 is None else f"{v5:.1f}"
        populated_v4 += v4 is not None
        populated_v5 += v5 is not None

    destination = args.output or args.input
    temporary = destination.with_suffix(".tmp")
    with temporary.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(destination)
    print(f"Updated {len(rows)} rows; populated V4: {populated_v4}; populated V5: {populated_v5}.")


if __name__ == "__main__":
    main()
