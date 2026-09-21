"""
WarSpotting targeted reconciliation audit.

Purpose
-------
Individually verify the 17 IDs identified by the previous
scope-aware reconciliation audit.

The script compares:
  - the current local warspotting_raw.csv row
  - the current WarSpotting API response for each target ID

IMPORTANT:
  - This script is DIAGNOSTIC ONLY.
  - It never modifies warspotting_raw.csv.
  - It never modifies dashboard/weekly outputs.
  - It writes only reconcile_ids.csv.

Target IDs come from the previous audit:
  Missing from RAW:
    24008, 41771, 43457, 47031, 47057, 47058,
    47059, 47064, 47077, 47116, 47133

  Extra in RAW:
    1216, 1217, 1218, 14067, 16310, 47160

Run from repository root:

    python reconcile_ids.py
"""

from __future__ import annotations

from pathlib import Path
import time

import pandas as pd
import requests


# ============================================================
# CONFIGURATION
# ============================================================

BASE_URL = "https://ukr.warspotting.net/api"

RAW_FILE = Path("warspotting_raw.csv")
OUTPUT_FILE = Path("reconcile_ids.csv")

REQUEST_DELAY = 1.1
MAX_RETRIES = 5
TIMEOUT = 60

USER_AGENT = (
    "Mozilla/5.0 "
    "(compatible; WarSpottingReconciliation/1.0; "
    "+https://github.com/ondrejhalda/warspotting-dashboard)"
)

HEADERS = {
    "User-Agent": USER_AGENT
}

