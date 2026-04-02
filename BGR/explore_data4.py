"""Complete data analysis for BGR project planning."""
import pandas as pd
import numpy as np

xlsx_path = r"C:\Users\radhe\OneDrive\Documents\AI_Self-adaptive_Chip\BGR\BGR_ML_DATA_JAN9_testsample_2023_MAR6.xlsx"

# Sheet-by-sheet analysis
for sheet_name in ['TT-VDD_TEMP', 'SS_VDD_TEMP', 'FF_VDD_TEMP']:
    df = pd.read_excel(xlsx_path, sheet_name=sheet_name)
    df = df.dropna(subset=['vdd', 'temperature'])
    
    print(f"\n{'='*60}")
    print(f"SHEET: {sheet_name} | {df.shape[0]} rows")
    print(f"{'='*60}")
    
    # All column names (raw)
    print(f"All columns (raw): {[repr(c) for c in df.columns]}")
    
    # pctrl analysis
    pctrl = df['pctrl<3:0>'].dropna()
    print(f"\npctrl<3:0> unique values: {list(pctrl.unique())}")
    print(f"pctrl value counts:")
    for val, cnt in pctrl.value_counts().items():
        print(f"  '{val}': {cnt}")
    
    # nctrl analysis  
    nctrl = df['nctrl<5:0>'].dropna()
    print(f"\nnctrl<5:0> unique values: {list(nctrl.unique())}")
    print(f"nctrl value counts:")
    for val, cnt in nctrl.value_counts().items():
        print(f"  '{val}': {cnt}")
    
    print(f"\nPMON_RING_CMOS_res: min={df['PMON_RING_CMOS_res'].min():.0f}, max={df['PMON_RING_CMOS_res'].max():.0f}")
    print(f"VDD range: {df['vdd'].min()} to {df['vdd'].max()}")
    print(f"Temperature range: {df['temperature'].min()} to {df['temperature'].max()}")
    
    # Check 'Measured' column
    for col in df.columns:
        if 'measur' in str(col).lower() or 'vbgr' in str(col).lower():
            vals = df[col].dropna()
            if len(vals) > 0:
                print(f"\n'{col}' column: {len(vals)} non-null values, range: {vals.min():.6f} to {vals.max():.6f}")

# Testing samples
print(f"\n{'='*60}")
print("TESTING SAMPLES")
print(f"{'='*60}")
df_test = pd.read_excel(xlsx_path, sheet_name='Testing samplesC0_TT_1720_x0009_8.60E')
df_test = df_test.dropna(subset=['vdd'])
print(df_test.to_string())

# Monte Carlo
print(f"\n{'='*60}")
print("GLOBAL MONTE CARLO")
print(f"{'='*60}")
df_mc = pd.read_excel(xlsx_path, sheet_name='Global_Monte carlo')
print(f"Shape: {df_mc.shape}")
print(f"Columns: {[repr(c) for c in df_mc.columns]}")
print(df_mc.head(5).to_string())
print(f"\n...last 5 rows:")
print(df_mc.tail(5).to_string())

# Decode trim bit patterns
print(f"\n{'='*60}")
print("TRIM BIT ENCODING ANALYSIS")
print(f"{'='*60}")

all_pctrl = set()
all_nctrl = set()
for sheet_name in ['TT-VDD_TEMP', 'SS_VDD_TEMP', 'FF_VDD_TEMP']:
    df = pd.read_excel(xlsx_path, sheet_name=sheet_name)
    df = df.dropna(subset=['vdd'])
    all_pctrl.update(df['pctrl<3:0>'].dropna().unique())
    all_nctrl.update(df['nctrl<5:0>'].dropna().unique())

print(f"\nAll pctrl<3:0> values across all corners: {sorted(str(x) for x in all_pctrl)}")
print(f"All nctrl<5:0> values across all corners: {sorted(str(x) for x in all_nctrl)}")

# Parse binary trim codes
print("\n\nDecoded pctrl (removing dashes):")
for val in sorted(str(x) for x in all_pctrl):
    clean = str(val).replace('-','').replace(' ','')
    try:
        decimal = int(clean, 2)
        print(f"  '{val}' -> binary='{clean}' -> decimal={decimal}")
    except:
        print(f"  '{val}' -> could not parse")

print("\nDecoded nctrl (removing dashes):")
for val in sorted(str(x) for x in all_nctrl):
    clean = str(val).replace('-','').replace(' ','')
    try:
        decimal = int(clean, 2)
        print(f"  '{val}' -> binary='{clean}' -> decimal={decimal}")
    except:
        print(f"  '{val}' -> could not parse")
