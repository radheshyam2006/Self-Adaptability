#!/usr/bin/env python3
"""
build_validation_excel.py
==========================
Generates a comprehensive, professional Excel workbook and CSV suite containing:
1. PVT Conditions (Corner, Voltage, Temp, Ring Osc Freq/PMON, Uncalibrated Res)
2. Ground Truth (Golden Trim bits/ints, Golden Res ~50 Ohms)
3. ML Predicted Trim (Predicted Trim bits/ints from Decision Tree model, Trim errors)
4. Empty Spectre Post-Simulation columns with live Excel formulas:
   - Simulated Pup (Ohm)
   - Simulated Pdn (Ohm)
   - Pup Delta vs 50 Ohm
   - Pdn Delta vs 50 Ohm
   - Pup Error %
   - Pdn Error %
   - 48-52 Ohm Spec Compliance ('PASS' / 'FAIL' / 'PENDING')
5. Separate sheets for each corner: TT, FF, SS, FS, SF
6. Summary Dashboard with metrics, statistics, and simulation trackers
7. Dedicated sheet for the 3,177 Held-Out Test Set points
"""

import os
import sys
import pickle
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
EXCEL_SRC = os.path.join(PROJECT_DIR, "data", "TSMC28nm_DRV_ML_MAR6_LookUP_Table_Mar20_ML Predictions.xlsx")
MODEL_P_PATH = os.path.join(PROJECT_DIR, "ASIC_Submission", "model_pvtp.pkl")
MODEL_N_PATH = os.path.join(PROJECT_DIR, "ASIC_Submission", "model_pvtn.pkl")

OUTPUT_EXCEL = os.path.join(PROJECT_DIR, "results", "TSMC28nm_Self_Adaptive_Driver_Validation_Master.xlsx")
OUTPUT_CSV_DIR = os.path.join(PROJECT_DIR, "results", "validation_sheets")
os.makedirs(OUTPUT_CSV_DIR, exist_ok=True)
os.makedirs(os.path.dirname(OUTPUT_EXCEL), exist_ok=True)

CORNER_SHEETS = {
    'TT': 'TT_vdd_test',
    'FF': 'FF_vdd_temp',
    'SS': 'SS_vdd_test',
    'FS': 'FS_vdd_test',
    'SF': 'SF_vdd_test'
}

def pad8(val):
    if pd.isna(val) or str(val).strip().lower() in ['na', 'nan']:
        return None
    return str(val).replace('-', '').strip().zfill(8)

def to_int(val):
    if val is None:
        return None
    try:
        return int(val, 2)
    except:
        return None

def clean_float(val):
    if pd.isna(val) or str(val).strip().lower() in ['na', 'nan']:
        return np.nan
    try:
        return abs(float(val))
    except:
        return np.nan

