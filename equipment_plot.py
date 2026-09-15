# ============================================================
# WARSPOTTING — ACLED-STYLE EQUIPMENT LOSS CHART
# ============================================================

# Purpose:
#   Create an interactive weekly stacked bar chart
#   of Russian equipment losses.
#
# Source:
#   warspotting_raw.csv
#
# Logic:
#   - one bar = one week
#   - total height = total documented losses
#   - each segment = WarSpotting equipment category
#   - hover = breakdown of categories for the selected week
#
# Output:
#   equipment_weekly.html
#
# This is an analytical prototype.
# It does not modify the main data pipeline.
# ============================================================


from pathlib import Path

import pandas as pd
import plotly.graph_objects as go


# ============================================================
# CONFIGURATION
# ============================================================

INPUT_FILE = Path("warspotting_raw.csv")
OUTPUT_FILE = Path("equipment_weekly.html")


# ============================================================
# LOAD RAW DATA
# ============================================================

def load_data():

    print("=" * 60)
    print("LOADING WARSPOTTING RAW DATA")
    print("=" * 60)

    if not INPUT_FILE.exists():

        raise FileNotFoundError(
            f"Input file not found: {INPUT_FILE}"
        )

    df = pd.read_csv(INPUT_FILE)

    print(
        f"Raw records loaded: {len(df):,}"
    )

    required_columns = [
        "id",
        "date",
        "type",
        "lost_by"
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing_columns:

        raise ValueError(
            f"Missing columns: {missing_columns}"
        )

    # Convert date.
    df["date"] = pd.to_datetime(
        df["date"],
        errors="coerce"
    )

    if df["date"].isna().any():

        raise ValueError(
            "Invalid dates found in raw dataset."
        )

    # Check equipment category.
    if df["type"].isna().any():

        raise ValueError(
            "Missing equipment categories found."
        )

    # Make sure we are analysing Russian losses.
    unexpected_lost_by = (
        df["lost_by"]
        .dropna()
        .astype(str)
        .str.strip()
        .unique()
    )

    unexpected_lost_by = [
        value
        for value in unexpected_lost_by
        if value != "Russia"
    ]

    if unexpected_lost_by:

        raise ValueError(
            "Unexpected lost_by values: "
            f"{unexpected_lost_by}"
        )

    return df


# ============================================================
# CREATE WEEKLY DATASET
# ============================================================

def create_weekly_dataset(df):

    print()
    print("=" * 60)
    print("CREATING WEEKLY EQUIPMENT DATA")
    print("=" * 60)

    data = df.copy()

    # --------------------------------------------------------
    # Monday-based week
    # --------------------------------------------------------

    data["week"] = (
        data["date"]
        - pd.to_timedelta(
            data["date"].dt.weekday,
            unit="D"
        )
    )

    # --------------------------------------------------------
    # Aggregate by week and WarSpotting equipment type
    # --------------------------------------------------------

    weekly = (
        data
        .groupby(
            ["week", "type"],
            as_index=False
        )
        .size()
        .rename(
            columns={
                "size": "losses"
            }
        )
        .sort_values(
            by=["week", "type"]
        )
        .reset_index(drop=True)
    )

    print(
        f"Weekly rows: {len(weekly):,}"
    )

    print(
        f"Equipment categories: "
        f"{weekly['type'].nunique()}"
    )

    return weekly


# ============================================================
# VALIDATION
# ============================================================

def validate_weekly_data(raw_df, weekly_df):

    print()
    print("=" * 60)
    print("WEEKLY DATA VALIDATION")
    print("=" * 60)

    # --------------------------------------------------------
    # 1. Overall total
    # --------------------------------------------------------

    raw_total = len(raw_df)

    weekly_total = weekly_df["losses"].sum()

    print(
        f"Raw records: {raw_total:,}"
    )

    print(
        f"Weekly aggregated records: "
        f"{weekly_total:,}"
    )

    if raw_total != weekly_total:

        raise ValueError(
            "Weekly aggregation does not match "
            "raw dataset: "
            f"raw={raw_total:,}, "
            f"weekly={weekly_total:,}"
        )

    print(
        "Raw vs weekly total: OK"
    )

    # --------------------------------------------------------
    # 2. Duplicate week/category combinations
    # --------------------------------------------------------

    duplicates = (
        weekly_df
        .duplicated(
            subset=["week", "type"]
        )
        .sum()
    )

    if duplicates > 0:

        raise ValueError(
            "Duplicate week/category combinations: "
            f"{duplicates}"
        )

    print(
        "Duplicate week/category combinations: 0"
    )

    # --------------------------------------------------------
    # 3. Negative values
    # --------------------------------------------------------

    negative_values = (
        weekly_df["losses"] < 0
    ).sum()

    if negative_values > 0:

        raise ValueError(
            f"Negative loss values: "
            f"{negative_values}"
        )

    print(
        "Negative loss values: 0"
    )

    # --------------------------------------------------------
    # 4. Categories
    # --------------------------------------------------------

    categories = weekly_df["type"].nunique()

    if categories == 0:

        raise ValueError(
            "No equipment categories found."
        )

    print(
        f"Equipment categories: {categories}"
    )

    print()
    print("VALIDATION STATUS: OK")


# ============================================================
# CATEGORY ORDER
# ============================================================

def get_category_order(df):

    # Order categories by their total number
    # of documented losses across the entire dataset.

    category_totals = (
        df
        .groupby("type")["losses"]
        .sum()
        .sort_values(
            ascending=False
        )
    )

    return category_totals.index.tolist()


# ============================================================
# CREATE ACLED-STYLE CHART
# ============================================================

def create_chart(weekly):

    print()
    print("=" * 60)
    print("CREATING INTERACTIVE CHART")
    print("=" * 60)

    categories = get_category_order(weekly)

    fig = go.Figure()

    # --------------------------------------------------------
    # One stacked bar trace per equipment category
    # --------------------------------------------------------

    for category in categories:

        category_data = (
            weekly[
                weekly["type"] == category
            ]
            .sort_values("week")
        )

        fig.add_trace(
            go.Bar(
                x=category_data["week"],
                y=category_data["losses"],
                name=category,

                hovertemplate=(
                    "<b>%{fullData.name}</b><br>"
                    "%{y} documented losses"
                    "<extra></extra>"
                )
            )
        )

    # --------------------------------------------------------
    # Layout
    # --------------------------------------------------------

    fig.update_layout(

        title={
            "text": (
                "Russian Equipment Losses — Weekly"
            ),
            "x": 0.5,
            "xanchor": "center"
        },

        barmode="stack",

        hovermode="x unified",

        xaxis={
            "title": "Date",
            "tickformat": "%m/%d/%y",
            "dtick": "M2"
        },

        yaxis={
            "title": "Documented losses",
            "rangemode": "tozero"
        },

        legend={
            "title": "Equipment category"
        },

        height=750,

        margin={
            "l": 70,
            "r": 40,
            "t": 90,
            "b": 70
        },

        hoverlabel={
            "align": "left"
        }
    )

    return fig


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 60)
    print("WARSPOTTING ACLED-STYLE ANALYSIS")
    print("=" * 60)

    print()

    # --------------------------------------------------------
    # 1. Load raw data
    # --------------------------------------------------------

    raw_df = load_data()

    # --------------------------------------------------------
    # 2. Create weekly equipment aggregation
    # --------------------------------------------------------

    weekly_df = create_weekly_dataset(
        raw_df
    )

    # --------------------------------------------------------
    # 3. Validate aggregation
    # --------------------------------------------------------

    validate_weekly_data(
        raw_df,
        weekly_df
    )

    # --------------------------------------------------------
    # 4. Create chart
    # --------------------------------------------------------

    fig = create_chart(
        weekly_df
    )

    # --------------------------------------------------------
    # 5. Save HTML
    # --------------------------------------------------------

    fig.write_html(
        OUTPUT_FILE,
        include_plotlyjs=True
    )

    print()
    print(
        f"Interactive chart saved: "
        f"{OUTPUT_FILE}"
    )

    print()
    print("=" * 60)
    print("ANALYSIS COMPLETE")
    print("=" * 60)


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()
