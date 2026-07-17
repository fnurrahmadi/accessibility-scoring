#!/usr/bin/env python3
"""Create automated evaluation outputs from an accessibility POC result CSV."""

from __future__ import annotations

import argparse
import csv
import math
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median

ROOT = Path(__file__).resolve().parent


def number(value: str) -> float | None:
    try:
        return float(value) if value not in ("", None) else None
    except ValueError:
        return None


def percentile(values: list[float], point: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * point
    low, high = math.floor(position), math.ceil(position)
    if low == high:
        return ordered[low]
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Completed accessibility result CSV.")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data" / "output" / "evaluation")
    args = parser.parse_args()
    with args.input.open(newline="", encoding="utf-8-sig") as stream:
        rows = list(csv.DictReader(stream))
    scored = [row for row in rows if row.get("processing_status") == "scored" and number(row.get("overall_accessibility_score")) is not None]
    if not scored:
        raise SystemExit("No successfully scored rows found.")

    scores = [number(row["overall_accessibility_score"]) for row in scored]
    low_cutoff, high_cutoff = percentile(scores, 0.10), percentile(scores, 0.90)
    city_groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in scored:
        city_groups[row["CITY"]].append(row)

    city_summary = []
    for city, group in sorted(city_groups.items()):
        city_scores = [number(row["overall_accessibility_score"]) for row in group]
        city_summary.append({
            "city": city,
            "property_count": len(group),
            "mean_overall_accessibility_score": round(mean(city_scores), 1),
            "median_overall_accessibility_score": round(median(city_scores), 1),
            "minimum_score": round(min(city_scores), 1),
            "maximum_score": round(max(city_scores), 1),
            "mean_data_confidence_score": round(mean(number(row["data_confidence_score"]) for row in group), 1),
            "width_fallback_count": sum(row.get("width_source") == "road_class_fallback" for row in group),
            "low_confidence_count": sum((number(row.get("data_confidence_score")) or 0) < 60 for row in group),
        })

    review_queue = []
    for row in scored:
        score = number(row["overall_accessibility_score"])
        confidence = number(row.get("data_confidence_score")) or 0
        road_distance = number(row.get("coordinate_to_road_m"))
        reasons = []
        priority = 0
        if score <= low_cutoff:
            reasons.append("lowest_10_percent_of_scores")
            priority += 2
        if score >= high_cutoff:
            reasons.append("highest_10_percent_of_scores")
            priority += 1
        if confidence < 60:
            reasons.append("low_data_confidence")
            priority += 3
        if row.get("width_source") == "road_class_fallback":
            reasons.append("road_width_is_fallback_estimate")
            priority += 1
        if road_distance is None or road_distance > 150:
            reasons.append("coordinate_far_from_drivable_road")
            priority += 3
        if row.get("flags"):
            reasons.append(f"flags:{row['flags']}")
            priority += 1
        if reasons:
            review_queue.append({
                "review_priority": "high" if priority >= 4 else "medium" if priority >= 2 else "low",
                "priority_points": priority,
                "review_reasons": ";".join(reasons),
                **row,
            })

    review_queue.sort(key=lambda row: (-int(row["priority_points"]), number(row["overall_accessibility_score"]) or 0))
    distribution = [
        {"metric": "scored_properties", "value": len(scored)},
        {"metric": "overall_score_mean", "value": round(mean(scores), 1)},
        {"metric": "overall_score_median", "value": round(median(scores), 1)},
        {"metric": "overall_score_minimum", "value": round(min(scores), 1)},
        {"metric": "overall_score_maximum", "value": round(max(scores), 1)},
        {"metric": "lowest_10_percent_cutoff", "value": round(low_cutoff, 1)},
        {"metric": "highest_10_percent_cutoff", "value": round(high_cutoff, 1)},
        {"metric": "review_queue_count", "value": len(review_queue)},
    ]
    write_csv(args.output_dir / "city_score_summary.csv", city_summary)
    write_csv(args.output_dir / "property_review_queue.csv", review_queue)
    write_csv(args.output_dir / "score_distribution_summary.csv", distribution)
    print(f"Created evaluation files for {len(scored)} scored properties in {args.output_dir}")


if __name__ == "__main__":
    main()
