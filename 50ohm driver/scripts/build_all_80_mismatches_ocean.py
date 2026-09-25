#!/usr/bin/env python3
"""
build_all_80_mismatches_ocean.py
=================================
Generates run_all_80_mismatches.ocn — a single continuous OCEAN script
running all 80 mismatch test cases (TT: 38, FF: 21, SS: 21) in ~100 seconds.
"""

import os
import pandas as pd

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
CSV_IN = os.path.join(PROJECT_DIR, "results", "validation_sheets", "working_mismatches_80.csv")
OUT_DIR = os.path.join(PROJECT_DIR, "validation_generated", "test_suite_mismatches_80_2jobs")
df = pd.read_csv(CSV_IN)

MODEL_1D8 = "/data/cad/pdk_all/pdk_tsmc/pdk_tsmc_28/PDK/TSMC_new_iPDK/models/spectre/crn28hpcp_1d8_elk_v1d0_2p2_shrink0d9_embedded_usage.scs"

CORNER_SECTIONS = {
    'TT': ('ttmacro_mos_moscap', 'tt_res_bip_dio_disres'),
    'FF': ('ffmacro_mos_moscap', 'ff_res_bip_dio_disres'),
    'SS': ('ssmacro_mos_moscap', 'ss_res_bip_dio_disres'),
}

def int_to_14bits(val):
    bits = {}
    for i in range(8):
        bits[i] = (val >> i) & 1
    for i in range(8, 14):
        bits[i] = 0
    return bits

lines = [
    '; =============================================================================',
    '; ALL 80 WORKING CORNER MISMATCHES - SINGLE CONTINUOUS OCEAN SCRIPT',
    '; Corners: TT (38 cases), FF (21 cases), SS (21 cases)',
    '; PDK Model: 1.8V (crn28hpcp_1d8_elk...)',
    '; Simulates ML PREDICTED TRIM to verify 48-52 Ohm Spec Compliance',
    '; Output CSV: results_all_80_mismatches.csv',
    '; Total Runtime: ~100 seconds',
    '; =============================================================================',
    "simulator('spectre)",
    'design("tsmc28_tx_tb" "tx_drv_ML" "schematic_seriliazer_top")',
    'resultsDir("./ocean_results_mismatches_80")',
    "analysis('dc ?saveOppoint t)",
    "analysis('tran ?stop \"275n\")",
    "envOption('termDirectionMismatch \"ignore\" 'termMismatch \"ignore\")",
    'saveOption( ?infoOptions list(list("modelParameter" "models" "rawfile" "" "" "" t) list("element" "inst" "rawfile" "" "" "" t) list("outputParameter" "output" "rawfile" "" "" "" t) list("designParamVals" "parameters" "rawfile" "" "" "" t) list("primitives" "primitives" "rawfile" "" "" "" t) list("subckts" "subckts" "rawfile" "" "" "" t) list("asserts" "assert" "rawfile" "" "" "" nil) list("extremeinfo" "all" "logfile" "" "yes" "" nil) list("allcap" "allcap" "file" "" "" "" nil) list("<Click_To_Add>" "none" "rawfile" "" "" "" nil) ) )',
    'save(\'i "/xdrv_p/out")',
    '',
    'out_file = outfile("results_all_80_mismatches.csv")',
    'fprintf(out_file "test_id,corner,vreg,temp,pmon,gt_pvtp,gt_pvtn,ml_pvtp,ml_pvtn,err_p,err_n,sim_pup,sim_pdn,gt_pup,gt_pdn\\n")',
    'drain(out_file)',
    '',
]

current_corner = None
for idx, row in df.iterrows():
    test_id = str(row['Test_ID'])
    corner = str(row['Corner'])
    vreg = float(row['Voltage_V'])
    temp = float(row['Temp_C'])
    pmon = int(row['Ring_Osc_Freq_PMON_Hz'])
    gt_p = int(row['Ground_Truth_PVTP_Int'])
    gt_n = int(row['Ground_Truth_PVTN_Int'])
    ml_p = int(row['ML_Predicted_PVTP_Int'])
    ml_n = int(row['ML_Predicted_PVTN_Int'])
    err_p = int(row['PVTP_Trim_Error_LSB'])
    err_n = int(row['PVTN_Trim_Error_LSB'])
    gt_pup = float(row['Ground_Truth_Target_Pup_Ohm'])
    gt_pdn = float(row['Ground_Truth_Target_Pdn_Ohm'])

    mos_sec, res_sec = CORNER_SECTIONS[corner]

    if corner != current_corner:
        lines.extend([
            f'; --- Set PDK Corner Model for {corner} ---',
            'modelFile(',
            f'    \'("{MODEL_1D8}" "{mos_sec}")',
            f'    \'("{MODEL_1D8}" "{res_sec}")',
            f'    \'("{MODEL_1D8}" "pre_simu")',
            ')',
            '',
        ])
        current_corner = corner

    p_bits = int_to_14bits(ml_p)
    n_bits = int_to_14bits(ml_n)

    lines.extend([
        f'; --- Sim {idx+1}/80: [{test_id}] {corner}, V={vreg}V, T={temp}C | ML=({ml_p},{ml_n}) GT=({gt_p},{gt_n}) ---',
        f'printf("\\n>>> Running Sim {idx+1}/80: {test_id} ({corner}) V={vreg}V, T={temp}C | ML=({ml_p},{ml_n}) GT=({gt_p},{gt_n}) <<<\\n")',
        f'desVar("tem" {temp})',
        f'desVar("vreg" {vreg})',
        f'temp({temp})',
    ])
    for b in range(14):
        lines.append(f'desVar("pvt{b}" {p_bits[b]})')
    for b in range(14):
        lines.append(f'desVar("pvtn{b}" {n_bits[b]})')

    lines.extend([
        'run()',
        "selectResults('tran)",
        'pup_val = average((clip((v("/vdd" ?result "tran") - v("/outn" ?result "tran")) 2e-07 2.5e-07) / clip(i("/xdrv_p/out" ?result "tran") 2e-07 2.5e-07)))',
        'pdn_val = (average((clip(v("/outp" ?result "tran") 2e-07 2.5e-07) / clip(i("/xdrv_p/out" ?result "tran") 2e-07 2.5e-07))) * -1)',
        f'fprintf(out_file "{test_id},{corner},{vreg},{temp},{pmon},{gt_p},{gt_n},{ml_p},{ml_n},{err_p},{err_n},%f,%f,{gt_pup},{gt_pdn}\\n" pup_val pdn_val)',
        'drain(out_file)',
        f'printf("Result {test_id} -> pup=%f, pdn=%f (GT Target: pup={gt_pup}, pdn={gt_pdn})\\n" pup_val pdn_val)',
        '',
    ])

lines.extend([
    'close(out_file)',
    'printf("\\n=== ALL 80 MISMATCH SIMULATIONS COMPLETED! Results saved to results_all_80_mismatches.csv ===\\n")',
    'exit()',
    ''
])

out_file = os.path.join(OUT_DIR, "run_all_80_mismatches.ocn")
with open(out_file, 'wb') as f:
    f.write('\n'.join(lines).encode('utf-8'))

print(f"Generated {out_file} successfully! Total lines: {len(lines)}")
