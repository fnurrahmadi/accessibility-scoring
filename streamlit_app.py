"""Streamlit interface for single-property accessibility assessments."""
from __future__ import annotations

import csv
import io
import math
from pathlib import Path
from datetime import datetime

import altair as alt
import streamlit as st

from scoring_service import assess_property, recent_assessments

OUTPUT_DIRECTORY = Path(__file__).resolve().parent / "data" / "output"
V3_FULL_POPULATION_OUTPUT = OUTPUT_DIRECTORY / "accessibility_poc_20260722T062125Z_v3.csv"
FULL_POPULATION_OUTPUT = (
    V3_FULL_POPULATION_OUTPUT
    if V3_FULL_POPULATION_OUTPUT.exists()
    else OUTPUT_DIRECTORY / "accessibility_poc_20260722T062125Z.csv"
)
CHART_METRICS = [
    "overall_accessibility_score_v3",
    "overall_accessibility_score_v4",
    "overall_accessibility_score_v5",
    "base_accessibility_score_v3",
    "vehicle_access_score_v3",
    "connectivity_score_v3",
    "accessibility_status_v3",
    "overall_accessibility_score_v2",
    "overall_accessibility_score",
    "connectivity_score",
    "road_width_score",
    "vehicle_access_score",
    "guest_convenience_score",
    "operational_access_score",
    "data_confidence_score",
    "beta",
    "graph_nodes",
    "graph_links",
    "nearest_road_type",
    "nearest_road_width_m",
    "width_source",
    "coordinate_to_road_m",
    "nearby_poi_count",
    "nearby_poi_categories",
    "flags",
    "processing_status",
    "error_message",
]
SCORE_METRICS = {
    "overall_accessibility_score_v3",
    "overall_accessibility_score_v4",
    "overall_accessibility_score_v5",
    "base_accessibility_score_v3",
    "vehicle_access_score_v3",
    "connectivity_score_v3",
    "overall_accessibility_score_v2",
    "overall_accessibility_score",
    "connectivity_score",
    "road_width_score",
    "vehicle_access_score",
    "guest_convenience_score",
    "operational_access_score",
    "data_confidence_score",
}


@st.cache_data
def full_population_rows(file_modified_ns: int) -> list[dict[str, str]]:
    """Read the completed output; the modification time invalidates stale CSV cache data."""
    with FULL_POPULATION_OUTPUT.open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def current_full_population_rows() -> list[dict[str, str]]:
    return full_population_rows(FULL_POPULATION_OUTPUT.stat().st_mtime_ns)


