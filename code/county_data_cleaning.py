import geopandas as gpd
import pandas as pd
import os
import altair as alt
from shapely.geometry import Point
import pyproj as pyproj   
import matplotlib.pyplot as plt
import numpy as np

#=========================
# school data cleaning
#=========================
in_path = "data/raw-data"
scorecard = os.path.join(in_path, "Most-Recent-Cohorts-Institution.csv")
scorecard = pd.read_csv(scorecard)

# Only keep the columns we need and rename them for clarity
needed_cols = ['UNITID', 'INSTNM', 'CITY', 'STABBR', 'ZIP', 'PREDDEG', 'LOCALE', 'LATITUDE', 'LONGITUDE', 'ADM_RATE', 'CONTROL',
               'UGDS_WHITE', 'UGDS_BLACK', 'UGDS_HISP', 'UGDS_ASIAN', 'UGDS_AIAN', 'UGDS_NHPI', 
               'PCTPELL', 
               'DEP_INC_PCT_LO', 'DEP_INC_PCT_M1', 'DEP_INC_PCT_M2', 'DEP_INC_PCT_H1', 'DEP_INC_PCT_H2',
               'MDEARN_ALL', 'C150_L4', 'C150_4', 'NPT4_PUB', 'NPT4_PRIV']
scorecard = scorecard[needed_cols]
scorecard.columns = ['id', 'school_name', 'city', 'state', 'zipcode', 'predom_degree_awarded', 'locale', 'latitude', 'longitude', 'admit_rate', 'control',
                     'prop_white', 'prop_black', 'prop_hispanic', 'prop_asian', 'prop_aian', 'prop_nhpi',
                     'pell_grant_rate',
                     'pct_lowinc', 'pct_lowmedinc', 'pct_medinc', 'pct_lowhighinc', 'pct_highinc',
                     'median_earnings', 'cc_completion_rate', '4yr_completion_rate', 'net_price_pub', 'net_price_priv']

# drop rows with no location data
scorecard = scorecard.dropna(subset=['latitude', 'longitude'])

# categorize each institution as either broad-access or not
scorecard['is_broad_access'] = (scorecard['admit_rate'] >= 0.75) | (scorecard['admit_rate'].isna())

# filter for community colleges and 4-year universities
scorecard = scorecard[(scorecard['predom_degree_awarded'] == 2) | (scorecard['predom_degree_awarded'] == 3)]

# filter for public and private non-profits
scorecard = scorecard[(scorecard['control'] == 1) | (scorecard['control'] == 2)]

# drop rows in the U.S. territories
scorecard = scorecard[~scorecard['state'].isin(['AS', 'GU', 'MP', 'PR', 'FM', 'PW', 'VI', 'MH'])]

scorecard

# 4. Define the output file path
derived_path = "data/derived-data"
out_file = os.path.join(derived_path, "scorecard.csv")
scorecard.to_csv(out_file, index=False)

# convert to a geodataframe
geometry = [Point(xy) for xy in zip(scorecard['longitude'], scorecard['latitude'])]
schools_gdf = gpd.GeoDataFrame(scorecard,
                geometry=geometry, 
                crs="EPSG:4326")

schools_gdf.to_csv(os.path.join(derived_path, "schools_gdf.csv"), index=False)
# save as geojson for spatial operations later
schools_gdf.to_file(os.path.join(derived_path, "schools.geojson"), driver='GeoJSON')

#=========================
# County data cleaning
#=========================
county_geo = os.path.join(in_path, 'cb_2024_us_county_500k', 'cb_2024_us_county_500k.shp')

counties = gpd.read_file(county_geo)


# 1. Only keep the four columns we need
counties = counties[['GEOID', 'NAMELSAD', 'STUSPS', 'STATE_NAME', 'geometry']]

# 2. Rename the STUSPS column to state, and also rename the other columns for clarity
counties = counties.rename(columns={'GEOID':'geoid','STUSPS': 'state','NAMELSAD':'county_name','STATE_NAME':'state_name'})
# 3. Check the first few rows of the cleaned data
print(counties.head())

