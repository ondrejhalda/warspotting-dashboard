# ============================================================
# WARSPOTTING ANALYTICS PIPELINE
# ============================================================
#
# Purpose:
#   Collect, validate and analyse Russian equipment losses
#   documented by WarSpotting.
#
# Data scope:
#   2022-02-24 -> present
#
# Update strategy:
#   1. First run:
#      - download complete historical dataset
#
#   2. Following runs:
#      - download newly added records via /recent
#      - refresh the last N days via date-based API
#      - merge everything by unique loss ID
#
# Outputs:
#   warspotting_raw.csv
#   weekly_losses.csv
#   dashboard.png
#
# ============================================================


from datetime import date, timedelta
from pathlib import Path
import time

import matplotlib.pyplot as plt
import pandas as pd
import requests


# ============================================================
# CONFIGURATION
# ============================================================

BASE_URL = "https://ukr.warspotting.net/api"

START_DATE = date(2022, 2, 24)

REFRESH_DAYS = 10

REQUEST_DELAY = 1.5

RAW_FILE = Path("warspotting_raw.csv")
WEEKLY_FILE = Path("weekly_losses.csv")
EQUIPMENT_WEEKLY_FILE = Path("weekly_equipment_losses.csv")
DASHBOARD_FILE = Path("dashboard.png")

USER_AGENT = (
    "Mozilla/5.0 "
    "(compatible; WarSpottingAnalytics/1.0; "
    "+https://github.com/ondrejhalda/warspotting-dashboard)"
)

HEADERS = {
    "User-Agent": USER_AGENT
}

REQUIRED_COLUMNS = [
    "id",
    "type",
    "model",
    "status",
    "lost_by",
    "date",
    "nearest_location",
    "geo",
    "unit",
    "tags",
]


# ============================================================
# API HELPERS
# ============================================================

def api_get(url, max_retries=5):
    """
    Perform a GET request with retries.

    Retries are used for temporary API/server errors
    and rate limiting.
    """

    for attempt in range(1, max_retries + 1):

        try:

            response = requests.get(
                url,
                headers=HEADERS,
                timeout=60
            )

            if response.status_code == 200:
                return response.json()

            if response.status_code in [429, 500, 502, 503, 504, 520]:

                wait_time = min(10 * attempt, 60)

                print(
                    f"  API status {response.status_code}. "
                    f"Retrying in {wait_time}s..."
                )

                time.sleep(wait_time)
                continue

            response.raise_for_status()

        except requests.RequestException as error:

            if attempt == max_retries:
                raise

            wait_time = min(10 * attempt, 60)

            print(
                f"  Request error: {error}. "
                f"Retrying in {wait_time}s..."
            )

            time.sleep(wait_time)

    raise RuntimeError(f"API request failed: {url}")


# ============================================================
# API: DATE-BASED DATA
# ============================================================

def get_day_data(target_date):
    """
    Download all Russian losses recorded for one date.

    WarSpotting returns up to 100 records per page,
    therefore pagination is handled automatically.
    """

    all_losses = []

    page = 1

    while True:

        date_string = target_date.isoformat()

        url = (
            f"{BASE_URL}/losses/russia/"
            f"{date_string}/{page}"
        )

        data = api_get(url)

        losses = data.get("losses", [])

        if not losses:
            break

        all_losses.extend(losses)

        print(
            f"    {date_string} | "
            f"page {page} | "
            f"{len(losses)} records"
        )

        # If fewer than 100 records were returned,
        # this was the final page.
        if len(losses) < 100:
            break

        page += 1

        # Respect API request limits.
        time.sleep(REQUEST_DELAY)

    return all_losses


def download_date_range(start_date, end_date):
    """
    Download losses between start_date and end_date,
    inclusive.
    """

    all_losses = []

    current_date = start_date

    total_days = (end_date - start_date).days + 1

    day_number = 0

    while current_date <= end_date:

        day_number += 1

        print(
            f"  [{day_number}/{total_days}] "
            f"Downloading {current_date.isoformat()}"
        )

        day_losses = get_day_data(current_date)

        all_losses.extend(day_losses)

        print(
            f"    Total records for day: "
            f"{len(day_losses)}"
        )

        current_date += timedelta(days=1)

        # Do not unnecessarily sleep after the final request.
        if current_date <= end_date:
            time.sleep(REQUEST_DELAY)

    return all_losses


# ============================================================
# API: RECENTLY ADDED DATA
# ============================================================

