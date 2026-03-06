#================================
# Streamlit
#================================
import streamlit as st
import pandas as pd
import geopandas as gpd
import numpy as np
import pydeck as pdk
from shapely.geometry import mapping

from pathlib import Path
import os

# app_EAS.py 在 code/ 里，所以项目根目录是 code/ 的上一级
from pathlib import Path
import geopandas as gpd
import pandas as pd
# --- 请替换你代码中的路径定义部分 ---
import streamlit as st
from pathlib import Path
import geopandas as gpd
import pandas as pd

# project root is the parent of the `code/` directory
ROOT = Path(__file__).resolve().parents[1]

# data files live under the project's data/derived-data directory
COUNTIES_PATH = ROOT / "data" / "derived-data" / "counties.geojson"
SCHOOLS_PATH  = ROOT / "data" / "derived-data" / "schools.geojson"
COUNTS_PATH   = ROOT / "data" / "derived-data" / "county_school_counts_by_radius.csv"
EAS_PATH      = ROOT / "data" / "derived-data" / "eas_by_radius.csv"

# Debug helper: show a clear Streamlit message if the geojson is missing
if not COUNTIES_PATH.exists():
    st.error(f"找不到文件！我正在尝试访问：{COUNTIES_PATH}")
    st.info(f"项目根目录：{ROOT}")
    st.info(f"当前的运行目录是：{Path.cwd()}")
# -------------------------------------------------------

# -----------------------------
# Config
# -----------------------------
st.set_page_config(page_title="Education Access Map", layout="wide")

PROJECTED_CRS = "EPSG:5070"  # meters
WGS84 = "EPSG:4326"
MILES_TO_METERS = 1609.344
RADII = [25, 50, 75]
EXCLUDE_STATES = ['AK', 'HI', 'AS', 'GU', 'MP', 'PR', 'VI']

# -----------------------------
# Load data (cache)
# -----------------------------
@st.cache_data
def load_data():
    counties = gpd.read_file(COUNTIES_PATH)
    schools = gpd.read_file(SCHOOLS_PATH)
    counts = pd.read_csv(COUNTS_PATH)
    eas = pd.read_csv(EAS_PATH)

    # Clean filters (CONUS only)
    counties = counties[~counties["state"].isin(EXCLUDE_STATES)].copy()
    schools = schools[~schools["state"].isin(EXCLUDE_STATES)].copy()

    # Ensure CRS
    if counties.crs is None:
        counties = counties.set_crs(WGS84)
    if schools.crs is None:
        schools = schools.set_crs(WGS84)

    # merge counts onto counties
    counties = counties.merge(
        counts,
        on=["county_name", "state_name", "state"],
        how="left",
        validate="1:1"
    )

    # merge EAS onto counties (for metrics)
    counties = counties.merge(
        eas[["county_name", "state_name", "eas_25mi_per10k", "eas_50mi_per10k", "eas_75mi_per10k"]],
        on=["county_name", "state_name"],
        how="left"
    )

    return counties, schools

counties_ll, schools_ll = load_data()

# Add a user-friendly county label
counties_ll["county_label"] = counties_ll["county_name"] + ", " + counties_ll["state"]

# -----------------------------
# Sidebar controls
# -----------------------------
st.sidebar.header("Controls")

county_label = st.sidebar.selectbox(
    "Select a county",
    options=sorted(counties_ll["county_label"].dropna().unique().tolist())
)

radius_mi = st.sidebar.radio(
    "Radius (miles)",
    options=RADII,
    index=1,  # default 50
    horizontal=True
)

# pull selected county row
county_row = counties_ll.loc[counties_ll["county_label"] == county_label].iloc[0:1].copy()
county_geom_ll = county_row.geometry.iloc[0]

# -----------------------------
# Build buffer circle + schools within buffer
# -----------------------------
# project for accurate distance buffers
county_gdf_p = gpd.GeoDataFrame(county_row, geometry="geometry", crs=WGS84).to_crs(PROJECTED_CRS)
schools_p = schools_ll.to_crs(PROJECTED_CRS)

# representative point (more robust than centroid for weird shapes)
rep_pt = county_gdf_p.geometry.representative_point().iloc[0]

buffer_poly_p = rep_pt.buffer(radius_mi * MILES_TO_METERS)
buffer_poly_ll = gpd.GeoSeries([buffer_poly_p], crs=PROJECTED_CRS).to_crs(WGS84).iloc[0]

# schools inside buffer
buf_gdf_p = gpd.GeoDataFrame(geometry=[buffer_poly_p], crs=PROJECTED_CRS)
schools_in = gpd.sjoin(
    schools_p,
    buf_gdf_p,
    how="inner",
    predicate="within"
).copy()

