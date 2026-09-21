"""
WarSpotting synchronization audit.

Purpose
-------
Compare the local warspotting_raw.csv with the complete Russian-loss
dataset exposed by the WarSpotting ID endpoint.

This script is DIAGNOSTIC ONLY:
- it never changes warspotting_raw.csv
- it never changes weekly datasets
- it never changes dashboard files
- it writes only a separate audit CSV and prints a summary

It also checks whether each missing source record would have been caught
by the current update strategy:
1. /losses/russia/recent (last 100 added records)
2. 10-day date refresh

Run from the repository root:

    python sync_audit.py
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
import time

import pandas as pd
import requests


# ============================================================
# CONFIGURATION
# ============================================================

BASE_URL = "https://ukr.warspotting.net/api"

RAW_FILE = Path("warspotting_raw.csv")
AUDIT_FILE = Path("sync_audit_missing.csv")

START_DATE = date(2022, 2, 24)

# Must stay within WarSpotting's documented limit:
# maximum 10 requests per 10 seconds.
REQUEST_DELAY = 1.1

MAX_RETRIES = 5
TIMEOUT = 60

USER_AGENT = (
    "Mozilla/5.0 "
    "(compatible; WarSpottingSyncAudit/1.0; "
    "+https://github.com/ondrejhalda/warspotting-dashboard)"
)

HEADERS = {
    "User-Agent": USER_AGENT
}


# ============================================================
# API HELPER
# ============================================================

def api_get(url: str) -> dict:
    """GET JSON from WarSpotting with retry handling."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(
                url,
                headers=HEADERS,
                timeout=TIMEOUT
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
            if attempt == MAX_RETRIES:
                raise

            wait_time = min(10 * attempt, 60)

            print(
                f"  Request error: {error}. "
                f"Retrying in {wait_time}s..."
            )

            time.sleep(wait_time)

    raise RuntimeError(f"API request failed: {url}")


# ============================================================
# LOAD LOCAL DATASET
# ============================================================

def load_raw_dataset() -> pd.DataFrame:
    """Load and validate the local raw dataset."""
    if not RAW_FILE.exists():
        raise FileNotFoundError(
            f"Missing local dataset: {RAW_FILE}"
        )

    df = pd.read_csv(RAW_FILE)

    required = {
        "id",
        "type",
        "model",
        "status",
        "lost_by",
        "date",
        "nearest_location",
    }

    missing_columns = sorted(required - set(df.columns))

    if missing_columns:
        raise ValueError(
            f"Missing required columns in {RAW_FILE}: "
            f"{missing_columns}"
        )

    df["id"] = pd.to_numeric(
        df["id"],
        errors="coerce"
    )

    if df["id"].isna().any():
        raise ValueError("Local dataset contains invalid IDs.")

    df["id"] = df["id"].astype("int64")

    df["date"] = pd.to_datetime(
        df["date"],
        errors="coerce"
    )

    if df["date"].isna().any():
        raise ValueError("Local dataset contains invalid dates.")

    return df


# ============================================================
# FULL SOURCE ID CRAWL
# ============================================================

def download_all_source_losses() -> pd.DataFrame:
    """
    Download the complete Russian loss list using the ID endpoint.

    WarSpotting documents this endpoint as:
        /api/losses/russia/<ID>

    It returns up to 100 losses starting at the requested ID.
    We therefore advance to max(returned_id) + 1 after each batch.
    """
    print()
    print("=" * 60)
    print("WARSPOTTING SOURCE AUDIT")
    print("=" * 60)

    all_records: list[dict] = []
    cursor = 1
    batch_number = 0

    while True:
        batch_number += 1

        url = f"{BASE_URL}/losses/russia/{cursor}"

        print(
            f"  Batch {batch_number:03d} | "
            f"request starting at ID {cursor}"
        )

        data = api_get(url)
        losses = data.get("losses", [])

        if not losses:
            print("  No more source records.")
            break

        all_records.extend(losses)

        ids = [
            int(record["id"])
            for record in losses
            if record.get("id") is not None
        ]

        if not ids:
            raise RuntimeError(
                "API returned records but no usable IDs."
            )

        batch_max_id = max(ids)

        print(
            f"    Received: {len(losses):,} | "
            f"ID range: {min(ids)} -> {batch_max_id}"
        )

        # Safety: cursor must always move forward.
        if batch_max_id < cursor:
            raise RuntimeError(
                "API ID pagination moved backwards."
            )

        # If fewer than 100 were returned, this is the final batch
        # according to the documented endpoint behaviour.
        if len(losses) < 100:
            break

        cursor = batch_max_id + 1

        time.sleep(REQUEST_DELAY)

    source_df = pd.DataFrame(all_records)

    if source_df.empty:
        raise RuntimeError(
            "Source audit returned zero records."
        )

    source_df["id"] = pd.to_numeric(
        source_df["id"],
        errors="coerce"
    )

    source_df = source_df.dropna(subset=["id"]).copy()
    source_df["id"] = source_df["id"].astype("int64")

    source_df["date"] = pd.to_datetime(
        source_df["date"],
        errors="coerce"
    )

    source_df = (
        source_df
        .drop_duplicates(subset="id", keep="last")
        .reset_index(drop=True)
    )

    return source_df


# ============================================================
# RECENT ENDPOINT
# ============================================================

