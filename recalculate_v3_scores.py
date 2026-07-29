#!/usr/bin/env python3
"""Add V3 accessibility scores to a completed POC CSV using only local OSM caches."""
from __future__ import annotations

import argparse
import bisect
import csv
import hashlib
import json
from concurrent.futures import ProcessPoolExecutor
from functools import partial
from pathlib import Path

import accessibility_poc as poc


V3_FIELDS = [
    "vehicle_access_score_v3",
    "connectivity_score_v3",
    "base_accessibility_score_v3",
    "overall_accessibility_score_v3",
    "accessibility_status_v3",
]


def vehicle_v3_from_cache(source: dict[str, str] | None, config: dict) -> tuple[float | None, bool | None]:
    if source is None:
        return None, None
    key_source = (
        f"{source['PROPERTY_CODE']}|{source['LATITUDE']}|{source['LONGITUDE']}|"
        f"{config['road_radius_m']}|{config['poi_radius_m']}"
    )
    cache_path = Path("data") / "cache" / f"{hashlib.sha256(key_source.encode()).hexdigest()[:20]}.json"
    if not cache_path.exists():
        return None, None
    elements = json.loads(cache_path.read_text(encoding="utf-8")).get("elements", [])
    nodes = {
        element["id"]: (element["lat"], element["lon"])
        for element in elements
        if element.get("type") == "node" and "lat" in element and "lon" in element
    }
    roads = [
        element for element in elements
        if element.get("type") == "way"
        and element.get("tags", {}).get("highway") not in poc.VEHICLE_EXCLUDED
    ]
    nearest, distance = poc.nearest_road(
        float(source["LATITUDE"]), float(source["LONGITUDE"]), roads, nodes
    )
    tags = nearest.get("tags", {}) if nearest else {}
    width, _ = poc.parse_width_m(tags, config["road_width_fallback_m"])
    return poc.vehicle_access_score_v3(
        tags, width, distance, config["score_thresholds"], nearest is not None
    )


def number(value: str | None) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except ValueError:
        return None


def percentile(value: float, ordered: list[float]) -> float:
    """Mid-rank empirical percentile, giving tied beta values the same score."""
    left = bisect.bisect_left(ordered, value)
    right = bisect.bisect_right(ordered, value)
    return 100 * ((left + right) / 2) / len(ordered)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", type=Path, help="Optional separate output path; leaves the input unchanged.")
    parser.add_argument("--properties", type=Path, default=Path("properties.csv"))
    parser.add_argument("--config", type=Path, default=Path("config.json"))
    args = parser.parse_args()

    config = json.loads(args.config.read_text(encoding="utf-8"))
    with args.properties.open(newline="", encoding="utf-8-sig") as stream:
        properties = {row["PROPERTY_CODE"]: row for row in csv.DictReader(stream)}
    with args.input.open(newline="", encoding="utf-8-sig") as stream:
        rows = list(csv.DictReader(stream))
        fieldnames = list(rows[0]) if rows else []
    for field in V3_FIELDS:
        if field not in fieldnames:
            fieldnames.append(field)

    national_beta = sorted(beta for beta in (number(row.get("beta")) for row in rows) if beta is not None)
    city_beta: dict[str, list[float]] = {}
    for row in rows:
        beta = number(row.get("beta"))
        if beta is not None:
            city_beta.setdefault(row.get("CITY", ""), []).append(beta)
    city_beta = {city: sorted(values) for city, values in city_beta.items()}

    sources = [properties.get(row.get("PROPERTY_CODE", "")) for row in rows]
    with ProcessPoolExecutor(max_workers=4) as executor:
        vehicle_results = list(executor.map(partial(vehicle_v3_from_cache, config=config), sources))

    blocked = review = insufficient = 0
    for row, (vehicle, is_hard_blocked) in zip(rows, vehicle_results):
        beta = number(row.get("beta"))
        confidence = number(row.get("data_confidence_score"))
        if vehicle is None or beta is None or confidence is None:
            row.update({
                "vehicle_access_score_v3": "" if vehicle is None else f"{vehicle:.1f}",
                "connectivity_score_v3": "",
                "base_accessibility_score_v3": "",
                "overall_accessibility_score_v3": "",
                "accessibility_status_v3": "Insufficient data",
            })
            insufficient += 1
            continue

        national = percentile(beta, national_beta)
        peers = city_beta.get(row.get("CITY", ""), [])
        connectivity = national if len(peers) < 20 else 0.75 * percentile(beta, peers) + 0.25 * national
        base = 0.60 * vehicle + 0.40 * connectivity
        adjusted = base * (0.85 + 0.15 * confidence / 100)
        if is_hard_blocked:
            overall, status = 0.0, "Blocked"
            blocked += 1
        elif vehicle < 25:
            overall, status = min(adjusted, 35), "Manual review"
            review += 1
        elif vehicle < 50:
            overall, status = min(adjusted, 60), "Review access"
            review += 1
        else:
            overall, status = adjusted, "Good"
        row.update({
            "vehicle_access_score_v3": f"{vehicle:.1f}",
            "connectivity_score_v3": f"{connectivity:.1f}",
            "base_accessibility_score_v3": f"{base:.1f}",
            "overall_accessibility_score_v3": f"{overall:.1f}",
            "accessibility_status_v3": status,
        })

    destination = args.output or args.input
    temporary = destination.with_suffix(".tmp")
    with temporary.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(destination)
    print(
        f"Updated V3 for {len(rows)} rows; blocked: {blocked}; review: {review}; "
        f"insufficient data: {insufficient}."
    )


if __name__ == "__main__":
    main()
