"""Local Streamlit interface for single-property accessibility assessments."""
from __future__ import annotations

import csv
import io
from datetime import datetime

import streamlit as st

from scoring_service import assess_property, recent_assessments

st.set_page_config(page_title="Accessibility scorer", page_icon="📍", layout="wide")
st.title("Property accessibility scorer")
st.caption("Assess a single property from its latitude and longitude. Scores are saved locally and repeated locations use the local cache.")

with st.expander("Data and scoring note", expanded=False):
    st.write("When a location is not already cached, its coordinates are sent to public Overpass services to retrieve OpenStreetMap features. Results are a screening signal, not an automatic approval or rejection decision.")

with st.form("assessment"):
    left, right = st.columns(2)
    with left:
        latitude = st.number_input("Latitude", min_value=-90.0, max_value=90.0, format="%.7f")
    with right:
        longitude = st.number_input("Longitude", min_value=-180.0, max_value=180.0, format="%.7f")
        st.caption("Use the best available vehicle-arrival coordinate when possible.")
    st.subheader("Overall-score weights")
    weight_a, weight_b = st.columns(2)
    with weight_a:
        connectivity_weight = st.number_input("Connectivity weight", min_value=0.0, max_value=100.0, value=50.0, step=1.0)
    with weight_b:
        road_width_weight = st.number_input("Road-width weight", min_value=0.0, max_value=100.0, value=50.0, step=1.0)
    submitted = st.form_submit_button("Calculate accessibility score", type="primary")

if submitted:
    code = f"manual-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    st.session_state["location_preview"] = {
        "latitude": latitude,
        "longitude": longitude,
    }
    try:
        with st.spinner("Retrieving map data and calculating scores…"):
            st.session_state["latest_result"] = assess_property(code, latitude, longitude, connectivity_weight, road_width_weight)
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
    st.caption(f"Source: {result['data_source']} · Saved: {result['created_at']}")
    metrics = [("Overall", "overall_accessibility_score"), ("Connectivity", "connectivity_score"), ("Road width", "road_width_score"), ("Vehicle access", "vehicle_access_score"), ("Guest convenience", "guest_convenience_score"), ("Operational access", "operational_access_score"), ("Data confidence", "data_confidence_score")]
    for start in range(0, len(metrics), 4):
        columns = st.columns(4)
        for column, (label, key) in zip(columns, metrics[start:start + 4]):
            value = result.get(key)
            column.metric(label, "—" if value is None else f"{float(value):.1f}/100")
    details = {"β connectivity index": result.get("beta"), "Nearest road": result.get("nearest_road_type"), "Road width (m)": result.get("nearest_road_width_m"), "Width source": result.get("width_source"), "Coordinate to road (m)": result.get("coordinate_to_road_m"), "Nearby POIs": result.get("nearby_poi_count"), "POI categories": result.get("nearby_poi_categories")}
    st.dataframe([details], width="stretch", hide_index=True)
    if result.get("flags"):
        st.warning("Review flags: " + result["flags"].replace(";", " · "))

st.divider()
st.subheader("Saved assessments")
history = recent_assessments()
if history:
    st.dataframe(history, width="stretch", hide_index=True)
    fields = list(dict.fromkeys(key for row in history for key in row))
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader(); writer.writerows(history)
    st.download_button("Download saved assessments as CSV", output.getvalue(), "accessibility_assessments.csv", "text/csv")
else:
    st.info("No assessments saved yet.")

st.caption("Planned next capability: batch upload with a downloadable CSV template.")
