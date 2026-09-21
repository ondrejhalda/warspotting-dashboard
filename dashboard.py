# ============================================================
# WARSPOTTING ANALYTICS PIPELINE
# ============================================================

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
#   weekly_equipment_losses.csv
#   dashboard.png
#
# ============================================================


from datetime import date, timedelta
from pathlib import Path
import time
import json

import matplotlib.pyplot as plt
import pandas as pd
import requests


# ============================================================
# CONFIGURATION
# ============================================================

BASE_URL = "https://ukr.warspotting.net/api"

START_DATE = date(2022, 2, 24)

REFRESH_DAYS = 10

REQUEST_DELAY = 1.1

# Full source reconciliation is enabled to detect historical
# records added after their original loss date.
FULL_SOURCE_RECONCILIATION = True

# Safety switch for the first production verification run.
# Missing source records are added automatically, while local-only
# records are preserved until the source snapshot behaviour is confirmed.
REMOVE_LOCAL_ONLY_RECORDS = False

SYNC_QUALITY_FILE = Path("sync_quality.json")

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
# SOURCE RECONCILIATION
# ============================================================

def get_full_source_snapshot():
    """
    Download the complete current Russian-loss snapshot using
    WarSpotting's ID-based endpoint.

    The endpoint returns batches of up to 100 records. The next
    request starts at max(returned_id) + 1.

    The result is used as a reconciliation source only after
    basic integrity checks have passed.
    """

    print()
    print("=" * 60)
    print("FULL SOURCE RECONCILIATION")
    print("=" * 60)

    records = []
    cursor = 1
    batch_number = 0

    while True:

        batch_number += 1

        url = f"{BASE_URL}/losses/russia/{cursor}"

        print(
            f"  Source batch {batch_number:03d} | "
            f"starting ID {cursor}"
        )

        data = api_get(url)

        losses = data.get("losses", [])

        if not losses:
            break

        records.extend(losses)

        ids = [
            int(record["id"])
            for record in losses
            if record.get("id") is not None
        ]

        if not ids:
            raise RuntimeError(
                "Source batch contains records but no valid IDs."
            )

        batch_min_id = min(ids)
        batch_max_id = max(ids)

        print(
            f"    Received: {len(losses):,} | "
            f"ID range: {batch_min_id} -> {batch_max_id}"
        )

        if batch_max_id < cursor:
            raise RuntimeError(
                "Source ID pagination did not advance."
            )

        if len(losses) < 100:
            break

        cursor = batch_max_id + 1

        time.sleep(REQUEST_DELAY)

    source_df = pd.DataFrame(records)

    if source_df.empty:
        raise RuntimeError(
            "Full source reconciliation returned zero records."
        )

    required_columns = [
        "id",
        "date",
        "type",
        "model",
        "status",
        "lost_by",
        "nearest_location",
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in source_df.columns
    ]

    if missing_columns:
        raise RuntimeError(
            "Source reconciliation is missing columns: "
            f"{missing_columns}"
        )

    source_df["id"] = pd.to_numeric(
        source_df["id"],
        errors="coerce"
    )

    if source_df["id"].isna().any():
        raise RuntimeError(
            "Source reconciliation contains invalid IDs."
        )

    source_df["id"] = source_df["id"].astype("int64")

    duplicate_ids = int(
        source_df["id"].duplicated().sum()
    )

    if duplicate_ids > 0:
        raise RuntimeError(
            "Source reconciliation returned duplicate IDs: "
            f"{duplicate_ids}"
        )

    source_df["date"] = pd.to_datetime(
        source_df["date"],
        errors="coerce"
    )

    invalid_dates = int(
        source_df["date"].isna().sum()
    )

    if invalid_dates > 0:
        raise RuntimeError(
            "Source reconciliation contains invalid dates: "
            f"{invalid_dates}"
        )

    return source_df


def save_sync_quality(
    source_df,
    source_in_scope,
    local_in_scope,
    missing_ids,
    extra_ids,
    final_df,
    status,
    detail,
):
    """
    Save reconciliation metadata separately from data_quality.json.

    equipment_plot.py currently owns data_quality.json, so this file
    intentionally remains separate for this controlled change.
    """

    payload = {
        "source_all_records": int(len(source_df)),
        "source_records_in_scope": int(len(source_in_scope)),
        "raw_records_before_sync": int(len(local_in_scope)),
        "raw_records_after_sync": int(len(final_df)),
        "missing_source_ids": [
            int(value)
            for value in missing_ids
        ],
        "extra_local_ids": [
            int(value)
            for value in extra_ids
        ],
        "missing_source_count": int(len(missing_ids)),
        "extra_local_count": int(len(extra_ids)),
        "sync_difference_before": int(
            len(source_in_scope) - len(local_in_scope)
        ),
        "sync_difference_after": int(
            len(source_in_scope) - len(final_df)
        ),
        "source_max_id": int(source_df["id"].max()),
        "raw_max_id_before": (
            int(local_in_scope["id"].max())
            if not local_in_scope.empty
            else None
        ),
        "raw_max_id_after": (
            int(final_df["id"].max())
            if not final_df.empty
            else None
        ),
        "last_date_in_source_scope": (
            source_in_scope["date"].max()
            .date()
            .isoformat()
            if not source_in_scope.empty
            else None
        ),
        "validation_status": status,
        "validation_detail": detail,
        "last_update": pd.Timestamp.now(
            tz="UTC"
        ).strftime("%Y-%m-%d %H:%M:%S"),
    }

    SYNC_QUALITY_FILE.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return payload