# 4. Define the output file path
derived_path = "data/derived-data"
out_file = os.path.join(derived_path, "counties.geojson")

# 5. Save the cleaned GeoDataFrame to a new file
# driver='GeoJSON'
counties.to_file(out_file, driver='GeoJSON')

# 检查唯一性
dup = (
    counties.groupby(["county_name", "state_name"])
    .size().reset_index(name="n").query("n>1")
)
print("duplicated pairs (should be 0):", len(dup))

#================================
# popolation data cleaning(18-24)
#================================
data = os.path.join(in_path, "ACSST5Y2023.S0101_2026-03-01T093929","ACSST5Y2023.S0101-Data.csv")

populations = pd.read_csv(data, skiprows=[1]).copy()

# 1. Only keep the columns we need
populations = populations.iloc[1:]
populations = populations[['NAME', 'S0101_C01_018E', 'S0101_C01_019E', 'S0101_C01_020E', 'S0101_C01_021E', 'S0101_C01_022E', 'S0101_C01_023E', 'S0101_C01_024E']]

# 2. Split the NAME column into county_name and state
populations['NAME'] = populations['NAME'].astype(str)
populations[['county_name', 'state_name']] = (
    populations['NAME'].str.split(',', n=1, expand=True)
)

# Strip leading/trailing whitespace from county_name and state
populations['county_name'] = populations['county_name'].str.strip()
populations['state_name'] = populations['state_name'].str.strip()


# 3. Clean & create a new column for the total population of 18-24 year olds
# Convert the population columns to numeric, coercing errors to NaN and then converting to Int64
populations['S0101_C01_018E'] = pd.to_numeric(populations['S0101_C01_018E'], errors='coerce').astype('Int64')
populations['S0101_C01_019E'] = pd.to_numeric(populations['S0101_C01_019E'], errors='coerce').astype('Int64')
populations['S0101_C01_020E'] = pd.to_numeric(populations['S0101_C01_020E'], errors='coerce').astype('Int64')
populations['S0101_C01_021E'] = pd.to_numeric(populations['S0101_C01_021E'], errors='coerce').astype('Int64')
populations['S0101_C01_022E'] = pd.to_numeric(populations['S0101_C01_022E'], errors='coerce').astype('Int64')       
populations['S0101_C01_023E'] = pd.to_numeric(populations['S0101_C01_023E'], errors='coerce').astype('Int64')
populations['S0101_C01_024E'] = pd.to_numeric(populations['S0101_C01_024E'], errors='coerce').astype('Int64')   

#Create a new column for the total population of 18-24 year olds by summing the relevant columns
populations['population_18_24'] = populations['S0101_C01_018E'] + populations['S0101_C01_019E'] + populations['S0101_C01_020E'] + populations['S0101_C01_021E'] + populations['S0101_C01_022E'] + populations['S0101_C01_023E'] + populations['S0101_C01_024E']

populations = populations[['county_name', 'state_name', 'population_18_24']]

print(populations.columns)


# 5. Save the cleaned population data to a new CSV file
out_file = os.path.join(derived_path, "county_population_18_24_2023.csv")
populations.to_csv(out_file, index=False)


#================================
# median income data cleaning
#================================
# load the mobility data
data = os.path.join(in_path, "ACSDT5Y2023.B19013_2026-03-02T221821","ACSDT5Y2023.B19013-Data.csv")
median_income= pd.read_csv(data, skiprows=[1]).copy()

# 2. Split the NAME column into county_name and state

median_income = median_income[['NAME', 'B19013_001E']]

# 2. Split the NAME column into county_name and state
median_income['NAME'] = median_income['NAME'].astype(str)
median_income[['county_name', 'state_name']] = (
    median_income['NAME'].str.split(',', n=1, expand=True)
)

