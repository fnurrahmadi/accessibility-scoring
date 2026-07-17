#!/usr/bin/env python3
"""Accessibility-scoring POC using OpenStreetMap data via the public Overpass API.

The script deliberately defaults to a deterministic, city-stratified sample rather
than the full input file. It sends one compact Overpass request per uncached property.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from http.client import IncompleteRead
from json import JSONDecodeError
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
VEHICLE_EXCLUDED = {"footway", "cycleway", "path", "steps", "pedestrian", "bridleway", "corridor", "construction", "proposed"}
POI_AMENITIES = {"restaurant", "cafe", "fast_food", "bar", "pub", "supermarket", "convenience", "pharmacy", "atm", "bank", "hospital", "clinic", "doctors", "taxi", "bus_station", "ferry_terminal"}
ROAD_SCORES = {"motorway": 100, "trunk": 95, "primary": 90, "secondary": 80, "tertiary": 70, "unclassified": 60, "residential": 55, "living_street": 45, "service": 35, "track": 15}


def clamp(value: float, low: float = 0, high: float = 100) -> float:
    return max(low, min(high, value))


def haversine_m(a_lat: float, a_lon: float, b_lat: float, b_lon: float) -> float:
    radius = 6_371_000
    p1, p2 = math.radians(a_lat), math.radians(b_lat)
    dp, dl = p2 - p1, math.radians(b_lon - a_lon)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(h))


def point_segment_distance_m(lat: float, lon: float, a: tuple[float, float], b: tuple[float, float]) -> float:
    """Local equirectangular projection; accurate enough within the POC radius."""
    lat_scale = 111_320.0
    lon_scale = lat_scale * math.cos(math.radians(lat))
    ax, ay = (a[1] - lon) * lon_scale, (a[0] - lat) * lat_scale
    bx, by = (b[1] - lon) * lon_scale, (b[0] - lat) * lat_scale
    dx, dy = bx - ax, by - ay
    denom = dx * dx + dy * dy
    if denom == 0:
        return math.hypot(ax, ay)
    t = clamp((-(ax * dx + ay * dy)) / denom, 0, 1)
    return math.hypot(ax + t * dx, ay + t * dy)


def parse_width_m(tags: dict[str, str], fallback: dict[str, float]) -> tuple[float | None, str]:
    for key, source in (("width", "width"), ("est_width", "estimated_width")):
        raw = tags.get(key, "")
        if raw:
            cleaned = raw.lower().replace("metres", "").replace("meters", "").replace("m", "").strip()
            try:
                return float(cleaned), source
            except ValueError:
                pass
    try:
        lanes = float(tags.get("lanes", ""))
        if lanes > 0:
            return lanes * 3.0, "lanes_estimate"
    except ValueError:
        pass
    road_type = tags.get("highway", "")
    if road_type in fallback:
        return fallback[road_type], "road_class_fallback"
    return None, "unavailable"


def overpass_query(lat: float, lon: float, road_radius: int, poi_radius: int) -> str:
    # Roads and POI nodes are returned together. Recursing only the road set yields
    # the OSM node IDs needed to construct an actual topological road graph.
    return f'''[out:json][timeout:25];
way(around:{road_radius},{lat},{lon})[highway]->.roads;
node(around:{poi_radius},{lat},{lon})[amenity~"restaurant|cafe|fast_food|bar|pub|supermarket|convenience|pharmacy|atm|bank|hospital|clinic|doctors|taxi|bus_station|ferry_terminal"]->.amenities;
node(around:{poi_radius},{lat},{lon})[highway=bus_stop]->.bus_stops;
node(around:{poi_radius},{lat},{lon})[public_transport~"platform|stop_position"]->.transit;
(.roads;.amenities;.bus_stops;.transit;);
out body;
.roads >;
out skel qt;'''


def fetch_overpass(query: str, config: dict[str, Any], cache_file: Path | None) -> dict[str, Any]:
    if cache_file and cache_file.exists():
        return json.loads(cache_file.read_text(encoding="utf-8"))
    payload = urlencode({"data": query}).encode("utf-8")
    endpoints = config.get("overpass_urls") or [config["overpass_url"]]
    for attempt in range(config["retry_attempts"]):
        endpoint = endpoints[attempt % len(endpoints)]
        request = Request(endpoint, data=payload, headers={"User-Agent": "locationaccessibility-poc/0.1 (internal proof of concept)"})
        try:
            with urlopen(request, timeout=config["request_timeout_seconds"]) as response:
                data = json.loads(response.read().decode("utf-8"))
            if cache_file:
                cache_file.parent.mkdir(parents=True, exist_ok=True)
                cache_file.write_text(json.dumps(data), encoding="utf-8")
            return data
        except HTTPError as error:
            if error.code not in {429, 504} or attempt == config["retry_attempts"] - 1:
                raise RuntimeError(f"Overpass returned HTTP {error.code}") from error
        except (URLError, OSError, IncompleteRead, JSONDecodeError) as error:
            if attempt == config["retry_attempts"] - 1:
                raise RuntimeError(f"Could not complete an Overpass request: {error}") from error
        time.sleep(2 ** attempt * 3)
    raise RuntimeError("Overpass retry attempts exhausted")


def select_sample(rows: list[dict[str, str]], size: int, seed: int) -> list[dict[str, str]]:
    """Deterministic city-stratified sample, preserving representation of small cities."""
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[row.get("CITY", "Unknown") or "Unknown"].append(row)
    if len(rows) <= size:
        return rows
    rng = random.Random(seed)
    for group in groups.values():
        rng.shuffle(group)
    # A minimum of one per city would exceed a 100-row sample when the source has
    # more than 100 cities. Largest-remainder allocation preserves city proportions
    # while keeping the hard request cap exact.
    quotas = {city: size * len(group) / len(rows) for city, group in groups.items()}
    allocation = {city: min(len(groups[city]), math.floor(quota)) for city, quota in quotas.items()}
    remaining = size - sum(allocation.values())
    for city in sorted(groups, key=lambda c: (quotas[c] - allocation[c], len(groups[c])), reverse=True):
        if remaining == 0:
            break
        if allocation[city] < len(groups[city]):
            allocation[city] += 1
            remaining -= 1
    return [row for city, group in sorted(groups.items()) for row in group[:allocation[city]]]


def build_network(elements: list[dict[str, Any]]) -> tuple[dict[int, tuple[float, float]], list[dict[str, Any]], dict[int, set[int]]]:
    nodes = {e["id"]: (e["lat"], e["lon"]) for e in elements if e.get("type") == "node" and "lat" in e and "lon" in e}
    roads = [e for e in elements if e.get("type") == "way" and e.get("tags", {}).get("highway") not in VEHICLE_EXCLUDED]
    adjacency: dict[int, set[int]] = defaultdict(set)
    for road in roads:
        valid = [n for n in road.get("nodes", []) if n in nodes]
        for a, b in zip(valid, valid[1:]):
            adjacency[a].add(b)
            adjacency[b].add(a)
    return nodes, roads, adjacency


def topology_beta(adjacency: dict[int, set[int]]) -> tuple[float | None, int, int]:
    """Count links between real intersections/dead ends; degree-2 shape points are excluded."""
    if not adjacency:
        return None, 0, 0
    important = {node for node, neighbours in adjacency.items() if len(neighbours) != 2}
    if not important:
        return 1.0, 1, 1  # isolated loop: one circuit
    traversed: set[tuple[int, int]] = set()
    links = 0
    for start in important:
        for next_node in adjacency[start]:
            edge = tuple(sorted((start, next_node)))
            if edge in traversed:
                continue
            previous, current = start, next_node
            traversed.add(edge)
            while current not in important:
                options = adjacency[current] - {previous}
                if not options:
                    break
                following = next(iter(options))
                traversed.add(tuple(sorted((current, following))))
                previous, current = current, following
            links += 1
    return links / len(important), len(important), links


def nearest_road(lat: float, lon: float, roads: list[dict[str, Any]], nodes: dict[int, tuple[float, float]]) -> tuple[dict[str, Any] | None, float | None]:
    winner, best = None, float("inf")
    for road in roads:
        geometry = [nodes[n] for n in road.get("nodes", []) if n in nodes]
        for a, b in zip(geometry, geometry[1:]):
            distance = point_segment_distance_m(lat, lon, a, b)
            if distance < best:
                winner, best = road, distance
    return winner, (best if winner else None)


def score_property(row: dict[str, str], data: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    lat, lon = float(row["LATITUDE"]), float(row["LONGITUDE"])
    elements = data.get("elements", [])
    nodes, roads, adjacency = build_network(elements)
    beta, graph_nodes, graph_links = topology_beta(adjacency)
    nearest, snap_distance = nearest_road(lat, lon, roads, nodes)
    tags = nearest.get("tags", {}) if nearest else {}
    raw_width, width_source = parse_width_m(tags, config["road_width_fallback_m"])
    thresholds = config["score_thresholds"]
    width_score = None if raw_width is None else clamp((raw_width - thresholds["width_min_m"]) / (thresholds["width_max_m"] - thresholds["width_min_m"]) * 100)
    # Beta values around 1 indicate tree-like access; 2.5 is treated as strong local redundancy.
    connectivity_score = None if beta is None else clamp((beta - 0.8) / (2.5 - 0.8) * 100)
    weights = config["initial_weights"]
    available = [(connectivity_score, weights["connectivity"]), (width_score, weights["road_width"])]
    available = [(score, weight) for score, weight in available if score is not None]
    overall = round(sum(score * weight for score, weight in available) / sum(weight for _, weight in available), 1) if available else None

    road_base = ROAD_SCORES.get(tags.get("highway", ""), 30)
    restrictions = 0
    if tags.get("access") in {"no", "private"} or tags.get("motor_vehicle") == "no" or tags.get("vehicle") == "no":
        restrictions += 60
    if tags.get("surface") in {"gravel", "ground", "dirt", "sand", "unpaved"}:
        restrictions += 20
    if tags.get("noexit") == "yes":
        restrictions += 15
    snap_score = 100 if snap_distance is not None and snap_distance <= thresholds["snap_distance_good_m"] else (0 if snap_distance is None else clamp(100 * (thresholds["snap_distance_poor_m"] - snap_distance) / (thresholds["snap_distance_poor_m"] - thresholds["snap_distance_good_m"])))
    vehicle_score = round(clamp(0.4 * road_base + 0.3 * (width_score if width_score is not None else 45) + 0.3 * snap_score - restrictions), 1)

    poi_nodes = [e for e in elements if e.get("type") == "node" and (e.get("tags", {}).get("amenity") in POI_AMENITIES or e.get("tags", {}).get("highway") == "bus_stop" or e.get("tags", {}).get("public_transport") in {"platform", "stop_position"})]
    poi_categories = {e.get("tags", {}).get("amenity") or e.get("tags", {}).get("highway") or e.get("tags", {}).get("public_transport") for e in poi_nodes}
    guest_score = round(clamp((0.7 * min(len(poi_nodes), thresholds["guest_poi_target"]) / thresholds["guest_poi_target"] + 0.3 * min(len(poi_categories), 6) / 6) * 100), 1)

    operation_bonus = 0
    if tags.get("oneway") != "yes": operation_bonus += 10
    if tags.get("highway") not in {"service", "track"}: operation_bonus += 15
    if raw_width and raw_width >= 5: operation_bonus += 20
    if tags.get("surface") in {"asphalt", "concrete", "paved"}: operation_bonus += 15
    operation_score = round(clamp(snap_score * 0.4 + operation_bonus), 1)

    evidence = 0
    evidence += 30 if nearest else 0
    evidence += 20 if snap_distance is not None and snap_distance <= thresholds["snap_distance_poor_m"] else 0
    evidence += 15 if beta is not None and graph_nodes >= 3 else 0
    evidence += 15 if width_source in {"width", "estimated_width", "lanes_estimate"} else (8 if width_source == "road_class_fallback" else 0)
    evidence += 10 if tags.get("surface") else 0
    evidence += 10 if any(tags.get(k) for k in ("access", "motor_vehicle", "vehicle", "oneway")) else 0
    confidence_score = round(clamp(evidence), 1)
    flags = []
    if width_source.endswith("fallback"): flags.append("missing_width_used_fallback")
    if not nearest: flags.append("no_nearby_drivable_road")
    if snap_distance and snap_distance > thresholds["snap_distance_poor_m"]: flags.append("coordinate_far_from_road")
    if tags.get("noexit") == "yes": flags.append("dead_end")
    if tags.get("oneway") == "yes": flags.append("one_way_final_approach")
    if confidence_score < 50: flags.append("low_data_confidence")
    return {**row, "overall_accessibility_score": overall, "connectivity_score": None if connectivity_score is None else round(connectivity_score, 1), "road_width_score": None if width_score is None else round(width_score, 1), "vehicle_access_score": vehicle_score, "guest_convenience_score": guest_score, "operational_access_score": operation_score, "data_confidence_score": confidence_score, "beta": None if beta is None else round(beta, 3), "graph_nodes": graph_nodes, "graph_links": graph_links, "nearest_road_type": tags.get("highway"), "nearest_road_width_m": raw_width, "width_source": width_source, "coordinate_to_road_m": None if snap_distance is None else round(snap_distance, 1), "nearby_poi_count": len(poi_nodes), "nearby_poi_categories": len(poi_categories), "flags": ";".join(flags)}


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(dict.fromkeys(key for row in rows for key in row.keys()))
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "properties.csv")
    parser.add_argument("--config", type=Path, default=ROOT / "config.json")
    parser.add_argument("--sample-size", type=int, help="Override the configured sample size.")
    parser.add_argument("--workers", type=int, default=1, help="Concurrent uncached Overpass requests (default: 1).")
    parser.add_argument("--property-code", action="append", help="Process only this property code; repeat for multiple codes.")
    parser.add_argument("--update-results", type=Path, help="Replace matching property rows in an existing result CSV.")
    parser.add_argument("--dry-run", action="store_true", help="Select and report the sample without contacting Overpass.")
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    with args.input.open(newline="", encoding="utf-8-sig") as stream:
        all_rows = list(csv.DictReader(stream))
    valid, invalid = [], []
    for row in all_rows:
        try:
            lat, lon = float(row["LATITUDE"]), float(row["LONGITUDE"])
            if not (-90 <= lat <= 90 and -180 <= lon <= 180): raise ValueError
            valid.append(row)
        except (KeyError, TypeError, ValueError):
            invalid.append(row)
    if args.property_code:
        requested = set(args.property_code)
        sample = [row for row in valid if row["PROPERTY_CODE"] in requested]
        missing = requested - {row["PROPERTY_CODE"] for row in sample}
        if missing:
            parser.error(f"Property codes not found: {', '.join(sorted(missing))}")
    else:
        sample = select_sample(valid, args.sample_size or config["sample_size"], config["sample_seed"])
    print(f"Selected {len(sample)} valid properties from {len(valid)} valid rows ({len(invalid)} invalid rows excluded).")
    print("City allocation:", dict(sorted(Counter(r.get("CITY", "Unknown") for r in sample).items())))
    if args.dry_run:
        return
    def process(row: dict[str, str]) -> dict[str, Any]:
        key = hashlib.sha256(f"{row['PROPERTY_CODE']}|{row['LATITUDE']}|{row['LONGITUDE']}|{config['road_radius_m']}|{config['poi_radius_m']}".encode()).hexdigest()[:20]
        cache = ROOT / "data" / "cache" / f"{key}.json"
        was_cached = cache.exists()
        data = fetch_overpass(overpass_query(float(row["LATITUDE"]), float(row["LONGITUDE"]), config["road_radius_m"], config["poi_radius_m"]), config, cache)
        if not was_cached:
            time.sleep(config["request_delay_seconds"])
        return score_property(row, data, config)

    results = []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = {executor.submit(process, row): row for row in sample}
        for index, future in enumerate(as_completed(futures), start=1):
            row = futures[future]
            try:
                result = future.result()
                result["processing_status"] = "scored"
                result["error_message"] = ""
            except Exception as error:
                # A public-instance failure must not discard the rest of the batch.
                # The row is retained explicitly for a later retry.
                result = {**row, "processing_status": "retry_required", "error_message": str(error)}
            results.append(result)
            write_csv(ROOT / "data" / "output" / "accessibility_poc_partial.csv", results)
            print(f"[{index}/{len(sample)}] scored {result['PROPERTY_CODE']}", flush=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = ROOT / "data" / "output" / f"accessibility_poc_{stamp}.csv"
    write_csv(output, results)
    print(f"Wrote {len(results)} scores to {output}")
    if args.update_results:
        with args.update_results.open(newline="", encoding="utf-8-sig") as stream:
            existing = list(csv.DictReader(stream))
        replacements = {row["PROPERTY_CODE"]: row for row in results}
        merged = [replacements.get(row["PROPERTY_CODE"], row) for row in existing]
        write_csv(args.update_results, merged)
        print(f"Updated {len(replacements)} rows in {args.update_results}")


if __name__ == "__main__":
    main()
