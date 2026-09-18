from pathlib import Path
import json

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


# ---------------------------------------------------------
# Page configuration
# ---------------------------------------------------------
st.set_page_config(
    page_title="WarSpotting Dashboard",
    page_icon="📊",
    layout="wide",
)


# ---------------------------------------------------------
# File paths
# ---------------------------------------------------------
WEEKLY_FILE = Path("weekly_equipment_losses.csv")
QUALITY_FILE = Path("data_quality.json")


# ---------------------------------------------------------
# Equipment colors
#
# These colors are copied from the original
# equipment_weekly.html / equipment_plot.py.
# ---------------------------------------------------------
CATEGORY_COLORS = {
    "Tanks": "#54A24B",
    "Infantry fighting vehicles": "#4C78A8",
    "Infantry mobility vehicles": "#9D755D",
    "Command posts, communication": "#EDC949",
    "Anti-tank systems": "#8CD17D",
    "Anti-aircraft systems": "#BAB0AC",
    "Towed artillery": "#59A14F",
    "Self-propelled artillery": "#E45756",
    "Rocket and missile artillery": "#FF9DA6",
    "Radars, jammers": "#AF7AA1",
    "Engineering": "#B279A2",
    "Ambulances, medical vehicles": "#5DA5DA",
    "Transport": "#F58518",
    "Airplanes": "#E15759",
    "Helicopters": "#F28E2B",
    "Drones": "#72B7B2",
    "Vessels": "#B6992D",
    "Other": "#76B7B2",
}

BASE_OPACITY = 0.42


# ---------------------------------------------------------
# Load weekly analytical data
# ---------------------------------------------------------
def load_weekly_data():
    if not WEEKLY_FILE.exists():
        raise FileNotFoundError(
            f"Required file not found: {WEEKLY_FILE}"
        )

    df = pd.read_csv(WEEKLY_FILE)

    required_columns = {"week", "type", "losses"}
    missing_columns = required_columns - set(df.columns)

    if missing_columns:
        raise ValueError(
            "weekly_equipment_losses.csv is missing required "
            f"columns: {', '.join(sorted(missing_columns))}"
        )

    df["week"] = pd.to_datetime(df["week"], errors="coerce")
    df["losses"] = pd.to_numeric(df["losses"], errors="coerce")

    if df["week"].isna().any():
        raise ValueError("Invalid week values found.")

    if df["losses"].isna().any():
        raise ValueError("Invalid losses values found.")

    return df


# ---------------------------------------------------------
# Load data quality information
# ---------------------------------------------------------
def load_quality_data():
    if not QUALITY_FILE.exists():
        raise FileNotFoundError(
            f"Required file not found: {QUALITY_FILE}"
        )

    with QUALITY_FILE.open("r", encoding="utf-8") as file:
        return json.load(file)


# ---------------------------------------------------------
# Load data
# ---------------------------------------------------------
try:
    weekly = load_weekly_data()
    quality = load_quality_data()

except Exception as exc:
    st.error("The dashboard could not load its data.")
    st.code(str(exc))
    st.stop()


# ---------------------------------------------------------
# Basic quality values
# ---------------------------------------------------------
validation_status = str(
    quality.get("validation_status", "UNKNOWN")
).upper()

raw_records = quality.get("raw_records", "—")
analytical_records = quality.get("analytical_records", "—")
excluded_records = quality.get("excluded_lost_by", "—")
weekly_rows = quality.get("weekly_rows", len(weekly))

category_totals = (
    weekly.groupby("type")["losses"]
    .sum()
    .sort_values(ascending=False)
)

categories = category_totals.index.tolist()

unique_weeks = weekly["week"].nunique()
total_losses = int(weekly["losses"].sum())
average_weekly_losses = (
    total_losses / unique_weeks if unique_weeks else 0
)


# ---------------------------------------------------------
# Header
# ---------------------------------------------------------
st.title("Russian Equipment Losses — Weekly")
st.caption(
    "Documented Russian equipment losses based on WarSpotting data."
)


# ---------------------------------------------------------
# KPI row
# ---------------------------------------------------------
kpi1, kpi2, kpi3, kpi4 = st.columns(4)

with kpi1:
    st.metric(
        "Documented losses",
        f"{total_losses:,}",
    )

with kpi2:
    st.metric(
        "Average per week",
        f"{average_weekly_losses:,.1f}",
    )

with kpi3:
    st.metric(
        "Equipment categories",
        f"{len(categories):,}",
    )

with kpi4:
    st.metric(
        "Data quality",
        validation_status,
    )


# ---------------------------------------------------------
# Main content: chart + information panels
# ---------------------------------------------------------
chart_col, side_col = st.columns([5.4, 1.5], gap="medium")


