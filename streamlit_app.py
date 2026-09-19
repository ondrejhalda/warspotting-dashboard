import json
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components


# --------------------------------------------------
# FILES
# --------------------------------------------------

WEEKLY_FILE = Path("weekly_equipment_losses.csv")
QUALITY_FILE = Path("data_quality.json")
HTML_FILE = Path("equipment_weekly.html")


# --------------------------------------------------
# PAGE CONFIG
# --------------------------------------------------

st.set_page_config(
    page_title="WarSpotting Dashboard",
    page_icon="📊",
    layout="wide",
)


# --------------------------------------------------
# LOAD DATA
# --------------------------------------------------

def load_weekly_data():
    return pd.read_csv(WEEKLY_FILE)


def load_quality_data():
    with open(QUALITY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def load_plot_html():
    return HTML_FILE.read_text(encoding="utf-8")


weekly = load_weekly_data()
quality = load_quality_data()
plot_html = load_plot_html()


# --------------------------------------------------
# PREPARE METRICS
# --------------------------------------------------

raw_records = quality.get("raw_records", 0)

analytical_records = len(weekly)

documented_losses = int(weekly["losses"].sum())

unique_weeks = weekly["week"].nunique()

unique_categories = weekly["type"].nunique()


# --------------------------------------------------
# TITLE
# --------------------------------------------------

st.title("WarSpotting — Russian Equipment Losses")

st.caption(
    "Weekly documented equipment losses based on WarSpotting data."
)


# --------------------------------------------------
# KPI ROW
# --------------------------------------------------

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        "Raw records",
        f"{raw_records:,}",
    )

with col2:
    st.metric(
        "Analytical records",
        f"{analytical_records:,}",
    )

with col3:
    st.metric(
        "Documented losses",
        f"{documented_losses:,}",
    )

with col4:
    st.metric(
        "Equipment categories",
        unique_categories,
    )


# --------------------------------------------------
# DATA QUALITY
# --------------------------------------------------

status = quality.get("validation_status", "UNKNOWN")
last_update = quality.get("last_update", "Unknown")

if status == "OK":
    status_text = "● OK"
elif status == "WARNING":
    status_text = "● WARNING"
else:
    status_text = "● ERROR"

st.markdown("### Data Quality")

dq_col1, dq_col2 = st.columns(2)

with dq_col1:
    st.write(f"**Status:** {status_text}")

with dq_col2:
    st.write(f"**Last update:** {last_update}")


# --------------------------------------------------
# MAIN PLOT
# --------------------------------------------------

st.markdown("### Weekly Equipment Losses")

components.html(
    plot_html,
    height=820,
    scrolling=False,
)


# --------------------------------------------------
# TECHNICAL DATA
# --------------------------------------------------

with st.expander("Technical data"):

    col1, col2, col3 = st.columns(3)

    with col1:
        st.write("**Source**")
        st.write("WarSpotting API")

    with col2:
        st.write("**Weekly records**")
        st.write(f"{len(weekly):,}")

    with col3:
        st.write("**Unique weeks**")
        st.write(f"{unique_weeks:,}")

    st.write(
        f"**Equipment categories:** {unique_categories}"
    )

    st.write(
        f"**Documented losses:** {documented_losses:,}"
    )


# --------------------------------------------------
# METHODOLOGY
# --------------------------------------------------

with st.expander("Methodology"):

    st.write(
        """
        The dashboard uses documented equipment-loss records
        from WarSpotting.

        Raw records are collected through the API and stored
        in the project's raw dataset.

        The data is validated, transformed and aggregated
        into weekly equipment-loss statistics.

        The resulting dataset is visualized as an interactive
        Plotly chart.
        """
    )