def get_recent_data():
    """
    Download the 100 most recently added Russian losses.

    Important:
    These records are sorted by when they were added to
    WarSpotting, not necessarily by their loss date.

    Therefore a record added today can have a loss date
    from 2022, 2023, etc.
    """

    url = f"{BASE_URL}/losses/russia/recent"

    print("Downloading recently added records...")

    data = api_get(url)

    losses = data.get("losses", [])

    print(
        f"  Recently added records: {len(losses)}"
    )

    return losses


# ============================================================
# LOAD EXISTING DATA
# ============================================================

def load_existing_data():
    """
    Load existing raw CSV.

    If the file does not exist, return an empty DataFrame.
    """

    if not RAW_FILE.exists():

        print("No existing raw dataset found.")

        return pd.DataFrame(columns=REQUIRED_COLUMNS)

    print(f"Loading existing dataset: {RAW_FILE}")

    df = pd.read_csv(RAW_FILE)

    print(
        f"Existing records: {len(df):,}"
    )

    return df


# ============================================================
# HISTORICAL INITIAL IMPORT
# ============================================================

def create_initial_dataset():
    """
    Perform the one-time historical backfill.

    Downloads all records from START_DATE until yesterday.

    This function is only used when the raw CSV does not yet
    exist.
    """

    yesterday = date.today() - timedelta(days=1)

    print()
    print("=" * 60)
    print("INITIAL HISTORICAL IMPORT")
    print("=" * 60)

    print(
        f"Date range: "
        f"{START_DATE.isoformat()} -> "
        f"{yesterday.isoformat()}"
    )

    records = download_date_range(
        START_DATE,
        yesterday
    )

    if not records:

        raise RuntimeError(
            "Historical import returned no records."
        )

    df = pd.DataFrame(records)

    print()
    print(
        f"Historical records downloaded: "
        f"{len(df):,}"
    )

    return df


# ============================================================
# UPDATE EXISTING DATASET
# ============================================================

def update_existing_dataset(df):
    """
    Update an existing dataset.

    Two sources are used:

    1. /recent
       Captures newly added records, including old loss dates.

    2. Last REFRESH_DAYS
       Refreshes recent dates to capture changes/corrections.
    """

    print()
    print("=" * 60)
    print("UPDATING EXISTING DATASET")
    print("=" * 60)

    # --------------------------------------------------------
    # 1. Recently added records
    # --------------------------------------------------------

    recent_records = get_recent_data()

    recent_df = pd.DataFrame(recent_records)

    if not recent_df.empty:

        print(
            f"  New/recent records received: "
            f"{len(recent_df):,}"
        )

    # --------------------------------------------------------
    # 2. Refresh recent date range
    # --------------------------------------------------------

    df["date"] = pd.to_datetime(
        df["date"],
        errors="coerce"
    )

    last_date = df["date"].max().date()

    yesterday = date.today() - timedelta(days=1)

    refresh_start = max(
        START_DATE,
        yesterday - timedelta(days=REFRESH_DAYS - 1)
    )

    refresh_end = yesterday

    print()
    print(
        f"Refreshing date range: "
        f"{refresh_start.isoformat()} -> "
        f"{refresh_end.isoformat()}"
    )

    refreshed_records = download_date_range(
        refresh_start,
        refresh_end
    )

    refreshed_df = pd.DataFrame(refreshed_records)

    # --------------------------------------------------------
    # 3. Remove old records from refresh window
    # --------------------------------------------------------

    before_count = len(df)

    df = df[
        ~(
            (df["date"].dt.date >= refresh_start)
            &
            (df["date"].dt.date <= refresh_end)
        )
    ].copy()

    removed_count = before_count - len(df)

    print(
        f"  Removed old records from refresh window: "
        f"{removed_count:,}"
    )

    # --------------------------------------------------------
    # 4. Merge all sources
    # --------------------------------------------------------

    frames = [df]

    if not recent_df.empty:
        frames.append(recent_df)

    if not refreshed_df.empty:
        frames.append(refreshed_df)

    combined = pd.concat(
        frames,
        ignore_index=True
    )

    # --------------------------------------------------------
    # 5. Deduplicate by unique WarSpotting ID
    # --------------------------------------------------------

    before_dedup = len(combined)

    combined = (
        combined
        .drop_duplicates(
            subset="id",
            keep="last"
        )
    )

    duplicates_removed = (
        before_dedup - len(combined)
    )

    print(
        f"  Duplicate records removed: "
        f"{duplicates_removed:,}"
    )

    # --------------------------------------------------------
    # 6. Sort
    # --------------------------------------------------------

    combined["date"] = pd.to_datetime(
        combined["date"],
        errors="coerce"
    )

    combined = (
        combined
        .sort_values(
            by=["date", "id"]
        )
        .reset_index(drop=True)
    )

    print(
        f"Updated total records: "
        f"{len(combined):,}"
    )

    return combined


