"""
WarSpotting scope-aware synchronization audit.

DIAGNOSTIC ONLY:
- does not modify warspotting_raw.csv
- does not modify dashboard/weekly outputs
- writes only sync_audit_scope.csv

The audit compares:
1. the complete WarSpotting Russian-loss ID snapshot
2. the local warspotting_raw.csv

BUT only records inside the project scope are compared:

    START_DATE <= date <= yesterday

This avoids false differences caused by:
- WarSpotting records before the project's START_DATE
- records dated today while the project intentionally stops at yesterday

Run from repository root:

    python sync_audit_scope.py
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
AUDIT_FILE = Path("sync_audit_scope.csv")

START_DATE = date(2022, 2, 24)

# 1.1 s/request stays below WarSpotting's documented
# limit of 10 requests per 10 seconds.
REQUEST_DELAY = 1.1

MAX_RETRIES = 5
TIMEOUT = 60

USER_AGENT = (
    "Mozilla/5.0 "
    "(compatible; WarSpottingScopeAudit/1.0; "
    "+https://github.com/ondrejhalda/warspotting-dashboard)"
)

HEADERS = {
    "User-Agent": USER_AGENT
}


# ============================================================
# API
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
# LOCAL DATA
# ============================================================

def load_raw_dataset() -> pd.DataFrame:
    """Load the local raw dataset and normalize ID/date."""
    if not RAW_FILE.exists():
        raise FileNotFoundError(
            f"Missing local dataset: {RAW_FILE}"
        )

    df = pd.read_csv(RAW_FILE)

    required = {"id", "date"}

    missing_columns = sorted(required - set(df.columns))

    if missing_columns:
        raise ValueError(
            f"Missing required columns: {missing_columns}"
        )

    df["id"] = pd.to_numeric(
        df["id"],
        errors="coerce"
    )

    if df["id"].isna().any():
        raise ValueError(
            "Local dataset contains invalid IDs."
        )

    df["id"] = df["id"].astype("int64")

    df["date"] = pd.to_datetime(
        df["date"],
        errors="coerce"
    )

    if df["date"].isna().any():
        raise ValueError(
            "Local dataset contains invalid dates."
        )

    if df["id"].duplicated().any():
        raise ValueError(
            "Local dataset contains duplicate IDs."
        )

    return df


# ============================================================
# SOURCE SNAPSHOT
# ============================================================

def download_all_source_losses() -> pd.DataFrame:
    """
    Download the complete Russian loss snapshot using the ID endpoint.

    The endpoint returns up to 100 records starting at the requested ID.
    We advance using max(returned_id) + 1 because IDs are not necessarily
    contiguous.
    """
    print()
    print("=" * 60)
    print("WARSPOTTING SCOPE-AWARE SOURCE AUDIT")
    print("=" * 60)

    all_records: list[dict] = []
    cursor = 1
    batch_number = 0

    while True:
        batch_number += 1

        url = f"{BASE_URL}/losses/russia/{cursor}"

        print(
            f"  Batch {batch_number:03d} | "
            f"starting ID {cursor}"
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

        batch_min = min(ids)
        batch_max = max(ids)

        print(
            f"    Received: {len(losses):,} | "
            f"ID range: {batch_min} -> {batch_max}"
        )

        if batch_max < cursor:
            raise RuntimeError(
                "API ID pagination did not advance."
            )

        if len(losses) < 100:
            break

        cursor = batch_max + 1
        time.sleep(REQUEST_DELAY)

    source_df = pd.DataFrame(all_records)

    if source_df.empty:
        raise RuntimeError(
            "Source API returned zero records."
        )

    source_df["id"] = pd.to_numeric(
        source_df["id"],
        errors="coerce"
    )

    source_df["date"] = pd.to_datetime(
        source_df["date"],
        errors="coerce"
    )

    source_df = source_df.dropna(
        subset=["id", "date"]
    ).copy()

    source_df["id"] = source_df["id"].astype("int64")

    duplicate_source_ids = int(
        source_df["id"].duplicated().sum()
    )

    if duplicate_source_ids:
        raise RuntimeError(
            "Source endpoint returned duplicate IDs: "
            f"{duplicate_source_ids}"
        )

    return source_df


# ============================================================
# SCOPE ANALYSIS
# ============================================================

def analyze_scope(
    raw_df: pd.DataFrame,
    source_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Compare source and local IDs only within project scope.

    Also report source records outside the project scope and local
    records that are outside the project scope.
    """
    yesterday = date.today() - timedelta(days=1)

    source_dates = source_df["date"].dt.date
    raw_dates = raw_df["date"].dt.date

    source_before_start = source_df[
        source_dates < START_DATE
    ].copy()

    source_today = source_df[
        source_dates > yesterday
    ].copy()

    source_in_scope = source_df[
        (source_dates >= START_DATE)
        & (source_dates <= yesterday)
    ].copy()

    raw_in_scope = raw_df[
        (raw_dates >= START_DATE)
        & (raw_dates <= yesterday)
    ].copy()

    raw_outside_scope = raw_df[
        (raw_dates < START_DATE)
        | (raw_dates > yesterday)
    ].copy()

    source_ids = set(source_in_scope["id"])
    raw_ids = set(raw_in_scope["id"])

    missing_ids = sorted(source_ids - raw_ids)
    extra_ids = sorted(raw_ids - source_ids)

    print()
    print("=" * 60)
    print("SCOPE RESULT")
    print("=" * 60)

    print(f"  Source all records:          {len(source_df):,}")
    print(
        f"  Source before START_DATE:   "
        f"{len(source_before_start):,}"
    )
    print(
        f"  Source after yesterday:     "
        f"{len(source_today):,}"
    )
    print(
        f"  Source IN PROJECT SCOPE:    "
        f"{len(source_in_scope):,}"
    )
    print(
        f"  Raw all records:             "
        f"{len(raw_df):,}"
    )
    print(
        f"  Raw IN PROJECT SCOPE:       "
        f"{len(raw_in_scope):,}"
    )
    print(
        f"  Raw outside project scope:  "
        f"{len(raw_outside_scope):,}"
    )

    print()
    print("  ID RECONCILIATION")
    print(
        f"  Missing source IDs:         "
        f"{len(missing_ids):,}"
    )
    print(
        f"  Extra local IDs:            "
        f"{len(extra_ids):,}"
    )
    print(
        f"  ID difference:              "
        f"{len(source_ids) - len(raw_ids):,}"
    )

    rows = []

    # --------------------------------------------------------
    # Missing from local dataset
    # --------------------------------------------------------

    if missing_ids:
        missing_df = source_in_scope[
            source_in_scope["id"].isin(missing_ids)
        ].copy()

        for _, row in missing_df.iterrows():
            rows.append({
                "direction": "MISSING_FROM_RAW",
                "id": int(row["id"]),
                "date": row["date"].date().isoformat(),
                "type": row.get("type", ""),
                "model": row.get("model", ""),
                "status": row.get("status", ""),
                "lost_by": row.get("lost_by", ""),
                "nearest_location": row.get(
                    "nearest_location", ""
                ),
            })

    # --------------------------------------------------------
    # Present locally but absent from source
    # --------------------------------------------------------

    if extra_ids:
        extra_df = raw_in_scope[
            raw_in_scope["id"].isin(extra_ids)
        ].copy()

        for _, row in extra_df.iterrows():
            rows.append({
                "direction": "EXTRA_IN_RAW",
                "id": int(row["id"]),
                "date": row["date"].date().isoformat(),
                "type": row.get("type", ""),
                "model": row.get("model", ""),
                "status": row.get("status", ""),
                "lost_by": row.get("lost_by", ""),
                "nearest_location": row.get(
                    "nearest_location", ""
                ),
            })

    audit_df = pd.DataFrame(
        rows,
        columns=[
            "direction",
            "id",
            "date",
            "type",
            "model",
            "status",
            "lost_by",
            "nearest_location",
        ],
    )

    audit_df = audit_df.sort_values(
        by=["direction", "id"]
    ).reset_index(drop=True)

    audit_df.to_csv(
        AUDIT_FILE,
        index=False
    )

    print()
    print(
        f"  Detailed audit saved: {AUDIT_FILE}"
    )

    if not audit_df.empty:
        print()
        print("RECONCILIATION DETAILS")
        print(audit_df.to_string(index=False))
    else:
        print()
        print(
            "  SOURCE AND RAW DATA MATCH "
            "WITHIN PROJECT SCOPE."
        )

    return audit_df


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    """Run the scope-aware audit without changing production data."""
    raw_df = load_raw_dataset()

    print(
        f"Local raw records: {len(raw_df):,}"
    )

    source_df = download_all_source_losses()

    audit_df = analyze_scope(
        raw_df,
        source_df
    )

    print()
    print("=" * 60)
    print("AUDIT COMPLETE")
    print("=" * 60)

    if audit_df.empty:
        print(
            "RESULT: Local raw dataset matches "
            "WarSpotting within project scope."
        )
    else:
        missing = int(
            (audit_df["direction"] == "MISSING_FROM_RAW").sum()
        )
        extra = int(
            (audit_df["direction"] == "EXTRA_IN_RAW").sum()
        )

        print(
            f"RESULT: {missing} source records are missing "
            f"from RAW; {extra} local records are not present "
            f"in the current source snapshot."
        )

    print()
    print(
        "No production dataset or dashboard file was modified."
    )


if __name__ == "__main__":
    main()