# Strip leading/trailing whitespace from county_name and state
median_income['county_name'] = median_income['county_name'].str.strip()
median_income['state_name'] = median_income['state_name'].str.strip()


# 3. Only keep the columns we need and rename the median income column for clarity
median_income = median_income[['county_name', 'state_name', 'B19013_001E']]
# Rename the median income column 
median_income = median_income.rename(columns={'B19013_001E': 'median_income'})


# 5. Save the cleaned median income data to a new CSV file
out_file = os.path.join(derived_path, "median_income.csv")
median_income.to_csv(out_file, index=False)

#================================
#  degree data cleaning
#================================
# load the mobility data
data = os.path.join(in_path, "ACSST5Y2023.S1501_2026-03-02T233050","ACSST5Y2023.S1501-Data.csv")
degree_data= pd.read_csv(data, skiprows=[1]).copy()

# 2. Split the NAME column into county_name and state

degree_data = degree_data[['NAME', 'S1501_C01_006E', 'S1501_C01_015E']]
# 2. Split the NAME column into county_name and state
degree_data['NAME'] = degree_data['NAME'].astype(str)
degree_data[['county_name', 'state_name']] = (
    degree_data['NAME'].str.split(',', n=1, expand=True)
)

# Strip leading/trailing whitespace from county_name and state
degree_data['county_name'] = degree_data['county_name'].str.strip()
degree_data['state_name'] = degree_data['state_name'].str.strip()

# 3. Only keep the columns we need and rename the median income column for clarity
degree_data = degree_data[['county_name', 'state_name', 'S1501_C01_006E', 'S1501_C01_015E']]
# Rename the degree data columns for clarity
degree_data = degree_data.rename(columns={'S1501_C01_006E': 'total_population', 'S1501_C01_015E': 'bachelor_degree_or_higher'})
# 4. Clean the degree data columns (remove non-numeric characters and convert to numeric)
# errors='coerce' 会把非数字字符变成 NaN
degree_data['bachelor_degree_or_higher'] = pd.to_numeric(degree_data['bachelor_degree_or_higher'], errors='coerce')
degree_data['total_population'] = pd.to_numeric(degree_data['total_population'], errors='coerce')

# 2. Handle missing values: if bachelor_degree_or_higher is NaN, we can assume it's 0 (no one has a bachelor's degree or higher); if total_population is NaN, we can keep it as NaN for now and handle it in the next step when we calculate the percentage
degree_data['bachelor_degree_or_higher'] = degree_data['bachelor_degree_or_higher'].fillna(0)
# if total_population is 0, we should set it to NaN to avoid division by zero when calculating the percentage later (since if total_population is 0, the percentage of people with a bachelor's degree or higher is undefined)
degree_data['total_population'] = degree_data['total_population'].replace(0, np.nan) 

# 3. Calculate the percentage of people with a bachelor's degree or higher
degree_data['percent_bachelor_degree_or_higher'] = (
    degree_data['bachelor_degree_or_higher'] / degree_data['total_population']
) * 100

# 5. Save the cleaned degree data to a new CSV file
out_file = os.path.join(derived_path, "degree_data.csv")
degree_data.to_csv(out_file, index=False)
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

#================================
# Calculating EAS
#================================

from shapely.geometry import Point
import pyproj
import matplotlib.pyplot as plt


MILES_TO_METERS = 1609.344
RADII_MILES = [25, 50, 75]
PROJECTED_CRS = "EPSG:5070"   # meters

# -------------------------
# 1) Read counties (polygons)
# -------------------------
derived_path = "data/derived-data"
counties = gpd.read_file(os.path.join(derived_path, "counties.geojson"))
# drop counties in U.S. territories
counties = counties[~counties['state'].isin(['AK', 'HI', 'AS', 'GU', 'MP', 'PR', 'VI'])]


# Ensure a known CRS (most GeoJSON are EPSG:4326)
if counties.crs is None:
    counties = counties.set_crs("EPSG:4326")

