import pandas as pd

RAW_FILE = "warspotting_raw.csv"

df = pd.read_csv(RAW_FILE)

print("=" * 60)
print("WARSPOTTING EQUIPMENT TYPES")
print("=" * 60)

type_counts = (
    df["type"]
    .value_counts(dropna=False)
    .sort_index()
)

print(type_counts.to_string())

print()
print("=" * 60)
print(f"Number of unique types: {df['type'].nunique(dropna=False)}")
print("=" * 60)
