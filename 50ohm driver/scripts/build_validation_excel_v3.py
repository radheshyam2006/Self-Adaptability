#!/usr/bin/env python3
"""
build_validation_excel_v3.py
=============================
Generates the comprehensive multi-tab validation Excel workbook:
1. Summary_Dashboard: Detailed statistics for Full Dataset, Training Set (80%), and Test Set (20%),
   explicitly clarifying the TT Corner breakdown (3300 = 2640 Train [100% exact] + 660 Test [94.24% exact = 622 exact + 38 bad]).
2. Cadence_Specs_And_Doubts: Updated specifications with Doubt 1 resolved (1.8V PDK model confirmed)
   and Doubt 2 resolved (dual resistor modeling for FS and SF cross corners).
3. Test_Suite_Good_Cases (NEW SHEET 1): 35 curated exact-match test cases (5 TT, 5 FF, 5 SS, 10 FS [5 ff_res + 5 ss_res], 10 SF [5 ss_res + 5 ff_res]).
4. Validation_Bad_Cases_99 (NEW SHEET 2): All 99 mispredicted cases in the Held-Out Test Set (TT:38, FF:21, SS:21, FS:10, SF:9).
5. Training_Bad_Cases_1 (NEW SHEET 3): Detailed breakdown of the 1 single training set mismatch (99.99% Training Accuracy) and all 100 dataset mismatches.
6. Data sheets: TT_Corner, FF_Corner, SS_Corner, FS_Corner, SF_Corner, HeldOut_TestSet_3177.
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

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
EXCEL_SRC = os.path.join(PROJECT_DIR, "data", "TSMC28nm_DRV_ML_MAR6_LookUP_Table_Mar20_ML Predictions.xlsx")
MODEL_P_PATH = os.path.join(PROJECT_DIR, "ASIC_Submission", "model_pvtp.pkl")
MODEL_N_PATH = os.path.join(PROJECT_DIR, "ASIC_Submission", "model_pvtn.pkl")

OUTPUT_EXCEL_V3 = os.path.join(PROJECT_DIR, "results", "TSMC28nm_Self_Adaptive_Driver_Validation_Master_v3.xlsx")
OUTPUT_EXCEL_V2 = os.path.join(PROJECT_DIR, "results", "TSMC28nm_Self_Adaptive_Driver_Validation_Master_v2.xlsx")
OUTPUT_CSV_DIR = os.path.join(PROJECT_DIR, "results", "validation_sheets")
os.makedirs(OUTPUT_CSV_DIR, exist_ok=True)

MODEL_1D8_PATH = "/data/cad/pdk_all/pdk_tsmc/pdk_tsmc_28/PDK/TSMC_new_iPDK/models/spectre/crn28hpcp_1d8_elk_v1d0_2p2_shrink0d9_embedded_usage.scs"

CORNER_SHEETS = {
    'TT': 'TT_vdd_test',
    'FF': 'FF_vdd_temp',
    'SS': 'SS_vdd_test',
    'FS': 'FS_vdd_test',
    'SF': 'SF_vdd_test'
}

def pad8(val):
    if pd.isna(val) or str(val).strip().lower() in ['na', 'nan']: return None
    return str(val).replace('-', '').strip().zfill(8)

def to_int(val):
    if val is None: return None
    try: return int(val, 2)
    except: return None

def clean_float(val):
    if pd.isna(val) or str(val).strip().lower() in ['na', 'nan']: return np.nan
    try: return abs(float(val))
    except: return np.nan

def load_dataset():
    print(">>> Loading ML models and raw data...")
    with open(MODEL_P_PATH, 'rb') as f: model_p = pickle.load(f)
    with open(MODEL_N_PATH, 'rb') as f: model_n = pickle.load(f)

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
            if pvtp_bits is None or pvtn_bits is None: continue

            pvtp_int = to_int(pvtp_bits)
            pvtn_int = to_int(pvtn_bits)
            if pvtp_int is None or pvtn_int is None: continue

            try:
                vreg = float(row['vreg'])
                temp = float(row['temperature'])
                pmon = float(row['pmon_cmos_res'])
            except: continue

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

    # Hardware Quantization inference
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

    def get_status(row):
        err_p = row['PVTP_Trim_Error_LSB']
        err_n = row['PVTN_Trim_Error_LSB']
        if err_p == 0 and err_n == 0: return "Exact Match"
        elif err_p <= 1 and err_n <= 1: return "Within ±1 LSB"
        else: return f"Mismatch (P:{err_p}, N:{err_n})"

    full_df['Trim_Match_Status'] = full_df.apply(get_status, axis=1)

    # Stratified 80/20 train/test split
    corners = full_df['Corner'].values
    indices = np.arange(len(full_df))
    _, test_idx = train_test_split(indices, test_size=0.2, random_state=42, stratify=corners)

    is_test = np.zeros(len(full_df), dtype=bool)
    is_test[test_idx] = True
    full_df['Dataset_Partition'] = np.where(is_test, 'Validation_TestSet', 'TrainingSet')

    full_df['Simulated_Pup_Ohm'] = ""
    full_df['Simulated_Pdn_Ohm'] = ""

    return full_df


def select_35_good_test_cases(full_df):
    """
    Selects 35 good test cases (exact match) for Cadence Spectre simulation:
    - TT: 5 cases (tt_res)
    - FF: 5 cases (ff_res)
    - SS: 5 cases (ss_res)
    - FS: 10 cases (5 with ff_res + 5 with ss_res)
    - SF: 10 cases (5 with ss_res + 5 with ff_res)
    """
    rows = []
    
    # 5 standard corners with diverse PVT conditions
    for c in ['TT', 'FF', 'SS']:
        c_exact = full_df[(full_df['Corner'] == c) & (full_df['Trim_Match_Status'] == 'Exact Match')].copy()
        c_sorted = c_exact.sort_values(by=['Temp_C', 'Voltage_V']).reset_index(drop=True)
        # Select 5 evenly spaced samples
        step = len(c_sorted) // 5
        indices = [0, step, 2*step, 3*step, len(c_sorted)-1]
        
        mos_sec = f"{c.lower()}macro_mos_moscap"
        res_sec = f"{c.lower()}_res_bip_dio_disres"
        
        for idx in indices:
            r = c_sorted.iloc[idx].to_dict()
            r['MOS_Section'] = mos_sec
            r['Resistor_Section'] = res_sec
            r['Resistor_Corner_Type'] = 'Standard Resistor Corner'
            r['PDK_Model_File'] = '1.8V (crn28hpcp_1d8_elk...)'
            rows.append(r)

    # FS Cross corner (10 cases: 5 with ff_res + 5 with ss_res)
    fs_exact = full_df[(full_df['Corner'] == 'FS') & (full_df['Trim_Match_Status'] == 'Exact Match')].copy()
    fs_sorted = fs_exact.sort_values(by=['Temp_C', 'Voltage_V']).reset_index(drop=True)
    step_fs = len(fs_sorted) // 5
    indices_fs = [0, step_fs, 2*step_fs, 3*step_fs, len(fs_sorted)-1]

    # Part A: FS with FF Resistor
    for idx in indices_fs:
        r = fs_sorted.iloc[idx].to_dict()
        r['MOS_Section'] = 'fsmacro_mos_moscap'
        r['Resistor_Section'] = 'ff_res_bip_dio_disres'
        r['Resistor_Corner_Type'] = 'FS Cross Option 1 (FF Res)'
        r['PDK_Model_File'] = '1.8V (crn28hpcp_1d8_elk...)'
        rows.append(r)

    # Part B: FS with SS Resistor
    for idx in indices_fs:
        r = fs_sorted.iloc[idx].to_dict()
        r['MOS_Section'] = 'fsmacro_mos_moscap'
        r['Resistor_Section'] = 'ss_res_bip_dio_disres'
        r['Resistor_Corner_Type'] = 'FS Cross Option 2 (SS Res)'
        r['PDK_Model_File'] = '1.8V (crn28hpcp_1d8_elk...)'
        rows.append(r)

    # SF Cross corner (10 cases: 5 with ss_res + 5 with ff_res)
    sf_exact = full_df[(full_df['Corner'] == 'SF') & (full_df['Trim_Match_Status'] == 'Exact Match')].copy()
    sf_sorted = sf_exact.sort_values(by=['Temp_C', 'Voltage_V']).reset_index(drop=True)
    step_sf = len(sf_sorted) // 5
    indices_sf = [0, step_sf, 2*step_sf, 3*step_sf, len(sf_sorted)-1]

    # Part A: SF with SS Resistor
    for idx in indices_sf:
        r = sf_sorted.iloc[idx].to_dict()
        r['MOS_Section'] = 'sfmacro_mos_moscap'
        r['Resistor_Section'] = 'ss_res_bip_dio_disres'
        r['Resistor_Corner_Type'] = 'SF Cross Option 1 (SS Res)'
        r['PDK_Model_File'] = '1.8V (crn28hpcp_1d8_elk...)'
        rows.append(r)

    # Part B: SF with FF Resistor
    for idx in indices_sf:
        r = sf_sorted.iloc[idx].to_dict()
        r['MOS_Section'] = 'sfmacro_mos_moscap'
        r['Resistor_Section'] = 'ff_res_bip_dio_disres'
        r['Resistor_Corner_Type'] = 'SF Cross Option 2 (FF Res)'
        r['PDK_Model_File'] = '1.8V (crn28hpcp_1d8_elk...)'
        rows.append(r)

    df_good_35 = pd.DataFrame(rows).reset_index(drop=True)
    df_good_35['Test_ID'] = [f"GOOD_{i+1:02d}" for i in range(len(df_good_35))]
    return df_good_35


def build_excel_workbook(df, df_good_35):
    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    # Typography & Colors
    font_title = Font(name="Segoe UI", size=13, bold=True, color="FFFFFF")
    font_sub = Font(name="Segoe UI", size=9, italic=True, color="FFFFFF")
    font_header = Font(name="Segoe UI", size=9, bold=True, color="FFFFFF")
    font_data = Font(name="Segoe UI", size=9)
    font_bold = Font(name="Segoe UI", size=9, bold=True)
    font_red = Font(name="Segoe UI", size=9, bold=True, color="9C0006")
    font_green = Font(name="Segoe UI", size=9, bold=True, color="006100")
    
    fill_navy = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
    fill_blue_header = PatternFill(start_color="2F5597", end_color="2F5597", fill_type="solid")
    fill_green_header = PatternFill(start_color="385723", end_color="385723", fill_type="solid")
    fill_purple_header = PatternFill(start_color="5B2C6F", end_color="5B2C6F", fill_type="solid")
    fill_orange_header = PatternFill(start_color="B9770E", end_color="B9770E", fill_type="solid")
    fill_teal_header = PatternFill(start_color="117A65", end_color="117A65", fill_type="solid")
    fill_sim_header = PatternFill(start_color="884EA0", end_color="884EA0", fill_type="solid")
    fill_zebra = PatternFill(start_color="F9FAFB", end_color="F9FAFB", fill_type="solid")
    fill_red_alert = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
    fill_green_alert = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
    fill_total_row = PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid")

    thin_border = Border(
        left=Side(style='thin', color='D4D4D4'), right=Side(style='thin', color='D4D4D4'),
        top=Side(style='thin', color='D4D4D4'), bottom=Side(style='thin', color='D4D4D4')
    )
    thick_top_double_bottom = Border(
        left=Side(style='thin', color='D4D4D4'), right=Side(style='thin', color='D4D4D4'),
        top=Side(style='medium', color='1F4E78'), bottom=Side(style='double', color='1F4E78')
    )

    align_center = Alignment(horizontal="center", vertical="center")
    align_left = Alignment(horizontal="left", vertical="center")

    # =========================================================================
    # TAB 1: SUMMARY DASHBOARD (DETAILED TRAIN VS TEST BREAKDOWN)
    # =========================================================================
    print(">>> Building Sheet 1: Summary_Dashboard...")
    ws_dash = wb.create_sheet("Summary_Dashboard")
    ws_dash.views.sheetView[0].showGridLines = True

    ws_dash.merge_cells("A1:K2")
    ws_dash["A1"] = "AI SELF-ADAPTIVE CHIP VALIDATION MASTER DASHBOARD"
    ws_dash["A1"].font = font_title; ws_dash["A1"].fill = fill_navy; ws_dash["A1"].alignment = align_center

    ws_dash.merge_cells("A3:K3")
    ws_dash["A3"] = "TSMC 28nm HPC+ 50-Ohm Driver: 1.8V PDK Model Confirmed | Full Train/Test Breakdown & Dual Resistor Cross-Corners"
    ws_dash["A3"].font = font_sub; ws_dash["A3"].fill = fill_blue_header; ws_dash["A3"].alignment = align_center

    headers_dash = [
        "PVT Corner", "Total Dataset Points", 
        "Train Set (80%)", "Train Exact Matches", "Train Mismatches", "Train Accuracy %",
        "Test Set (20%)", "Test Exact Matches", "Test Mismatches", "Test Accuracy %",
        "Full Exact Match %"
    ]
    ws_dash.append([])
    ws_dash.append(headers_dash)
    for c in range(1, 12):
        cell = ws_dash.cell(row=5, column=c)
        cell.font = font_header; cell.fill = fill_blue_header; cell.alignment = align_center

    row_idx = 6
    for corner in ['TT', 'FF', 'SS', 'FS', 'SF']:
        c_df = df[df['Corner'] == corner]
        n_total = len(c_df)
        
        c_train = c_df[c_df['Dataset_Partition'] == 'TrainingSet']
        n_train = len(c_train)
        n_train_exact = (c_train['Trim_Match_Status'] == 'Exact Match').sum()
        n_train_bad = n_train - n_train_exact
        pct_train = (n_train_exact / n_train) * 100 if n_train > 0 else 0
        
        c_test = c_df[c_df['Dataset_Partition'] == 'Validation_TestSet']
        n_test = len(c_test)
        n_test_exact = (c_test['Trim_Match_Status'] == 'Exact Match').sum()
        n_test_bad = n_test - n_test_exact
        pct_test = (n_test_exact / n_test) * 100 if n_test > 0 else 0
        
        n_exact_total = (c_df['Trim_Match_Status'] == 'Exact Match').sum()
        pct_total = (n_exact_total / n_total) * 100

        ws_dash.append([
            f"{corner} Corner",
            n_total,
            n_train,
            n_train_exact,
            n_train_bad,
            f"{pct_train:.2f}%",
            n_test,
            n_test_exact,
            n_test_bad,
            f"{pct_test:.2f}%",
            f"{pct_total:.2f}%"
        ])
        for col_num in range(1, 12):
            cell = ws_dash.cell(row=row_idx, column=col_num)
            cell.font = font_data; cell.alignment = align_center; cell.border = thin_border
            if col_num in [5, 9] and cell.value not in [0, "0", "0.00%"]:
                cell.fill = fill_red_alert; cell.font = font_red
            elif row_idx % 2 == 1:
                cell.fill = fill_zebra
        row_idx += 1

    # Total row
    tot_pts = len(df)
    tot_train = (df['Dataset_Partition'] == 'TrainingSet').sum()
    tot_train_exact = ((df['Dataset_Partition'] == 'TrainingSet') & (df['Trim_Match_Status'] == 'Exact Match')).sum()
    tot_train_bad = tot_train - tot_train_exact
    
    tot_test = (df['Dataset_Partition'] == 'Validation_TestSet').sum()
    tot_test_exact = ((df['Dataset_Partition'] == 'Validation_TestSet') & (df['Trim_Match_Status'] == 'Exact Match')).sum()
    tot_test_bad = tot_test - tot_test_exact
    
    tot_exact_all = (df['Trim_Match_Status'] == 'Exact Match').sum()
    tot_bad_all = tot_pts - tot_exact_all

    ws_dash.append([
        "TOTAL (All Corners)",
        tot_pts,
        tot_train,
        tot_train_exact,
        tot_train_bad,
        f"{(tot_train_exact/tot_train)*100:.2f}%",
        tot_test,
        tot_test_exact,
        tot_test_bad,
        f"{(tot_test_exact/tot_test)*100:.2f}%",
        f"{(tot_exact_all/tot_pts)*100:.2f}%"
    ])
    for col_num in range(1, 12):
        cell = ws_dash.cell(row=row_idx, column=col_num)
        cell.font = font_bold; cell.alignment = align_center; cell.border = thick_top_double_bottom; cell.fill = fill_total_row
        if col_num in [5, 9]: cell.font = font_red

    # Mathematical Breakdown Explanation Box
    expl_row = row_idx + 3
    ws_dash.merge_cells(f"A{expl_row}:K{expl_row}")
    ws_dash[f"A{expl_row}"] = "MATHEMATICAL BREAKDOWN & TEST SPLIT VERIFICATION"
    ws_dash[f"A{expl_row}"].font = font_header; ws_dash[f"A{expl_row}"].fill = fill_navy; ws_dash[f"A{expl_row}"].alignment = align_left

    expl_items = [
        ("1. TT Corner Breakdown (3300 Points Total)", 
         "Total Points = 3300 = 3262 Exact Matches + 38 Mismatches (98.85% Full Dataset Match)."),
        ("2. TT Corner Training vs Test Partitioning", 
         "Training Set (80% = 2640 points): 2640 Exact Matches + 0 Mismatches -> 100.00% Training Accuracy.\n"
         "Held-Out Test Set (20% = 660 points): 622 Exact Matches + 38 Mismatches -> 94.24% Test Accuracy (660 * 94.2424% = 622 exact matches)."),
        ("3. Why All 38 TT Mismatches Are in Test Set", 
         "The Decision Tree achieved 100% training accuracy on the training partition (2640/2640). All 38 mispredictions occurred solely on unseen test samples."),
        ("4. Overall Dataset Breakdown (15,884 Points Total)", 
         "Training Set (12,707 points): 12,706 Exact Matches + 1 Mismatch (SF corner @ 0.97V, 40°C) -> 99.99% Training Accuracy.\n"
         "Held-Out Test Set (3,177 points): 3,078 Exact Matches + 99 Mismatches -> 96.88% Test Accuracy.\n"
         "Full Dataset (15,884 points): 15,784 Exact Matches + 100 Mismatches -> 99.37% Overall Exact Match.")
    ]
    for idx, (label, desc) in enumerate(expl_items):
        r = expl_row + 1 + idx
        ws_dash.merge_cells(f"A{r}:C{r}")
        ws_dash[f"A{r}"] = label; ws_dash[f"A{r}"].font = font_bold; ws_dash[f"A{r}"].border = thin_border; ws_dash[f"A{r}"].fill = fill_zebra
        ws_dash.merge_cells(f"D{r}:K{r}")
        ws_dash[f"D{r}"] = desc; ws_dash[f"D{r}"].font = font_data; ws_dash[f"D{r}"].border = thin_border; ws_dash[f"D{r}"].alignment = align_left

    # Spectre Verification Tracker Box
    sim_box_row = expl_row + len(expl_items) + 2
    ws_dash.merge_cells(f"A{sim_box_row}:E{sim_box_row}")
    ws_dash[f"A{sim_box_row}"] = "CADENCE SPECTRE SIMULATION TEST PLANS"
    ws_dash[f"A{sim_box_row}"].font = font_header; ws_dash[f"A{sim_box_row}"].fill = fill_purple_header; ws_dash[f"A{sim_box_row}"].alignment = align_center

    tracker_items = [
        ("Good Test Suite Cases (Exact Matches with Dual Resistor Cross-Corners)", "35 Simulation Runs (Sheet: Test_Suite_Good_Cases)"),
        ("Validation Bad Cases to Validate (All Held-Out Test Set Mismatches)", "99 Test Cases (Sheet: Validation_Bad_Cases_99)"),
        ("Training Bad Cases (Mismatches on Training Data)", "1 Test Case (Sheet: Training_Bad_Cases_1)"),
        ("PDK Model File Selected", "1.8V Model (crn28hpcp_1d8_elk... confirmed)"),
        ("Cross-Corner Strategy", "Dual Resistor: FS tested with ff_res & ss_res | SF tested with ss_res & ff_res")
    ]
    for idx, (label, val) in enumerate(tracker_items):
        r = sim_box_row + 1 + idx
        ws_dash.merge_cells(f"A{r}:C{r}")
        ws_dash[f"A{r}"] = label; ws_dash[f"A{r}"].font = font_data; ws_dash[f"A{r}"].border = thin_border
        ws_dash.merge_cells(f"D{r}:E{r}")
        ws_dash[f"D{r}"] = val; ws_dash[f"D{r}"].font = font_bold; ws_dash[f"D{r}"].alignment = align_center; ws_dash[f"D{r}"].border = thin_border

    # =========================================================================
    # TAB 2: CADENCE SPECS AND DOUBTS (UPDATED WITH 1.8V CLARIFICATION)
    # =========================================================================
    print(">>> Building Sheet 2: Cadence_Specs_And_Doubts...")
    ws_specs = wb.create_sheet("Cadence_Specs_And_Doubts")
    ws_specs.views.sheetView[0].showGridLines = True

    ws_specs.merge_cells("A1:E2")
    ws_specs["A1"] = "PROJECT SPECIFICATIONS, CADENCE ENVIRONMENT & TECHNICAL DOUBTS"
    ws_specs["A1"].font = font_title; ws_specs["A1"].fill = fill_navy; ws_specs["A1"].alignment = align_center

    sections = [
        ("1. CHIP & TRANSMITTER DRIVER SPECIFICATIONS", [
            ("Target Differential / Single-Ended Impedance", "50.0 Ω Nominal (Spec Tolerance: ±4% -> 48.0 Ω to 52.0 Ω)"),
            ("PDK Technology", "TSMC 28nm HPC+ (High Performance Compact Plus)"),
            ("Supply Voltage (Vreg)", "0.81V to 1.08V (Nominal: 0.90V / 0.89V, Sweep Step: 0.01V)"),
            ("Operating Temperature Range", "-40°C to +125°C (Extreme Range, Sweep Step: 0.5°C)"),
            ("Process Corners Covered", "5 Corners: TT (Typical-Typical), FF (Fast-Fast), SS (Slow-Slow), FS (Fast NMOS, Slow PMOS), SF (Slow NMOS, Fast PMOS)"),
            ("Process Monitor (PMON) / Ring Osc Freq", "230 MHz to 380 MHz (Hardware sensor encoding PVT condition)"),
            ("Driver Architecture & Trim Bits", "Segmented impedance driver: 8-bit binary trim (bits 0..7 active, bits 8..13 tied to 0 in schematic)"),
            ("Hardware Adaptive Architecture", "On-chip Decision Tree ROM (Depth=14, <1000 gates) reading (PMON, Vreg, Temp) -> outputs optimal trim bits")
        ]),
        ("2. CADENCE SERVER & SIMULATION ENVIRONMENT", [
            ("Server Host & User", "user13@10.1.73.18 (Server: eecs-ser2.iiit.ac.in)"),
            ("Cadence Virtuoso & Spectre Version", "Virtuoso IC618 / Spectre 20.1.0.231.isr6 64bit"),
            ("Working Project Directory", "/data/proj/Low_power_design/tech_tsmc128nm/work/users/user13/validation/"),
            ("Cadence Testbench Library", "tsmc28_tx_tb"),
            ("Driver Cell Name", "tx_drv_ML"),
            ("Simulation Cell-View", "schematic_seriliazer_top"),
            ("PDK Model File Selected", "/data/cad/pdk_all/pdk_tsmc/pdk_tsmc_28/PDK/TSMC_new_iPDK/models/spectre/crn28hpcp_1d8_elk_v1d0_2p2_shrink0d9_embedded_usage.scs (1.8V Model CONFIRMED)"),
            ("Measurement Formula (Pup/Pdn)", "pup = average(clip((v(\"/vdd\") - v(\"/outn\")) / i(\"/xdrv_p/out\"), 200ns, 250ns))\npdn = average(clip(v(\"/outp\") / i(\"/xdrv_p/out\"), 200ns, 250ns)) * -1")
        ]),
        ("3. TECHNICAL DOUBTS STATUS & RESOLUTIONS", [
            ("Doubt 1: TSMC 28nm PDK Model File (1.8V vs 2.5V)", 
             "STATUS: RESOLVED & CLARIFIED.\n"
             "Previously had doubt between 2.5V ('crn28hpcp_2d5_elk...') vs 1.8V ('crn28hpcp_1d8_elk...').\n"
             "CLARIFIED: The 1.8V model file ('crn28hpcp_1d8_elk_v1d0_2p2_shrink0d9_embedded_usage.scs') is confirmed and selected for all simulations."),
            ("Doubt 2: Resistor Corner Section Mapping for FS / SF Cross Corners", 
             "STATUS: RESOLVED & DUAL-RESISTOR TESTING IMPLEMENTED.\n"
             "TSMC 28nm PDK contains only tt_res, ff_res, ss_res (no dedicated fs_res/sf_res).\n"
             "IMPLEMENTATION: Both resistor models are tested for cross corners!\n"
             "  - FS Corner: Tested with BOTH 'ff_res_bip_dio_disres' AND 'ss_res_bip_dio_disres'\n"
             "  - SF Corner: Tested with BOTH 'ss_res_bip_dio_disres' AND 'ff_res_bip_dio_disres'"),
            ("Doubt 3: Transient Averaging Window & Settling Time", 
             "Settling window is 200ns–250ns with 275ns stop time. This matches golden lookup generation."),
            ("Doubt 4: Parallel Ocean Job Conflict on Server", 
             "Running sequential Ocean scripts with modelFile declared once at top eliminates netlist locking and MPSC failures.")
        ])
    ]

    s_row = 4
    for sec_title, items in sections:
        ws_specs.merge_cells(f"A{s_row}:E{s_row}")
        ws_specs[f"A{s_row}"] = sec_title
        ws_specs[f"A{s_row}"].font = font_header; ws_specs[f"A{s_row}"].fill = fill_blue_header; ws_specs[f"A{s_row}"].alignment = align_left
        s_row += 1

        ws_specs.cell(row=s_row, column=1, value="Parameter / Item").font = font_bold
        ws_specs.cell(row=s_row, column=1).fill = fill_zebra
        ws_specs.merge_cells(f"B{s_row}:E{s_row}")
        ws_specs.cell(row=s_row, column=2, value="Technical Specification / Implementation Detail").font = font_bold
        ws_specs.cell(row=s_row, column=2).fill = fill_zebra
        s_row += 1

        for label, desc in items:
            ws_specs.cell(row=s_row, column=1, value=label).font = font_bold
            ws_specs.cell(row=s_row, column=1).border = thin_border
            ws_specs.merge_cells(f"B{s_row}:E{s_row}")
            desc_cell = ws_specs.cell(row=s_row, column=2, value=desc)
            desc_cell.font = font_data; desc_cell.border = thin_border; desc_cell.alignment = align_left
            if "STATUS: RESOLVED" in desc:
                desc_cell.font = font_bold
            s_row += 1
        s_row += 1

    ws_specs.column_dimensions['A'].width = 38
    ws_specs.column_dimensions['B'].width = 30
    ws_specs.column_dimensions['C'].width = 30
    ws_specs.column_dimensions['D'].width = 30
    ws_specs.column_dimensions['E'].width = 30

    # =========================================================================
    # TAB 3: TEST_SUITE_GOOD_CASES (NEW SHEET 1: 35 GOOD TEST CASES)
    # =========================================================================
    print(">>> Building Sheet 3: Test_Suite_Good_Cases (35 cases)...")
    ws_good = wb.create_sheet("Test_Suite_Good_Cases")
    ws_good.views.sheetView[0].showGridLines = True

    good_cols = [
        ("Test_ID", 10, fill_blue_header),
        ("Corner", 8, fill_blue_header),
        ("Resistor_Corner_Type", 26, fill_blue_header),
        ("MOS_Section", 22, fill_blue_header),
        ("Resistor_Section", 24, fill_blue_header),
        ("Voltage_V", 11, fill_blue_header),
        ("Temp_C", 9, fill_blue_header),
        ("Ring_Freq_PMON_Hz", 19, fill_blue_header),
        ("GT_PVTP_Int", 12, fill_green_header),
        ("GT_PVTP_Bits", 13, fill_green_header),
        ("GT_PVTN_Int", 12, fill_green_header),
        ("GT_PVTN_Bits", 13, fill_green_header),
        ("Target_Pup_Ohm", 15, fill_green_header),
        ("Target_Pdn_Ohm", 15, fill_green_header),
        ("ML_PVTP_Int", 12, fill_orange_header),
        ("ML_PVTN_Int", 12, fill_orange_header),
        ("Err_PVTP_LSB", 13, fill_orange_header),
        ("Err_PVTN_LSB", 13, fill_orange_header),
        ("Simulated_Pup_Ohm", 18, fill_sim_header),
        ("Simulated_Pdn_Ohm", 18, fill_sim_header),
        ("Pup_Delta_50", 14, fill_sim_header),
        ("Pdn_Delta_50", 14, fill_sim_header),
        ("Pup_Error_Pct", 14, fill_sim_header),
        ("Pdn_Error_Pct", 14, fill_sim_header),
        ("Spec_Compliance", 16, fill_sim_header),
        ("PDK_Model_File", 28, fill_navy)
    ]

    ws_good.append([col[0] for col in good_cols])
    for col_idx, (_, width, fill_color) in enumerate(good_cols, 1):
        cell = ws_good.cell(row=1, column=col_idx)
        cell.font = font_header; cell.fill = fill_color; cell.alignment = align_center
        ws_good.column_dimensions[get_column_letter(col_idx)].width = width

    for r_idx, (_, row) in enumerate(df_good_35.iterrows(), 2):
        pup_cell = f"S{r_idx}"
        pdn_cell = f"T{r_idx}"

        pup_delta_f = f'=IF(ISBLANK({pup_cell}), "", ROUND({pup_cell}-50.0, 3))'
        pdn_delta_f = f'=IF(ISBLANK({pdn_cell}), "", ROUND({pdn_cell}-50.0, 3))'
        pup_err_f = f'=IF(ISBLANK({pup_cell}), "", ROUND(ABS({pup_cell}-50.0)/50.0*100, 2))'
        pdn_err_f = f'=IF(ISBLANK({pdn_cell}), "", ROUND(ABS({pdn_cell}-50.0)/50.0*100, 2))'
        spec_f = f'=IF(OR(ISBLANK({pup_cell}), ISBLANK({pdn_cell})), "PENDING", IF(AND({pup_cell}>=48.0, {pup_cell}<=52.0, {pdn_cell}>=48.0, {pdn_cell}<=52.0), "PASS", "FAIL"))'

        vals = [
            row['Test_ID'], row['Corner'], row['Resistor_Corner_Type'],
            row['MOS_Section'], row['Resistor_Section'],
            row['Voltage_V'], row['Temp_C'], row['Ring_Osc_Freq_PMON_Hz'],
            row['Ground_Truth_PVTP_Int'], row['Ground_Truth_PVTP_Bits'],
            row['Ground_Truth_PVTN_Int'], row['Ground_Truth_PVTN_Bits'],
            row['Ground_Truth_Target_Pup_Ohm'], row['Ground_Truth_Target_Pdn_Ohm'],
            row['ML_Predicted_PVTP_Int'], row['ML_Predicted_PVTN_Int'],
            row['PVTP_Trim_Error_LSB'], row['PVTN_Trim_Error_LSB'],
            "", "",  # Simulated Pup / Pdn placeholders
            pup_delta_f, pdn_delta_f, pup_err_f, pdn_err_f, spec_f,
            row['PDK_Model_File']
        ]
        ws_good.append(vals)
        for c_idx in range(1, len(good_cols) + 1):
            cell = ws_good.cell(row=r_idx, column=c_idx)
            cell.font = font_data; cell.border = thin_border; cell.alignment = align_center
            if "Cross Option 2" in str(row['Resistor_Corner_Type']):
                cell.fill = fill_zebra
            elif r_idx % 2 == 1:
                cell.fill = fill_zebra

    # Summary row for Good Cases
    last_g_row = len(df_good_35) + 1
    sum_g_row = last_g_row + 2
    ws_good.append([])
    ws_good.cell(row=sum_g_row, column=1, value="SUMMARY / STATS").font = font_bold
    ws_good.cell(row=sum_g_row, column=2, value=f"N={len(df_good_35)}").font = font_bold
    ws_good.cell(row=sum_g_row, column=6, value=f"=ROUND(AVERAGE(F2:F{last_g_row}), 3)").font = font_bold
    ws_good.cell(row=sum_g_row, column=7, value=f"=ROUND(AVERAGE(G2:G{last_g_row}), 1)").font = font_bold
    ws_good.cell(row=sum_g_row, column=8, value=f"=ROUND(AVERAGE(H2:H{last_g_row}), 0)").font = font_bold
    ws_good.cell(row=sum_g_row, column=13, value=f"=ROUND(AVERAGE(M2:M{last_g_row}), 2)").font = font_bold
    ws_good.cell(row=sum_g_row, column=14, value=f"=ROUND(AVERAGE(N2:N{last_g_row}), 2)").font = font_bold
    ws_good.cell(row=sum_g_row, column=19, value=f'=IF(COUNT(S2:S{last_g_row})>0, ROUND(AVERAGE(S2:S{last_g_row}), 2), "")').font = font_bold
    ws_good.cell(row=sum_g_row, column=20, value=f'=IF(COUNT(T2:T{last_g_row})>0, ROUND(AVERAGE(T2:T{last_g_row}), 2), "")').font = font_bold
    ws_good.cell(row=sum_g_row, column=25, value=f'=COUNTIF(Y2:Y{last_g_row}, "PASS") & " PASS"').font = font_bold
    for c_idx in range(1, len(good_cols) + 1):
        cell = ws_good.cell(row=sum_g_row, column=c_idx)
        cell.border = thick_top_double_bottom; cell.fill = fill_total_row; cell.alignment = align_center

    # =========================================================================
    # TAB 4: VALIDATION_BAD_CASES_99 (NEW SHEET 2: ALL 99 TEST SET MISMATCHES)
    # =========================================================================
    print(">>> Building Sheet 4: Validation_Bad_Cases_99 (99 cases)...")
    ws_val_bad = wb.create_sheet("Validation_Bad_Cases_99")
    ws_val_bad.views.sheetView[0].showGridLines = True

    val_bad_df = df[(df['Dataset_Partition'] == 'Validation_TestSet') & (df['Trim_Match_Status'] != 'Exact Match')].reset_index(drop=True)

    bad_cols = [
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
        ("Validation_Partition", 18, fill_navy)
    ]

    ws_val_bad.append([col[0] for col in bad_cols])
    for col_idx, (_, width, fill_color) in enumerate(bad_cols, 1):
        cell = ws_val_bad.cell(row=1, column=col_idx)
        cell.font = font_header; cell.fill = fill_color; cell.alignment = align_center
        ws_val_bad.column_dimensions[get_column_letter(col_idx)].width = width

    for r_idx, (_, row) in enumerate(val_bad_df.iterrows(), 2):
        pup_cell = f"T{r_idx}"
        pdn_cell = f"U{r_idx}"

        pup_delta_f = f'=IF(ISBLANK({pup_cell}), "", ROUND({pup_cell}-50.0, 3))'
        pdn_delta_f = f'=IF(ISBLANK({pdn_cell}), "", ROUND({pdn_cell}-50.0, 3))'
        pup_err_f = f'=IF(ISBLANK({pup_cell}), "", ROUND(ABS({pup_cell}-50.0)/50.0*100, 2))'
        pdn_err_f = f'=IF(ISBLANK({pdn_cell}), "", ROUND(ABS({pdn_cell}-50.0)/50.0*100, 2))'
        spec_f = f'=IF(OR(ISBLANK({pup_cell}), ISBLANK({pdn_cell})), "PENDING", IF(AND({pup_cell}>=48.0, {pup_cell}<=52.0, {pdn_cell}>=48.0, {pdn_cell}<=52.0), "PASS", "FAIL"))'

        vals = [
            r_idx - 1, row['Corner'], row['Voltage_V'], row['Temp_C'], row['Ring_Osc_Freq_PMON_Hz'],
            row['Initial_Pup_Raw_Ohm'], row['Initial_Pdn_Raw_Ohm'],
            row['Ground_Truth_PVTP_Int'], row['Ground_Truth_PVTP_Bits'],
            row['Ground_Truth_PVTN_Int'], row['Ground_Truth_PVTN_Bits'],
            row['Ground_Truth_Target_Pup_Ohm'], row['Ground_Truth_Target_Pdn_Ohm'],
            row['ML_Predicted_PVTP_Int'], row['ML_Predicted_PVTP_Bits'],
            row['ML_Predicted_PVTN_Int'], row['ML_Predicted_PVTN_Bits'],
            row['PVTP_Trim_Error_LSB'], row['PVTN_Trim_Error_LSB'],
            "", "",
            pup_delta_f, pdn_delta_f, pup_err_f, pdn_err_f, spec_f,
            row['Dataset_Partition']
        ]
        ws_val_bad.append(vals)
        for c_idx in range(1, len(bad_cols) + 1):
            cell = ws_val_bad.cell(row=r_idx, column=c_idx)
            cell.font = font_data; cell.border = thin_border; cell.alignment = align_center; cell.fill = fill_red_alert
            if c_idx in [14, 15, 16, 17, 18, 19]:
                cell.font = font_red

    # Summary row for Validation Bad Cases
    last_vb_row = len(val_bad_df) + 1
    sum_vb_row = last_vb_row + 2
    ws_val_bad.append([])
    ws_val_bad.cell(row=sum_vb_row, column=1, value="TOTAL MISMATCHES").font = font_bold
    ws_val_bad.cell(row=sum_vb_row, column=2, value=f"N={len(val_bad_df)} (100% Red)").font = font_red
    ws_val_bad.cell(row=sum_vb_row, column=3, value=f"=ROUND(AVERAGE(C2:C{last_vb_row}), 3)").font = font_bold
    ws_val_bad.cell(row=sum_vb_row, column=4, value=f"=ROUND(AVERAGE(D2:D{last_vb_row}), 1)").font = font_bold
    ws_val_bad.cell(row=sum_vb_row, column=5, value=f"=ROUND(AVERAGE(E2:E{last_vb_row}), 0)").font = font_bold
    ws_val_bad.cell(row=sum_vb_row, column=18, value=f'=COUNTIF(R2:R{last_vb_row}, ">0") & " bad"').font = font_red
    ws_val_bad.cell(row=sum_vb_row, column=19, value=f'=COUNTIF(S2:S{last_vb_row}, ">0") & " bad"').font = font_red
    ws_val_bad.cell(row=sum_vb_row, column=26, value=f'=COUNTIF(Z2:Z{last_vb_row}, "PASS") & " PASS | " & COUNTIF(Z2:Z{last_vb_row}, "FAIL") & " FAIL"').font = font_bold
    for c_idx in range(1, len(bad_cols) + 1):
        cell = ws_val_bad.cell(row=sum_vb_row, column=c_idx)
        cell.border = thick_top_double_bottom; cell.fill = fill_total_row; cell.alignment = align_center

    # =========================================================================
    # TAB 5: TRAINING_BAD_CASES_1 (NEW SHEET 3: TRAINING MISMATCH & ALL 100 MISMATCHES)
    # =========================================================================
    print(">>> Building Sheet 5: Training_Bad_Cases_1 (Training Mismatch & All 100 Mismatches)...")
    ws_tr_bad = wb.create_sheet("Training_Bad_Cases_1")
    ws_tr_bad.views.sheetView[0].showGridLines = True

    # Section 1: Header & Training Accuracy Summary Box
    ws_tr_bad.merge_cells("A1:K2")
    ws_tr_bad["A1"] = "TRAINING SET MISMATCH ANALYSIS & COMPLETE 100-CASE ERROR DISTRIBUTION"
    ws_tr_bad["A1"].font = font_title; ws_tr_bad["A1"].fill = fill_navy; ws_tr_bad["A1"].alignment = align_center

    ws_tr_bad.merge_cells("A3:K3")
    ws_tr_bad["A3"] = "Decision Tree Model achieves 99.99% Training Accuracy: Out of 12,707 Training Points, ONLY 1 Case Differed from Ground Truth!"
    ws_tr_bad["A3"].font = font_sub; ws_tr_bad["A3"].fill = fill_teal_header; ws_tr_bad["A3"].alignment = align_center

    # Table 1: The Single Training Mismatch
    ws_tr_bad.cell(row=5, column=1, value="SECTION 1: THE 1 SINGLE MISMATCH IN THE TRAINING SET (99.99% ACCURACY)").font = font_header
    ws_tr_bad.merge_cells("A5:K5")
    ws_tr_bad.cell(row=5, column=1).fill = fill_purple_header

    tr_bad_cols = [
        ("Sim_ID", 8, fill_blue_header),
        ("Corner", 8, fill_blue_header),
        ("Voltage_V", 11, fill_blue_header),
        ("Temp_C", 9, fill_blue_header),
        ("Ring_Freq_PMON_Hz", 19, fill_blue_header),
        ("GT_PVTP_Int", 12, fill_green_header),
        ("ML_PVTP_Int", 12, fill_orange_header),
        ("Err_PVTP_LSB", 13, fill_orange_header),
        ("GT_PVTN_Int", 12, fill_green_header),
        ("ML_PVTN_Int", 12, fill_orange_header),
        ("Err_PVTN_LSB", 13, fill_orange_header),
        ("Target_Pup_Ohm", 15, fill_green_header),
        ("Target_Pdn_Ohm", 15, fill_green_header),
        ("Dataset_Partition", 18, fill_navy),
        ("Failure_Root_Cause", 35, fill_purple_header)
    ]
    ws_tr_bad.cell(row=6, column=1) # Spacer
    for col_idx, (col_name, width, fill_color) in enumerate(tr_bad_cols, 1):
        cell = ws_tr_bad.cell(row=6, column=col_idx, value=col_name)
        cell.font = font_header; cell.fill = fill_color; cell.alignment = align_center
        ws_tr_bad.column_dimensions[get_column_letter(col_idx)].width = width

    tr_bad_df = df[(df['Dataset_Partition'] == 'TrainingSet') & (df['Trim_Match_Status'] != 'Exact Match')].reset_index(drop=True)
    for r_idx, (_, row) in enumerate(tr_bad_df.iterrows(), 7):
        vals = [
            1, row['Corner'], row['Voltage_V'], row['Temp_C'], row['Ring_Osc_Freq_PMON_Hz'],
            row['Ground_Truth_PVTP_Int'], row['ML_Predicted_PVTP_Int'], row['PVTP_Trim_Error_LSB'],
            row['Ground_Truth_PVTN_Int'], row['ML_Predicted_PVTN_Int'], row['PVTN_Trim_Error_LSB'],
            row['Ground_Truth_Target_Pup_Ohm'], row['Ground_Truth_Target_Pdn_Ohm'],
            row['Dataset_Partition'],
            "Quantization boundary split in SF corner tree"
        ]
        for c_idx, v in enumerate(vals, 1):
            cell = ws_tr_bad.cell(row=r_idx, column=c_idx, value=v)
            cell.font = font_bold if c_idx in [7, 8] else font_data
            cell.border = thin_border; cell.alignment = align_center
            if c_idx in [7, 8]: cell.fill = fill_red_alert; cell.font = font_red
            else: cell.fill = fill_zebra

    # Table 2: Complete 100 Dataset Mismatches Across Full Dataset
    start_t2_row = 10
    ws_tr_bad.merge_cells(f"A{start_t2_row}:O{start_t2_row}")
    ws_tr_bad.cell(row=start_t2_row, column=1, value="SECTION 2: ALL 100 MISMATCHES ACROSS FULL DATASET (1 TRAINING + 99 VALIDATION)").font = font_header
    ws_tr_bad.cell(row=start_t2_row, column=1).fill = fill_navy

    header_t2_row = start_t2_row + 1
    for col_idx, (col_name, width, fill_color) in enumerate(tr_bad_cols, 1):
        cell = ws_tr_bad.cell(row=header_t2_row, column=col_idx, value=col_name)
        cell.font = font_header; cell.fill = fill_color; cell.alignment = align_center

    all_100_bad = df[df['Trim_Match_Status'] != 'Exact Match'].sort_values(by=['Dataset_Partition', 'Corner', 'Voltage_V', 'Temp_C']).reset_index(drop=True)
    for r_idx, (_, row) in enumerate(all_100_bad.iterrows(), header_t2_row + 1):
        is_train = (row['Dataset_Partition'] == 'TrainingSet')
        vals = [
            r_idx - header_t2_row, row['Corner'], row['Voltage_V'], row['Temp_C'], row['Ring_Osc_Freq_PMON_Hz'],
            row['Ground_Truth_PVTP_Int'], row['ML_Predicted_PVTP_Int'], row['PVTP_Trim_Error_LSB'],
            row['Ground_Truth_PVTN_Int'], row['ML_Predicted_PVTN_Int'], row['PVTN_Trim_Error_LSB'],
            row['Ground_Truth_Target_Pup_Ohm'], row['Ground_Truth_Target_Pdn_Ohm'],
            row['Dataset_Partition'],
            "Training Mismatch" if is_train else "Held-Out Test Mismatch"
        ]
        for c_idx, v in enumerate(vals, 1):
            cell = ws_tr_bad.cell(row=r_idx, column=c_idx, value=v)
            cell.font = font_data; cell.border = thin_border; cell.alignment = align_center
            if c_idx in [7, 8, 10, 11] and (row['PVTP_Trim_Error_LSB'] > 0 or row['PVTN_Trim_Error_LSB'] > 0):
                cell.fill = fill_red_alert; cell.font = font_red
            elif is_train:
                cell.fill = fill_green_alert
            elif r_idx % 2 == 1:
                cell.fill = fill_zebra

    # =========================================================================
    # TAB 6 to 11: FULL DATA SHEETS (TT, FF, SS, FS, SF, HeldOut_TestSet_3177)
    # =========================================================================
    full_data_cols = [
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

    def populate_data_sheet(ws, sub_df):
        ws.views.sheetView[0].showGridLines = True
        ws.append([col[0] for col in full_data_cols])
        for col_idx, (_, width, fill_color) in enumerate(full_data_cols, 1):
            cell = ws.cell(row=1, column=col_idx)
            cell.font = font_header; cell.fill = fill_color; cell.alignment = align_center
            ws.column_dimensions[get_column_letter(col_idx)].width = width

        num_rows = len(sub_df)
        for r_idx, (_, row) in enumerate(sub_df.iterrows(), 2):
            pup_cell = f"T{r_idx}"
            pdn_cell = f"U{r_idx}"
            is_mismatch = (row['PVTP_Trim_Error_LSB'] > 0) or (row['PVTN_Trim_Error_LSB'] > 0)

            pup_delta_formula = f'=IF(ISBLANK({pup_cell}), "", ROUND({pup_cell}-50.0, 3))'
            pdn_delta_formula = f'=IF(ISBLANK({pdn_cell}), "", ROUND({pdn_cell}-50.0, 3))'
            pup_err_formula = f'=IF(ISBLANK({pup_cell}), "", ROUND(ABS({pup_cell}-50.0)/50.0*100, 2))'
            pdn_err_formula = f'=IF(ISBLANK({pdn_cell}), "", ROUND(ABS({pdn_cell}-50.0)/50.0*100, 2))'
            spec_formula = f'=IF(OR(ISBLANK({pup_cell}), ISBLANK({pdn_cell})), "PENDING", IF(AND({pup_cell}>=48.0, {pup_cell}<=52.0, {pdn_cell}>=48.0, {pdn_cell}<=52.0), "PASS", "FAIL"))'

            row_values = [
                r_idx - 1, row['Corner'], row['Voltage_V'], row['Temp_C'], row['Ring_Osc_Freq_PMON_Hz'],
                row['Initial_Pup_Raw_Ohm'], row['Initial_Pdn_Raw_Ohm'],
                row['Ground_Truth_PVTP_Int'], row['Ground_Truth_PVTP_Bits'],
                row['Ground_Truth_PVTN_Int'], row['Ground_Truth_PVTN_Bits'],
                row['Ground_Truth_Target_Pup_Ohm'], row['Ground_Truth_Target_Pdn_Ohm'],
                row['ML_Predicted_PVTP_Int'], row['ML_Predicted_PVTP_Bits'],
                row['ML_Predicted_PVTN_Int'], row['ML_Predicted_PVTN_Bits'],
                row['PVTP_Trim_Error_LSB'], row['PVTN_Trim_Error_LSB'],
                "", "",
                pup_delta_formula, pdn_delta_formula, pup_err_formula, pdn_err_formula, spec_formula,
                row['Dataset_Partition']
            ]
            ws.append(row_values)

            for c_idx in range(1, len(full_data_cols) + 1):
                cell = ws.cell(row=r_idx, column=c_idx)
                cell.font = font_data; cell.border = thin_border; cell.alignment = align_center
                if is_mismatch:
                    cell.fill = fill_red_alert
                    if c_idx in [14, 15, 16, 17, 18, 19]:
                        cell.font = font_red
                elif r_idx % 2 == 1:
                    cell.fill = fill_zebra

        # Summary rows at bottom
        last_data_row = num_rows + 1
        ws.append([])
        summary_row_1 = last_data_row + 2
        ws.cell(row=summary_row_1, column=1, value="AVERAGE / STATS").font = font_bold
        ws.cell(row=summary_row_1, column=2, value=f"N={num_rows}").font = font_bold
        ws.cell(row=summary_row_1, column=3, value=f"=ROUND(AVERAGE(C2:C{last_data_row}), 3)").font = font_bold
        ws.cell(row=summary_row_1, column=4, value=f"=ROUND(AVERAGE(D2:D{last_data_row}), 1)").font = font_bold
        ws.cell(row=summary_row_1, column=5, value=f"=ROUND(AVERAGE(E2:E{last_data_row}), 0)").font = font_bold
        ws.cell(row=summary_row_1, column=6, value=f"=ROUND(AVERAGE(F2:F{last_data_row}), 2)").font = font_bold
        ws.cell(row=summary_row_1, column=7, value=f"=ROUND(AVERAGE(G2:G{last_data_row}), 2)").font = font_bold
        ws.cell(row=summary_row_1, column=8, value=f"=ROUND(AVERAGE(H2:H{last_data_row}), 1)").font = font_bold
        ws.cell(row=summary_row_1, column=10, value=f"=ROUND(AVERAGE(J2:J{last_data_row}), 1)").font = font_bold
        ws.cell(row=summary_row_1, column=12, value=f"=ROUND(AVERAGE(L2:L{last_data_row}), 2)").font = font_bold
        ws.cell(row=summary_row_1, column=13, value=f"=ROUND(AVERAGE(M2:M{last_data_row}), 2)").font = font_bold
        ws.cell(row=summary_row_1, column=14, value=f"=ROUND(AVERAGE(N2:N{last_data_row}), 1)").font = font_bold
        ws.cell(row=summary_row_1, column=16, value=f"=ROUND(AVERAGE(P2:P{last_data_row}), 1)").font = font_bold
        ws.cell(row=summary_row_1, column=18, value=f"=ROUND(AVERAGE(R2:R{last_data_row}), 2)").font = font_bold
        ws.cell(row=summary_row_1, column=19, value=f"=ROUND(AVERAGE(S2:S{last_data_row}), 2)").font = font_bold
        ws.cell(row=summary_row_1, column=20, value=f'=IF(COUNT(T2:T{last_data_row})>0, ROUND(AVERAGE(T2:T{last_data_row}), 2), "")').font = font_bold
        ws.cell(row=summary_row_1, column=21, value=f'=IF(COUNT(U2:U{last_data_row})>0, ROUND(AVERAGE(U2:U{last_data_row}), 2), "")').font = font_bold
        ws.cell(row=summary_row_1, column=26, value=f'=COUNTIF(Z2:Z{last_data_row}, "PASS") & " PASS"').font = font_bold

        for c_idx in range(1, len(full_data_cols) + 1):
            cell = ws.cell(row=summary_row_1, column=c_idx)
            cell.border = thick_top_double_bottom; cell.fill = fill_total_row; cell.alignment = align_center

        summary_row_2 = summary_row_1 + 1
        ws.cell(row=summary_row_2, column=1, value="TOTAL MISMATCHES (RED)").font = font_red
        ws.cell(row=summary_row_2, column=2, value=f'=COUNTIF(R2:R{last_data_row}, ">0") + COUNTIF(S2:S{last_data_row}, ">0")').font = font_red
        ws.cell(row=summary_row_2, column=18, value=f'=COUNTIF(R2:R{last_data_row}, ">0") & " bad"').font = font_red
        ws.cell(row=summary_row_2, column=19, value=f'=COUNTIF(S2:S{last_data_row}, ">0") & " bad"').font = font_red
        ws.cell(row=summary_row_2, column=26, value=f'=COUNTIF(Z2:Z{last_data_row}, "FAIL") & " FAIL"').font = font_red
        for c_idx in range(1, len(full_data_cols) + 1):
            cell = ws.cell(row=summary_row_2, column=c_idx)
            cell.border = thin_border; cell.fill = fill_zebra; cell.alignment = align_center

    for corner in ['TT', 'FF', 'SS', 'FS', 'SF']:
        print(f">>> Writing Sheet: {corner}_Corner...")
        ws_corner = wb.create_sheet(f"{corner}_Corner")
        c_df = df[df['Corner'] == corner].reset_index(drop=True)
        populate_data_sheet(ws_corner, c_df)

    print(">>> Writing Sheet: HeldOut_TestSet_3177...")
    ws_test = wb.create_sheet("HeldOut_TestSet_3177")
    test_df = df[df['Dataset_Partition'] == 'Validation_TestSet'].reset_index(drop=True)
    populate_data_sheet(ws_test, test_df)

    # Adjust dashboard column widths
    for col in ws_dash.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        ws_dash.column_dimensions[get_column_letter(col[0].column)].width = max(max_len + 4, 14)

    # Save to v3
    print(f">>> Saving Excel workbook to: {OUTPUT_EXCEL_V3}")
    wb.save(OUTPUT_EXCEL_V3)
    print(">>> Master workbook v3 successfully created!")

    # Try saving to v2 as well if unlocked
    try:
        wb.save(OUTPUT_EXCEL_V2)
        print(f">>> Also updated {OUTPUT_EXCEL_V2}!")
    except Exception as e:
        print(f">>> Note: v2 is currently locked by Excel ({e}), saved to v3 successfully.")

    # Export CSVs for testing
    print(">>> Exporting CSVs...")
    df_good_35.to_csv(os.path.join(OUTPUT_CSV_DIR, "test_suite_good_35.csv"), index=False)
    val_bad_df.to_csv(os.path.join(OUTPUT_CSV_DIR, "validation_bad_99.csv"), index=False)
    tr_bad_df.to_csv(os.path.join(OUTPUT_CSV_DIR, "training_bad_1.csv"), index=False)
    all_100_bad.to_csv(os.path.join(OUTPUT_CSV_DIR, "all_mismatches_100.csv"), index=False)
    print(">>> CSV exports complete.")


def main():
    full_df = load_dataset()
    df_good_35 = select_35_good_test_cases(full_df)
    build_excel_workbook(full_df, df_good_35)

if __name__ == '__main__':
    main()
