from pathlib import Path
import json

import pandas as pd
import plotly.express as px
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
        quality = json.load(file)

    return quality


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
# Basic data validation for the dashboard
# ---------------------------------------------------------
weekly["week"] = pd.to_datetime(weekly["week"], errors="coerce")
weekly["losses"] = pd.to_numeric(weekly["losses"], errors="coerce")

invalid_dates = int(weekly["week"].isna().sum())
invalid_losses = int(weekly["losses"].isna().sum())

if invalid_dates or invalid_losses:
    st.warning(
        "The analytical dataset contains invalid values. "
        f"Invalid dates: {invalid_dates}; "
        f"invalid losses: {invalid_losses}."
    )


# ---------------------------------------------------------
# Header
# ---------------------------------------------------------
st.title("WarSpotting Equipment Dashboard")
st.caption("Interactive weekly equipment-loss visualization.")


# ---------------------------------------------------------
# Data quality status
# ---------------------------------------------------------
validation_status = str(
    quality.get("validation_status", "UNKNOWN")
).upper()

if validation_status == "OK":
    st.success("Data quality: OK")
elif validation_status == "WARNING":
    st.warning("Data quality: WARNING – review the details below.")
else:
    st.error(
        f"Data quality: {validation_status} – "
        "the dataset requires attention."
    )


# ---------------------------------------------------------
# KPI cards
# ---------------------------------------------------------
raw_records = quality.get("raw_records", "—")
analytical_records = quality.get("analytical_records", "—")
equipment_categories = quality.get("equipment_categories", "—")
weekly_rows = quality.get("weekly_rows", len(weekly))

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Raw records", f"{raw_records:,}" if isinstance(raw_records, int) else raw_records)

with col2:
    st.metric(
        "Analytical records",
        f"{analytical_records:,}"
        if isinstance(analytical_records, int)
        else analytical_records,
    )

with col3:
    st.metric(
        "Equipment categories",
        f"{equipment_categories:,}"
        if isinstance(equipment_categories, int)
        else equipment_categories,
    )

with col4:
    st.metric(
        "Weekly rows",
        f"{weekly_rows:,}"
        if isinstance(weekly_rows, int)
        else weekly_rows,
    )


# ---------------------------------------------------------
# Update information
# ---------------------------------------------------------
st.subheader("Data quality details")

detail_col1, detail_col2 = st.columns(2)

with detail_col1:
    st.write(
        "**Last update (UTC):**",
        quality.get("last_update", "—"),
    )
    st.write(
        "**Excluded records:**",
        quality.get("excluded_lost_by", "—"),
    )

with detail_col2:
    st.write(
        "**Validation:**",
        quality.get("validation_detail", "—"),
    )
    st.write(
        "**New equipment categories:**",
        quality.get("new_equipment_categories", []),
    )


# ---------------------------------------------------------
# Plotly chart
# ---------------------------------------------------------
st.subheader("Russian Equipment Losses — Weekly")

chart_data = (
    weekly
    .dropna(subset=["week", "type", "losses"])
    .sort_values(["week", "type"])
)

fig = px.bar(
    chart_data,
    x="week",
    y="losses",
    color="type",
    barmode="stack",
    labels={
        "week": "Date",
        "losses": "Documented losses",
        "type": "Equipment type",
    },
)

fig.update_layout(
    height=650,
    hovermode="x unified",
    legend_title_text="Equipment",
    margin=dict(l=20, r=20, t=20, b=20),
)

st.plotly_chart(
    fig,
    use_container_width=True,
)


# ---------------------------------------------------------
# Analytical dataset preview
# ---------------------------------------------------------
st.subheader("Weekly analytical data")

st.write(
    f"Loaded **{len(weekly):,} rows** from "
    "`weekly_equipment_losses.csv`."
)

st.dataframe(
    weekly.head(10),
    use_container_width=True,
)


# ---------------------------------------------------------
# Current dataset summary
# ---------------------------------------------------------
st.subheader("Current dataset summary")

summary_col1, summary_col2, summary_col3 = st.columns(3)

with summary_col1:
    st.metric(
        "Categories in weekly data",
        weekly["type"].nunique(dropna=True),
    )

with summary_col2:
    st.metric(
        "Weeks in weekly data",
        weekly["week"].nunique(dropna=True),
    )

with summary_col3:
    st.metric(
        "Documented losses in weekly data",
        f"{weekly['losses'].sum():,.0f}",
    )
