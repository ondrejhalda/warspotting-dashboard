"""
WarSpotting Losses Dashboard

Automated data pipeline:

WarSpotting API
        ↓
Raw CSV
        ↓
Data validation
        ↓
Weekly aggregation
        ↓
Dashboard

Designed for GitHub Actions and local execution.
"""

from datetime import date, timedelta
from pathlib import Path
import time

import matplotlib.pyplot as plt
import pandas as pd
import requests


# ============================================================
# CONFIGURATION
# ============================================================

BASE_URL = "https://ukr.warspotting.net/api/losses/russia"

RAW_FILE = Path("warspotting_raw_2026.csv")
WEEKLY_FILE = Path("weekly_losses_2026.csv")
DASHBOARD_FILE = Path("dashboard.png")

# First date included in the project.
START_DATE = date(2026, 1, 1)

# Re-download the most recent 10 days on every run.
# This helps capture late-added or corrected records.
REFRESH_DAYS = 10

# WarSpotting API limit:
# maximum 10 requests per 10 seconds.
REQUEST_DELAY = 1.1

HEADERS = {
    "User-Agent": "WarSpotting-Analytics-Dashboard/1.0"
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
# API FUNCTIONS
# ============================================================

def get_day_data(target_date):
    """
    Download all loss records for one day.

    Handles pagination automatically.
    One API page can contain up to 100 records.
    """

    all_losses = []
    page = 1

    while True:

        url = f"{BASE_URL}/{target_date.isoformat()}/{page}"

        max_retries = 5
        losses = None

        for attempt in range(1, max_retries + 1):

            try:

                response = requests.get(
                    url,
                    headers=HEADERS,
                    timeout=30
                )

                # ------------------------------------------------
                # Successful request
                # ------------------------------------------------

                if response.status_code == 200:

                    data = response.json()

                    losses = data.get("losses", [])

                    break

                # ------------------------------------------------
                # Rate limit
                # ------------------------------------------------

                if response.status_code == 429:

                    wait_time = 10 * attempt

                    print(
                        f"Rate limited. "
                        f"Waiting {wait_time}s..."
                    )

                    time.sleep(wait_time)

                    continue

                # ------------------------------------------------
                # Temporary server errors
                # ------------------------------------------------

                if response.status_code in [
                    500,
                    502,
                    503,
                    504,
                    520,
                ]:

                    wait_time = 3 * attempt

                    print(
                        f"HTTP {response.status_code}. "
                        f"Retry {attempt}/{max_retries} "
                        f"in {wait_time}s..."
                    )

                    time.sleep(wait_time)

                    continue

                # ------------------------------------------------
                # Unexpected HTTP error
                # ------------------------------------------------

                response.raise_for_status()

            except requests.RequestException as error:

                if attempt == max_retries:

                    raise RuntimeError(
                        f"Request failed for "
                        f"{target_date}, page {page}: "
                        f"{error}"
                    )

                wait_time = 3 * attempt

                print(
                    f"Request error: {error}. "
                    f"Retry {attempt}/{max_retries} "
                    f"in {wait_time}s..."
                )

                time.sleep(wait_time)

        # --------------------------------------------------------
        # All retries failed
        # --------------------------------------------------------

        if losses is None:

            raise RuntimeError(
                f"Could not download "
                f"{target_date}, page {page}"
            )

        # --------------------------------------------------------
        # No records = no more pages
        # --------------------------------------------------------

        if not losses:

            break

        all_losses.extend(losses)

        print(
            f"  {target_date} | "
            f"page {page} | "
            f"{len(losses)} records"
        )

        # --------------------------------------------------------
        # Fewer than 100 records means last page
        # --------------------------------------------------------

        if len(losses) < 100:

            break

        page += 1

        # Respect API rate limit.
        time.sleep(REQUEST_DELAY)

    return all_losses


def download_date_range(start_date, end_date):
    """
    Download all records between two dates.
    """

    if start_date > end_date:

        return []

    all_losses = []

    current_date = start_date

    while current_date <= end_date:

        print(
            f"Downloading {current_date}..."
        )

        daily_losses = get_day_data(
            current_date
        )

        all_losses.extend(
            daily_losses
        )

        current_date += timedelta(days=1)

        # Respect API rate limit.
        time.sleep(REQUEST_DELAY)

    return all_losses


# ============================================================
# DATA LOADING
# ============================================================

def load_existing_data():
    """
    Load existing raw CSV.

    If the file does not exist, return an empty DataFrame.
    """

    if not RAW_FILE.exists():

        print(
            "No existing raw CSV found."
        )

        return pd.DataFrame(
            columns=REQUIRED_COLUMNS
        )

    df = pd.read_csv(
        RAW_FILE
    )

    print(
        f"Existing raw data loaded: "
        f"{len(df):,} records"
    )

    return df


# ============================================================
# DATA UPDATE
# ============================================================

def update_raw_data(df):
    """
    Update the raw dataset.

    Existing data is preserved.

    The most recent REFRESH_DAYS are downloaded again
    to capture late-added or corrected records.

    Older data is not downloaded again.
    """

    today = date.today()

    # We only process completed days.
    yesterday = today - timedelta(days=1)

    # --------------------------------------------------------
    # First run
    # --------------------------------------------------------

    if df.empty:

        download_start = START_DATE

        print(
            f"First run: "
            f"{download_start} → {yesterday}"
        )

        new_records = download_date_range(
            download_start,
            yesterday
        )

        return pd.DataFrame(
            new_records
        )

    # --------------------------------------------------------
    # Prepare existing dates
    # --------------------------------------------------------

    df["date"] = pd.to_datetime(
        df["date"],
        errors="coerce"
    )

    last_date = df["date"].max().date()

    # --------------------------------------------------------
    # Determine refresh window
    # --------------------------------------------------------

    refresh_start = max(
        START_DATE,
        last_date - timedelta(
            days=REFRESH_DAYS - 1
        )
    )

    download_end = max(
        last_date,
        yesterday
    )

    print(
        f"Refreshing last "
        f"{REFRESH_DAYS} days:"
    )

    print(
        f"{refresh_start} → {download_end}"
    )

    # --------------------------------------------------------
    # Download refresh window
    # --------------------------------------------------------

    new_records = download_date_range(
        refresh_start,
        download_end
    )

    new_df = pd.DataFrame(
        new_records
    )

    # --------------------------------------------------------
    # Nothing downloaded
    # --------------------------------------------------------

    if new_df.empty:

        print(
            "No records downloaded "
            "during refresh window."
        )

        return df

    # --------------------------------------------------------
    # Prepare new data
    # --------------------------------------------------------

    new_df["date"] = pd.to_datetime(
        new_df["date"],
        errors="coerce"
    )

    # --------------------------------------------------------
    # Remove old records from refresh window
    # --------------------------------------------------------

    keep_old = df[
        ~(
            (df["date"].dt.date >= refresh_start)
            &
            (df["date"].dt.date <= download_end)
        )
    ]

    # --------------------------------------------------------
    # Combine old + refreshed data
    # --------------------------------------------------------

    combined = pd.concat(
        [
            keep_old,
            new_df
        ],
        ignore_index=True
    )

    # --------------------------------------------------------
    # Deduplicate by WarSpotting ID
    # --------------------------------------------------------

    combined = (
        combined
        .drop_duplicates(
            subset="id",
            keep="last"
        )
        .sort_values(
            by=["date", "id"]
        )
        .reset_index(drop=True)
    )

    return combined


# ============================================================
# VALIDATION
# ============================================================

def validate_data(df):
    """
    Perform data-quality checks.

    The pipeline stops if a critical validation fails.
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
            f"Missing required columns: "
            f"{missing_columns}"
        )

    # --------------------------------------------------------
    # Empty dataset
    # --------------------------------------------------------

    if df.empty:

        raise ValueError(
            "Dataset is empty."
        )

    # --------------------------------------------------------
    # ID validation
    # --------------------------------------------------------

    if df["id"].isna().any():

        raise ValueError(
            "Dataset contains missing IDs."
        )

    duplicate_ids = (
        df["id"]
        .duplicated()
        .sum()
    )

    if duplicate_ids > 0:

        raise ValueError(
            f"Dataset contains "
            f"{duplicate_ids} duplicate IDs."
        )

    # --------------------------------------------------------
    # Date validation
    # --------------------------------------------------------

    df["date"] = pd.to_datetime(
        df["date"],
        errors="coerce"
    )

    invalid_dates = (
        df["date"]
        .isna()
        .sum()
    )

    if invalid_dates > 0:

        raise ValueError(
            f"Dataset contains "
            f"{invalid_dates} invalid dates."
        )

    min_date = df["date"].min().date()
    max_date = df["date"].max().date()

    # Dataset should not start before project start.
    if min_date < START_DATE:

        raise ValueError(
            f"Unexpected date before "
            f"{START_DATE}: {min_date}"
        )

    # Dataset should not contain future records.
    if max_date > date.today():

        raise ValueError(
            f"Dataset contains "
            f"future dates: {max_date}"
        )

    # --------------------------------------------------------
    # lost_by validation
    # --------------------------------------------------------

    lost_by_values = (
        df["lost_by"]
        .dropna()
        .astype(str)
        .unique()
    )

    unexpected_values = [
        value
        for value in lost_by_values
        if value != "Russia"
    ]

    if unexpected_values:

        raise ValueError(
            "Unexpected values in lost_by: "
            f"{unexpected_values}"
        )

    # --------------------------------------------------------
    # Basic record integrity
    # --------------------------------------------------------

    if df["type"].isna().any():

        raise ValueError(
            "Dataset contains records "
            "without equipment type."
        )

    # --------------------------------------------------------
    # Validation summary
    # --------------------------------------------------------

    print(
        f"Records     : {len(df):,}"
    )

    print(
        f"Unique IDs  : "
        f"{df['id'].nunique():,}"
    )

    print(
        f"First date  : {min_date}"
    )

    print(
        f"Last date   : {max_date}"
    )

    print()
    print("VALIDATION: OK")


# ============================================================
# WEEKLY ANALYSIS
# ============================================================

def create_weekly_dataset(df):
    """
    Aggregate equipment losses by Monday-based week.
    """

    analysis_df = df.copy()

    analysis_df["date"] = pd.to_datetime(
        analysis_df["date"]
    )

    # --------------------------------------------------------
    # Calculate Monday of each week
    # --------------------------------------------------------

    analysis_df["week"] = (
        analysis_df["date"]
        - pd.to_timedelta(
            analysis_df["date"].dt.weekday,
            unit="D"
        )
    ).dt.normalize()

    # --------------------------------------------------------
    # Weekly loss count
    # --------------------------------------------------------

    weekly = (
        analysis_df
        .groupby("week")
        .size()
        .reset_index(
            name="weekly_losses"
        )
    )

    weekly = (
        weekly
        .sort_values("week")
        .reset_index(drop=True)
    )

    # --------------------------------------------------------
    # Cumulative losses
    # --------------------------------------------------------

    weekly["cumulative_losses"] = (
        weekly["weekly_losses"]
        .cumsum()
    )

    # --------------------------------------------------------
    # Rolling 4-week average
    # --------------------------------------------------------

    weekly["rolling_4_week_avg"] = (
        weekly["weekly_losses"]
        .rolling(
            window=4,
            min_periods=1
        )
        .mean()
        .round(2)
    )

    # --------------------------------------------------------
    # Save weekly dataset
    # --------------------------------------------------------

    weekly.to_csv(
        WEEKLY_FILE,
        index=False
    )

    print()
    print("=" * 60)
    print("WEEKLY ANALYSIS")
    print("=" * 60)

    print(
        f"Number of weeks : "
        f"{len(weekly)}"
    )

    print(
        f"First week      : "
        f"{weekly['week'].min().date()}"
    )

    print(
        f"Last week       : "
        f"{weekly['week'].max().date()}"
    )

    print()
    print("Last 10 weeks:")

    print(
        weekly.tail(10).to_string(
            index=False
        )
    )

    print()
    print(
        f"WEEKLY DATA SAVED: "
        f"{WEEKLY_FILE}"
    )

    return weekly


# ============================================================
# DASHBOARD
# ============================================================

def create_dashboard(df, weekly):
    """
    Create the WarSpotting dashboard.

    Dashboard contains:

    - TOTAL LOSSES
    - THIS WEEK
    - 4-WEEK AVG
    - DATA CHECK
    - Weekly loss bars
    - Cumulative loss line
    """

    print()
    print("=" * 60)
    print("WARSPOTTING DASHBOARD")
    print("=" * 60)

    # --------------------------------------------------------
    # KPI calculations
    # --------------------------------------------------------

    total_losses = len(df)

    latest_date = (
        df["date"]
        .max()
        .date()
    )

    # Monday of latest data week.
    current_week_start = (
        latest_date
        - timedelta(
            days=latest_date.weekday()
        )
    )

    this_week_losses = len(
        df[
            df["date"].dt.date
            >= current_week_start
        ]
    )

    # --------------------------------------------------------
    # 4-week average
    # --------------------------------------------------------

    last_four_weeks = weekly.tail(4)

    four_week_average = (
        last_four_weeks[
            "weekly_losses"
        ].mean()
    )

    # --------------------------------------------------------
    # Data integrity check
    # --------------------------------------------------------

    weekly_total = (
        weekly["weekly_losses"]
        .sum()
    )

    data_check = (
        "OK"
        if weekly_total == total_losses
        else "ERROR"
    )

    print(
        f"TOTAL LOSSES : "
        f"{total_losses:,}"
    )

    print(
        f"THIS WEEK    : "
        f"{this_week_losses:,}"
    )

    print(
        f"4-WEEK AVG   : "
        f"{four_week_average:.1f}"
    )

    print(
        f"DATA CHECK   : "
        f"{data_check}"
    )

    if data_check != "OK":

        raise ValueError(
            "Data integrity check failed: "
            "weekly losses do not equal "
            "total losses."
        )

    # --------------------------------------------------------
    # Create figure
    # --------------------------------------------------------

    fig = plt.figure(
        figsize=(14, 8)
    )

    # --------------------------------------------------------
    # KPI cards
    # --------------------------------------------------------

    ax_total = fig.add_axes(
        [0.06, 0.78, 0.20, 0.13]
    )

    ax_week = fig.add_axes(
        [0.29, 0.78, 0.20, 0.13]
    )

    ax_avg = fig.add_axes(
        [0.52, 0.78, 0.20, 0.13]
    )

    ax_check = fig.add_axes(
        [0.75, 0.78, 0.19, 0.13]
    )

    kpi_axes = [
        ax_total,
        ax_week,
        ax_avg,
        ax_check
    ]

    for ax in kpi_axes:

        ax.set_xticks([])
        ax.set_yticks([])

        for spine in ax.spines.values():
            spine.set_visible(True)

    # --------------------------------------------------------
    # TOTAL LOSSES
    # --------------------------------------------------------

    ax_total.text(
        0.5,
        0.70,
        "TOTAL LOSSES",
        ha="center",
        va="center",
        fontsize=10
    )

    ax_total.text(
        0.5,
        0.30,
        f"{total_losses:,}",
        ha="center",
        va="center",
        fontsize=24,
        fontweight="bold"
    )

    # --------------------------------------------------------
    # THIS WEEK
    # --------------------------------------------------------

    ax_week.text(
        0.5,
        0.70,
        "THIS WEEK",
        ha="center",
        va="center",
        fontsize=10
    )

    ax_week.text(
        0.5,
        0.30,
        f"{this_week_losses:,}",
        ha="center",
        va="center",
        fontsize=24,
        fontweight="bold"
    )

    # --------------------------------------------------------
    # 4-WEEK AVG
    # --------------------------------------------------------

    ax_avg.text(
        0.5,
        0.70,
        "4-WEEK AVG",
        ha="center",
        va="center",
        fontsize=10
    )

    ax_avg.text(
        0.5,
        0.30,
        f"{four_week_average:.1f}",
        ha="center",
        va="center",
        fontsize=24,
        fontweight="bold"
    )

    # --------------------------------------------------------
    # DATA CHECK
    # --------------------------------------------------------

    ax_check.text(
        0.5,
        0.70,
        "DATA CHECK",
        ha="center",
        va="center",
        fontsize=10
    )

    ax_check.text(
        0.5,
        0.30,
        data_check,
        ha="center",
        va="center",
        fontsize=24,
        fontweight="bold"
    )

    # --------------------------------------------------------
    # Main chart
    # --------------------------------------------------------

    ax = fig.add_axes(
        [0.08, 0.12, 0.84, 0.57]
    )

    x = range(len(weekly))

    # Weekly losses
    ax.bar(
        x,
        weekly["weekly_losses"],
        width=0.85,
        alpha=0.8
    )

    ax.set_ylabel(
        "Weekly losses",
        fontsize=10
    )

    ax.set_xlabel(
        "Week",
        fontsize=10
    )

    ax.grid(
        axis="y",
        alpha=0.2
    )

    # --------------------------------------------------------
    # Cumulative losses
    # --------------------------------------------------------

    ax_cumulative = ax.twinx()

    ax_cumulative.plot(
        x,
        weekly["cumulative_losses"],
        linewidth=1.5,
        alpha=0.55
    )

    ax_cumulative.set_ylabel(
        "Cumulative losses",
        fontsize=10
    )

    # --------------------------------------------------------
    # X-axis month labels
    # --------------------------------------------------------

    weeks = weekly["week"]

    tick_positions = []

    last_labelled_month = None

    for i, week in enumerate(weeks):

        month = week.month

        # Approximately every 2 months.
        if (
            month != last_labelled_month
            and month in [1, 3, 5, 7, 9, 11]
        ):

            tick_positions.append(i)

            last_labelled_month = month

    # Always show first week.
    if 0 not in tick_positions:

        tick_positions.insert(0, 0)

    tick_labels = [
        weeks.iloc[i].strftime(
            "%b %Y"
        )
        for i in tick_positions
    ]

    ax.set_xticks(
        tick_positions
    )

    ax.set_xticklabels(
        tick_labels
    )

    # --------------------------------------------------------
    # Chart title
    # --------------------------------------------------------

    ax.set_title(
        "Russian Equipment Losses — Weekly",
        fontsize=16,
        fontweight="bold",
        pad=15
    )

    # --------------------------------------------------------
    # Footer
    # --------------------------------------------------------

    fig.text(
        0.08,
        0.04,
        f"WarSpotting | Data through "
        f"{latest_date.isoformat()}",
        fontsize=9
    )

    # --------------------------------------------------------
    # Save dashboard
    # --------------------------------------------------------

    fig.savefig(
        DASHBOARD_FILE,
        dpi=150,
        bbox_inches="tight"
    )

    plt.close(fig)

    print()
    print("DASHBOARD CREATED")

    print(
        f"File: {DASHBOARD_FILE}"
    )


# ============================================================
# MAIN PIPELINE
# ============================================================

def main():

    print("=" * 60)
    print("WARSPOTTING ANALYTICS PIPELINE")
    print("=" * 60)

    print()

    # --------------------------------------------------------
    # 1. Load existing raw data
    # --------------------------------------------------------

    df = load_existing_data()

    # --------------------------------------------------------
    # 2. Update raw data
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
        f"RAW DATA SAVED: "
        f"{RAW_FILE}"
    )

    # --------------------------------------------------------
    # 7. Weekly analysis
    # --------------------------------------------------------

    weekly = create_weekly_dataset(
        df
    )

    # --------------------------------------------------------
    # 8. Create dashboard
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
    print("STATUS: OK")


# ============================================================
# SCRIPT ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
