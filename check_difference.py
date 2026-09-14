import pandas as pd
import requests
import time
from datetime import date, timedelta

BASE_URL = "https://ukr.warspotting.net/api"
RAW_FILE = "warspotting_raw.csv"

HEADERS = {
    "User-Agent": "WarSpotting Analytics Project"
}

REQUEST_DELAY = 1.1


# ============================================================
# 1. LOAD OUR DATASET
# ============================================================

print("=" * 70)
print("OUR DATASET")
print("=" * 70)

df = pd.read_csv(RAW_FILE)

print(f"Total records: {len(df):,}")

# Normalize status names
df["status_normalized"] = (
    df["status"]
    .astype(str)
    .str.strip()
    .str.lower()
)

our_status = (
    df["status_normalized"]
    .value_counts()
    .to_dict()
)

print("\nRecords by status:")

for status, count in sorted(our_status.items()):
    print(f"  {status}: {count:,}")


# ============================================================
# 2. CURRENT WARSPOTTING STATS
# ============================================================

print("\n" + "=" * 70)
print("CURRENT WARSPOTTING API")
print("=" * 70)

response = requests.get(
    f"{BASE_URL}/stats/russia",
    headers=HEADERS,
    timeout=60
)

response.raise_for_status()

stats = response.json()

api_status = {
    str(status).lower(): int(count)
    for status, count in stats["counts_by_status"].items()
}

print("\nWarSpotting status totals:")

for status, count in sorted(api_status.items()):
    print(f"  {status}: {count:,}")

api_total = sum(api_status.values())

print(f"  TOTAL: {api_total:,}")


# ============================================================
# 3. STATUS COMPARISON
# ============================================================

print("\n" + "=" * 70)
print("STATUS COMPARISON")
print("=" * 70)

print(
    f"{'Status':<15}"
    f"{'Our CSV':>12}"
    f"{'WarSpotting':>15}"
    f"{'Difference':>15}"
)

print("-" * 57)

all_statuses = sorted(
    set(our_status.keys()) | set(api_status.keys())
)

for status in all_statuses:

    our_count = our_status.get(status, 0)
    api_count = api_status.get(status, 0)

    difference = api_count - our_count

    print(
        f"{status:<15}"
        f"{our_count:>12,}"
        f"{api_count:>15,}"
        f"{difference:>15,}"
    )


# ============================================================
# 4. TOTAL COMPARISON
# ============================================================

print("\n" + "=" * 70)
print("TOTAL COMPARISON")
print("=" * 70)

our_total = len(df)

print(f"Our CSV:       {our_total:,}")
print(f"WarSpotting:   {api_total:,}")
print(f"Difference:    {api_total - our_total:+,}")


# ============================================================
# 5. CHECK /recent
# ============================================================

print("\n" + "=" * 70)
print("RECENT RECORD CHECK")
print("=" * 70)

response = requests.get(
    f"{BASE_URL}/losses/russia/recent",
    headers=HEADERS,
    timeout=60
)

response.raise_for_status()

recent = response.json()["losses"]

recent_df = pd.DataFrame(recent)

our_ids = set(df["id"].astype(str))
recent_ids = set(recent_df["id"].astype(str))

missing_ids = recent_ids - our_ids

print(f"Recent records returned: {len(recent_df):,}")
print(f"Recent IDs missing from our dataset: {len(missing_ids):,}")

if missing_ids:

    print("\nMissing recent records:")

    columns = [
        "id",
        "date",
        "status",
        "type_name"
    ]

    available_columns = [
        column
        for column in columns
        if column in recent_df.columns
    ]

    missing = recent_df[
        recent_df["id"].astype(str).isin(missing_ids)
    ]

    print(
        missing[available_columns]
        .to_string(index=False)
    )

else:

    print("No missing recent IDs.")


# ============================================================
# 6. IF DIFFERENCE EXISTS, FIND STATUS CHANGES
# ============================================================

print("\n" + "=" * 70)
print("STATUS CHANGE DIAGNOSTIC")
print("=" * 70)

destroyed_difference = (
    api_status.get("destroyed", 0)
    - our_status.get("destroyed", 0)
)

print(
    f"Destroyed difference: {destroyed_difference:+,}"
)

if destroyed_difference == 0:

    print("No destroyed-status difference.")
    print("No further diagnostic required.")

else:

    print()
    print(
        "The API has a different number of destroyed records."
    )
    print(
        "We will check recent loss dates first."
    )
    print()

    # --------------------------------------------------------
    # Check the last 30 days individually.
    # This is only a diagnostic and does NOT modify our data.
    # --------------------------------------------------------

    end_date = date.today() - timedelta(days=1)
    start_date = end_date - timedelta(days=29)

    print(
        f"Checking destroyed records from "
        f"{start_date} -> {end_date}"
    )

    differences_found = []

    current_date = start_date

    while current_date <= end_date:

        date_string = current_date.isoformat()

        url = (
            f"{BASE_URL}/losses/russia/"
            f"{date_string}/destroyed/1"
        )

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=60
        )

        response.raise_for_status()

        data = response.json()

        api_losses = data.get("losses", [])

        api_ids = {
            str(loss["id"])
            for loss in api_losses
            if "id" in loss
        }

        our_day = df[
            (df["date"].astype(str) == date_string)
            & (df["status_normalized"] == "destroyed")
        ]

        our_ids_for_day = set(
            our_day["id"].astype(str)
        )

        missing_for_day = api_ids - our_ids_for_day

        if missing_for_day:

            print(
                f"{date_string}: "
                f"{len(missing_for_day)} missing destroyed IDs"
            )

            for loss in api_losses:

                if str(loss.get("id")) in missing_for_day:

                    differences_found.append(loss)

        current_date += timedelta(days=1)

        time.sleep(REQUEST_DELAY)

    print()

    if differences_found:

        print("=" * 70)
        print("POSSIBLE MISSING DESTROYED RECORDS")
        print("=" * 70)

        for loss in differences_found:

            print(
                f"ID: {loss.get('id')} | "
                f"Date: {loss.get('date')} | "
                f"Status: {loss.get('status')}"
            )

    else:

        print(
            "No missing destroyed IDs found in the last 30 days."
        )

        print(
            "The difference is therefore likely caused by "
            "an older record whose status was changed."
        )


# ============================================================
# 7. FINAL SUMMARY
# ============================================================

print("\n" + "=" * 70)
print("DIAGNOSTIC SUMMARY")
print("=" * 70)

print(f"Our dataset:          {our_total:,}")
print(f"WarSpotting API:      {api_total:,}")
print(f"Difference:           {api_total - our_total:+,}")

print(
    f"Our destroyed:        "
    f"{our_status.get('destroyed', 0):,}"
)

print(
    f"API destroyed:        "
    f"{api_status.get('destroyed', 0):,}"
)

print("\nDiagnostic complete.")
