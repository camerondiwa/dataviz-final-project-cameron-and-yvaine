import streamlit as st
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import requests
import os

#----- set up the app -----#
st.set_page_config(layout="wide", page_title="U.S. Education Desert Diagnostic Tool")
st.sidebar.header("Policy Weights")
st.sidebar.markdown("Adjust the importance of each metric to recalculate the Opportunity Score.")

# interactive weights
access_weight = st.sidebar.slider("Physical Access (School Count in County)", 0.0, 1.0, 0.4)
mobility_weight = st.sidebar.slider("Economic Mobility (Post-Graduation Earnings)", 0.0, 1.0, 0.3)
equity_weight = st.sidebar.slider("Equity (Pell Grant Rate)", 0.0, 1.0, 0.3)

# normalize weights
total_weight = access_weight + mobility_weight + equity_weight

# demographic filters
st.sidebar.header("Vulnerability Filters")
poverty_threshold = st.sidebar.slider("Minimum County Poverty Rate (%)", 0, 50, 15)
racial_minority_threshold = st.sidebar.slider("Minimum Racial Minority Population (%)", 0, 100, 20)

#----- process the data -----#
@st.cache_data
def load_data():
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    data_path = os.path.join(BASE_DIR, "..", "data", "derived-data", "county_and_opscore_gdf.parquet")
    county_and_opscore_gdf = gpd.read_parquet(data_path)
    county_and_opscore_gdf = county_and_opscore_gdf.to_crs("EPSG:5070")

    pov_opscore_rm_df = os.path.join(BASE_DIR, "..", "data", "derived-data", "pov_opscore_rm_df.csv")

    # merge into one geodataframe
    master = county_and_opscore_gdf.merge(pov_opscore_rm_df[['fips', 'poverty_rate', 'prop_racial_min']], on='fips', how='left')

    return master

# initialize the data
with st.spinner("Loading Data..."):
    master_gdf = load_data()

@st.cache_data
def calculate_opscore(access_weight, mobility_weight, equity_weight):
    """
    Calculates an Opportunity Score based on the user's inputs.
    """
    df = master_gdf.copy()
    total_weight = access_weight + mobility_weight + equity_weight

    # prevent division by 0
    if total_weight == 0: 
        total_weight = 1

    df['dynamic_opscore'] = (
        (df['access_score'] * access_weight) +
        (df['earnings_score'] * mobility_weight) +
        (df['pell_score'] * equity_weight)
    ) * 100 / total_weight

    return df
    
data = calculate_opscore(access_weight, mobility_weight, equity_weight)

# apply the filters
filtered_data = data[(data['poverty_rate'] >= poverty_threshold) & (data['prop_racial_min'] >= racial_minority_threshold)]


#----- visuals -----#
m1, m2, m3 = st.columns(3)

# summary metrics
count = len(filtered_data)
avg_score = filtered_data['dynamic_opscore'].mean() if count > 0 else 0
avg_minority = filtered_data['minority_pct'].mean() if count > 0 else 0

m1.metric("Counties Identified", count)
m2.metric("Average Opportunity Score", f"{avg_score:.1f}")
m3.metric("Average Minority %", f"{avg_minority:.1f}%")

# map and table data
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("Geographic Distribution of Priority Education Deserts")
    fig, ax = plt.subplots(figsize=(10, 6))

    # create a base map
    master_gdf.plot(ax=ax, color='#f5f5f5', edgecolor='none', linewidth=0.1)

    # filtered layer
    if not filtered_data.empty:
        filtered_data.plot(
            column='dynamic_opscore', 
            cmap='RdYlBu', 
            ax=ax, 
            legend=True,
            legend_kwds={'shrink': 0.5}
        )
    ax.set_axis_off()
    st.pyplot(fig)
    plt.close(fig)

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