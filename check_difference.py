import pandas as pd
import requests

BASE_URL = "https://ukr.warspotting.net/api"
RAW_FILE = "warspotting_raw.csv"

HEADERS = {
    "User-Agent": "WarSpotting Analytics Project"
}


# ============================================================
# 1. OUR DATASET
# ============================================================

print("=" * 70)
print("OUR DATASET")
print("=" * 70)

df = pd.read_csv(RAW_FILE)

print(f"Total records: {len(df):,}")

print("\nRecords by status:")
print(df["status"].value_counts().to_string())


# ============================================================
# 2. CURRENT WARSPOTTING TOTAL STATS
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

counts = stats["counts_by_status"]

print("\nWarSpotting totals:")

for status, count in counts.items():
    print(f"  {status}: {count:,}")

api_total = sum(counts.values())

print(f"  TOTAL: {api_total:,}")


# ============================================================
# 3. COMPARE STATUS TOTALS
# ============================================================

print("\n" + "=" * 70)
print("STATUS COMPARISON")
print("=" * 70)

our_status = df["status"].value_counts().to_dict()

all_statuses = sorted(
    set(our_status.keys()) | set(counts.keys())
)

print(
    f"{'Status':<15}"
    f"{'Our CSV':>12}"
    f"{'WarSpotting':>15}"
    f"{'Difference':>15}"
)

print("-" * 57)

for status in all_statuses:

    our_count = our_status.get(status, 0)
    api_count = counts.get(status, 0)
    difference = api_count - our_count

    print(
        f"{status:<15}"
        f"{our_count:>12,}"
        f"{api_count:>15,}"
        f"{difference:>15,}"
    )


# ============================================================
# 4. COMPARE EQUIPMENT TYPES
# ============================================================

print("\n" + "=" * 70)
print("EQUIPMENT TYPE COMPARISON")
print("=" * 70)

# Our data
our_type_counts = (
    df[df["status"].isin(["Destroyed", "Captured", "Abandoned"])]
    .groupby("equipment_type")
    .size()
    .to_dict()
)

# API data
api_types = {
    item["type_name"]: item["counts"]
    for item in stats["counts_by_type"]
}

print(
    f"{'Equipment type':<35}"
    f"{'Our CSV':>10}"
    f"{'API':>10}"
    f"{'Diff':>10}"
)

print("-" * 65)

for equipment_type in sorted(api_types.keys()):

    api_count = api_types[equipment_type]["losses"]

    our_count = our_type_counts.get(equipment_type, 0)

    difference = api_count - our_count

    if difference != 0:

        print(
            f"{equipment_type:<35}"
            f"{our_count:>10,}"
            f"{api_count:>10,}"
            f"{difference:>10,}"
        )


# ============================================================
# 5. RECENT RECORDS
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

    missing = recent_df[
        recent_df["id"].astype(str).isin(missing_ids)
    ]

    columns = [
        "id",
        "date",
        "status",
        "equipment_type"
    ]

    available_columns = [
        column
        for column in columns
        if column in missing.columns
    ]

    print(
        missing[available_columns]
        .to_string(index=False)
    )

else:

    print("No missing recent IDs.")


# ============================================================
# 6. FINAL SUMMARY
# ============================================================

print("\n" + "=" * 70)
print("DIAGNOSTIC SUMMARY")
print("=" * 70)

print(f"Our dataset:          {len(df):,}")
print(f"WarSpotting API:      {api_total:,}")
print(f"Difference:           {api_total - len(df):+,}")

print("\nDiagnostic complete.")