schools_in_ll = schools_in.to_crs(WGS84)

# counts (two ways: from sjoin, and from precomputed column)
count_live = len(schools_in_ll)
col_pre = f"schools_within_{radius_mi}mi"
count_pre = int(county_row[col_pre].fillna(0).iloc[0]) if col_pre in county_row.columns else None

# EAS metric value (dynamic based on radius)
eas_col = f"eas_{radius_mi}mi_per10k"
eas_val = county_row[eas_col].iloc[0] if eas_col in county_row.columns else np.nan

# -----------------------------
# Header metrics (prominent county label; show live schools and EAS)
# -----------------------------
st.title("Education Access Explorer")

# Prominent county name
st.header(county_label)

# Two concise metric columns: live schools and EAS
c1, c2 = st.columns(2)
c1.metric(f"Schools within {radius_mi} miles (live)", f"{count_live}")
c2.metric(f"EAS ({radius_mi} mi, per 10k age 18–24)", f"{eas_val:.2f}" if pd.notna(eas_val) else "N/A")

st.caption("Tip: You can zoom/pan the map. The circle is centered at a representative point of the county.")
# -----------------------------
# Prepare GeoJSON for Pydeck
# -----------------------------
county_geojson = {
    "type": "FeatureCollection",
    "features": [{
        "type": "Feature",
        "geometry": mapping(county_geom_ll),
        "properties": {"name": county_label}
    }]
}

buffer_geojson = {
    "type": "FeatureCollection",
    "features": [{
        "type": "Feature",
        "geometry": mapping(buffer_poly_ll),
        "properties": {"radius_mi": radius_mi}
    }]
}

schools_points = schools_in_ll.copy()
# ensure lon/lat columns exist for pydeck
schools_points["lon"] = schools_points.geometry.x
schools_points["lat"] = schools_points.geometry.y

# map center = representative point (in WGS84)
rep_pt_ll = gpd.GeoSeries([rep_pt], crs=PROJECTED_CRS).to_crs(WGS84).iloc[0]
center_lat = rep_pt_ll.y
center_lon = rep_pt_ll.x

# -----------------------------
# Pydeck layers (background first, smaller school markers)
# -----------------------------
layer_us = pdk.Layer(
    "GeoJsonLayer",
    data=counties_ll.__geo_interface__,
    stroked=True,
    filled=True,
    getFillColor=[240, 240, 240, 60],
    getLineColor=[200, 200, 200, 140],
    lineWidthMinPixels=0.3,
)

layer_county = pdk.Layer(
    "GeoJsonLayer",
    data=county_geojson,
    stroked=True,
    filled=False,
    getLineColor=[0, 0, 0, 200],
    lineWidthMinPixels=2,
)

layer_buffer = pdk.Layer(
    "GeoJsonLayer",
    data=buffer_geojson,
    stroked=True,
    filled=True,
    getFillColor=[80, 160, 240, 40],
    getLineColor=[80, 160, 240, 200],
    lineWidthMinPixels=2,
)

layer_schools = pdk.Layer(
    "ScatterplotLayer",
    data=schools_points,
    get_position=["lon", "lat"],
    radiusUnits="pixels",   # keep markers small regardless of zoom
    get_radius=4,           # small dot size (adjust 2-8 as needed)
    getFillColor=[255, 140, 0, 200],
    pickable=True,
)

tooltip = {
    "html": "<b>{school_name}</b><br/>"
            "City: {city}<br/>"
            "State: {state}<br/>"
            "Admit rate: {admit_rate}",
    "style": {"backgroundColor": "white", "color": "black"}
}

view_state = pdk.ViewState(
    latitude=center_lat,
    longitude=center_lon,
    zoom=8,
    pitch=0
)

deck = pdk.Deck(
    layers=[layer_us, layer_county, layer_buffer, layer_schools],
    initial_view_state=view_state,
    tooltip=tooltip,
    map_style="mapbox://styles/mapbox/light-v11",
)

st.pydeck_chart(deck, use_container_width=True)

# -----------------------------
# Optional: table of schools in radius
# -----------------------------
with st.expander(f"Show schools within {radius_mi} miles (table)"):
    cols_show = ["school_name", "city", "state", "admit_rate", "pell_grant_rate", "median_earnings"]
    cols_show = [c for c in cols_show if c in schools_in_ll.columns]
    st.dataframe(
        schools_in_ll[cols_show].sort_values(by=["state", "city"], na_position="last"),
        use_container_width=True,
        hide_index=True
    )