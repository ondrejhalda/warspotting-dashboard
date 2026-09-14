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

print("=" * 60)
print("OUR DATASET")
print("=" * 60)

df = pd.read_csv(RAW_FILE)

print(f"Total records: {len(df):,}")

print("\nRecords by status:")
print(df["status"].value_counts().to_string())


# ============================================================
# 2. CURRENT WARSPOTTING STATS
# ============================================================

print("\n" + "=" * 60)
print("WARSPOTTING API STATS")
print("=" * 60)

response = requests.get(
    f"{BASE_URL}/stats/russia",
    headers=HEADERS,
    timeout=60
)

response.raise_for_status()

stats = response.json()

print(stats)


# ============================================================
# 3. RECENT RECORDS
# ============================================================

print("\n" + "=" * 60)
print("RECENT RECORDS")
print("=" * 60)

response = requests.get(
    f"{BASE_URL}/losses/russia/recent",
    headers=HEADERS,
    timeout=60
)

response.raise_for_status()

recent = response.json()["losses"]

recent_df = pd.DataFrame(recent)

print(f"Recent records returned: {len(recent_df):,}")


# ============================================================
# 4. COMPARE IDs
# ============================================================

our_ids = set(df["id"].astype(str))
recent_ids = set(recent_df["id"].astype(str))

missing_ids = recent_ids - our_ids

print(f"Recent IDs missing from our dataset: {len(missing_ids)}")


if missing_ids:
    print("\nRecords found in /recent but NOT in our dataset:")

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
        column for column in columns
        if column in missing.columns
    ]

    print(
        missing[available_columns]
        .to_string(index=False)
    )

else:
    print("\nNo missing recent IDs.")


# ============================================================
# 5. SUMMARY
# ============================================================

print("\n" + "=" * 60)
print("DIAGNOSTIC SUMMARY")
print("=" * 60)

print(f"Our dataset:              {len(df):,}")
print(f"Recent records:            {len(recent_df):,}")
print(f"Missing recent IDs:        {len(missing_ids):,}")

print("\nDiagnostic complete.")