# ============================================================
# MASTER DATA UPDATE
# ============================================================

def update_raw_data(existing_df):
    """
    Decide whether this is the first run or a normal update.
    """

    # --------------------------------------------------------
    # FIRST RUN
    # --------------------------------------------------------

    if existing_df.empty:

        df = create_initial_dataset()

        # Deduplicate historical import.
        df = (
            df
            .drop_duplicates(
                subset="id",
                keep="last"
            )
            .reset_index(drop=True)
        )

        return df

    # --------------------------------------------------------
    # NORMAL DAILY UPDATE
    # --------------------------------------------------------

    return update_existing_dataset(
        existing_df
    )


# ============================================================
# DATA VALIDATION
# ============================================================

def validate_data(df):
    """
    Validate the complete raw dataset.

    Raises an error if a critical validation fails.
    """

    print()
    print("=" * 60)
    print("DATA VALIDATION")
    print("=" * 60)

    # --------------------------------------------------------
    # Required columns
    # --------------------------------------------------------

    missing_columns = [
        column
        for column in REQUIRED_COLUMNS
        if column not in df.columns
    ]

    if missing_columns:

        raise ValueError(
            f"Missing columns: {missing_columns}"
        )

    print("  Required columns: OK")

    # --------------------------------------------------------
    # Dataset not empty
    # --------------------------------------------------------

    if df.empty:
        raise ValueError("Dataset is empty.")

    print("  Dataset not empty: OK")

    # --------------------------------------------------------
    # IDs
    # --------------------------------------------------------

    missing_ids = df["id"].isna().sum()

    if missing_ids > 0:

        raise ValueError(
            f"Missing IDs: {missing_ids}"
        )

    print("  Missing IDs: 0")

    duplicate_ids = df["id"].duplicated().sum()

    if duplicate_ids > 0:

        raise ValueError(
            f"Duplicate IDs: {duplicate_ids}"
        )

    print("  Duplicate IDs: 0")

    # --------------------------------------------------------
    # Dates
    # --------------------------------------------------------

    df["date"] = pd.to_datetime(
        df["date"],
        errors="coerce"
    )

    invalid_dates = df["date"].isna().sum()

    if invalid_dates > 0:

        raise ValueError(
            f"Invalid dates: {invalid_dates}"
        )

    print("  Invalid dates: 0")

    min_date = df["date"].min().date()
    max_date = df["date"].max().date()

    today = date.today()

    if min_date < START_DATE:

        raise ValueError(
            f"Date before START_DATE found: {min_date}"
        )

    if max_date > today:

        raise ValueError(
            f"Future date found: {max_date}"
        )

    print(
        f"  Date range: "
        f"{min_date} -> {max_date}"
    )

    # --------------------------------------------------------
    # Lost by
    # --------------------------------------------------------

    lost_by_values = (
        df["lost_by"]
        .dropna()
        .astype(str)
        .str.strip()
        .unique()
    )

    unexpected_lost_by = [
        value
        for value in lost_by_values
        if value != "Russia"
    ]

    if unexpected_lost_by:

        raise ValueError(
            "Unexpected lost_by values: "
            f"{unexpected_lost_by}"
        )

    print("  lost_by = Russia: OK")

    # --------------------------------------------------------
    # Type
    # --------------------------------------------------------

    missing_types = df["type"].isna().sum()

    if missing_types > 0:

        raise ValueError(
            f"Missing equipment types: "
            f"{missing_types}"
        )

    print("  Equipment type: OK")

    # --------------------------------------------------------
    # Year distribution
    # --------------------------------------------------------

    year_counts = (
        df["date"]
        .dt.year
        .value_counts()
        .sort_index()
    )

    print()
    print("Records by year:")

    for year, count in year_counts.items():

        print(
            f"  {year}: {count:,}"
        )

    print()
    print("VALIDATION STATUS: OK")

    return True


# ============================================================
# WEEKLY ANALYSIS
# ============================================================

