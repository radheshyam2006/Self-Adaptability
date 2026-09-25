#!/usr/bin/env python3
import glob
import pandas as pd
import numpy as np

print("=" * 70)
print("  EVALUATION REPORT: 10 BAD SIMULATIONS")
print("=" * 70)

files = sorted(glob.glob("results_bad_*.csv"))
if not files:
    print("No result files found! Check test_bad_logs/")
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

print(f"Total Sims Completed: {len(df)} / 10")
print(f"Points meeting 48-52 Ohm spec: {df['spec_pass'].sum()} / {len(df)} ({df['spec_pass'].mean()*100:.1f}%)\n")

print(f"{'Corner':<8} {'Vreg':<6} {'Temp':<6} {'PVTP':<6} {'PVTN':<6} {'Sim_Pup':<9} {'Excel_Pup':<10} {'Sim_Pdn':<9} {'Excel_Pdn':<10} {'Spec':<6}")
print("-" * 88)
for _, r in df.iterrows():
    c = str(r['corner'])
    v = float(r['vreg'])
    t = float(r['temp'])
    p = int(r['pvtp_sim'])
    n = int(r['pvtn_sim'])
    spup = float(r['sim_pup'])
    epup = float(r['excel_pup'])
    spdn = float(r['sim_pdn'])
    epdn = float(r['excel_pdn'])
    status = "PASS" if r['spec_pass'] else "FAIL"
    print(f"{c:<8} {v:<6.2f} {t:<6.1f} {p:<6} {n:<6} {spup:<9.3f} {epup:<10.3f} {spdn:<9.3f} {epdn:<10.3f} {status:<6}")

print("=" * 70)