def reconcile_with_source(df):
    """
    Reconcile the current working dataset with a complete
    WarSpotting source snapshot.

    Project scope:
        START_DATE <= date <= yesterday

    Safety behaviour for the first verification run:
      - missing source records are added
      - local-only records are preserved unless
        REMOVE_LOCAL_ONLY_RECORDS is explicitly enabled

    A source snapshot is accepted only after basic integrity checks.
    If the source max ID is below the local max ID, the pipeline stops
    instead of replacing the dataset with an obviously incomplete
    snapshot.
    """

    source_df = get_full_source_snapshot()

    yesterday = date.today() - timedelta(days=1)

    source_dates = source_df["date"].dt.date

    source_in_scope = source_df[
        (source_dates >= START_DATE)
        & (source_dates <= yesterday)
    ].copy()

    if source_in_scope.empty:
        raise RuntimeError(
            "Source reconciliation produced no records "
            "inside project scope."
        )

    lost_by_values = (
        source_in_scope["lost_by"]
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
        raise RuntimeError(
            "Unexpected lost_by values in source scope: "
            f"{unexpected_lost_by}"
        )

    working_df = df.copy()

    working_df["id"] = pd.to_numeric(
        working_df["id"],
        errors="coerce"
    )

    if working_df["id"].isna().any():
        raise RuntimeError(
            "Working dataset contains invalid IDs."
        )

    working_df["id"] = working_df["id"].astype("int64")

    working_df["date"] = pd.to_datetime(
        working_df["date"],
        errors="coerce"
    )

    if working_df["date"].isna().any():
        raise RuntimeError(
            "Working dataset contains invalid dates."
        )

    local_dates = working_df["date"].dt.date

    local_in_scope = working_df[
        (local_dates >= START_DATE)
        & (local_dates <= yesterday)
    ].copy()

    source_ids = set(source_in_scope["id"])
    local_ids = set(local_in_scope["id"])

    missing_ids = sorted(
        source_ids - local_ids
    )

    extra_ids = sorted(
        local_ids - source_ids
    )

    source_max_id = int(
        source_df["id"].max()
    )

    local_max_id = int(
        local_in_scope["id"].max()
    )

    print()
    print("SOURCE RECONCILIATION RESULT")
    print(
        f"  Source all records      : "
        f"{len(source_df):,}"
    )
    print(
        f"  Source in project scope: "
        f"{len(source_in_scope):,}"
    )
    print(
        f"  Local in project scope : "
        f"{len(local_in_scope):,}"
    )
    print(
        f"  Missing source IDs     : "
        f"{len(missing_ids):,}"
    )
    print(
        f"  Extra local IDs        : "
        f"{len(extra_ids):,}"
    )
    print(
        f"  Source max ID          : "
        f"{source_max_id:,}"
    )
    print(
        f"  Local max ID           : "
        f"{local_max_id:,}"
    )

    if missing_ids:
        print(
            f"  Missing IDs: {missing_ids}"
        )

    if extra_ids:
        print(
            f"  Extra local IDs: {extra_ids}"
        )

    # --------------------------------------------------------
    # Fail-safe against an obviously incomplete source crawl.
    # --------------------------------------------------------

    if source_max_id < local_max_id:

        detail = (
            "SOURCE MAX ID BELOW LOCAL MAX ID — "
            "local dataset preserved"
        )

        save_sync_quality(
            source_df,
            source_in_scope,
            local_in_scope,
            missing_ids,
            extra_ids,
            local_in_scope,
            "ERROR",
            detail,
        )

        raise RuntimeError(
            "Source reconciliation appears incomplete: "
            f"source_max_id={source_max_id}, "
            f"local_max_id={local_max_id}. "
            "Existing dataset was NOT replaced."
        )

    # --------------------------------------------------------
    # Build reconciled dataset.
    # --------------------------------------------------------

    if REMOVE_LOCAL_ONLY_RECORDS:

        reconciled_df = (
            source_in_scope
            .copy()
        )

        status = (
            "OK"
            if not missing_ids and not extra_ids
            else "SYNCED"
        )

        detail = (
            "Source and local IDs matched"
            if not missing_ids and not extra_ids
            else
            "Source reconciliation applied"
        )

    else:

        # Add source records that are missing locally.
        # Preserve local-only records during the first verification
        # run so that potentially temporary source inconsistencies do
        # not cause irreversible data loss.
        local_only_df = local_in_scope[
            local_in_scope["id"].isin(extra_ids)
        ].copy()

        reconciled_df = pd.concat(
            [
                source_in_scope,
                local_only_df,
            ],
            ignore_index=True,
        )

        reconciled_df = (
            reconciled_df
            .drop_duplicates(
                subset="id",
                keep="last"
            )
            .sort_values(
                by=["date", "id"]
            )
            .reset_index(drop=True)
        )

        status = (
            "OK"
            if not missing_ids and not extra_ids
            else "WARNING"
        )

        if extra_ids:
            detail = (
                "Source records synchronized; "
                "local-only records preserved for review"
            )
        else:
            detail = (
                "Source records synchronized"
            )

    # --------------------------------------------------------
    # Final local/source comparison.
    # --------------------------------------------------------

    final_ids = set(
        reconciled_df["id"]
    )

    remaining_missing_ids = sorted(
        source_ids - final_ids
    )

    remaining_extra_ids = sorted(
        final_ids - source_ids
    )

    if remaining_missing_ids:
        save_sync_quality(
            source_df,
            source_in_scope,
            local_in_scope,
            missing_ids,
            extra_ids,
            reconciled_df,
            "ERROR",
            "Source records remain missing after reconciliation",
        )

        raise RuntimeError(
            "Source reconciliation did not add all missing IDs: "
            f"{remaining_missing_ids}"
        )

    print()
    print(
        f"  Final reconciled records: "
        f"{len(reconciled_df):,}"
    )
    print(
        f"  Missing after sync       : "
        f"{len(remaining_missing_ids):,}"
    )
    print(
        f"  Local-only after sync    : "
        f"{len(remaining_extra_ids):,}"
    )

    save_sync_quality(
        source_df,
        source_in_scope,
        local_in_scope,
        missing_ids,
        extra_ids,
        reconciled_df,
        status,
        detail,
    )

    return reconciled_df


# ============================================================
# MASTER DATA UPDATE
# ============================================================

def update_raw_data(existing_df):
    """
    Update the raw dataset.

    The existing daily mechanism remains unchanged:
      1. /recent
      2. refresh recent dates
      3. merge and deduplicate

    A full source reconciliation is then performed as an additional
    synchronization layer.

    During the first verification run, source records that are present
    in WarSpotting but missing locally are added automatically. Local-only
    records are preserved for review and are not deleted automatically.
    """

    if existing_df.empty:

        df = create_initial_dataset()

        df = (
            df
            .drop_duplicates(
                subset="id",
                keep="last"
            )
            .reset_index(drop=True)
        )

        return df

    df = update_existing_dataset(
        existing_df
    )

    if FULL_SOURCE_RECONCILIATION:

        df = reconcile_with_source(
            df
        )

    return df


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
        .resample(
            "W-MON",
            label="left",
            closed="left"
        )
        .size()
        .reset_index(
            name="weekly_losses"
        )
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

    The WarSpotting 'type' field is used directly.
    No manual model-to-category mapping is applied.

    Includes validation to ensure that the equipment
    aggregation matches the complete raw dataset.
    """

    data = df.copy()

    data["date"] = pd.to_datetime(
        data["date"],
        errors="coerce"
    )

    # --------------------------------------------------------
    # Create Monday-based week
    # --------------------------------------------------------

    data["week"] = (
        data["date"]
        - pd.to_timedelta(
            data["date"].dt.weekday,
            unit="D"
        )
    )

    # --------------------------------------------------------
    # Aggregate losses by week and equipment category
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # Validation
    # --------------------------------------------------------

    raw_total = len(data)

    equipment_total = weekly_equipment["losses"].sum()

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

    print()
    print("EQUIPMENT DATA VALIDATION")

    print(
        f"  Raw records: "
        f"{raw_total:,}"
    )

    print(
        f"  Equipment aggregated records: "
        f"{equipment_total:,}"
    )

    # The sum of all equipment categories must equal
    # the number of records in the raw dataset.
    if equipment_total != raw_total:

        raise ValueError(
            "Equipment aggregation does not match "
            "the raw dataset: "
            f"raw={raw_total:,}, "
            f"equipment={equipment_total:,}"
        )

    print(
        "  Raw vs equipment total: OK"
    )

    print(
        "EQUIPMENT VALIDATION STATUS: OK"
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
    # 8. Weekly equipment analysis
    # --------------------------------------------------------

    equipment_weekly = create_weekly_equipment_dataset(df)

    equipment_weekly.to_csv(
        EQUIPMENT_WEEKLY_FILE,
        index=False
    )

    print(
        f"Weekly equipment dataset saved: "
        f"{EQUIPMENT_WEEKLY_FILE}"
    )

    # --------------------------------------------------------
    # 9. Dashboard
    # --------------------------------------------------------

    create_dashboard(
        df,
        weekly
    )

    # --------------------------------------------------------
    # 10. Complete
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
        f"Equipment categories: "
        f"{equipment_weekly['type'].nunique()}"
    )

    print(
        "STATUS: OK"
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()
