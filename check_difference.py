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

our_status = (
    df["status"]
    .str.lower()
    .value_counts()
    .to_dict()
)

for status, count in sorted(our_status.items()):
    print(f"  {status}: {count:,}")


# ============================================================
# 2. COMPARE EACH STATUS WITH WARSPOTTING
# ============================================================

print("\n" + "=" * 70)
print("STATUS COMPARISON")
print("=" * 70)

statuses = [
    "destroyed",
    "captured",
    "abandoned",
    "damaged"
]

print(
    f"{'Status':<15}"
    f"{'Our CSV':>12}"
    f"{'WarSpotting':>15}"
    f"{'Difference':>15}"
)

print("-" * 57)

api_totals = {}

for status in statuses:

    response = requests.get(
        f"{BASE_URL}/stats/russia/{status}",
        headers=HEADERS,
        timeout=60
    )

    response.raise_for_status()

    data = response.json()

    # API returns total count
    api_count = data["count"]

    api_totals[status] = api_count

    our_count = our_status.get(status, 0)

    difference = api_count - our_count

    print(
        f"{status:<15}"
        f"{our_count:>12,}"
        f"{api_count:>15,}"
        f"{difference:>15,}"
    )


# ============================================================
# 3. TOTAL COMPARISON
# ============================================================

print("\n" + "=" * 70)
print("TOTAL")
print("=" * 70)

our_total = len(df)

api_total = sum(api_totals.values())

print(f"Our CSV:       {our_total:,}")
print(f"WarSpotting:   {api_total:,}")
print(f"Difference:    {api_total - our_total:+,}")


# ============================================================
# 4. RECENT RECORD CHECK
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

    print(missing.to_string(index=False))

else:

    print("No missing recent IDs.")


# ============================================================
# 5. FINAL SUMMARY
# ============================================================

print("\n" + "=" * 70)
print("DIAGNOSTIC SUMMARY")
print("=" * 70)

print(f"Our dataset:          {our_total:,}")
print(f"WarSpotting API:      {api_total:,}")
print(f"Difference:           {api_total - our_total:+,}")

print("\nDiagnostic complete.")
