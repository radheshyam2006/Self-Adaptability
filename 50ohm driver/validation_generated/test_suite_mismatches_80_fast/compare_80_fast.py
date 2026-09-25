#!/usr/bin/env python3
import os
import glob
import pandas as pd
import numpy as np

print("=" * 95)
print("   EVALUATION REPORT: 80 WORKING CORNER MISMATCHES (4 PARALLEL JOBS)")
print("   PDK Model: 1.8V | Verifying ML Predicted Trim Bits vs 48-52 Ohm Spec")
print("=" * 95)

csv_files = [
    "results_job1_TT_pt1.csv",
    "results_job2_TT_pt2.csv",
    "results_job3_FF.csv",
    "results_job4_SS.csv"
]

all_dfs = []
for f in csv_files:
    if os.path.exists(f):
        try:
            d = pd.read_csv(f)
            if len(d) > 0 and 'sim_pup' in d.columns:
                all_dfs.append(d)
        except: pass

if not all_dfs:
    # Also check if results_all_80_mismatches.csv exists
    if os.path.exists("results_all_80_mismatches.csv"):
        d = pd.read_csv("results_all_80_mismatches.csv")
        if len(d) > 0 and 'sim_pup' in d.columns:
            all_dfs.append(d)

if not all_dfs:
    print("No simulation result CSVs found! Check logs_parallel/")
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

print(f"Total Completed Simulations: {n_tot} / 80")
print(f"Points Meeting 48-52 Ohm Spec with ML Predicted Trim: {n_pass} / {n_tot} ({pass_pct:.1f}%)")
print(f"Average Delta vs Ground Truth: Pup={df['err_pup_vs_gt'].mean():.2f} Ohm, Pdn={df['err_pdn_vs_gt'].mean():.2f} Ohm\n")

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