def create_weekly_dataset(df):
    """
    Create weekly loss dataset.

    Weeks start on Monday.
    """

    print()
    print("=" * 60)
    print("WEEKLY ANALYSIS")
    print("=" * 60)

    weekly = (
        df
        .set_index("date")
        .resample("W-MON", label="left", closed="left")
        .size()
        .reset_index(name="weekly_losses")
    )

    weekly = weekly.rename(
        columns={"date": "week"}
    )

    # Cumulative documented losses.
    weekly["cumulative_losses"] = (
        weekly["weekly_losses"]
        .cumsum()
    )

    # Four-week rolling average.
    weekly["rolling_4_week_avg"] = (
        weekly["weekly_losses"]
        .rolling(
            window=4,
            min_periods=1
        )
        .mean()
    )

    weekly.to_csv(
        WEEKLY_FILE,
        index=False
    )

    print(
        f"Weekly dataset saved: "
        f"{WEEKLY_FILE}"
    )

    print(
        f"Weeks: {len(weekly):,}"
    )

    return weekly

# ============================================================
# WEEKLY EQUIPMENT ANALYSIS
# ============================================================

def create_weekly_equipment_dataset(df):
    """
    Create weekly equipment-loss dataset using
    WarSpotting's own equipment categories.
    """

    data = df.copy()

    data["date"] = pd.to_datetime(
        data["date"],
        errors="coerce"
    )

    # Monday as the start of the week
    data["week"] = (
        data["date"]
        - pd.to_timedelta(
            data["date"].dt.weekday,
            unit="D"
        )
    )

    weekly_equipment = (
        data
        .groupby(
            ["week", "type"],
            as_index=False
        )
        .size()
        .rename(
            columns={"size": "losses"}
        )
        .sort_values(
            by=["week", "type"]
        )
        .reset_index(drop=True)
    )

    print()
    print("=" * 60)
    print("WEEKLY EQUIPMENT ANALYSIS")
    print("=" * 60)

    print(
        f"Weekly equipment rows: "
        f"{len(weekly_equipment):,}"
    )

    print(
        f"Equipment categories: "
        f"{weekly_equipment['type'].nunique()}"
    )

    return weekly_equipment


# ============================================================
# DASHBOARD
# ============================================================

def create_dashboard(df, weekly):
    """
    Create static dashboard visualization.
    """

    print()
    print("=" * 60)
    print("CREATING DASHBOARD")
    print("=" * 60)

    # --------------------------------------------------------
    # KPI calculations
    # --------------------------------------------------------

    latest_date = df["date"].max().date()

    latest_monday = (
        latest_date
        - timedelta(
            days=latest_date.weekday()
        )
    )

    this_week_count = len(
        df[
            df["date"].dt.date >= latest_monday
        ]
    )

    four_week_average = (
        weekly["weekly_losses"]
        .tail(4)
        .mean()
    )

    data_check = (
        weekly["weekly_losses"].sum()
        == len(df)
    )

    # --------------------------------------------------------
    # Figure
    # --------------------------------------------------------

    fig, ax = plt.subplots(
        figsize=(14, 8)
    )

    fig.patch.set_facecolor("white")

    # --------------------------------------------------------
    # Weekly bars
    # --------------------------------------------------------

    bars = ax.bar(
        weekly["week"],
        weekly["weekly_losses"],
        width=5,
        alpha=0.8
    )

    # --------------------------------------------------------
    # Cumulative line
    # --------------------------------------------------------

    ax2 = ax.twinx()

    ax2.plot(
        weekly["week"],
        weekly["cumulative_losses"],
        linewidth=1.5,
        alpha=0.45
    )

    # --------------------------------------------------------
    # Titles
    # --------------------------------------------------------

    ax.set_title(
        "Russian Equipment Losses — Weekly",
        fontsize=18,
        fontweight="bold",
        pad=20
    )

    ax.set_ylabel(
        "Weekly documented losses"
    )

    ax2.set_ylabel(
        "Cumulative documented losses"
    )

    # --------------------------------------------------------
    # X-axis
    #
    # Use a date several days into the week when generating
    # labels. This prevents the first week of 2022 from being
    # visually labelled as the previous month.
    # --------------------------------------------------------

    weeks = weekly["week"]

    tick_positions = []

    last_labelled_month = None

    for i, week in enumerate(weeks):

        display_date = (
            week
            + pd.Timedelta(days=3)
        )

        month = display_date.month

        if (
            month != last_labelled_month
            and month in [1, 3, 5, 7, 9, 11]
        ):

            tick_positions.append(i)

            last_labelled_month = month

    if 0 not in tick_positions:

        tick_positions.insert(0, 0)

    tick_labels = [
        (
            weeks.iloc[i]
            + pd.Timedelta(days=3)
        ).strftime("%b %Y")
        for i in tick_positions
    ]

    ax.set_xticks(
        weeks.iloc[tick_positions]
    )

    ax.set_xticklabels(
        tick_labels,
        rotation=0
    )

    # --------------------------------------------------------
    # Grid
    # --------------------------------------------------------

    ax.grid(
        axis="y",
        alpha=0.25
    )

    ax.set_axisbelow(True)

    # --------------------------------------------------------
    # KPI cards
    # --------------------------------------------------------

    fig.text(
        0.12,
        0.91,
        "TOTAL LOSSES",
        fontsize=10,
        fontweight="bold"
    )

    fig.text(
        0.12,
        0.865,
        f"{len(df):,}",
        fontsize=22,
        fontweight="bold"
    )

    fig.text(
        0.34,
        0.91,
        "THIS WEEK",
        fontsize=10,
        fontweight="bold"
    )

    fig.text(
        0.34,
        0.865,
        f"{this_week_count:,}",
        fontsize=22,
        fontweight="bold"
    )

    fig.text(
        0.56,
        0.91,
        "4-WEEK AVG",
        fontsize=10,
        fontweight="bold"
    )

    fig.text(
        0.56,
        0.865,
        f"{four_week_average:.1f}",
        fontsize=22,
        fontweight="bold"
    )

    fig.text(
        0.78,
        0.91,
        "DATA CHECK",
        fontsize=10,
        fontweight="bold"
    )

    fig.text(
        0.78,
        0.865,
        "OK" if data_check else "ERROR",
        fontsize=22,
        fontweight="bold"
    )

    # --------------------------------------------------------
    # Footer
    # --------------------------------------------------------

    fig.text(
        0.5,
        0.02,
        f"WarSpotting | Data through "
        f"{latest_date.isoformat()}",
        ha="center",
        fontsize=9
    )

    # --------------------------------------------------------
    # Layout
    # --------------------------------------------------------

    plt.subplots_adjust(
        top=0.78,
        bottom=0.12,
        left=0.08,
        right=0.92
    )

    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------

    plt.savefig(
        DASHBOARD_FILE,
        dpi=160,
        bbox_inches="tight"
    )

    plt.close()

    print(
        f"Dashboard saved: "
        f"{DASHBOARD_FILE}"
    )


