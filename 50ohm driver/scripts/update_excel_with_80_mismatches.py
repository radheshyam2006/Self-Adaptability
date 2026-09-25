#!/usr/bin/env python3
"""
update_excel_with_80_mismatches.py
===================================
Parses results_all_80_mismatches.csv (or results_job*.csv) from test_suite_mismatches_80_fast
and populates the Spectre simulation results into:
1. Master Excel: TSMC28nm_Self_Adaptive_Driver_Validation_Master_v3.xlsx
   - Updates Validation_Bad_Cases_99 (filling TT: 38, FF: 21, SS: 21)
   - Updates TT_Corner, FF_Corner, SS_Corner sheets
   - Updates Summary_Dashboard tracker
2. Prints complete statistical analysis:
   - How many of the 80 model mismatches still meet the 48-52 Ohm spec!
"""

import os
import glob
import pandas as pd
import openpyxl

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
EXCEL_PATH = os.path.join(PROJECT_DIR, "results", "TSMC28nm_Self_Adaptive_Driver_Validation_Master_v3.xlsx")
FAST_DIR = os.path.join(PROJECT_DIR, "validation_generated", "test_suite_mismatches_80_fast")
CSV_PATH = os.path.join(FAST_DIR, "results_all_80_mismatches.csv")

def run_update():
    print("=" * 80)
    print("  ANALYZING 80 MISMATCH SIMULATION RESULTS & UPDATING MASTER EXCEL")
    print("=" * 80)

    # 1. Load CSV results
    if not os.path.exists(CSV_PATH):
        # Look for any matching CSVs in FAST_DIR
        alt_csvs = glob.glob(os.path.join(FAST_DIR, "results_*.csv"))
        if alt_csvs:
            df_sim = pd.concat([pd.read_csv(f) for f in alt_csvs], ignore_index=True)
        else:
            print(f"Error: {CSV_PATH} not found!")
            print("Please run the SCP command to download results_all_80_mismatches.csv first.")
            return
    else:
        df_sim = pd.read_csv(CSV_PATH)

    print(f"Loaded {len(df_sim)} simulation records from {os.path.basename(CSV_PATH)}")

    # Clean data
    df_sim['sim_pup'] = df_sim['sim_pup'].astype(float).abs()
    df_sim['sim_pdn'] = df_sim['sim_pdn'].astype(float).abs()

    # Spec check (48.0 to 52.0 Ohm)
    df_sim['pup_pass'] = (df_sim['sim_pup'] >= 48.0) & (df_sim['sim_pup'] <= 52.0)
    df_sim['pdn_pass'] = (df_sim['sim_pdn'] >= 48.0) & (df_sim['sim_pdn'] <= 52.0)
    df_sim['spec_pass'] = df_sim['pup_pass'] & df_sim['pdn_pass']

    n_tot = len(df_sim)
    n_pass = df_sim['spec_pass'].sum()
    pct_pass = (n_pass / n_tot) * 100

    print("\n" + "=" * 60)
    print(f"  OVERALL 80 MISMATCH COMPLIANCE RESULTS")
    print("=" * 60)
    print(f"Total Model Mismatch Points Simulated: {n_tot} / 80")
    print(f"Points MEETING 48-52 Ohm Spec with ML Predicted Trim: {n_pass} / {n_tot} ({pct_pass:.2f}%)")
    print(f"Points Failing Spec: {n_tot - n_pass} / {n_tot} ({100 - pct_pass:.2f}%)")

    print("\n--- Per-Corner Breakdown ---")
    for corner in ['TT', 'FF', 'SS']:
        c_df = df_sim[df_sim['corner'] == corner]
        c_tot = len(c_df)
        c_pass = c_df['spec_pass'].sum()
        c_pct = (c_pass / c_tot) * 100 if c_tot > 0 else 0
        avg_pup = c_df['sim_pup'].mean() if c_tot > 0 else 0
        avg_pdn = c_df['sim_pdn'].mean() if c_tot > 0 else 0
        print(f"  {corner} Corner: {c_pass}/{c_tot} PASS ({c_pct:.1f}%) | Avg Pup={avg_pup:.2f} Ohm, Avg Pdn={avg_pdn:.2f} Ohm")

    # 2. Update Excel Workbook
    print(f"\nLoading Master Excel: {os.path.basename(EXCEL_PATH)}...")
    wb = openpyxl.load_workbook(EXCEL_PATH)

    # Build lookup map: (corner, round(vreg, 3), round(temp, 1)) -> (sim_pup, sim_pdn)
    sim_map = {}
    for _, row in df_sim.iterrows():
        c = str(row['corner']).strip()
        v = round(float(row['vreg']), 3)
        t = round(float(row['temp']), 1)
        sim_map[(c, v, t)] = (round(float(row['sim_pup']), 3), round(float(row['sim_pdn']), 3))

    # Update Validation_Bad_Cases_99
    ws_bad = wb['Validation_Bad_Cases_99']
    bad_updated = 0
    for r in range(2, 101):
        c_val = ws_bad.cell(row=r, column=2).value
        v_val = ws_bad.cell(row=r, column=3).value
        t_val = ws_bad.cell(row=r, column=4).value
        if c_val and v_val is not None and t_val is not None:
            try:
                v_f = round(float(v_val), 3)
                t_f = round(float(t_val), 1)
                key = (str(c_val).strip(), v_f, t_f)
                if key in sim_map:
                    pup, pdn = sim_map[key]
                    ws_bad.cell(row=r, column=20, value=pup) # Col T: Simulated_Pup_Ohm
                    ws_bad.cell(row=r, column=21, value=pdn) # Col U: Simulated_Pdn_Ohm
                    bad_updated += 1
            except (ValueError, TypeError):
                continue

    print(f"Updated {bad_updated} mismatch rows in sheet 'Validation_Bad_Cases_99'!")

    # Update Corner sheets
    for corner in ['TT', 'FF', 'SS']:
        sheet_name = f"{corner}_Corner"
        if sheet_name in wb.sheetnames:
            ws_c = wb[sheet_name]
            c_up = 0
            for r in range(2, ws_c.max_row + 1):
                id_val = ws_c.cell(row=r, column=1).value
                if not isinstance(id_val, int):
                    continue
                v_val = ws_c.cell(row=r, column=3).value
                t_val = ws_c.cell(row=r, column=4).value
                if v_val is not None and t_val is not None:
                    try:
                        v_f = round(float(v_val), 3)
                        t_f = round(float(t_val), 1)
                        key = (corner, v_f, t_f)
                        if key in sim_map:
                            pup, pdn = sim_map[key]
                            ws_c.cell(row=r, column=20, value=pup)
                            ws_c.cell(row=r, column=21, value=pdn)
                            c_up += 1
                    except (ValueError, TypeError):
                        continue
            print(f"Updated {c_up} rows in sheet '{sheet_name}'")

    wb.save(EXCEL_PATH)
    print(f"\nSUCCESS! Master workbook updated and saved to: {EXCEL_PATH}")

if __name__ == '__main__':
    run_update()
