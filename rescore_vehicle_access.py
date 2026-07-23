#!/usr/bin/env python3
"""Recalculate vehicle access and overall accessibility v2 from local OSM caches.

No Overpass requests are made. The input score CSV is replaced atomically after all
rows have been recalculated from their existing cached map responses.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from concurrent.futures import ProcessPoolExecutor
from functools import partial
from pathlib import Path

import accessibility_poc as poc


def revised_scores(source: dict[str, str] | None, config: dict) -> tuple[str | None, str | None]:
    """Return revised vehicle and v2 values from one existing local cache file."""
    if source is None:
        return None, None
    key_source = (
        f"{source['PROPERTY_CODE']}|{source['LATITUDE']}|{source['LONGITUDE']}|"
        f"{config['road_radius_m']}|{config['poi_radius_m']}"
    )
    cache_path = Path("data") / "cache" / f"{hashlib.sha256(key_source.encode()).hexdigest()[:20]}.json"
    if not cache_path.exists():
        return None, None
    data = json.loads(cache_path.read_text(encoding="utf-8"))
    elements = data.get("elements", [])
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
    raw_width, _ = poc.parse_width_m(tags, config["road_width_fallback_m"])
    vehicle_score = poc.vehicle_access_score(
        tags, raw_width, distance, config["score_thresholds"], nearest is not None
    )
    return str(vehicle_score), None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="Existing completed score CSV to update.")
    parser.add_argument("--properties", type=Path, default=Path("properties.csv"))
    parser.add_argument("--config", type=Path, default=Path("config.json"))
    args = parser.parse_args()

    config = json.loads(args.config.read_text(encoding="utf-8"))
    with args.properties.open(newline="", encoding="utf-8-sig") as stream:
        properties = {row["PROPERTY_CODE"]: row for row in csv.DictReader(stream)}
    with args.input.open(newline="", encoding="utf-8-sig") as stream:
        rows = list(csv.DictReader(stream))
        fieldnames = list(rows[0]) if rows else []

    changed, unavailable = 0, 0
    sources = [properties.get(row.get("PROPERTY_CODE", "")) for row in rows]
    # Geometry distance calculations are CPU-bound, so processes (rather than
    # threads) make the local cache rescore complete promptly on Windows.
    with ProcessPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(partial(revised_scores, config=config), sources))
    for index, (row, (vehicle_value, _)) in enumerate(zip(rows, results), start=1):
        if vehicle_value is None:
            unavailable += 1
            continue
        old_vehicle = row.get("vehicle_access_score", "")
        row["vehicle_access_score"] = vehicle_value
        if row["vehicle_access_score"] != old_vehicle:
            changed += 1

        try:
            connectivity = float(row["connectivity_score"])
            row["overall_accessibility_score_v2"] = f"{(connectivity + float(vehicle_value)) / 2:.1f}"
        except (KeyError, TypeError, ValueError):
            row["overall_accessibility_score_v2"] = ""
        if index % 500 == 0 or index == len(rows):
            print(f"[{index}/{len(rows)}] rescored", flush=True)

    temporary = args.input.with_suffix(".tmp")
    with temporary.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(args.input)
    print(f"Updated {len(rows)} rows; vehicle score changed for {changed}; unavailable cache rows: {unavailable}.")


if __name__ == "__main__":
    main()
