#!/usr/bin/env python3
"""
build_validation_excel_v2.py
=============================
Enhancements:
1. Red highlighting for ALL rows where the ML model had a mismatch (>0 LSB error).
2. Column totals / statistics at the bottom of every sheet (Count, Exact matches, Mismatch count, Averages).
3. Dedicated "Cadence_Specs_And_Doubts" sheet detailing:
   - Full driver specifications (impedance, PVT ranges, resolution, bits)
   - Server details (user13@10.1.73.18, Cadence IC618/Spectre201)
   - Library, Cell, and Cell-view names (tsmc28_tx_tb / tx_drv_ML / schematic_seriliazer_top)
   - The 4 core technical doubts for Sir
4. Summary Dashboard with both Full-Dataset and Held-Out Test-Set breakdowns.
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

OUTPUT_EXCEL = os.path.join(PROJECT_DIR, "results", "TSMC28nm_Self_Adaptive_Driver_Validation_Master_v2.xlsx")
OUTPUT_CSV_DIR = os.path.join(PROJECT_DIR, "results", "validation_sheets")
os.makedirs(OUTPUT_CSV_DIR, exist_ok=True)

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

def load_and_predict():
    print("=" * 70)
    print("  BUILDING ENHANCED VALIDATION EXCEL (WITH RED HIGHLIGHTING & SPECS)")
    print("=" * 70)

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


def create_excel_workbook(df):
    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    # Typography & Colors
    font_title = Font(name="Segoe UI", size=13, bold=True, color="FFFFFF")
    font_sub = Font(name="Segoe UI", size=9, italic=True, color="FFFFFF")
    font_header = Font(name="Segoe UI", size=9, bold=True, color="FFFFFF")
    font_data = Font(name="Segoe UI", size=9)
    font_bold = Font(name="Segoe UI", size=9, bold=True)
    font_red = Font(name="Segoe UI", size=9, bold=True, color="9C0006")
    
    fill_navy = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
    fill_blue_header = PatternFill(start_color="2F5597", end_color="2F5597", fill_type="solid")
    fill_green_header = PatternFill(start_color="385723", end_color="385723", fill_type="solid")
    fill_purple_header = PatternFill(start_color="5B2C6F", end_color="5B2C6F", fill_type="solid")
    fill_orange_header = PatternFill(start_color="B9770E", end_color="B9770E", fill_type="solid")
    fill_sim_header = PatternFill(start_color="884EA0", end_color="884EA0", fill_type="solid")
    fill_zebra = PatternFill(start_color="F9FAFB", end_color="F9FAFB", fill_type="solid")
    fill_red_alert = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")  # Red for mismatches
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
    # SHEET 1: SUMMARY DASHBOARD
    # =========================================================================
    ws_dash = wb.create_sheet("Summary_Dashboard")
    ws_dash.views.sheetView[0].showGridLines = True

    ws_dash.merge_cells("A1:G2")
    ws_dash["A1"] = "AI SELF-ADAPTIVE CHIP VALIDATION MASTER DASHBOARD"
    ws_dash["A1"].font = font_title; ws_dash["A1"].fill = fill_navy; ws_dash["A1"].alignment = align_center

    ws_dash.merge_cells("A3:G3")
    ws_dash["A3"] = "TSMC 28nm HPC+ 50-Ohm Driver: Red rows indicate model mismatches to verify in Spectre"
    ws_dash["A3"].font = font_sub; ws_dash["A3"].fill = fill_blue_header; ws_dash["A3"].alignment = align_center

    headers_dash = ["PVT Corner", "Total Dataset Points", "Held-Out Test Set (20%)", "Total Exact Matches", "Total Mismatches (Red)", "Full Exact Match %", "Test Set Exact Match %"]
    ws_dash.append([])
    ws_dash.append(headers_dash)
    for c in range(1, 8):
        cell = ws_dash.cell(row=5, column=c)
        cell.font = font_header; cell.fill = fill_blue_header; cell.alignment = align_center

    row_idx = 6
    for corner in ['TT', 'FF', 'SS', 'FS', 'SF']:
        c_df = df[df['Corner'] == corner]
        n_total = len(c_df)
        c_test = c_df[c_df['Dataset_Partition'] == 'Validation_TestSet']
        n_test = len(c_test)
        
        n_exact_total = (c_df['Trim_Match_Status'] == 'Exact Match').sum()
        n_bad_total = n_total - n_exact_total
        pct_exact_total = (n_exact_total / n_total) * 100
        
        n_exact_test = (c_test['Trim_Match_Status'] == 'Exact Match').sum()
        pct_exact_test = (n_exact_test / n_test) * 100

        ws_dash.append([
            f"{corner} Corner",
            n_total,
            n_test,
            n_exact_total,
            n_bad_total,
            f"{pct_exact_total:.2f}%",
            f"{pct_exact_test:.2f}%"
        ])
        for col_num in range(1, 8):
            cell = ws_dash.cell(row=row_idx, column=col_num)
            cell.font = font_data; cell.alignment = align_center; cell.border = thin_border
            if col_num == 5 and n_bad_total > 0:
                cell.fill = fill_red_alert; cell.font = font_red
            elif row_idx % 2 == 1:
                cell.fill = fill_zebra
        row_idx += 1

    # Total row
    tot_pts = len(df)
    tot_test = (df['Dataset_Partition'] == 'Validation_TestSet').sum()
    tot_exact_all = (df['Trim_Match_Status'] == 'Exact Match').sum()
    tot_bad_all = tot_pts - tot_exact_all
    tot_test_exact = ((df['Dataset_Partition'] == 'Validation_TestSet') & (df['Trim_Match_Status'] == 'Exact Match')).sum()

    ws_dash.append([
        "TOTAL (All Corners)",
        tot_pts,
        tot_test,
        tot_exact_all,
        tot_bad_all,
        f"{(tot_exact_all/tot_pts)*100:.2f}%",
        f"{(tot_test_exact/tot_test)*100:.2f}%"
    ])
    for col_num in range(1, 8):
        cell = ws_dash.cell(row=row_idx, column=col_num)
        cell.font = font_bold; cell.alignment = align_center; cell.border = thick_top_double_bottom; cell.fill = fill_total_row
        if col_num == 5: cell.font = font_red

    # Spectre Verification Tracker Box
    sim_box_row = row_idx + 3
    ws_dash.merge_cells(f"A{sim_box_row}:D{sim_box_row}")
    ws_dash[f"A{sim_box_row}"] = "SPECTRE POST-SIMULATION VERIFICATION TRACKER"
    ws_dash[f"A{sim_box_row}"].font = font_header; ws_dash[f"A{sim_box_row}"].fill = fill_purple_header; ws_dash[f"A{sim_box_row}"].alignment = align_center

    tracker_items = [
        ("Total Held-Out Validation Points (Test Set)", tot_test),
        ("Total Model Mismatches in Test Set (Red Rows to Validate)", len(df[(df['Dataset_Partition']=='Validation_TestSet') & (df['Trim_Match_Status'] != 'Exact Match')])),
        ("Simulations Completed in Spectre", '=COUNT(HeldOut_TestSet_3177!T3:T3179)'),
        ("Points Meeting 48 - 52 Ω Impedance Spec", '=COUNTIF(HeldOut_TestSet_3177!Z3:Z3179, "PASS")'),
        ("Points Failing 48 - 52 Ω Impedance Spec", '=COUNTIF(HeldOut_TestSet_3177!Z3:Z3179, "FAIL")'),
        ("Post-Calibration Spec Compliance Yield", '=IF(COUNT(HeldOut_TestSet_3177!T3:T3179)>0, TEXT(COUNTIF(HeldOut_TestSet_3177!Z3:Z3179, "PASS")/COUNT(HeldOut_TestSet_3177!T3:T3179)*100, "0.00") & "%", "Pending Sim")')
    ]
    for idx, (label, val_or_f) in enumerate(tracker_items):
        r = sim_box_row + 1 + idx
        ws_dash.merge_cells(f"A{r}:C{r}")
        ws_dash[f"A{r}"] = label; ws_dash[f"A{r}"].font = font_data; ws_dash[f"A{r}"].border = thin_border
        ws_dash[f"D{r}"] = val_or_f; ws_dash[f"D{r}"].font = font_bold; ws_dash[f"D{r}"].alignment = align_center; ws_dash[f"D{r}"].border = thin_border

    # =========================================================================
    # SHEET 2: CADENCE SPECS AND DOUBTS (DEDICATED REFERENCE SHEET)
    # =========================================================================
    ws_specs = wb.create_sheet("Cadence_Specs_And_Doubts")
    ws_specs.views.sheetView[0].showGridLines = True

    ws_specs.merge_cells("A1:E2")
    ws_specs["A1"] = "PROJECT SPECIFICATIONS, CADENCE ENVIRONMENT & TECHNICAL DOUBTS"
    ws_specs["A1"].font = font_title; ws_specs["A1"].fill = fill_navy; ws_specs["A1"].alignment = align_center

    sections = [
        ("1. CHIP & TRANSMITTER DRIVER SPECIFICATIONS", [
            ("Target Differential / Single-Ended Impedance", "50.0 Ω Nominal (Spec Tolerance: ±4% → 48.0 Ω to 52.0 Ω)"),
            ("PDK Technology", "TSMC 28nm HPC+ (High Performance Compact Plus)"),
            ("Supply Voltage (Vreg)", "0.81V to 1.08V (Nominal: 0.90V / 0.89V, Sweep Step: 0.01V)"),
            ("Operating Temperature Range", "-40°C to +125°C (Extreme Range, Sweep Step: 0.5°C)"),
            ("Process Corners Covered", "5 Corners: TT (Typical-Typical), FF (Fast-Fast), SS (Slow-Slow), FS (Fast NMOS, Slow PMOS), SF (Slow NMOS, Fast PMOS)"),
            ("Process Monitor (PMON) / Ring Osc Freq", "230 MHz to 380 MHz (Hardware sensor encoding PVT condition)"),
            ("Driver Architecture & Trim Bits", "Segmented impedance driver: 8-bit binary trim (bits 0..7 active, bits 8..13 tied to 0 in schematic)"),
            ("Hardware Adaptive Architecture", "On-chip Decision Tree ROM (Depth=14, <1000 gates) reading (PMON, Vreg, Temp) → outputs optimal trim bits")
        ]),
        ("2. CADENCE SERVER & SIMULATION ENVIRONMENT", [
            ("Server Host & User", "user13@10.1.73.18 (Server: eecs-ser2.iiit.ac.in)"),
            ("Cadence Virtuoso & Spectre Version", "Virtuoso IC618 / Spectre 20.1.0.231.isr6 64bit"),
            ("Working Project Directory", "/data/proj/Low_power_design/tech_tsmc128nm/work/users/user13/validation/"),
            ("Cadence Testbench Library", "tsmc28_tx_tb"),
            ("Driver Cell Name", "tx_drv_ML"),
            ("Simulation Cell-View", "schematic_seriliazer_top"),
            ("Transient Simulation Command", "run_corners_final.ocn structure: simulator('spectre), analysis('tran ?stop 275ns / 500ns)"),
            ("Measurement Formula (Pupp/Pdn)", "pup = average(clip((v(\"/vdd\") - v(\"/outn\")) / i(\"/xdrv_p/out\"), 200ns, 250ns))\npdn = average(clip(v(\"/outp\") / i(\"/xdrv_p/out\"), 200ns, 250ns)) * -1")
        ]),
        ("3. TECHNICAL DOUBTS & QUESTIONS FOR SIR", [
            ("Doubt 1: TSMC 28nm PDK Model File", "On server, two PDK model files exist: 'crn28hpcp_2d5_elk_v1d0_2p2_shrink0d9_embedded_usage.scs' (2.5V IO) vs 'crn28hpcp_1d8_elk...' (1.8V IO). Which exact model was selected when generating the golden Excel table?"),
            ("Doubt 2: Resistor Corner Section Mapping for FS/SF", "TSMC 28nm PDK has only tt_res, ff_res, ss_res (no fs_res/sf_res). In Maestro/ADE, was FS paired with 'ff_res_bip_dio_disres' and SF with 'ss_res_bip_dio_disres'?"),
            ("Doubt 3: Transient Averaging Window & Settling Time", "Is the 200ns–250ns time window the exact settling window used for the paper/lookup table? Is a 275ns stop time sufficient, or is 500ns needed for extreme corners?"),
            ("Doubt 4: Parallel Ocean Job Conflict on Server", "Running parallel 'ocean' instances clashing on the shared netlist directory ('schematic_seriliazer_top/netlist/input.scs') causes Spectre MPSC IPC lock failures. Is running sequential Ocean or isolated directories preferred?")
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
            s_row += 1
        s_row += 1

    ws_specs.column_dimensions['A'].width = 38
    ws_specs.column_dimensions['B'].width = 30
    ws_specs.column_dimensions['C'].width = 30
    ws_specs.column_dimensions['D'].width = 30
    ws_specs.column_dimensions['E'].width = 30

    # =========================================================================
    # DATA SHEETS (TT, FF, SS, FS, SF, HeldOut_TestSet_3177)
    # =========================================================================
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

    def populate_sheet_with_totals(ws, sub_df):
        ws.views.sheetView[0].showGridLines = True
        
        # Header
        ws.append([col[0] for col in columns])
        for col_idx, (_, width, fill_color) in enumerate(columns, 1):
            cell = ws.cell(row=1, column=col_idx)
            cell.font = font_header; cell.fill = fill_color; cell.alignment = align_center
            ws.column_dimensions[get_column_letter(col_idx)].width = width

        # Data rows
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
                "", "",  # Simulated Pup / Pdn
                pup_delta_formula, pdn_delta_formula, pup_err_formula, pdn_err_formula, spec_formula,
                row['Dataset_Partition']
            ]
            ws.append(row_values)

            # Styling: If mismatch, highlight in RED ALERT!
            for c_idx in range(1, len(columns) + 1):
                cell = ws.cell(row=r_idx, column=c_idx)
                cell.font = font_data; cell.border = thin_border; cell.alignment = align_center
                if is_mismatch:
                    cell.fill = fill_red_alert
                    if c_idx in [14, 15, 16, 17, 18, 19]: # Highlight ML columns in bold red
                        cell.font = font_red
                elif r_idx % 2 == 1:
                    cell.fill = fill_zebra

        # =====================================================================
        # COLUMN ADDITIONS / SUMMARY ROWS AT THE END OF THE SHEET
        # =====================================================================
        last_data_row = num_rows + 1
        ws.append([]) # Blank spacer row

        # Row 1: TOTAL COUNT / AVERAGE SUMMARY
        summary_row_1 = last_data_row + 2
        ws.cell(row=summary_row_1, column=1, value="AVERAGE / STATS").font = font_bold
        ws.cell(row=summary_row_1, column=2, value=f"N={num_rows}").font = font_bold
        ws.cell(row=summary_row_1, column=3, value=f"=ROUND(AVERAGE(C2:C{last_data_row}), 3)").font = font_bold # Avg Vreg
        ws.cell(row=summary_row_1, column=4, value=f"=ROUND(AVERAGE(D2:D{last_data_row}), 1)").font = font_bold # Avg Temp
        ws.cell(row=summary_row_1, column=5, value=f"=ROUND(AVERAGE(E2:E{last_data_row}), 0)").font = font_bold # Avg PMON
        ws.cell(row=summary_row_1, column=6, value=f"=ROUND(AVERAGE(F2:F{last_data_row}), 2)").font = font_bold # Avg Raw Pup
        ws.cell(row=summary_row_1, column=7, value=f"=ROUND(AVERAGE(G2:G{last_data_row}), 2)").font = font_bold # Avg Raw Pdn
        ws.cell(row=summary_row_1, column=8, value=f"=ROUND(AVERAGE(H2:H{last_data_row}), 1)").font = font_bold # Avg GT PVTP
        ws.cell(row=summary_row_1, column=10, value=f"=ROUND(AVERAGE(J2:J{last_data_row}), 1)").font = font_bold # Avg GT PVTN
        ws.cell(row=summary_row_1, column=12, value=f"=ROUND(AVERAGE(L2:L{last_data_row}), 2)").font = font_bold # Avg Target Pup
        ws.cell(row=summary_row_1, column=13, value=f"=ROUND(AVERAGE(M2:M{last_data_row}), 2)").font = font_bold # Avg Target Pdn
        ws.cell(row=summary_row_1, column=14, value=f"=ROUND(AVERAGE(N2:N{last_data_row}), 1)").font = font_bold # Avg ML PVTP
        ws.cell(row=summary_row_1, column=16, value=f"=ROUND(AVERAGE(P2:P{last_data_row}), 1)").font = font_bold # Avg ML PVTN
        ws.cell(row=summary_row_1, column=18, value=f"=ROUND(AVERAGE(R2:R{last_data_row}), 2)").font = font_bold # Avg Err PVTP
        ws.cell(row=summary_row_1, column=19, value=f"=ROUND(AVERAGE(S2:S{last_data_row}), 2)").font = font_bold # Avg Err PVTN
        ws.cell(row=summary_row_1, column=20, value=f'=IF(COUNT(T2:T{last_data_row})>0, ROUND(AVERAGE(T2:T{last_data_row}), 2), "")').font = font_bold # Avg Sim Pup
        ws.cell(row=summary_row_1, column=21, value=f'=IF(COUNT(U2:U{last_data_row})>0, ROUND(AVERAGE(U2:U{last_data_row}), 2), "")').font = font_bold # Avg Sim Pdn
        ws.cell(row=summary_row_1, column=26, value=f'=COUNTIF(Z2:Z{last_data_row}, "PASS") & " PASS"').font = font_bold

        for c_idx in range(1, len(columns) + 1):
            cell = ws.cell(row=summary_row_1, column=c_idx)
            cell.border = thick_top_double_bottom; cell.fill = fill_total_row; cell.alignment = align_center

        # Row 2: MISMATCH COUNTERS (COLUMN ADDITION)
        summary_row_2 = summary_row_1 + 1
        ws.cell(row=summary_row_2, column=1, value="TOTAL MISMATCHES (RED)").font = font_red
        ws.cell(row=summary_row_2, column=2, value=f'=COUNTIF(R2:R{last_data_row}, ">0") + COUNTIF(S2:S{last_data_row}, ">0")').font = font_red
        ws.cell(row=summary_row_2, column=18, value=f'=COUNTIF(R2:R{last_data_row}, ">0") & " bad"').font = font_red
        ws.cell(row=summary_row_2, column=19, value=f'=COUNTIF(S2:S{last_data_row}, ">0") & " bad"').font = font_red
        ws.cell(row=summary_row_2, column=26, value=f'=COUNTIF(Z2:Z{last_data_row}, "FAIL") & " FAIL"').font = font_red
        for c_idx in range(1, len(columns) + 1):
            cell = ws.cell(row=summary_row_2, column=c_idx)
            cell.border = thin_border; cell.fill = fill_zebra; cell.alignment = align_center

    # Populate corner sheets
    for corner in ['TT', 'FF', 'SS', 'FS', 'SF']:
        print(f"      Writing sheet: {corner}_Corner (with red highlights & summary row)...")
        ws_corner = wb.create_sheet(f"{corner}_Corner")
        c_df = df[df['Corner'] == corner].reset_index(drop=True)
        populate_sheet_with_totals(ws_corner, c_df)

    # Dedicated Test Set Sheet
    print("      Writing sheet: HeldOut_TestSet_3177 (with red highlights & summary row)...")
    ws_test = wb.create_sheet("HeldOut_TestSet_3177")
    test_df = df[df['Dataset_Partition'] == 'Validation_TestSet'].reset_index(drop=True)
    populate_sheet_with_totals(ws_test, test_df)

    # Adjust dashboard column widths
    for col in ws_dash.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        ws_dash.column_dimensions[get_column_letter(col[0].column)].width = max(max_len + 4, 14)

    # Save
    print(f"      Saving enhanced Excel file to: {OUTPUT_EXCEL}")
    wb.save(OUTPUT_EXCEL)
    print("SUCCESS! Enhanced master workbook generated.")

if __name__ == '__main__':
    df = load_and_predict()
    create_excel_workbook(df)
