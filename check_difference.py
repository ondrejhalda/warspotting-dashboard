import pandas as pd
import requests
import time
from datetime import date, timedelta


# ============================================================
# CONFIG
# ============================================================

BASE_URL = "https://ukr.warspotting.net/api"
RAW_FILE = "warspotting_raw.csv"

HEADERS = {
    "User-Agent": "WarSpotting Analytics Project"
}

# WarSpotting limit:
# maximum 10 requests per 10 seconds.
REQUEST_DELAY = 1.5

# How many times to retry a request after temporary errors
MAX_RETRIES = 5

# How long to wait after HTTP 429
RATE_LIMIT_WAIT = 15


# ============================================================
# SAFE API REQUEST
# ============================================================

def api_get(url):
    """
    Make a rate-limit-safe GET request to WarSpotting API.
    """

    for attempt in range(1, MAX_RETRIES + 1):

        try:

            response = requests.get(
                url,
                headers=HEADERS,
                timeout=60
            )

        except requests.RequestException as error:

            print(
                f"  Request error "
                f"(attempt {attempt}/{MAX_RETRIES}): {error}"
            )

            if attempt == MAX_RETRIES:
                raise

            time.sleep(RATE_LIMIT_WAIT)
            continue


        # ----------------------------------------------------
        # Rate limit
        # ----------------------------------------------------

        if response.status_code == 429:

            print(
                f"  HTTP 429 - rate limit reached."
                f" Waiting {RATE_LIMIT_WAIT}s..."
            )

            if attempt == MAX_RETRIES:
                response.raise_for_status()

            time.sleep(RATE_LIMIT_WAIT)
            continue


        # ----------------------------------------------------
        # Temporary server errors
        # ----------------------------------------------------

        if response.status_code in [500, 502, 503, 504, 520]:

            print(
                f"  HTTP {response.status_code}."
                f" Retrying..."
            )

            if attempt == MAX_RETRIES:
                response.raise_for_status()

            time.sleep(RATE_LIMIT_WAIT)
            continue


        response.raise_for_status()

        # Respect API request frequency
        time.sleep(REQUEST_DELAY)

        return response.json()


    raise RuntimeError("API request failed after retries.")


# ============================================================
# 1. LOAD OUR DATASET
# ============================================================

print("=" * 70)
print("OUR DATASET")
print("=" * 70)

df = pd.read_csv(RAW_FILE)

print(f"Total records: {len(df):,}")


# Normalize status

df["status_normalized"] = (
    df["status"]
    .astype(str)
    .str.strip()
    .str.lower()
)


# Normalize date

df["date_normalized"] = (
    df["date"]
    .astype(str)
    .str[:10]
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

stats = api_get(
    f"{BASE_URL}/stats/russia"
)

api_status = {
    str(status).lower(): int(count)
    for status, count
    in stats["counts_by_status"].items()
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
    set(our_status.keys()) |
    set(api_status.keys())
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

recent_data = api_get(
    f"{BASE_URL}/losses/russia/recent"
)

recent = recent_data["losses"]

recent_df = pd.DataFrame(recent)

our_ids = set(
    df["id"].astype(str)
)

recent_ids = set(
    recent_df["id"].astype(str)
)

missing_ids = recent_ids - our_ids


print(
    f"Recent records returned: "
    f"{len(recent_df):,}"
)

print(
    f"Recent IDs missing from our dataset: "
    f"{len(missing_ids):,}"
)


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
# 6. DESTROYED DIFFERENCE
# ============================================================

print("\n" + "=" * 70)
print("DESTROYED STATUS DIAGNOSTIC")
print("=" * 70)

our_destroyed = our_status.get(
    "destroyed",
    0
)

api_destroyed = api_status.get(
    "destroyed",
    0
)

destroyed_difference = (
    api_destroyed -
    our_destroyed
)


print(
    f"Our destroyed:       {our_destroyed:,}"
)

print(
    f"WarSpotting:         {api_destroyed:,}"
)

print(
    f"Difference:          {destroyed_difference:+,}"
)


# ============================================================
# 7. CHECK LAST 30 DAYS
# ============================================================

if destroyed_difference != 0:

    print("\n" + "=" * 70)
    print("CHECKING LAST 30 DAYS")
    print("=" * 70)

    end_date = date.today() - timedelta(days=1)

    start_date = (
        end_date -
        timedelta(days=29)
    )

    print(
        f"Date range: "
        f"{start_date} -> {end_date}"
    )

    missing_destroyed = []

    current_date = start_date


    while current_date <= end_date:

        date_string = current_date.isoformat()

        print(
            f"\nChecking {date_string}..."
        )

        page = 1

        day_api_ids = set()

        while True:

            url = (
                f"{BASE_URL}/losses/russia/"
                f"{date_string}/destroyed/{page}"
            )

            data = api_get(url)

            losses = data.get(
                "losses",
                []
            )

            print(
                f"  page {page}: "
                f"{len(losses)} records"
            )

            for loss in losses:

                if "id" in loss:

                    day_api_ids.add(
                        str(loss["id"])
                    )


            # Less than 100 means last page
            if len(losses) < 100:
                break

            page += 1


        # Our destroyed IDs for this date

        our_day = df[
            (df["date_normalized"] == date_string)
            &
            (
                df["status_normalized"]
                == "destroyed"
            )
        ]


        our_day_ids = set(
            our_day["id"].astype(str)
        )


        missing_for_day = (
            day_api_ids -
            our_day_ids
        )


        if missing_for_day:

            print(
                f"  >>> "
                f"{len(missing_for_day)} "
                f"missing ID(s)"
            )

            for loss in losses:

                if str(
                    loss.get("id")
                ) in missing_for_day:

                    missing_destroyed.append(
                        loss
                    )

        else:

            print(
                "  No missing destroyed IDs."
            )


        current_date += timedelta(days=1)


    # ========================================================
    # 8. SHOW FOUND RECORDS
    # ========================================================

    print("\n" + "=" * 70)
    print("POSSIBLE MISSING DESTROYED RECORDS")
    print("=" * 70)


    if missing_destroyed:

        for loss in missing_destroyed:

            print(
                f"ID: {loss.get('id')} | "
                f"Date: {loss.get('date')} | "
                f"Status: {loss.get('status')}"
            )

    else:

        print(
            "No missing destroyed records "
            "found in the last 30 days."
        )

        print(
            "The difference is likely caused "
            "by older records or status changes."
        )


else:

    print(
        "\nDestroyed counts already match."
    )


# ============================================================
# 9. FINAL SUMMARY
# ============================================================

print("\n" + "=" * 70)
print("DIAGNOSTIC SUMMARY")
print("=" * 70)

print(
    f"Our dataset:          {our_total:,}"
)

print(
    f"WarSpotting API:      {api_total:,}"
)

print(
    f"Difference:           "
    f"{api_total - our_total:+,}"
)

print(
    f"Our destroyed:        "
    f"{our_destroyed:,}"
)

print(
    f"API destroyed:        "
    f"{api_destroyed:,}"
)

print(
    f"Destroyed difference: "
    f"{destroyed_difference:+,}"
)

print("\nDiagnostic complete.")
