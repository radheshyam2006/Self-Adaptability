#!/usr/bin/env python3
import glob
import pandas as pd
import numpy as np

print("=" * 95)
print("   EVALUATION REPORT: 80 WORKING CORNER MISMATCH SIMULATIONS (TT, FF, SS)")
print("   Testing ML Predicted Trim Bits vs 48 - 52 Ohm Specification")
print("=" * 95)

files = sorted(glob.glob("results_job*.csv"))
if not files:
    print("No result CSVs found! Check logs_mismatches/")
    exit()

all_dfs = []
for f in files:
    try:
        d = pd.read_csv(f)
        if len(d) > 0 and 'sim_pup' in d.columns:
            all_dfs.append(d)
    except: pass

if not all_dfs:
    print("No valid simulation data found in CSVs!")
    exit()

df = pd.concat(all_dfs, ignore_index=True)
df['sim_pup'] = df['sim_pup'].abs()
df['sim_pdn'] = df['sim_pdn'].abs()

df['pup_in_spec'] = (df['sim_pup'] >= 48.0) & (df['sim_pup'] <= 52.0)
df['pdn_in_spec'] = (df['sim_pdn'] >= 48.0) & (df['sim_pdn'] <= 52.0)
df['spec_pass'] = df['pup_in_spec'] & df['pdn_in_spec']

df['err_pup_vs_gt'] = (df['sim_pup'] - df['gt_pup']).abs()
df['err_pdn_vs_gt'] = (df['sim_pdn'] - df['gt_pdn']).abs()

n_tot = len(df)
n_pass = df['spec_pass'].sum()
pass_pct = (n_pass / n_tot) * 100

print(f"Total Mismatch Simulations: {n_tot} / 80")
print(f"Points PASSING 48-52 Ohm Spec with ML Predicted Trim: {n_pass} / {n_tot} ({pass_pct:.1f}%)")
print(f"Average Error vs Ground Truth: Pup={df['err_pup_vs_gt'].mean():.2f} Ohm, Pdn={df['err_pdn_vs_gt'].mean():.2f} Ohm\n")

print(f"{'Test_ID':<9} {'Corner':<6} {'Vreg':<6} {'Temp':<6} {'ML_Trim':<10} {'GT_Trim':<10} {'Err_LSB':<9} {'Sim_Pup':<9} {'Sim_Pdn':<9} {'Spec_Pass':<9}")
print("-" * 95)
for _, r in df.sort_values(by=['corner', 'test_id']).iterrows():
    tid = str(r['test_id'])
    c = str(r['corner'])
    v = float(r['vreg'])
    t = float(r['temp'])
    ml_t = f"({int(r['ml_pvtp'])},{int(r['ml_pvtn'])})"
    gt_t = f"({int(r['gt_pvtp'])},{int(r['gt_pvtn'])})"
    err = f"(P:{int(r['err_p'])},N:{int(r['err_n'])})"
    spup = float(r['sim_pup'])
    spdn = float(r['sim_pdn'])
    status = "PASS" if r['spec_pass'] else "FAIL"
    print(f"{tid:<9} {c:<6} {v:<6.2f} {t:<6.1f} {ml_t:<10} {gt_t:<10} {err:<9} {spup:<9.2f} {spdn:<9.2f} {status:<9}")

print("=" * 95)
