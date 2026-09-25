#!/usr/bin/env python3
import glob
import pandas as pd
import numpy as np

print("=" * 75)
print("  EVALUATION REPORT: GOOD SIMULATION SUITE")
print("  PDK Model: 1.8V (crn28hpcp_1d8_elk...)")
print("=" * 75)

files = sorted(glob.glob("results_good_*.csv"))
if not files:
    print("No result files found! Check good_logs/")
    exit()

all_dfs = []
for f in files:
    try:
        d = pd.read_csv(f)
        if len(d) > 0: all_dfs.append(d)
    except: pass

if not all_dfs:
    print("No valid data in CSVs!")
    exit()

df = pd.concat(all_dfs, ignore_index=True)
df['pup_err_vs_excel'] = np.abs(df['sim_pup'] - df['excel_pup'])
df['pdn_err_vs_excel'] = np.abs(df['sim_pdn'] - df['excel_pdn'])
df['pup_in_spec'] = (df['sim_pup'] >= 48.0) & (df['sim_pup'] <= 52.0)
df['pdn_in_spec'] = (df['sim_pdn'] >= 48.0) & (df['sim_pdn'] <= 52.0)
df['spec_pass'] = df['pup_in_spec'] & df['pdn_in_spec']

print(f"Total Sims Completed: {len(df)}")
print(f"Points meeting 48-52 Ohm Spec: {df['spec_pass'].sum()} / {len(df)} ({df['spec_pass'].mean()*100:.1f}%)\n")

print(f"{'Suite':<16} {'Corner':<6} {'Res_Sec':<22} {'Vreg':<6} {'Temp':<6} {'Sim_Pup':<9} {'GT_Pup':<8} {'Sim_Pdn':<9} {'GT_Pdn':<8} {'Spec':<6}")
print("-" * 105)
for _, r in df.iterrows():
    s = str(r['suite'])
    c = str(r['corner'])
    res = str(r['res_sec']).replace('_res_bip_dio_disres', '')
    v = float(r['vreg'])
    t = float(r['temp'])
    spup = float(r['sim_pup'])
    epup = float(r['excel_pup'])
    spdn = float(r['sim_pdn'])
    epdn = float(r['excel_pdn'])
    status = "PASS" if r['spec_pass'] else "FAIL"
    print(f"{s:<16} {c:<6} {res:<22} {v:<6.2f} {t:<6.1f} {spup:<9.3f} {epup:<8.2f} {spdn:<9.3f} {epdn:<8.2f} {status:<6}")

print("=" * 75)