def load_and_predict():
    print("=" * 70)
    print("  BUILDING VALIDATION MASTER DATASET WITH ML PREDICTIONS")
    print("=" * 70)

    # 1. Load ML models
    print("[1/4] Loading trained Decision Tree models...")
    with open(MODEL_P_PATH, 'rb') as f:
        model_p = pickle.load(f)
    with open(MODEL_N_PATH, 'rb') as f:
        model_n = pickle.load(f)
    print("      Loaded model_pvtp.pkl and model_pvtn.pkl successfully.")

    # 2. Parse Excel sheets
    print("[2/4] Reading data from source lookup table...")
    xl = pd.ExcelFile(EXCEL_SRC)
    all_rows = []

    for corner, sheet_name in CORNER_SHEETS.items():
        df = xl.parse(sheet_name)
        p_col = 'ML data up driver\npvtp<7:0>' if 'ML data up driver\npvtp<7:0>' in df.columns else 'ML data up driver\npvtp<5:0>'
        n_col = 'ML data DN driver\npvtn<7:0>' if 'ML data DN driver\npvtn<7:0>' in df.columns else 'ML data DN driver\npvtn<5:0>'
        golden_pup_col = 'PULL_UP_RES\nnew value' if 'PULL_UP_RES\nnew value' in df.columns else 'PULL_UP_RES_new'
        golden_pdn_col = 'PULL_DN_RES\nnew value' if 'PULL_DN_RES\nnew value' in df.columns else 'PULL_DN_RES_new'

        for idx, row in df.iterrows():
            pvtp_bits = pad8(row[p_col])
            pvtn_bits = pad8(row[n_col])
            if pvtp_bits is None or pvtn_bits is None:
                continue

            pvtp_int = to_int(pvtp_bits)
            pvtn_int = to_int(pvtn_bits)
            if pvtp_int is None or pvtn_int is None:
                continue

            try:
                vreg = float(row['vreg'])
                temp = float(row['temperature'])
                pmon = float(row['pmon_cmos_res'])
            except:
                continue

            init_pup = clean_float(row.get('PULL_UP_RES', np.nan))
            init_pdn = clean_float(row.get('PULL_DN_RES', np.nan))
            target_pup = clean_float(row.get(golden_pup_col, np.nan))
            target_pdn = clean_float(row.get(golden_pdn_col, np.nan))

            all_rows.append({
                'Corner': corner,
                'Voltage_V': vreg,
                'Temp_C': temp,
                'Ring_Osc_Freq_PMON_Hz': int(round(pmon)),
                'Initial_Pup_Raw_Ohm': round(init_pup, 2) if not pd.isna(init_pup) else np.nan,
                'Initial_Pdn_Raw_Ohm': round(init_pdn, 2) if not pd.isna(init_pdn) else np.nan,
                'Ground_Truth_PVTP_Int': pvtp_int,
                'Ground_Truth_PVTP_Bits': pvtp_bits,
                'Ground_Truth_PVTN_Int': pvtn_int,
                'Ground_Truth_PVTN_Bits': pvtn_bits,
                'Ground_Truth_Target_Pup_Ohm': round(target_pup, 3) if not pd.isna(target_pup) else np.nan,
                'Ground_Truth_Target_Pdn_Ohm': round(target_pdn, 3) if not pd.isna(target_pdn) else np.nan,
            })

    full_df = pd.DataFrame(all_rows)
    print(f"      Loaded {len(full_df)} valid PVT conditions across 5 corners.")

    # 3. Model Predictions (Hardware Quantization)
    print("[3/4] Running ML model inference for all rows...")
    X_quant = np.column_stack([
        full_df['Ring_Osc_Freq_PMON_Hz'].values.astype(float),
        np.round((full_df['Voltage_V'].values - 0.80) * 100),
        np.round((full_df['Temp_C'].values + 40.0) * 4)
    ])

    pred_p = model_p.predict(X_quant).astype(int)
    pred_n = model_n.predict(X_quant).astype(int)

    full_df['ML_Predicted_PVTP_Int'] = pred_p
    full_df['ML_Predicted_PVTP_Bits'] = [format(val, '08b') for val in pred_p]
    full_df['ML_Predicted_PVTN_Int'] = pred_n
    full_df['ML_Predicted_PVTN_Bits'] = [format(val, '08b') for val in pred_n]

    full_df['PVTP_Trim_Error_LSB'] = np.abs(pred_p - full_df['Ground_Truth_PVTP_Int'].values)
    full_df['PVTN_Trim_Error_LSB'] = np.abs(pred_n - full_df['Ground_Truth_PVTN_Int'].values)

    def get_match_status(row):
        err_p = row['PVTP_Trim_Error_LSB']
        err_n = row['PVTN_Trim_Error_LSB']
        if err_p == 0 and err_n == 0:
            return "Exact Match"
        elif err_p <= 1 and err_n <= 1:
            return "Within ±1 LSB"
        else:
            return f"Off by P:{err_p} N:{err_n}"

    full_df['Trim_Match_Status'] = full_df.apply(get_match_status, axis=1)

    # 4. Stratified 80/20 train/test split
    corners = full_df['Corner'].values
    indices = np.arange(len(full_df))
    _, test_idx = train_test_split(indices, test_size=0.2, random_state=42, stratify=corners)

    is_test = np.zeros(len(full_df), dtype=bool)
    is_test[test_idx] = True
    full_df['Dataset_Partition'] = np.where(is_test, 'Validation_TestSet', 'TrainingSet')

    # Add empty columns for Spectre simulation
    full_df['Simulated_Pup_Ohm'] = ""
    full_df['Simulated_Pdn_Ohm'] = ""

    print(f"      Validation Test Set (to simulate): {sum(is_test)} points")
    print(f"      Training Set: {len(full_df) - sum(is_test)} points")

    return full_df