# IDs identified by sync_audit_scope.py.
TARGET_IDS = {
    "MISSING_FROM_RAW": [
        24008,
        41771,
        43457,
        47031,
        47057,
        47058,
        47059,
        47064,
        47077,
        47116,
        47133,
    ],
    "EXTRA_IN_RAW": [
        1216,
        1217,
        1218,
        14067,
        16310,
        47160,
    ],
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
# LOCAL DATA
# ============================================================

def load_local_data() -> pd.DataFrame:
    """Load local raw data and normalize IDs."""
    if not RAW_FILE.exists():
        raise FileNotFoundError(
            f"Missing local dataset: {RAW_FILE}"
        )

    df = pd.read_csv(RAW_FILE)

    required = {
        "id",
        "date",
        "type",
        "model",
        "status",
        "lost_by",
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
        raise ValueError(
            "Local dataset contains invalid IDs."
        )

    df["id"] = df["id"].astype("int64")

    return df


# ============================================================
# TARGETED API CHECK
# ============================================================

def get_api_record_for_id(target_id: int) -> dict:
    """
    Query the ID endpoint starting at target_id and look for
    the exact target ID.

    IMPORTANT:
    The endpoint can return subsequent records when the exact
    requested ID is absent. Therefore we DO NOT treat a
    non-empty response as proof that target_id exists.
    We search the returned records for an exact ID match.
    """
    url = f"{BASE_URL}/losses/russia/{target_id}"

    data = api_get(url)

    losses = data.get("losses", [])

    exact_matches = [
        record
        for record in losses
        if record.get("id") is not None
        and int(record["id"]) == target_id
    ]

    if exact_matches:
        return {
            "exact_found": True,
            "record": exact_matches[0],
            "returned_count": len(losses),
            "returned_min_id": min(
                int(x["id"])
                for x in losses
                if x.get("id") is not None
            ),
            "returned_max_id": max(
                int(x["id"])
                for x in losses
                if x.get("id") is not None
            ),
        }

    returned_ids = [
        int(record["id"])
        for record in losses
        if record.get("id") is not None
    ]

    return {
        "exact_found": False,
        "record": None,
        "returned_count": len(losses),
        "returned_min_id": min(returned_ids)
        if returned_ids else None,
        "returned_max_id": max(returned_ids)
        if returned_ids else None,
    }


# ============================================================
# COMPARISON
# ============================================================

def compare_record(
    direction: str,
    target_id: int,
    local_row: pd.Series | None,
    api_result: dict,
) -> dict:
    """Build one comparison row."""

    source = api_result["record"]

    row = {
        "direction_from_previous_audit": direction,
        "id": target_id,
        "local_exists": local_row is not None,
        "source_exact_found": api_result["exact_found"],
        "api_returned_count": api_result["returned_count"],
        "api_returned_min_id": api_result["returned_min_id"],
        "api_returned_max_id": api_result["returned_max_id"],
    }

    # Local fields.
    if local_row is not None:
        row.update({
            "local_date": local_row.get("date", ""),
            "local_type": local_row.get("type", ""),
            "local_model": local_row.get("model", ""),
            "local_status": local_row.get("status", ""),
            "local_lost_by": local_row.get("lost_by", ""),
            "local_nearest_location": local_row.get(
                "nearest_location", ""
            ),
        })
    else:
        row.update({
            "local_date": "",
            "local_type": "",
            "local_model": "",
            "local_status": "",
            "local_lost_by": "",
            "local_nearest_location": "",
        })

    # Source fields.
    if source is not None:
        row.update({
            "source_date": source.get("date", ""),
            "source_type": source.get("type", ""),
            "source_model": source.get("model", ""),
            "source_status": source.get("status", ""),
            "source_lost_by": source.get("lost_by", ""),
            "source_nearest_location": source.get(
                "nearest_location", ""
            ),
        })
    else:
        row.update({
            "source_date": "",
            "source_type": "",
            "source_model": "",
            "source_status": "",
            "source_lost_by": "",
            "source_nearest_location": "",
        })

    # High-level interpretation.
    if local_row is not None and source is not None:
        if direction == "MISSING_FROM_RAW":
            interpretation = (
                "SOURCE_PRESENT_LOCAL_MISSING"
            )
        elif direction == "EXTRA_IN_RAW":
            interpretation = (
                "SOURCE_PRESENT_DESPITE_PREVIOUS_EXTRA_FLAG"
            )
        else:
            interpretation = "BOTH_PRESENT"

    elif local_row is not None and source is None:
        interpretation = (
            "LOCAL_PRESENT_SOURCE_EXACT_ID_NOT_FOUND"
        )

    elif local_row is None and source is not None:
        interpretation = (
            "SOURCE_PRESENT_LOCAL_MISSING"
        )

    else:
        interpretation = (
            "NOT_FOUND_IN_EITHER"
        )

    row["interpretation"] = interpretation

    return row


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    local_df = load_local_data()

    local_by_id = (
        local_df
        .drop_duplicates(subset="id", keep="last")
        .set_index("id")
    )

    targets = []

    for direction, ids in TARGET_IDS.items():
        for target_id in ids:
            targets.append((direction, target_id))

    print("=" * 60)
    print("WARSPOTTING TARGETED RECONCILIATION")
    print("=" * 60)

    print(
        f"Target IDs: {len(targets)}"
    )

    results = []

    for number, (direction, target_id) in enumerate(
        targets,
        start=1
    ):
        print()
        print(
            f"[{number}/{len(targets)}] "
            f"{direction} | ID {target_id}"
        )

        local_row = None

        if target_id in local_by_id.index:
            local_row = local_by_id.loc[target_id]

        api_result = get_api_record_for_id(target_id)

        print(
            f"  Local exists: {local_row is not None}"
        )
        print(
            f"  Exact source ID found: "
            f"{api_result['exact_found']}"
        )

        if api_result["exact_found"]:
            source = api_result["record"]

            print(
                f"  Source: "
                f"{source.get('date', '')} | "
                f"{source.get('type', '')} | "
                f"{source.get('status', '')}"
            )
        else:
            print(
                "  Exact source ID was not found in "
                "the returned batch."
            )

        results.append(
            compare_record(
                direction=direction,
                target_id=target_id,
                local_row=local_row,
                api_result=api_result,
            )
        )

        if number < len(targets):
            time.sleep(REQUEST_DELAY)

    result_df = pd.DataFrame(results)

    result_df.to_csv(
        OUTPUT_FILE,
        index=False
    )

    print()
    print("=" * 60)
    print("RECONCILIATION RESULT")
    print("=" * 60)

    print(
        result_df[
            [
                "direction_from_previous_audit",
                "id",
                "local_exists",
                "source_exact_found",
                "interpretation",
            ]
        ].to_string(index=False)
    )

    print()
    print(
        f"Detailed result saved to: {OUTPUT_FILE}"
    )

    print()
    print(
        "No production dataset or dashboard file was modified."
    )


if __name__ == "__main__":
    main()
