#!/usr/bin/env python3
import glob
import pandas as pd
import numpy as np

print("=" * 85)
print("     FINAL CADENCE SPECTRE VALIDATION REPORT: 35 GOOD TEST CASES (6 JOBS)")
print("     PDK Model: 1.8V (crn28hpcp_1d8_elk...) | Dual Resistor Cross-Corners")
print("=" * 85)

files = sorted(glob.glob("results_job*.csv"))
if not files:
    print("No results_job*.csv files found! Check logs_6jobs/")
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

print(f"Total Simulations Completed: {len(df)} / 35")
print(f"Simulations Meeting 48-52 Ohm Spec: {df['spec_pass'].sum()} / {len(df)} ({df['spec_pass'].mean()*100:.1f}%)")
print(f"Average Pup Error vs Excel Golden: {df['pup_err_vs_excel'].mean():.4f} Ohms")
print(f"Average Pdn Error vs Excel Golden: {df['pdn_err_vs_excel'].mean():.4f} Ohms\n")

print(f"{'Test_ID':<9} {'Corner':<6} {'Resistor_Sec':<22} {'Vreg':<6} {'Temp':<6} {'Sim_Pup':<9} {'GT_Pup':<8} {'Sim_Pdn':<9} {'GT_Pdn':<8} {'Spec':<6}")
print("-" * 98)
for _, r in df.sort_values(by=['test_id']).iterrows():
    tid = str(r['test_id'])
    c = str(r['corner'])
    res = str(r['res_sec']).replace('_res_bip_dio_disres', '')
    v = float(r['vreg'])
    t = float(r['temp'])
    spup = float(r['sim_pup'])
    epup = float(r['excel_pup'])
    spdn = float(r['sim_pdn'])
    epdn = float(r['excel_pdn'])
    status = "PASS" if r['spec_pass'] else "FAIL"
    print(f"{tid:<9} {c:<6} {res:<22} {v:<6.2f} {t:<6.1f} {spup:<9.3f} {epup:<8.2f} {spdn:<9.3f} {epdn:<8.2f} {status:<6}")

print("=" * 85)
