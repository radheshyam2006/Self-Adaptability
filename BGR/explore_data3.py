"""Deep dive into BGR data - trim encoding, value distributions."""
import pandas as pd
import numpy as np

xlsx_path = r"C:\Users\radhe\OneDrive\Documents\AI_Self-adaptive_Chip\BGR\BGR_ML_DATA_JAN9_testsample_2023_MAR6.xlsx"

for sheet_name in ['TT-VDD_TEMP', 'SS_VDD_TEMP', 'FF_VDD_TEMP']:
    df = pd.read_excel(xlsx_path, sheet_name=sheet_name)
    df = df.dropna(subset=['vdd', 'temperature'])
    
    print(f"\n{'='*60}")
    print(f"SHEET: {sheet_name} | {df.shape[0]} rows")
    print(f"{'='*60}")
    print(f"Columns: {list(df.columns)}")
    print(f"VDD unique ({df['vdd'].nunique()}): {sorted(df['vdd'].unique())}")
    print(f"Temp: {df['temperature'].min()} to {df['temperature'].max()}, step~{np.diff(sorted(df['temperature'].unique())).mean():.2f}")
    
    # pctrl analysis
    pctrl = df['pctrl<3:0>'].dropna()
    print(f"\npctrl<3:0> values (type={pctrl.dtype}):")
    vc = pctrl.value_counts()
    for val, cnt in vc.items():
        print(f"  '{val}' (type={type(val).__name__}): {cnt} samples")
    
    # nctrl analysis  
    nctrl = df['nctrl<5:0>'].dropna()
    print(f"\nnctrl<5:0> values (type={nctrl.dtype}):")
    vc = nctrl.value_counts()
    for val, cnt in vc.items():
        print(f"  '{val}' (type={type(val).__name__}): {cnt} samples")
    
    # PMON_RING_CMOS_res
    pmon = df['PMON_RING_CMOS_res'].dropna()
    print(f"\nPMON_RING_CMOS_res: min={pmon.min():.0f}, max={pmon.max():.0f}, mean={pmon.mean():.0f}")
    
    # vbgr (output voltage)
    vbgr = df['vbgr'].dropna()
    print(f"vbgr: min={vbgr.min():.6f}, max={vbgr.max():.6f}, mean={vbgr.mean():.6f}, std={vbgr.std():.6f}")

# Also check testing samples
print(f"\n{'='*60}")
print("TESTING SAMPLES SHEET")
print(f"{'='*60}")
df_test = pd.read_excel(xlsx_path, sheet_name='Testing samplesC0_TT_1720_x0009_8.60E')
df_test = df_test.dropna(subset=['vdd'])
print(f"Shape: {df_test.shape}")
print(f"Columns: {list(df_test.columns)}")
print(df_test[['Corner','vdd','temperature','PMON_RING_CMOS_res','pctrl<3:0>','nctrl<5:0>','Measured values']].to_string())

# Monte Carlo sheet
print(f"\n{'='*60}")
print("GLOBAL MONTE CARLO SHEET")
print(f"{'='*60}")
df_mc = pd.read_excel(xlsx_path, sheet_name='Global_Monte carlo')
print(f"Shape: {df_mc.shape}")
print(f"Columns: {list(df_mc.columns)}")
print(df_mc.head(10).to_string())