# -------------------------
# 2) Read schools (points)
# -------------------------
schools = gpd.read_file(os.path.join(derived_path, "schools.geojson"))  

# -------------------------
# 3) Project both to meters
# -------------------------
counties_p = counties.to_crs(PROJECTED_CRS)
schools_p = schools.to_crs(PROJECTED_CRS)

# -------------------------
# 4) County "centroid" points (use representative_point for safety)
# -------------------------
county_pts = counties_p.copy()
county_pts["geometry"] = counties_p.geometry.representative_point()
county_pts = gpd.GeoDataFrame(county_pts, geometry="geometry", crs=PROJECTED_CRS)

# -------------------------
# 5) Buffer rings and count schools within each radius
# -------------------------
out = counties_p.copy()

for r in RADII_MILES:
    buf = county_pts.copy()
    buf["geometry"] = buf.geometry.buffer(r * MILES_TO_METERS)
    buf = gpd.GeoDataFrame(buf, geometry="geometry", crs=PROJECTED_CRS)

    # spatial join: each school matched to the county buffer it falls within
    joined = gpd.sjoin(
        schools_p[["geometry"]],
        buf[["county_name", "state_name","state","geometry"]],
        how="inner",
        predicate="within"
    )

    counts = joined.groupby(["county_name", "state_name", "state"]).size().rename(f"schools_within_{r}mi")
    out = out.merge(counts.reset_index(), on=["county_name", "state_name", "state"], how="left")

# fill missing with 0
for r in RADII_MILES:
    col = f"schools_within_{r}mi"
    out[col] = out[col].fillna(0).astype(int)


# -------------------------
# 6) Save derived data outputs
#   (1) human-readable CSV for EAS calc (NO geometry)
#   (2) mapping-ready spatial file (WITH geometry)
# -------------------------

# (1) CSV: drop geometry to avoid "乱码"/Excel错列
out_csv = out.drop(columns="geometry").copy()
out_csv.to_csv("data/derived-data/county_school_counts_by_radius.csv", index=False)

# (2) Spatial output for mapping later
out.to_file(
    "data/derived-data/county_school_counts_by_radius.gpkg",
    layer="county_school_counts",
    driver="GPKG"
)

# also save as geojson for easy use in web mapping
out.to_file("data/derived-data/county_school_counts_by_radius.geojson", driver="GeoJSON")

print("Saved:")
print("- data/derived-data/county_school_counts_by_radius.csv (no geometry)")
print("- data/derived-data/county_school_counts_by_radius.gpkg (with geometry)")
print("- data/derived-data/county_school_counts_by_radius.geojson (with geometry)")

import numpy as np

# -------------------------
# 7) Compute EAS (per 10k people age 18-24)
#     merge keys:
#       counts: county_name + state_name + state
#       population: county_name + state_name
# -------------------------

counts = pd.read_csv("data/derived-data/county_school_counts_by_radius.csv")

pop = pd.read_csv("data/derived-data/county_population_18_24_2023.csv")



# merge on county_name and state_name (and also state for safety, but it should be unique by then)
df_eas = counts.merge(
    pop,
    on=["county_name", "state_name"],
    how="left",
    validate="m:1"
)

for r in [25, 50, 75]:
    df_eas[f"eas_{r}mi_per10k"] = (df_eas[f"schools_within_{r}mi"] / df_eas["population_18_24"]) * 10000

# drop counties in U.S. territories
df_eas = df_eas[df_eas['state'].isin(['AK', 'HI', 'AS', 'GU', 'MP', 'PR', 'VI']) == False]

df_eas.to_csv("data/derived-data/eas_by_radius.csv", index=False)

print("Saved: data/derived-data/eas_by_radius.csv")
print(df_eas[["county_name","state_name","state","eas_25mi_per10k","eas_50mi_per10k","eas_75mi_per10k"]].head())

