#!/usr/bin/env python3
"""Pearson correlations between POC metrics and monthly day-specific occupancy."""
import argparse
import csv
from pathlib import Path

import pandas as pd

METRICS = [
    "overall_accessibility_score", "connectivity_score", "road_width_score",
    "vehicle_access_score", "guest_convenience_score", "operational_access_score",
    "data_confidence_score", "beta", "graph_nodes", "graph_links",
    "nearest_road_width_m", "coordinate_to_road_m", "nearby_poi_count",
    "nearby_poi_categories",
]
DAYS = {
    "weekday": "OCCUPANCY_WEEKDAY",
    "friday": "OCCUPANCY_FRIDAY",
    "saturday": "OCCUPANCY_SATURDAY",
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--accessibility", type=Path, required=True)
    parser.add_argument("--occupancy", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--exclude-never-positive", action="store_true", help="Exclude properties with no positive occupancy in any available month/day value.")
    args = parser.parse_args()
    accessibility = pd.read_csv(args.accessibility)
    occupancy = pd.read_csv(args.occupancy)
    occupancy["MONTH_YEAR"] = pd.to_datetime(occupancy["MONTH_YEAR"])
    joined = accessibility.merge(occupancy, on="PROPERTY_CODE", how="inner")
    for column in METRICS + list(DAYS.values()):
        joined[column] = pd.to_numeric(joined[column], errors="coerce")
    if args.exclude_never_positive:
        occupancy_columns = list(DAYS.values())
        active = joined.groupby("PROPERTY_CODE")[occupancy_columns].max().max(axis=1).gt(0)
        joined = joined[joined["PROPERTY_CODE"].isin(active[active].index)]
    rows = []
    for month, month_data in joined.groupby(joined["MONTH_YEAR"].dt.strftime("%Y-%m")):
        for day, occupancy_column in DAYS.items():
            for metric in METRICS:
                usable = month_data[[metric, occupancy_column]].dropna()
                rows.append({
                    "month": month,
                    "occupancy_day_type": day,
                    "poc_metric": metric,
                    "pearson_correlation": round(usable[metric].corr(usable[occupancy_column]), 4),
                    "property_count": len(usable),
                })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} correlations to {args.output}")


if __name__ == "__main__":
    main()