def metric_distribution(
    metric: str, selected_cities: list[str]
) -> tuple[list[dict[str, int | str]], int, int, bool, str]:
    """Return numeric histogram bins or categorical frequency counts."""
    rows = [row for row in current_full_population_rows() if row.get("CITY") in selected_cities]
    categorical_metrics = {"nearest_road_type", "width_source", "flags", "processing_status", "error_message", "accessibility_status_v3"}

    if metric in categorical_metrics:
        counts: dict[str, int] = {}
        if metric == "flags":
            for row in rows:
                values = row.get("flags", "").strip().split(";") if row.get("flags", "").strip() else ["(none)"]
                for value in values:
                    counts[value] = counts.get(value, 0) + 1
            detail = "Each flag occurrence is counted separately; properties without a flag are shown as (none)."
        else:
            for row in rows:
                value = row.get(metric, "").strip() or "(blank)"
                counts[value] = counts.get(value, 0) + 1
            detail = "Categorical values are shown as frequency bars."
        data = [{"Value": value, "Properties": count} for value, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))]
        for order, row in enumerate(data):
            row["Order"] = order
        return data, len(rows), 0, True, detail

    values = [row.get(metric, "").strip() for row in rows if row.get(metric, "").strip()]
    missing = len(rows) - len(values)

    numeric_values = [float(value) for value in values]
    if metric in SCORE_METRICS:
        counts = [0] * 20
        for value in numeric_values:
            counts[min(int(value // 5), 19)] += 1
        labels = [f"{start}-<{start + 5}" for start in range(0, 95, 5)] + ["95-100"]
        data = [{"Value": label, "Properties": count} for label, count in zip(labels, counts)]
        for order, row in enumerate(data):
            row["Order"] = order
        return data, len(numeric_values), missing, False, "Numeric values are grouped into five-point score bins."

    minimum, maximum = min(numeric_values), max(numeric_values)
    if math.isclose(minimum, maximum):
        return [{"Value": f"{minimum:g}", "Properties": len(numeric_values), "Order": 0}], len(numeric_values), missing, False, "All populated values are identical."
    bin_width = (maximum - minimum) / 20
    counts = [0] * 20
    for value in numeric_values:
        counts[min(int((value - minimum) / bin_width), 19)] += 1
    data = []
    for index, count in enumerate(counts):
        lower = minimum + index * bin_width
        upper = minimum + (index + 1) * bin_width
        label = f"{lower:.1f}-<{upper:.1f}" if index < 19 else f"{lower:.1f}-{maximum:.1f}"
        data.append({"Value": label, "Properties": count, "Order": index})
    return data, len(numeric_values), missing, False, "Numeric values are grouped into 20 equal-width bins."


st.set_page_config(page_title="Accessibility scorer", layout="wide")
st.title("Property accessibility scorer")
st.caption(
    "Assess a single property from its latitude and longitude. Scores and cached "
    "map responses are stored in the shared database."
)

with st.expander("Data and scoring note", expanded=False):
    st.write(
        "When a location is not already cached, its coordinates are sent to public "
        "Overpass services to retrieve OpenStreetMap features. Results are a screening "
        "signal, not an automatic approval or rejection decision."
    )

with st.form("assessment"):
    left, right = st.columns(2)
    with left:
        latitude = st.number_input("Latitude", min_value=-90.0, max_value=90.0, format="%.7f")
    with right:
        longitude = st.number_input("Longitude", min_value=-180.0, max_value=180.0, format="%.7f")
        st.caption("Use the best available vehicle-arrival coordinate when possible.")
    st.caption(
        "V3 uses fixed model weights: 60% vehicle access and 40% connectivity, "
        "followed by the data-confidence adjustment and access safeguards."
    )
    submitted = st.form_submit_button("Calculate accessibility score", type="primary")

if submitted:
    code = f"manual-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    st.session_state["location_preview"] = {"latitude": latitude, "longitude": longitude}
    try:
        with st.spinner("Retrieving map data and calculating scores..."):
            st.session_state["latest_result"] = assess_property(code, latitude, longitude)
    except Exception as error:
        st.error(f"Could not calculate the score: {error}")

location_preview = st.session_state.get("location_preview")
if location_preview:
    st.subheader("Location map")
    st.map(
        [{"latitude": location_preview["latitude"], "longitude": location_preview["longitude"]}],
        latitude="latitude",
        longitude="longitude",
        zoom=15,
        width="stretch",
    )

result = st.session_state.get("latest_result")
if result:
    st.divider()
    st.subheader(f"Result: {result['PROPERTY_CODE']}")
    st.caption(
        f"Model: {result.get('scoring_model_version', 'legacy')} | "
        f"Source: {result['data_source']} | Saved: {result['created_at']}"
    )
    status_v3 = result.get("accessibility_status_v3")
    if status_v3 == "Good":
        st.success(f"V3 access status: {status_v3}")
    elif status_v3 in {"Review access", "Manual review", "Insufficient data"}:
        st.warning(f"V3 access status: {status_v3}")
    elif status_v3:
        st.error(f"V3 access status: {status_v3}")
    metrics = [
        ("Overall v3", "overall_accessibility_score_v3"),
        ("Vehicle access v3", "vehicle_access_score_v3"),
        ("Connectivity v3", "connectivity_score_v3"),
        ("Base score v3", "base_accessibility_score_v3"),
        ("Data confidence", "data_confidence_score"),
    ]
    for start in range(0, len(metrics), 4):
        columns = st.columns(4)
        for column, (label, key) in zip(columns, metrics[start : start + 4]):
            value = result.get(key)
            column.metric(label, "N/A" if value is None else f"{float(value):.1f}/100")
    details = {
        "Beta connectivity index": result.get("beta"),
        "Nearest road": result.get("nearest_road_type"),
        "Road width (m)": result.get("nearest_road_width_m"),
        "Width source": result.get("width_source"),
        "Coordinate to road (m)": result.get("coordinate_to_road_m"),
        "Nearby POIs": result.get("nearby_poi_count"),
        "POI categories": result.get("nearby_poi_categories"),
        "Connectivity reference": result.get("connectivity_reference_v3"),
    }
    st.dataframe([details], width="stretch", hide_index=True)
    if result.get("flags"):
        st.warning("Review flags: " + result["flags"].replace(";", " | "))

st.divider()
st.subheader("Full-property metric distribution")
if FULL_POPULATION_OUTPUT.exists():
    all_cities = sorted({row.get("CITY", "") for row in current_full_population_rows() if row.get("CITY", "")})
    if "distribution_cities" not in st.session_state:
        st.session_state["distribution_cities"] = all_cities
    filter_left, filter_right = st.columns([4, 1])
    with filter_right:
        if st.button("Select all cities", key="select_all_distribution_cities"):
            st.session_state["distribution_cities"] = all_cities
    with filter_left:
        selected_cities = st.multiselect(
            "Cities",
            all_cities,
            key="distribution_cities",
            placeholder="Select one or more cities",
        )
    selected_metric = st.selectbox(
        "Metric",
        CHART_METRICS,
        index=0,
        key="distribution_metric",
    )
    if selected_cities:
        distribution, populated_values, missing_values, categorical, detail = metric_distribution(selected_metric, selected_cities)
        st.caption(
            f"{len(selected_cities):,} cities selected. {populated_values:,} populated values plotted; "
            f"{missing_values} blank numeric values excluded. {detail}"
        )
        chart = (
            alt.Chart(alt.Data(values=distribution))
            .mark_bar()
            .encode(
                x=alt.X(
                    "Value:N",
                    sort=alt.SortField(field="Order", order="ascending"),
                    axis=alt.Axis(labelAngle=-90),
                    title="Value",
                ),
                y=alt.Y("Properties:Q", title="Properties"),
                tooltip=[alt.Tooltip("Value:N"), alt.Tooltip("Properties:Q", format=",")],
            )
            .properties(title=selected_metric)
        )
        # The key changes with the selected metric, so Streamlit replaces the
        # chart rather than retaining the prior chart's visual state.
        st.altair_chart(chart, width="stretch", key=f"distribution_chart_{selected_metric}")
    else:
        st.info("Select at least one city to display the distribution.")
else:
    st.info("The completed 3,709-property output file is not available on this machine.")

st.divider()
st.subheader("Saved assessments")
history = recent_assessments()
if history:
    st.dataframe(history, width="stretch", hide_index=True)
    fields = list(dict.fromkeys(key for row in history for key in row))
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    writer.writerows(history)
    st.download_button(
        "Download saved assessments as CSV",
        output.getvalue(),
        "accessibility_assessments.csv",
        "text/csv",
    )
else:
    st.info("No assessments saved yet.")

st.caption("Planned next capability: batch upload with a downloadable CSV template.")
