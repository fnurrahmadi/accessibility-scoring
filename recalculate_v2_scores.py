"""Add or refresh overall_accessibility_score_v2 in a completed POC CSV."""
from __future__ import annotations

import argparse
import csv
from pathlib import Path


def to_float(value: str | None) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except ValueError:
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--connectivity-weight", type=float, default=50.0)
    parser.add_argument("--vehicle-access-weight", type=float, default=50.0)
    args = parser.parse_args()
    if args.connectivity_weight < 0 or args.vehicle_access_weight < 0:
        parser.error("Weights cannot be negative.")
    total_weight = args.connectivity_weight + args.vehicle_access_weight
    if total_weight <= 0:
        parser.error("At least one weight must be positive.")

    with args.input.open(newline="", encoding="utf-8-sig") as stream:
        rows = list(csv.DictReader(stream))
        fields = list(rows[0].keys()) if rows else []
    if "overall_accessibility_score_v2" not in fields:
        insert_at = fields.index("overall_accessibility_score") + 1
        fields.insert(insert_at, "overall_accessibility_score_v2")

    completed, blank = 0, 0
    for row in rows:
        connectivity = to_float(row.get("connectivity_score"))
        vehicle_access = to_float(row.get("vehicle_access_score"))
        if connectivity is None or vehicle_access is None:
            row["overall_accessibility_score_v2"] = ""
            blank += 1
            continue
        score = (connectivity * args.connectivity_weight + vehicle_access * args.vehicle_access_weight) / total_weight
        row["overall_accessibility_score_v2"] = f"{score:.1f}"
        completed += 1

    temporary_path = args.input.with_suffix(".tmp")
    with temporary_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    temporary_path.replace(args.input)
    print(f"Updated {completed} v2 scores; {blank} blank due to missing component scores.")


if __name__ == "__main__":
    main()