# ===============================================
# Static Plot 1: Choropleth map of EAS (50 miles)
# ===============================================
import matplotlib.pyplot as plt
import numpy as np
import geopandas as gpd
import pandas as pd

EXCLUDE_STATES = ['AK', 'HI', 'AS', 'GU', 'MP', 'PR', 'VI']  # U.S. territories + non-continental states to exclude from the map

counties_map = gpd.read_file("data/derived-data/counties.geojson")
eas = pd.read_csv("data/derived-data/eas_by_radius.csv")

# drop counties in U.S. territories
counties_map = counties_map[~counties_map["state"].isin(EXCLUDE_STATES)].copy()

# merge
gdf_map = counties_map.merge(
    eas[["county_name", "state_name", "eas_50mi_per10k"]],
    on=["county_name", "state_name"],
    how="left",
    validate="1:1"
)

# log scale for better visualization
gdf_map["eas50_plot"] = np.log1p(gdf_map["eas_50mi_per10k"])

# is this in lat/lon? If so, convert to projected CRS for accurate buffering and distance-based visualization
if gdf_map.crs is None:
    gdf_map = gdf_map.set_crs("EPSG:4326")

# if it's in lat/lon, convert to projected CRS for accurate buffering and distance-based visualization
gdf_ll = gdf_map.to_crs("EPSG:4326")

# sometimes geometries can be invalid after operations, so we can fix them with buffer(0)
gdf_ll["geometry"] = gdf_ll.geometry.buffer(0)

# clip to the continental US bounding box to avoid weird outliers in AK/HI and make the map more focused
gdf_ll = gdf_ll.cx[slice(-125, -66.5), slice(24, 49.5)]

fig, ax = plt.subplots(1, 1, figsize=(16, 10))

gdf_ll.plot(
    column="eas50_plot",
    ax=ax,
    legend=True,
    linewidth=0.15,
    edgecolor="white",
    missing_kwds={"color": "lightgrey", "label": "Missing"},
    legend_kwds={
        "label": "log(1 + EAS per 10k), 50-mile radius",
        "shrink": 0.6,   # colorbar
        "pad": 0.02
    },
)

ax.set_title("Education Access Score (EAS), 50-mile radius", fontsize=16, pad=12)
ax.set_axis_off()

plt.tight_layout()
plt.savefig("data/derived-data/static_map_eas_50mi.png", dpi=350, bbox_inches="tight")
plt.close()

print("Saved: data/derived-data/static_map_eas_50mi.png")

# ===============================================
# Static Plot 1c: Education Deserts (Bottom 20%) + Schools (50 miles)
# ===============================================
import geopandas as gpd
import pandas as pd
import matplotlib.pyplot as plt

COUNTIES_PATH = "data/derived-data/counties.geojson"
EAS_PATH = "data/derived-data/eas_by_radius.csv"
SCHOOLS_PATH = "data/derived-data/schools.geojson"   
OUT_PATH = "data/derived-data/static_map_deserts_50mi_with_schools.png"

# 1) Load
counties_map = gpd.read_file(COUNTIES_PATH)
eas = pd.read_csv(EAS_PATH)
schools = gpd.read_file(SCHOOLS_PATH)
counts = pd.read_csv("data/derived-data/county_school_counts_by_radius.csv")

# 2) Keep CONUS only
counties_map = counties_map[~counties_map["state"].isin(EXCLUDE_STATES)].copy()
schools = schools[~schools["state"].isin(EXCLUDE_STATES)].copy()

# 3) Merge EAS onto counties
gdf = counties_map.merge(
    eas[["county_name", "state_name", "eas_50mi_per10k"]],
    on=["county_name", "state_name"],
    how="left",
    validate="1:1"
)

# merge school counts（bring schools_wthin_50mi）
gdf = gdf.merge(
    counts[["county_name", "state_name", "schools_within_50mi"]],
    on=["county_name", "state_name"],
    how="left",
    validate="1:1"
)

