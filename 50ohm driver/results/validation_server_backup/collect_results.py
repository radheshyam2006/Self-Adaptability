#!/usr/bin/env python3
"""
Collect all per-row Spectre results into a single CSV with resistance values.
Run after run_all_corners.sh completes for all corners.
"""
import csv, os, glob

RESULTS_DIR = "results"
PREDICTIONS = "all_predictions.csv"
OUTPUT = "final_results.csv"

# Read predictions
with open(PREDICTIONS, 'r') as f:
    preds = list(csv.DictReader(f))

# Read all results
res_map = {}
for corner in ['FF', 'SS', 'TT', 'FS', 'SF']:
    combined = f"{RESULTS_DIR}/{corner}_combined.csv"
    if os.path.exists(combined):
        with open(combined, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                res_map[row['row_name']] = row

# Merge
with open(OUTPUT, 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow([
        'row_idx', 'corner', 'vreg', 'temperature', 'pmon_cmos_res',
        'pvtp_true', 'pvtn_true', 'pvtp_pred', 'pvtn_pred',
        'pvtp_match', 'pvtn_match',
        'cadence_pull_up_res', 'cadence_pull_dn_res',
        'pull_up_error_pct', 'pull_dn_error_pct'
    ])
    
    found = 0
    for idx, pred in enumerate(preds):
        corner = pred['corner_label']
        row_name = f"{corner}_row{idx:05d}"
        
        if row_name in res_map:
            r = res_map[row_name]
            try:
                pup = float(r['pull_up_res'])
                pdn = float(r['pull_dn_res'])
                pup_err = abs(pup - 50.0) / 50.0 * 100
                pdn_err = abs(pdn - 50.0) / 50.0 * 100
            except:
                pup = pdn = pup_err = pdn_err = 'FAIL'
            found += 1
        else:
            pup = pdn = pup_err = pdn_err = 'PENDING'
        
        writer.writerow([
            idx, corner, pred['vreg'], pred['temperature'], pred['pmon_cmos_res'],
            pred['pvtp_int_true'], pred['pvtn_int_true'],
            pred['pvtp_int_pred'], pred['pvtn_int_pred'],
            pred['pvtp_match'], pred['pvtn_match'],
            pup, pdn, pup_err, pdn_err
        ])

print(f"Merged {found}/{len(preds)} rows with Cadence results")
print(f"Output: {OUTPUT}")
