#!/usr/bin/env python3
"""
build_all_35_ocean.py
======================
Generates run_all_35_good.ocn — a single monolithic OCEAN script that runs
all 35 simulations continuously in ~60 seconds and writes all results to results_all_35_good.csv.
"""

import os
import pandas as pd

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
CSV_GOOD = os.path.join(PROJECT_DIR, "results", "validation_sheets", "test_suite_good_35.csv")
OUT_DIR = os.path.join(PROJECT_DIR, "validation_generated", "test_suite_35_6jobs")
df_good = pd.read_csv(CSV_GOOD)

MODEL_1D8 = "/data/cad/pdk_all/pdk_tsmc/pdk_tsmc_28/PDK/TSMC_new_iPDK/models/spectre/crn28hpcp_1d8_elk_v1d0_2p2_shrink0d9_embedded_usage.scs"

def int_to_14bits(val):
    bits = {}
    for i in range(8):
        bits[i] = (val >> i) & 1
    for i in range(8, 14):
        bits[i] = 0
    return bits

lines = [
    '; =============================================================================',
    '; ALL 35 GOOD TEST CASES - SINGLE CONTINUOUS OCEAN SCRIPT',
    '; PDK Model: 1.8V (crn28hpcp_1d8_elk...) | Dual Resistor Cross Corners',
    '; Output CSV: results_all_35_good.csv',
    '; Total Runtime: ~60 seconds',
    '; =============================================================================',
    "simulator('spectre)",
    'design("tsmc28_tx_tb" "tx_drv_ML" "schematic_seriliazer_top")',
    'resultsDir("./ocean_results_all35")',
    "analysis('dc ?saveOppoint t)",
    "analysis('tran ?stop \"275n\")",
    "envOption('termDirectionMismatch \"ignore\" 'termMismatch \"ignore\")",
    'saveOption( ?infoOptions list(list("modelParameter" "models" "rawfile" "" "" "" t) list("element" "inst" "rawfile" "" "" "" t) list("outputParameter" "output" "rawfile" "" "" "" t) list("designParamVals" "parameters" "rawfile" "" "" "" t) list("primitives" "primitives" "rawfile" "" "" "" t) list("subckts" "subckts" "rawfile" "" "" "" t) list("asserts" "assert" "rawfile" "" "" "" nil) list("extremeinfo" "all" "logfile" "" "yes" "" nil) list("allcap" "allcap" "file" "" "" "" nil) list("<Click_To_Add>" "none" "rawfile" "" "" "" nil) ) )',
    'save(\'i "/xdrv_p/out")',
    '',
    'out_file = outfile("results_all_35_good.csv")',
    'fprintf(out_file "test_id,corner,res_type,res_sec,vreg,temp,pmon,pvtp,pvtn,sim_pup,sim_pdn,excel_pup,excel_pdn\\n")',
    'drain(out_file)',
    '',
]

current_setup = None
for idx, row in df_good.iterrows():
    test_id = str(row['Test_ID'])
    corner = str(row['Corner'])
    res_type = str(row['Resistor_Corner_Type'])
    mos_sec = str(row['MOS_Section'])
    res_sec = str(row['Resistor_Section'])
    vreg = float(row['Voltage_V'])
    temp = float(row['Temp_C'])
    pmon = int(row['Ring_Osc_Freq_PMON_Hz'])
    pvtp = int(row['Ground_Truth_PVTP_Int'])
    pvtn = int(row['Ground_Truth_PVTN_Int'])
    excel_pup = float(row['Ground_Truth_Target_Pup_Ohm'])
    excel_pdn = float(row['Ground_Truth_Target_Pdn_Ohm'])

    p_bits = int_to_14bits(pvtp)
    n_bits = int_to_14bits(pvtn)

    lines.append(f'; --- Sim {idx+1}/35: [{test_id}] {corner} ({res_type}), V={vreg}V, T={temp}C, pvtp={pvtp}, pvtn={pvtn} ---')
    if (mos_sec, res_sec) != current_setup:
        lines.extend([
            'modelFile(',
            f'    \'("{MODEL_1D8}" "{mos_sec}")',
            f'    \'("{MODEL_1D8}" "{res_sec}")',
            f'    \'("{MODEL_1D8}" "pre_simu")',
            ')',
        ])
        current_setup = (mos_sec, res_sec)

    lines.extend([
        f'printf("\\n>>> Running Sim {idx+1}/35: {test_id} ({corner}, {res_sec}) V={vreg}V, T={temp}C <<<\\n")',
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
        f'fprintf(out_file "{test_id},{corner},{res_type},{res_sec},{vreg},{temp},{pmon},{pvtp},{pvtn},%f,%f,{excel_pup},{excel_pdn}\\n" pup_val pdn_val)',
        'drain(out_file)',
        f'printf("Result {test_id} -> pup=%f, pdn=%f (Target: pup={excel_pup}, pdn={excel_pdn})\\n" pup_val pdn_val)',
        '',
    ])

lines.extend([
    'close(out_file)',
    'printf("\\n=== ALL 35 SIMULATIONS COMPLETED! Results saved to results_all_35_good.csv ===\\n")',
    'exit()',
    ''
])

out_file = os.path.join(OUT_DIR, "run_all_35_good.ocn")
with open(out_file, 'wb') as f:
    f.write('\n'.join(lines).encode('utf-8'))

print(f"Generated {out_file} successfully! Total lines: {len(lines)}")