def download_recent_ids() -> set[int]:
    """
    Download IDs from /recent.

    This is used only to diagnose whether a missing record should
    have been captured by the current updater.
    """
    print()
    print("Checking /recent endpoint...")

    url = f"{BASE_URL}/losses/russia/recent"

    data = api_get(url)
    losses = data.get("losses", [])

    recent_ids = {
        int(record["id"])
        for record in losses
        if record.get("id") is not None
    }

    print(f"  Recent records available: {len(recent_ids):,}")

    return recent_ids


# ============================================================
# AUDIT
# ============================================================

def build_audit(
    raw_df: pd.DataFrame,
    source_df: pd.DataFrame,
    recent_ids: set[int],
) -> pd.DataFrame:
    """Find missing/extra IDs and classify missing records."""

    raw_ids = set(raw_df["id"])
    source_ids = set(source_df["id"])

    missing_ids = sorted(source_ids - raw_ids)
    extra_ids = sorted(raw_ids - source_ids)

    print()
    print("=" * 60)
    print("AUDIT RESULT")
    print("=" * 60)

    print(f"  Source records:       {len(source_ids):,}")
    print(f"  Raw records:          {len(raw_ids):,}")
    print(f"  Missing source IDs:   {len(missing_ids):,}")
    print(f"  Extra local IDs:      {len(extra_ids):,}")
    print(
        f"  Source max ID:        {max(source_ids):,}"
    )
    print(
        f"  Raw max ID:           {max(raw_ids):,}"
    )

    yesterday = date.today() - timedelta(days=1)

    refresh_start = max(
        START_DATE,
        yesterday - timedelta(days=9)
    )

    refresh_end = yesterday

    source_missing = (
        source_df[source_df["id"].isin(missing_ids)]
        .copy()
    )

    if source_missing.empty:
        audit_df = pd.DataFrame(
            columns=[
                "id",
                "date",
                "type",
                "model",
                "status",
                "lost_by",
                "nearest_location",
                "in_recent",
                "in_10_day_refresh",
                "possible_current_updater_capture",
            ]
        )
    else:
        source_missing["date_only"] = (
            source_missing["date"].dt.date
        )

        source_missing["in_recent"] = (
            source_missing["id"].isin(recent_ids)
        )

        source_missing["in_10_day_refresh"] = (
            (source_missing["date_only"] >= refresh_start)
            & (source_missing["date_only"] <= refresh_end)
        )

        # A missing record should have been visible to at least one
        # of the current updater's two intended capture mechanisms.
        source_missing["possible_current_updater_capture"] = (
            source_missing["in_recent"]
            | source_missing["in_10_day_refresh"]
        )

        columns = [
            "id",
            "date",
            "type",
            "model",
            "status",
            "lost_by",
            "nearest_location",
            "in_recent",
            "in_10_day_refresh",
            "possible_current_updater_capture",
        ]

        audit_df = (
            source_missing[columns]
            .sort_values("id")
            .reset_index(drop=True)
        )

    audit_df.to_csv(
        AUDIT_FILE,
        index=False
    )

    print()
    print(
        f"  Audit file saved: {AUDIT_FILE}"
    )

    if not audit_df.empty:
        print()
        print("MISSING SOURCE RECORDS")
        print(audit_df.to_string(index=False))

    print()
    print("CURRENT UPDATE STRATEGY DIAGNOSTIC")
    print(
        f"  10-day refresh window: "
        f"{refresh_start.isoformat()} -> {refresh_end.isoformat()}"
    )

    if audit_df.empty:
        print("  No missing source records.")
    else:
        recent_count = int(audit_df["in_recent"].sum())
        refresh_count = int(
            audit_df["in_10_day_refresh"].sum()
        )
        uncaught_count = int(
            (~audit_df["possible_current_updater_capture"]).sum()
        )

        print(
            f"  Missing IDs found in /recent: "
            f"{recent_count}"
        )
        print(
            f"  Missing IDs inside 10-day refresh: "
            f"{refresh_count}"
        )
        print(
            f"  Missing IDs outside both mechanisms: "
            f"{uncaught_count}"
        )

        if uncaught_count > 0:
            print()
            print(
                "  INTERPRETATION:"
            )
            print(
                "  At least one missing source record was "
                "outside both current capture mechanisms."
            )
        else:
            print()
            print(
                "  INTERPRETATION:"
            )
            print(
                "  Every missing record was visible to at least "
                "one current capture mechanism."
            )

    return audit_df


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    """Run the audit without changing production data."""
    raw_df = load_raw_dataset()

    print(f"Local raw records: {len(raw_df):,}")
    print(
        f"Local ID range: "
        f"{raw_df['id'].min():,} -> {raw_df['id'].max():,}"
    )

    source_df = download_all_source_losses()
    recent_ids = download_recent_ids()

    audit_df = build_audit(
        raw_df,
        source_df,
        recent_ids,
    )

    print()
    print("=" * 60)
    print("AUDIT COMPLETE")
    print("=" * 60)

    if len(source_df) == len(raw_df) and audit_df.empty:
        print("RESULT: Local raw dataset matches source IDs.")
    else:
        print(
            "RESULT: Local raw dataset does not yet match "
            "the source IDs."
        )

    print()
    print(
        "Nothing in warspotting_raw.csv or the dashboard "
        "was modified."
    )


if __name__ == "__main__":
    main()