def create_excel_workbook(df):
    print("[4/4] Generating formatted Excel workbook with formulas & styles...")
    wb = openpyxl.Workbook()
    # Remove default sheet
    wb.remove(wb.active)

    # -------------------------------------------------------------
    # STYLES DEFINITION
    # -------------------------------------------------------------
    font_title = Font(name="Segoe UI", size=14, bold=True, color="FFFFFF")
    font_sub = Font(name="Segoe UI", size=10, italic=True, color="FFFFFF")
    font_header = Font(name="Segoe UI", size=10, bold=True, color="FFFFFF")
    font_data = Font(name="Segoe UI", size=9)
    font_bold = Font(name="Segoe UI", size=9, bold=True)
    
    fill_navy = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
    fill_blue_header = PatternFill(start_color="2F5597", end_color="2F5597", fill_type="solid")
    fill_green_header = PatternFill(start_color="385723", end_color="385723", fill_type="solid")
    fill_purple_header = PatternFill(start_color="5B2C6F", end_color="5B2C6F", fill_type="solid")
    fill_orange_header = PatternFill(start_color="B9770E", end_color="B9770E", fill_type="solid")
    fill_sim_header = PatternFill(start_color="884EA0", end_color="884EA0", fill_type="solid")
    fill_zebra = PatternFill(start_color="F2F4F4", end_color="F2F4F4", fill_type="solid")

    thin_border = Border(
        left=Side(style='thin', color='D4D4D4'),
        right=Side(style='thin', color='D4D4D4'),
        top=Side(style='thin', color='D4D4D4'),
        bottom=Side(style='thin', color='D4D4D4')
    )

    align_center = Alignment(horizontal="center", vertical="center")
    align_right = Alignment(horizontal="right", vertical="center")
    align_left = Alignment(horizontal="left", vertical="center")

    # -------------------------------------------------------------
    # SHEET 1: SUMMARY DASHBOARD
    # -------------------------------------------------------------
    ws_dash = wb.create_sheet("Summary_Dashboard")
    ws_dash.views.sheetView[0].showGridLines = True

    ws_dash.merge_cells("A1:G2")
    ws_dash["A1"] = "AI SELF-ADAPTIVE CHIP VALIDATION MASTER DASHBOARD"
    ws_dash["A1"].font = font_title
    ws_dash["A1"].fill = fill_navy
    ws_dash["A1"].alignment = align_center

    ws_dash.merge_cells("A3:G3")
    ws_dash["A3"] = "TSMC 28nm HPC+ 50-Ohm Driver: Machine Learning Adaptive Trim vs Cadence Spectre Ground Truth"
    ws_dash["A3"].font = font_sub
    ws_dash["A3"].fill = fill_blue_header
    ws_dash["A3"].alignment = align_center

    # Statistics Table
    headers_dash = ["PVT Corner", "Total PVT Points", "Held-Out Test Points", "Vreg Range (V)", "Temp Range (°C)", "ML Exact Match %", "Target Impedance Spec"]
    ws_dash.append([])
    ws_dash.append(headers_dash)
    for col_num in range(1, 8):
        cell = ws_dash.cell(row=5, column=col_num)
        cell.font = font_header
        cell.fill = fill_blue_header
        cell.alignment = align_center

    row_idx = 6
    for corner in ['TT', 'FF', 'SS', 'FS', 'SF']:
        c_df = df[df['Corner'] == corner]
        n_total = len(c_df)
        n_test = (c_df['Dataset_Partition'] == 'Validation_TestSet').sum()
        v_min, v_max = c_df['Voltage_V'].min(), c_df['Voltage_V'].max()
        t_min, t_max = c_df['Temp_C'].min(), c_df['Temp_C'].max()
        exact_pct = (c_df['Trim_Match_Status'] == 'Exact Match').mean() * 100

        ws_dash.append([
            f"{corner} Corner",
            n_total,
            n_test,
            f"{v_min:.2f} - {v_max:.2f} V",
            f"{t_min:.0f} to {t_max:.0f} °C",
            f"{exact_pct:.2f}%",
            "50.0 Ω ± 4% (48 - 52 Ω)"
        ])
        for col_num in range(1, 8):
            c_cell = ws_dash.cell(row=row_idx, column=col_num)
            c_cell.font = font_data
            c_cell.alignment = align_center
            c_cell.border = thin_border
            if row_idx % 2 == 1:
                c_cell.fill = fill_zebra
        row_idx += 1

    # Total Row
    total_all = len(df)
    total_test = (df['Dataset_Partition'] == 'Validation_TestSet').sum()
    total_exact = (df['Trim_Match_Status'] == 'Exact Match').mean() * 100
    ws_dash.append([
        "TOTAL (All Corners)",
        total_all,
        total_test,
        f"{df['Voltage_V'].min():.2f} - {df['Voltage_V'].max():.2f} V",
        f"{df['Temp_C'].min():.0f} to {df['Temp_C'].max():.0f} °C",
        f"{total_exact:.2f}%",
        "50.0 Ω ± 4% (48 - 52 Ω)"
    ])
    for col_num in range(1, 8):
        c_cell = ws_dash.cell(row=row_idx, column=col_num)
        c_cell.font = font_bold
        c_cell.alignment = align_center
        c_cell.border = thin_border
        c_cell.fill = fill_zebra

    # Add Simulation Status Box
    ws_dash.append([])
    ws_dash.append([])
    sim_box_row = row_idx + 3
    ws_dash.merge_cells(f"A{sim_box_row}:D{sim_box_row}")
    ws_dash[f"A{sim_box_row}"] = "SPECTRE POST-SIMULATION VERIFICATION TRACKER"
    ws_dash[f"A{sim_box_row}"].font = font_header
    ws_dash[f"A{sim_box_row}"].fill = fill_purple_header
    ws_dash[f"A{sim_box_row}"].alignment = align_center

    tracker_items = [
        ("Total Held-Out Validation Simulations Required", total_test),
        ("Simulations Completed in Spectre", '=COUNT(HeldOut_TestSet_3177!T3:T3179)'),
        ("Total Points Meeting 48 - 52 Ω Spec", '=COUNTIF(HeldOut_TestSet_3177!Z3:Z3179, "PASS")'),
        ("Total Points Failing 48 - 52 Ω Spec", '=COUNTIF(HeldOut_TestSet_3177!Z3:Z3179, "FAIL")'),
        ("Post-Calibration Spec Yield (%)", '=IF(B16>0, ROUND(B17/B16*100, 2), "Pending Sim")')
    ]
    for idx, (label, formula_or_val) in enumerate(tracker_items):
        r = sim_box_row + 1 + idx
        ws_dash.merge_cells(f"A{r}:C{r}")
        ws_dash[f"A{r}"] = label
        ws_dash[f"A{r}"].font = font_data
        ws_dash[f"A{r}"].border = thin_border
        ws_dash[f"D{r}"] = formula_or_val
        ws_dash[f"D{r}"].font = font_bold
        ws_dash[f"D{r}"].alignment = align_center
        ws_dash[f"D{r}"].border = thin_border

    # -------------------------------------------------------------
    # COLUMNS CONFIGURATION FOR DATA SHEETS
    # -------------------------------------------------------------
    columns = [
        ("Sim_ID", 8, fill_blue_header),
        ("Corner", 8, fill_blue_header),
        ("Voltage_V", 11, fill_blue_header),
        ("Temp_C", 9, fill_blue_header),
        ("Ring_Freq_PMON_Hz", 19, fill_blue_header),
        ("Raw_Pup_Ohm", 13, fill_blue_header),
        ("Raw_Pdn_Ohm", 13, fill_blue_header),
        ("GT_PVTP_Int", 12, fill_green_header),
        ("GT_PVTP_Bits", 13, fill_green_header),
        ("GT_PVTN_Int", 12, fill_green_header),
        ("GT_PVTN_Bits", 13, fill_green_header),
        ("Target_Pup_Ohm", 15, fill_green_header),
        ("Target_Pdn_Ohm", 15, fill_green_header),
        ("ML_PVTP_Int", 12, fill_orange_header),
        ("ML_PVTP_Bits", 13, fill_orange_header),
        ("ML_PVTN_Int", 12, fill_orange_header),
        ("ML_PVTN_Bits", 13, fill_orange_header),
        ("Err_PVTP_LSB", 13, fill_orange_header),
        ("Err_PVTN_LSB", 13, fill_orange_header),
        ("Simulated_Pup_Ohm", 18, fill_sim_header),
        ("Simulated_Pdn_Ohm", 18, fill_sim_header),
        ("Pup_Delta_50", 14, fill_sim_header),
        ("Pdn_Delta_50", 14, fill_sim_header),
        ("Pup_Error_Pct", 14, fill_sim_header),
        ("Pdn_Error_Pct", 14, fill_sim_header),
        ("Spec_Compliance", 16, fill_sim_header),
        ("Dataset_Partition", 18, fill_navy)
    ]

    def populate_sheet(ws, sub_df):
        ws.views.sheetView[0].showGridLines = True
        
        # Header Row
        header_row = [col[0] for col in columns]
        ws.append(header_row)
        for col_idx, (_, width, fill_color) in enumerate(columns, 1):
            cell = ws.cell(row=1, column=col_idx)
            cell.font = font_header
            cell.fill = fill_color
            cell.alignment = align_center
            col_letter = get_column_letter(col_idx)
            ws.column_dimensions[col_letter].width = width

        # Data Rows
        for r_idx, (_, row) in enumerate(sub_df.iterrows(), 2):
            # Excel row index is r_idx
            # Simulated_Pup_Ohm is Column T (20)
            # Simulated_Pdn_Ohm is Column U (21)
            pup_cell = f"T{r_idx}"
            pdn_cell = f"U{r_idx}"

            pup_delta_formula = f'=IF(ISBLANK({pup_cell}), "", ROUND({pup_cell}-50.0, 3))'
            pdn_delta_formula = f'=IF(ISBLANK({pdn_cell}), "", ROUND({pdn_cell}-50.0, 3))'
            pup_err_formula = f'=IF(ISBLANK({pup_cell}), "", ROUND(ABS({pup_cell}-50.0)/50.0*100, 2))'
            pdn_err_formula = f'=IF(ISBLANK({pdn_cell}), "", ROUND(ABS({pdn_cell}-50.0)/50.0*100, 2))'
            spec_formula = f'=IF(OR(ISBLANK({pup_cell}), ISBLANK({pdn_cell})), "PENDING", IF(AND({pup_cell}>=48.0, {pup_cell}<=52.0, {pdn_cell}>=48.0, {pdn_cell}<=52.0), "PASS", "FAIL"))'

            row_values = [
                r_idx - 1,
                row['Corner'],
                row['Voltage_V'],
                row['Temp_C'],
                row['Ring_Osc_Freq_PMON_Hz'],
                row['Initial_Pup_Raw_Ohm'],
                row['Initial_Pdn_Raw_Ohm'],
                row['Ground_Truth_PVTP_Int'],
                row['Ground_Truth_PVTP_Bits'],
                row['Ground_Truth_PVTN_Int'],
                row['Ground_Truth_PVTN_Bits'],
                row['Ground_Truth_Target_Pup_Ohm'],
                row['Ground_Truth_Target_Pdn_Ohm'],
                row['ML_Predicted_PVTP_Int'],
                row['ML_Predicted_PVTP_Bits'],
                row['ML_Predicted_PVTN_Int'],
                row['ML_Predicted_PVTN_Bits'],
                row['PVTP_Trim_Error_LSB'],
                row['PVTN_Trim_Error_LSB'],
                "",  # Simulated_Pup_Ohm (User/Script fills)
                "",  # Simulated_Pdn_Ohm (User/Script fills)
                pup_delta_formula,
                pdn_delta_formula,
                pup_err_formula,
                pdn_err_formula,
                spec_formula,
                row['Dataset_Partition']
            ]
            ws.append(row_values)

            # Cell formatting
            for c_idx in range(1, len(columns) + 1):
                cell = ws.cell(row=r_idx, column=c_idx)
                cell.font = font_data
                cell.border = thin_border
                cell.alignment = align_center
                if r_idx % 2 == 1:
                    cell.fill = fill_zebra

    # Generate sheets for each corner
    for corner in ['TT', 'FF', 'SS', 'FS', 'SF']:
        print(f"      Writing sheet: {corner}_Corner...")
        ws_corner = wb.create_sheet(f"{corner}_Corner")
        c_df = df[df['Corner'] == corner].reset_index(drop=True)
        populate_sheet(ws_corner, c_df)

        # Export CSV for this corner
        csv_path = os.path.join(OUTPUT_CSV_DIR, f"{corner}_validation.csv")
        c_df.to_csv(csv_path, index=False)

    # Dedicated Test Set Sheet (3,177 points across corners)
    print("      Writing sheet: HeldOut_TestSet_3177...")
    ws_test = wb.create_sheet("HeldOut_TestSet_3177")
    test_df = df[df['Dataset_Partition'] == 'Validation_TestSet'].reset_index(drop=True)
    populate_sheet(ws_test, test_df)

    # Export CSV for held-out test set
    test_csv_path = os.path.join(OUTPUT_CSV_DIR, "HeldOut_TestSet_3177.csv")
    test_df.to_csv(test_csv_path, index=False)

    # Adjust dashboard column widths
    for col in ws_dash.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws_dash.column_dimensions[col_letter].width = max(max_len + 4, 14)

    # Save Workbook
    print(f"      Saving Excel file to: {OUTPUT_EXCEL}")
    wb.save(OUTPUT_EXCEL)
    print(f"\nSUCCESS! Master Excel generated: {OUTPUT_EXCEL}")
    print(f"Individual CSVs saved to: {OUTPUT_CSV_DIR}")


if __name__ == '__main__':
    df = load_and_predict()
    create_excel_workbook(df)
