import streamlit as st
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import requests

#----- set up the app -----#
st.set_page_config(layout="wide")
st.title("U.S. Education Desert Diagnostic Tool")
st.sidebar.header("Policy Weights")
st.sidebar.markdown("Adjust the importance of each metric to recalculate the Opportunity Score.")

# interactive weights
access_weight = st.sidebar.slider("Physical Access (School Count in County)", 0.0, 1.0, 0.4)
mobility_weight = st.sidebar.slider("Economic Mobility (Post-Graduation Earnings)", 0.0, 1.0, 0.3)
equity_weight = st.sidebar.slider("Equity (Pell Grant Rate)", 0.0, 1.0, 0.3)

# normalize weights
total_weight = access_weight + mobility_weight + equity_weight

#----- process the data -----#
county_and_opscore_gdf = pd.read_csv("../data/derived-data/county_and_opscore_gdf.csv")

@st.cache_data
def calculate_opscore(access_weight, mobility_weight, equity_weight):
    """
    Calculates an Opportunity Score based on the user's inputs.
    """
    df = county_and_opscore_gdf.copy()
    df['dynamic_opscore'] = (
        (df['access_score'] * access_weight) +
        (df['earnings_score'] * mobility_weight) +
        (df['pell_score'] * equity_weight)
    ) * 100 / (access_weight + mobility_weight + equity_weight)

    return df

data = calculate_opscore(access_weight, mobility_weight, equity_weight)

@st.cache_data
def get_acs_data():
    """
    Collects income and racial demographics from ACS.
    """
    url = "https://api.census.gov/data/2022/acs/acs5?get=NAME,S1701_C03_001E,B01001_001E,B02001_002E&for=county:*"
    response = requests.get(url)
    response.encoding = 'latin-1' 
    data = response.json()

    df = pd.DataFrame(data[1:], columns=data[0])
    df['fips'] = df['state'] + df['county']

    df['poverty_rate'] = pd.to_numeric(df['S1701_C03_001E'], errors='coerce')
    total_pop = pd.to_numeric(df['B01001_001E'], errors='coerce')
    white_alone = pd.to_numeric(df['B02001_002E'], errors='coerce')

    df['minority_pct'] = ((total_pop - white_alone) / total_pop) * 100

    return df[['fips', 'poverty_rate', 'minority_pct']]

# demographic filters
st.sidebar.header("Vulnerability Filters")
poverty_threshold = st.sidebar.slider("Minimum County Poverty Rate (%)", 0, 50, 0)
racial_minority_threshold = st.sidebar.slider("Minimum Racial Minority Population (%)", 0, 100, 0)

# merge and filter
acs_df = get_acs_data()
merged_data = county_and_opscore_gdf.merge(acs_df, on='fips', how='left')

# show counties that meet the criteria
filtered_data = merged_data[
    (merged_data['poverty_rate'] >= poverty_threshold) & 
    (merged_data['minority_pct'] >= racial_minority_threshold)
]

#----- visuals -----#
county_gdf = pd.read_csv("../data/derived-data/county_gdf.csv")

m1, m2, m3 = st.columns(3)

# summary metrics
m1.metric("Counties Identified", len(filtered_data))
m2.metric("Avgerage Opportunity Score", f"{filtered_data['dynamic_opscore'].mean():.1f}")
m3.metric("Avgerage Minority %", f"{filtered_data['minority_pct'].mean():.1f}%")

# map and table data
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("Geographic Distribution of Priority Deserts")
    fig, ax = plt.subplots(figsize=(10, 6))

    # create a base map
    county_gdf.to_crs("EPSG:5070").plot(ax=ax, color='#f5f5f5', edgecolor='none')

    # filtered layer
    if not filtered_data.empty:
        filtered_data.to_crs("EPSG:5070").plot(
            column='dynamic_opscore', 
            cmap='RdYlBu', 
            ax=ax, 
            legend=True,
            legend_kwds={'shrink': 0.5}
        )
    ax.set_axis_off()
    st.pyplot(fig)

with col2:
    st.subheader("High-Priority Action List")
    st.markdown("Counties matching your equity criteria, sorted by lowest opportunity.")

    display_df = filtered_data.sort_values('dynamic_opscore').head(15)
    st.dataframe(
        display_df[['County_Name', 'State_Abbr', 'poverty_rate', 'minority_pct', 'dynamic_opscore']],
        hide_index=True,
        column_config={
            "poverty_rate": st.column_config.NumberColumn("Poverty %", format="%.1f"),
            "minority_pct": st.column_config.NumberColumn("Minority %", format="%.1f"),
            "dynamic_opscore": st.column_config.ProgressColumn("Opportunity Score", min_value=0, max_value=100)
        }
    )