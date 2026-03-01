import geopandas as gpd
import pandas as pd
import os
import altair as alt
from shapely.geometry import Point
import pyproj
import matplotlib.pyplot as plt
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
data = os.path.join(in_path, "ACSST5Y2023.S0101_2026-02-27T181826","ACSST1Y2023.S0101-Data.csv")

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


populations['county_name'] = (
    populations['county_name']
    .str.strip()
)

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

# 4. Merge the population data with the county geodataframe to get the geoid for each county
populations = populations.merge(
    counties_keys[["geoid", "match_name", "state_name"]],
    left_on=["county_name", "state_name"],
    right_on=["match_name", "state_name"],
    how="left",
    validate="m:1"
)

# 5. Save the cleaned population data to a new CSV file
out_file = os.path.join(derived_path, "county_population_18_24_2023.csv")
populations.to_csv(out_file, index=False)


#================================
# mobility rate data cleaning
#================================
# load the mobility data
data = os.path.join(in_path, "cty_kfr_top20_rP_gP_pall.csv")
mobility = gpd.read_file(data)

# 2. Split the NAME column into county_name and state
mobility['Name'] = mobility['Name'].astype(str)
mobility[['county_name', 'state']] = (
    mobility['Name'].str.split(',', n=1, expand=True)
)
mobility["state"] = mobility["state"].str.strip()


mobility['county_name'] = (
    mobility['county_name']
    .str.strip()
)

# 3. Only keep the columns we need and rename the mobility rate column for clarity
mobility = mobility[['county_name', 'state', 'Frac._in_Top_20%_Based_on_Household_Income_rP_gP_pall']]
# Rename the mobility rate column 
mobility = mobility.rename(columns={'Frac._in_Top_20%_Based_on_Household_Income_rP_gP_pall': 'mobility_rate'})

# 4. Merge the mobility data with the county geodataframe to get the geoid for each county
mobility = mobility.merge(
    counties_keys[["geoid", "match_name", "state"]],
    left_on=["county_name", "state"],
    right_on=["match_name", "state"],
    how="left",
    validate="m:1"
)

# 5. Save the cleaned mobility data to a new CSV file
out_file = os.path.join(derived_path, "mobility_rate.csv")
mobility.to_csv(out_file, index=False)

#=============================================================================
