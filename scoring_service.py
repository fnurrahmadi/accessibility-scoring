"""Reusable single-property accessibility scoring service with SQLite persistence."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from accessibility_poc import ROOT, fetch_overpass, overpass_query, score_property

DATABASE_PATH = ROOT / "data" / "accessibility_service.sqlite3"
RAW_CACHE_DIR = ROOT / "data" / "ui_raw_cache"


def load_config() -> dict[str, Any]:
    return json.loads((ROOT / "config.json").read_text(encoding="utf-8"))


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("""CREATE TABLE IF NOT EXISTS raw_cache (
        cache_key TEXT PRIMARY KEY, response_json TEXT NOT NULL, fetched_at TEXT NOT NULL
    )""")
    connection.execute("""CREATE TABLE IF NOT EXISTS assessments (
        id INTEGER PRIMARY KEY AUTOINCREMENT, property_code TEXT NOT NULL, latitude REAL NOT NULL,
        longitude REAL NOT NULL, connectivity_weight REAL NOT NULL, road_width_weight REAL NOT NULL,
        source TEXT NOT NULL, created_at TEXT NOT NULL, result_json TEXT NOT NULL
    )""")
    return connection


def raw_cache_key(latitude: float, longitude: float, config: dict[str, Any]) -> str:
    value = f"{latitude:.7f}|{longitude:.7f}|{config['road_radius_m']}|{config['poi_radius_m']}"
    return hashlib.sha256(value.encode()).hexdigest()[:24]


def get_raw_data(connection: sqlite3.Connection, latitude: float, longitude: float, config: dict[str, Any]) -> tuple[dict[str, Any], str]:
    key = raw_cache_key(latitude, longitude, config)
    cached = connection.execute("SELECT response_json FROM raw_cache WHERE cache_key = ?", (key,)).fetchone()
    if cached:
        return json.loads(cached["response_json"]), "SQLite cache"
    RAW_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    file_cache = RAW_CACHE_DIR / f"{key}.json"
    existed = file_cache.exists()
    data = fetch_overpass(overpass_query(latitude, longitude, config["road_radius_m"], config["poi_radius_m"]), config, file_cache)
    connection.execute("INSERT OR REPLACE INTO raw_cache VALUES (?, ?, ?)", (key, json.dumps(data), datetime.now(timezone.utc).isoformat()))
    connection.commit()
    return data, "Local file cache" if existed else "Public Overpass"


def assess_property(property_code: str, latitude: float, longitude: float, connectivity_weight: float, road_width_weight: float) -> dict[str, Any]:
    if connectivity_weight < 0 or road_width_weight < 0 or connectivity_weight + road_width_weight <= 0:
        raise ValueError("At least one positive weight is required.")
    config = load_config()
    config["initial_weights"] = {"connectivity": connectivity_weight, "road_width": road_width_weight}
    connection = connect()
    try:
        raw_data, source = get_raw_data(connection, latitude, longitude, config)
        result = score_property({"PROPERTY_CODE": property_code, "LATITUDE": str(latitude), "LONGITUDE": str(longitude), "CITY": ""}, raw_data, config)
        result.update({"connectivity_weight": connectivity_weight, "road_width_weight": road_width_weight, "data_source": source, "created_at": datetime.now(timezone.utc).isoformat(), "processing_status": "scored", "error_message": ""})
        connection.execute("""INSERT INTO assessments (property_code, latitude, longitude, connectivity_weight, road_width_weight, source, created_at, result_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""", (property_code, latitude, longitude, connectivity_weight, road_width_weight, source, result["created_at"], json.dumps(result)))
        connection.commit()
        return result
    finally:
        connection.close()


def recent_assessments(limit: int = 200) -> list[dict[str, Any]]:
    connection = connect()
    try:
        rows = connection.execute("SELECT result_json FROM assessments ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [json.loads(row["result_json"]) for row in rows]
    finally:
        connection.close()
