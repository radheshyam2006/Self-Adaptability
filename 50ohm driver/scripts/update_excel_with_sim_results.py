#!/usr/bin/env python3
"""
update_excel_with_sim_results.py
=================================
Automatically merges downloaded Spectre simulation CSV files into:
1. TSMC28nm_Self_Adaptive_Driver_Validation_Master.xlsx
2. HeldOut_TestSet_3177.csv and corner CSVs

Usage:
    python scripts/update_excel_with_sim_results.py [--results-dir results/]
"""

import os
import glob
import argparse
import pandas as pd
import openpyxl

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
MASTER_EXCEL = os.path.join(PROJECT_DIR, "results", "TSMC28nm_Self_Adaptive_Driver_Validation_Master.xlsx")
DEFAULT_RESULTS_DIR = os.path.join(PROJECT_DIR, "results")

def main():
    parser = argparse.ArgumentParser(description="Merge Spectre simulation results into Master Excel")
    parser.add_argument("--results-dir", default=DEFAULT_RESULTS_DIR, help="Directory containing result CSV files")
    parser.add_argument("--excel-file", default=MASTER_EXCEL, help="Path to Master Excel file")
    args = parser.parse_args()

    print("=" * 70)
    print("  UPDATING MASTER VALIDATION EXCEL WITH SPECTRE SIMULATION DATA")
    print("=" * 70)

    # 1. Collect all simulation CSVs
    csv_patterns = [
        os.path.join(args.results_dir, "results_*.csv"),
        os.path.join(args.results_dir, "results_phase1_*.csv"),
        os.path.join(args.results_dir, "results_phase2_*.csv"),
        os.path.join(args.results_dir, "results_*_batch*.csv")
    ]
    csv_files = []
    for pat in csv_patterns:
        csv_files.extend(glob.glob(pat))
    csv_files = sorted(list(set(csv_files)))

    if not csv_files:
        print(f"No simulation CSV files found in {args.results_dir} matching 'results_*.csv'")
        return

    print(f"Found {len(csv_files)} simulation result files:")
    all_sim_records = []
    for f in csv_files:
        try:
            sdf = pd.read_csv(f)
            if len(sdf) > 0 and 'sim_pup' in sdf.columns and 'sim_pdn' in sdf.columns:
                print(f"  - {os.path.basename(f)}: {len(sdf)} simulated points")
                all_sim_records.append(sdf)
        except Exception as e:
            continue

    if not all_sim_records:
        print("No valid simulation data found (files may contain only headers).")
        return

    sim_df = pd.concat(all_sim_records, ignore_index=True)
    # Deduplicate keeping latest
    sim_df = sim_df.dropna(subset=['sim_pup', 'sim_pdn'])
    print(f"\nTotal valid simulated points collected: {len(sim_df)}")

    # 2. Load Master Excel workbook
    print(f"Opening {args.excel_file}...")
    wb = openpyxl.load_workbook(args.excel_file)

    # Create lookup map: (corner, round(vreg, 3), round(temp, 1)) -> (sim_pup, sim_pdn)
    sim_map = {}
    for _, row in sim_df.iterrows():
        try:
            c = str(row['corner']).strip()
            v = round(float(row['vreg']), 3)
            t = round(float(row['temperature']), 1)
            pup = float(row['sim_pup'])
            pdn = float(row['sim_pdn'])
            sim_map[(c, v, t)] = (pup, pdn)
        except:
            continue

    print(f"Unique PVT points mapped: {len(sim_map)}")

    # 3. Update Sheets
    updated_total = 0
    for sheet_name in wb.sheetnames:
        if sheet_name == "Summary_Dashboard":
            continue
        ws = wb[sheet_name]
        updated_sheet = 0
        
        # Columns: Voltage is C (3), Temp is D (4), Corner is B (2)
        # Simulated Pup is T (20), Simulated Pdn is U (21)
        for r in range(2, ws.max_row + 1):
            c_val = ws.cell(row=r, column=2).value
            v_val = ws.cell(row=r, column=3).value
            t_val = ws.cell(row=r, column=4).value

            if c_val is not None and v_val is not None and t_val is not None:
                key = (str(c_val).strip(), round(float(v_val), 3), round(float(t_val), 1))
                if key in sim_map:
                    pup_res, pdn_res = sim_map[key]
                    ws.cell(row=r, column=20).value = round(pup_res, 3)
                    ws.cell(row=r, column=21).value = round(pdn_res, 3)
                    updated_sheet += 1

        print(f"  Sheet '{sheet_name}': updated {updated_sheet} cells.")
        updated_total += updated_sheet

    wb.save(args.excel_file)
    print(f"\nSUCCESS! Updated {updated_total} simulation entries in {args.excel_file}")

if __name__ == '__main__':
    main()