# 4) Ensure CRS, crop to CONUS bbox for better visualization, and fix any invalid geometries
if gdf.crs is None:
    gdf = gdf.set_crs("EPSG:4326")
if schools.crs is None:
    schools = schools.set_crs("EPSG:4326")

gdf_ll = gdf.to_crs("EPSG:4326")
schools_ll = schools.to_crs("EPSG:4326")

# 
gdf_ll["geometry"] = gdf_ll.geometry.buffer(0)

# clip to the continental US bounding box to avoid weird outliers in AK/HI and make the map more focused
gdf_ll = gdf_ll.cx[slice(-125, -66.5), slice(24, 49.5)]
schools_ll = schools_ll.cx[slice(-125, -66.5), slice(24, 49.5)]

# 5) Identify deserts = bottom 20% of EAS (50mi)
#   rank(pct=True) 
gdf_ll["eas_rank_pct"] = gdf_ll["eas_50mi_per10k"].rank(pct=True, method="average")
gdf_ll["is_desert"] = (gdf_ll["eas_rank_pct"] <= 0.20) & (gdf_ll["schools_within_50mi"] <= 2)

deserts = gdf_ll[gdf_ll["is_desert"]].copy()
flag = gdf_ll[["county_name", "state_name", "state", "is_desert"]].copy()
flag.to_csv("data/derived-data/county_desert_flag.csv", index=False)
print("Saved: data/derived-data/county_desert_flag.csv")

# 6) Select schools to plot
#    only plot schools that fall within desert counties or within 50 miles of them (for better visibility)
schools_plot = schools_ll.copy()


# 7) Identify schools that fall within desert counties 
schools_in_deserts = gpd.sjoin(
    schools_plot,
    deserts[["county_name", "state_name", "geometry"]],
    how="inner",
    predicate="within"
)

# 8) Plot (report-style)
fig, ax = plt.subplots(1, 1, figsize=(16, 10))

# base layer
gdf_ll.plot(ax=ax, color="#efefef", linewidth=0.05, edgecolor="white")

# deserts highlight
deserts.plot(ax=ax, color="#4a1486", linewidth=0.08, edgecolor="white", alpha=0.95)

# schools points (small + semi-transparent)
schools_in_deserts.plot(
    ax=ax,
    markersize=7,
    color="#FFD700",        # golden color for better visibility
    linewidth=0.3,
    alpha=0.9
)

ax.set_title("Education Deserts (Bottom 20% EAS) and Nearby Institutions, 50-mile definition", fontsize=16, pad=12)
ax.set_axis_off()

plt.tight_layout()
plt.savefig(OUT_PATH, dpi=350, bbox_inches="tight")
plt.close()

print(f"Saved: {OUT_PATH}")
print("Desert counties:", len(deserts))
print("Schools shown:", len(schools_in_deserts))    



# ===============================================
# Static Plot 2: Scatter (EAS vs Degree)
# ===============================================
import pandas as pd
import altair as alt

# Paths
EAS_PATH = "data/derived-data/eas_by_radius.csv"
DEGREE_DATA_PATH = "data/derived-data/degree_data.csv"
OUT_PATH = "data/derived-data/static_scatter_eas_vs_degree_50mi.png"

# 1) Load
eas = pd.read_csv(EAS_PATH)
degree_data = pd.read_csv(DEGREE_DATA_PATH)

# find out the duplicated rows are NA
degree_data = degree_data.dropna(subset=["county_name", "state_name"])

# 2) Merge EAS and degree_data data on county_name and state
df = eas.merge(
    degree_data,
    on=["county_name", "state_name"],
    how="left",
    validate="1:1"
)


#  is_desert flag
deserts_flag = pd.read_csv("data/derived-data/county_desert_flag.csv")

# merge the desert flag onto df
df = df.merge(
    deserts_flag[["county_name", "state_name", "is_desert"]],
    on=["county_name", "state_name"],
    how="left"
)

