"""Quick data exploration script for BGR Excel file."""
import pandas as pd
import sys

xlsx_path = r"C:\Users\radhe\OneDrive\Documents\AI_Self-adaptive_Chip\BGR\BGR_ML_DATA_JAN9_testsample_2023_MAR6.xlsx"

# Read Excel and show structure
xl = pd.ExcelFile(xlsx_path)
print("=== SHEET NAMES ===")
print(xl.sheet_names)
print()

for sheet in xl.sheet_names:
    df = pd.read_excel(xlsx_path, sheet_name=sheet)
    print(f"\n=== SHEET: '{sheet}' ===")
    print(f"Shape: {df.shape}")
    print(f"\nColumns ({len(df.columns)}):")
    for i, col in enumerate(df.columns):
        print(f"  [{i}] '{col}' — dtype: {df[col].dtype}, nulls: {df[col].isnull().sum()}, unique: {df[col].nunique()}")
    print(f"\nFirst 5 rows:")
    print(df.head().to_string())
    print(f"\nBasic stats:")
    print(df.describe().to_string())
    print(f"\n{'='*80}")
