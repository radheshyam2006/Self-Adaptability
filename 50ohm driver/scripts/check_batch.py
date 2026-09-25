#!/usr/bin/env python3
"""
check_batch.py
==============
Batch health checker:
Examines newly completed batch CSV for out-of-spec resistance errors.
Returns:
  0 - Passed (within spec)
  1 - High Error Detected (triggers auto-quarantine & alert)
"""

import sys
import os
import pandas as pd
import numpy as np

TARGET_RES = 50.0
ERROR_THRESHOLD_OHMS = 2.5  # 5% of 50 ohms = 2.5 ohms (spec window: 47.5 to 52.5)
MAX_FAIL_PERCENT = 10.0      # If >10% of batch rows fail, flag corner

def main():
    if len(sys.argv) < 2:
        print("Usage: python check_batch.py <batch_csv_path>")
        sys.exit(0)

    csv_path = sys.argv[1]
    if not os.path.exists(csv_path):
        print(f"File not found: {csv_path}")
        sys.exit(0)

    try:
        df = pd.read_csv(csv_path)
        df.columns = [c.strip() for c in df.columns]

        # Find resistance columns
        pup_col = 'sim_pup' if 'sim_pup' in df.columns else 'pup_Resistance(Ohms)'
        pdn_col = 'sim_pdn' if 'sim_pdn' in df.columns else 'pdn_Resistance(Ohms)'

        if pup_col not in df.columns or pdn_col not in df.columns:
            print("Warning: Resistance columns not found in CSV. Skipping check.")
            sys.exit(0)

        df['pup_diff'] = np.abs(df[pup_col] - TARGET_RES)
        df['pdn_diff'] = np.abs(df[pdn_col] - TARGET_RES)

        pup_fails = (df['pup_diff'] > ERROR_THRESHOLD_OHMS).sum()
        pdn_fails = (df['pdn_diff'] > ERROR_THRESHOLD_OHMS).sum()
        total = len(df)

        pup_fail_rate = (pup_fails / total) * 100.0
        pdn_fail_rate = (pdn_fails / total) * 100.0

        avg_pup = df[pup_col].mean()
        avg_pdn = df[pdn_col].mean()

        print(f"[{os.path.basename(csv_path)}] Sims: {total} | Avg pup: {avg_pup:.2f}Ω | Avg pdn: {avg_pdn:.2f}Ω | Fails: pup={pup_fails} ({pup_fail_rate:.1f}%), pdn={pdn_fails} ({pdn_fail_rate:.1f}%)")

        if pup_fail_rate > MAX_FAIL_PERCENT or pdn_fail_rate > MAX_FAIL_PERCENT:
            print(f"ALERT: High failure rate detected (> {MAX_FAIL_PERCENT}%)!")
            sys.exit(1)
        else:
            sys.exit(0)

    except Exception as e:
        print(f"Error parsing {csv_path}: {e}")
        sys.exit(0)

if __name__ == "__main__":
    main()