# fill missing desert flag with False (assume missing means not a desert, since we only flagged the bottom 20%)
df["is_desert"] = df["is_desert"].fillna(False)

# 3) Drop missing
df = df.dropna(subset=["eas_50mi_per10k", "percent_bachelor_degree_or_higher"])

# 4) log transform EAS if very skewed
df["eas_50mi_per10k"] = pd.to_numeric(df["eas_50mi_per10k"], errors="coerce")
df["log_eas_50mi"] = np.log1p(df["eas_50mi_per10k"].clip(lower=0))

# 5) Build Altair chart
base = alt.Chart(df).encode(
    x=alt.X("log_eas_50mi:Q", title="EAS , 50-mile"),
    y=alt.Y(
        "percent_bachelor_degree_or_higher:Q",
        title="Percent Bachelor's Degree or Higher",),
    color=alt.Color(
    "is_desert:N",
    title="Education desert?",
    scale=alt.Scale(
        domain=[False, True],
        range=["#c7c7c7", "#311B92"]
    )
)
)
    


points = base.mark_circle(
    size=40,
    opacity=0.4
)

trend = base.transform_regression(
    "log_eas_50mi",
    "percent_bachelor_degree_or_higher",
).mark_line(
    color="red",
    size=2
)

chart = (points + trend).properties(
    width=700,
    height=500,
    title="Education Access vs Educational Attainment (Bachelor's or Higher)"
)

# 6) Save
chart.save(OUT_PATH)

print(f"Saved: {OUT_PATH}")


import numpy as np
import altair as alt
import pandas as pd

chart = alt.Chart(df).mark_boxplot().encode(
    x=alt.X("is_desert:N", title="Education desert?"),
    y=alt.Y("percent_bachelor_degree_or_higher:Q", title="Percent Bachelor's Degree or Higher")
).properties(width=450, height=400, title="Percent Bachelor's Degree or Higher: Deserts vs Non-deserts")

chart.save("data/derived-data/static_box_degree_desert.png")


#================================
# Streamlit
#================================
import streamlit as st
import pandas as pd
import geopandas as gpd
import numpy as np
import pydeck as pdk
from shapely.geometry import mapping

# -----------------------------
# Config
# -----------------------------
st.set_page_config(page_title="Education Access Map", layout="wide")

COUNTIES_PATH = "data/derived-data/counties.geojson"
SCHOOLS_PATH = "data/derived-data/schools.geojson"
COUNTS_PATH = "data/derived-data/county_school_counts_by_radius.csv"

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

# -----------------------------
# Header metrics
# -----------------------------
st.title("Education Access Explorer")

c1, c2, c3 = st.columns(3)
c1.metric("Selected county", county_label)
c2.metric(f"Schools within {radius_mi} miles (live spatial)", f"{count_live}")
if count_pre is not None:
    c3.metric(f"Schools within {radius_mi} miles (precomputed)", f"{count_pre}")
else:
    c3.metric("Schools within radius (precomputed)", "N/A")

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
# Pydeck layers
# -----------------------------
layer_county = pdk.Layer(
    "GeoJsonLayer",
    data=county_geojson,
    stroked=True,
    filled=False,
    lineWidthMinPixels=2,
)

layer_buffer = pdk.Layer(
    "GeoJsonLayer",
    data=buffer_geojson,
    stroked=True,
    filled=True,
    getFillColor=[80, 160, 240, 40],   # light transparent
    getLineColor=[80, 160, 240, 200],
    lineWidthMinPixels=2,
)

layer_schools = pdk.Layer(
    "ScatterplotLayer",
    data=schools_points,
    get_position=["lon", "lat"],
    get_radius=250,     # meters-ish visual size, not exact; adjust if you want
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
    zoom=7,   # default zoom; user can zoom in/out
    pitch=0
)

deck = pdk.Deck(
    layers=[layer_county, layer_buffer, layer_schools],
    initial_view_state=view_state,
    tooltip=tooltip,
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