# ============================================================
# MAIN PIPELINE
# ============================================================

def main():

    print("=" * 60)
    print("WARSPOTTING ANALYTICS PIPELINE")
    print("=" * 60)

    print()
    print(
        f"Data scope starts: "
        f"{START_DATE.isoformat()}"
    )

    print()

    # --------------------------------------------------------
    # 1. Load existing raw data
    # --------------------------------------------------------

    df = load_existing_data()

    # --------------------------------------------------------
    # 2. Update / create raw dataset
    # --------------------------------------------------------

    df = update_raw_data(df)

    # --------------------------------------------------------
    # 3. Convert date column
    # --------------------------------------------------------

    df["date"] = pd.to_datetime(
        df["date"],
        errors="coerce"
    )

    # --------------------------------------------------------
    # 4. Deduplicate
    # --------------------------------------------------------

    df = (
        df
        .drop_duplicates(
            subset="id",
            keep="last"
        )
        .sort_values(
            by=["date", "id"]
        )
        .reset_index(drop=True)
    )

    # --------------------------------------------------------
    # 5. Validate
    # --------------------------------------------------------

    validate_data(df)

    # --------------------------------------------------------
    # 6. Save raw data
    # --------------------------------------------------------

    df.to_csv(
        RAW_FILE,
        index=False
    )

    print()
    print(
        f"Raw dataset saved: "
        f"{RAW_FILE}"
    )

    print(
        f"Total records: "
        f"{len(df):,}"
    )

    # --------------------------------------------------------
    # 7. Weekly analysis
    # --------------------------------------------------------

    weekly = create_weekly_dataset(df)

    # --------------------------------------------------------
    # 8. Dashboard
    # --------------------------------------------------------

    create_dashboard(
        df,
        weekly
    )

    # --------------------------------------------------------
    # 9. Complete
    # --------------------------------------------------------

    print()
    print("=" * 60)
    print("PIPELINE COMPLETE")
    print("=" * 60)

    print(
        f"Records: {len(df):,}"
    )

    print(
        f"Latest data date: "
        f"{df['date'].max().date()}"
    )

    print(
        "STATUS: OK"
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()
