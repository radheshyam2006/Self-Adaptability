"""See all sheet names, columns, and trim bit encoding patterns."""
import pandas as pd

xlsx_path = r"C:\Users\radhe\OneDrive\Documents\AI_Self-adaptive_Chip\BGR\BGR_ML_DATA_JAN9_testsample_2023_MAR6.xlsx"
xl = pd.ExcelFile(xlsx_path)

print("=== ALL SHEET NAMES ===")
for i, s in enumerate(xl.sheet_names):
    print(f"  [{i}] {s}")

# Focus on the main training data sheets
for sheet_name in ['TT_VDD_TEMP', 'SS_VDD_TEMP', 'FF_VDD_TEMP']:
    if sheet_name in xl.sheet_names:
        df = pd.read_excel(xlsx_path, sheet_name=sheet_name)
        df = df.dropna(subset=['vdd','temperature'])
        print(f"\n=== {sheet_name} ===")
        print(f"Shape: {df.shape}")
        print(f"VDD unique values ({df['vdd'].nunique()}): {sorted(df['vdd'].unique())}")
        print(f"Temp range: {df['temperature'].min()} to {df['temperature'].max()}, unique={df['temperature'].nunique()}")
        
        # Trim bit analysis
        if 'pctrl<3:0>' in df.columns:
            print(f"\npctrl<3:0> unique values ({df['pctrl<3:0>'].nunique()}):")
            for v in sorted(df['pctrl<3:0>'].dropna().unique()):
                count = (df['pctrl<3:0>'] == v).sum()
                print(f"  '{v}' -> count={count}")
        
        if 'nctrl<5:0>' in df.columns:
            print(f"\nnctrl<5:0> unique values ({df['nctrl<5:0>'].nunique()}):")
            for v in sorted(df['nctrl<5:0>'].dropna().unique()):
                count = (df['nctrl<5:0>'] == v).sum()
                print(f"  '{v}' -> count={count}")
        
        # PMON_RING_CMOS_res range
        if 'PMON_RING_CMOS_res' in df.columns:
            col = df['PMON_RING_CMOS_res'].dropna()
            print(f"\nPMON_RING_CMOS_res range: {col.min():.0f} to {col.max():.0f}")
        
        # vbgr range
        if 'vbgr' in df.columns:
            col = df['vbgr'].dropna()
            print(f"vbgr range: {col.min():.6f} to {col.max():.6f}")
            print(f"vbgr mean: {col.mean():.6f}, std: {col.std():.6f}")

# Check all available data sheets
print("\n\n=== ALL SHEETS DATA SUMMARY ===")
for sheet in xl.sheet_names:
    df = pd.read_excel(xlsx_path, sheet_name=sheet)
    print(f"\n{sheet}: {df.shape[0]} rows x {df.shape[1]} cols | columns: {list(df.columns[:5])}...")