# ---------------------------------------------------------
# Main Plotly chart
# ---------------------------------------------------------
with chart_col:
    st.subheader("Equipment losses by week")

    fig = go.Figure()

    for category in categories:
        category_data = (
            weekly[weekly["type"] == category]
            .sort_values("week")
        )

        color = CATEGORY_COLORS.get(category)

        # Keep the dashboard robust if a new category appears.
        if color is None:
            color = "#999999"

        fig.add_trace(
            go.Bar(
                x=category_data["week"],
                y=category_data["losses"],
                name=category,
                marker={
                    "color": color,
                    "opacity": BASE_OPACITY,
                    "line": {
                        "color": "rgba(255,255,255,0.55)",
                        "width": 0.5,
                    },
                },
                hovertemplate=(
                    "<b>%{x|%d/%m/%y}</b><br>"
                    f"{category}: "
                    "%{y:,}"
                    "<extra></extra>"
                ),
            )
        )

    fig.update_layout(
        barmode="stack",
        hovermode="closest",
        showlegend=False,
        height=750,
        margin={
            "l": 70,
            "r": 20,
            "t": 20,
            "b": 70,
        },
        xaxis={
            "title": "Date",
            "tickformat": "%m/%d/%y",
            "dtick": "M2",
            "type": "date",
            "showspikes": True,
            "spikemode": "across",
            "spikesnap": "cursor",
            "spikethickness": 1,
            "spikedash": "dot",
            "spikecolor": "rgba(80,80,80,0.65)",
        },
        yaxis={
            "title": "Documented losses",
            "rangemode": "tozero",
        },
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
    )


# ---------------------------------------------------------
# Data quality panel
# ---------------------------------------------------------
with side_col:
    quality_color = "#2E7D32"

    if validation_status == "WARNING":
        quality_color = "#C77700"
    elif validation_status not in {"OK", "WARNING"}:
        quality_color = "#B3261E"

    st.markdown(
        f"""
        <div style="
            border: 1px solid #c7cdd4;
            box-shadow: 0 1px 4px rgba(0,0,0,0.12);
            background: #ffffff;
            margin-bottom: 16px;
        ">
            <div style="
                background: #2f5d84;
                color: #ffffff;
                padding: 8px 10px;
                font-weight: 700;
            ">
                Data quality
            </div>

            <div style="
                padding: 10px;
                font-size: 13px;
                line-height: 1.55;
                color: #222222;
            ">
                <div style="font-size: 14px; font-weight: 700;">
                    <span style="
                        display:inline-block;
                        width:10px;
                        height:10px;
                        border-radius:50%;
                        background:{quality_color};
                        margin-right:6px;
                    "></span>
                    {validation_status}
                </div>
                <div>Last update (UTC): <b>{quality.get("last_update", "—")}</b></div>
                <div>Raw records: <b>{raw_records:,}</b></div>
                <div>Analytical records: <b>{analytical_records:,}</b></div>
                <div>Excluded records: <b>{excluded_records:,}</b></div>
                <div>Equipment categories: <b>{len(categories):,}</b></div>
                <div>Weekly rows: <b>{weekly_rows:,}</b></div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------
# Equipment panel
#
# Static version for this step.
# Selection behaviour will be added in the next step.
# ---------------------------------------------------------
equipment_rows = []

for category in categories:
    color = CATEGORY_COLORS.get(category, "#999999")

    equipment_rows.append(
        f"""
        <div style="
            display:flex;
            align-items:center;
            margin:5px 0;
            font-size:13px;
            line-height:1.15;
        ">
            <span style="
                display:inline-block;
                width:10px;
                height:10px;
                background:{color};
                margin-right:8px;
                flex:0 0 10px;
            "></span>
            <span>{category}</span>
        </div>
        """
    )

equipment_html = "".join(equipment_rows)

st.markdown(
    f"""
    <div style="
        border: 1px solid #c7cdd4;
        box-shadow: 0 1px 4px rgba(0,0,0,0.12);
        background: #ffffff;
    ">
        <div style="
            background: #2f5d84;
            color: #ffffff;
            padding: 8px 10px;
            font-weight: 700;
        ">
            Equipment
        </div>
        <div style="
            padding: 8px 10px;
        ">
            {equipment_html}
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------
# Technical data
# ---------------------------------------------------------
with st.expander("Technical data"):
    st.write(
        f"Loaded **{len(weekly):,} rows** from "
        "`weekly_equipment_losses.csv`."
    )

    st.dataframe(
        weekly.head(10),
        use_container_width=True,
    )

    st.write(
        f"Coverage: **{unique_weeks:,} weeks** | "
        f"**{len(categories):,} equipment categories**"
    )


# ---------------------------------------------------------
# Methodology
# ---------------------------------------------------------
with st.expander("Methodology and limitations"):
    st.write(
        "The dashboard uses documented WarSpotting equipment-loss records "
        "aggregated by week and equipment category."
    )
    st.write(
        "The dataset represents documented/visually confirmed records and "
        "should not be interpreted as a complete count of actual military losses."
    )
