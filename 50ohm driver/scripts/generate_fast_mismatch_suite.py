#!/usr/bin/env python3
"""
generate_fast_mismatch_suite.py
================================
Generates an ultra-fast 4-job parallel OCEAN simulation suite for all 80 working corner mismatches:
- Job 1: TT part 1 (19 cases) -> in job1_TT_pt1/
- Job 2: TT part 2 (19 cases) -> in job2_TT_pt2/
- Job 3: FF (21 cases)         -> in job3_FF/
- Job 4: SS (21 cases)         -> in job4_SS/

Each job runs in its own dedicated subfolder to ensure 100% private CDS.log files,
eliminating any locking conflicts. All 4 jobs run concurrently in parallel,
finishing all 80 simulations in ONLY ~25 to 30 seconds!

Also generates run_all_80_single.ocn for single-command execution.
"""

import os
import pandas as pd

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
CSV_IN = os.path.join(PROJECT_DIR, "results", "validation_sheets", "working_mismatches_80.csv")
BASE_OUT = os.path.join(PROJECT_DIR, "validation_generated", "test_suite_mismatches_80_fast")
os.makedirs(BASE_OUT, exist_ok=True)

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

def build_ocean_script(job_name, corner, rows):
    mos_sec, res_sec = CORNER_SECTIONS[corner]
    csv_out = f"results_{job_name}.csv"

    lines = [
        f"; =============================================================================",
        f"; CADENCE SPECTRE OCEAN SCRIPT: {job_name.upper()} ({corner} CORNER)",
        f"; Total Test Cases: {len(rows)} | PDK Model: 1.8V (crn28hpcp_1d8_elk...)",
        f"; Simulating with ML PREDICTED TRIM to verify 48-52 Ohm Spec Compliance",
        f"; Results CSV: {csv_out}",
        f"; =============================================================================",
        "simulator('spectre)",
        'design("tsmc28_tx_tb" "tx_drv_ML" "schematic_seriliazer_top")',
        'resultsDir("./ocean_results")',
        '',
        '; modelFile declared once at top',
        'modelFile(',
        f'    \'("{MODEL_1D8}" "{mos_sec}")',
        f'    \'("{MODEL_1D8}" "{res_sec}")',
        f'    \'("{MODEL_1D8}" "pre_simu")',
        ')',
        '',
        "analysis('dc ?saveOppoint t)",
        "analysis('tran ?stop \"275n\")",
        "envOption('termDirectionMismatch \"ignore\" 'termMismatch \"ignore\")",
        'saveOption( ?infoOptions list(list("modelParameter" "models" "rawfile" "" "" "" t) list("element" "inst" "rawfile" "" "" "" t) list("outputParameter" "output" "rawfile" "" "" "" t) list("designParamVals" "parameters" "rawfile" "" "" "" t) list("primitives" "primitives" "rawfile" "" "" "" t) list("subckts" "subckts" "rawfile" "" "" "" t) list("asserts" "assert" "rawfile" "" "" "" nil) list("extremeinfo" "all" "logfile" "" "yes" "" nil) list("allcap" "allcap" "file" "" "" "" nil) list("<Click_To_Add>" "none" "rawfile" "" "" "" nil) ) )',
        'save(\'i "/xdrv_p/out")',
        '',
        f'out_file = outfile("{csv_out}")',
        'fprintf(out_file "test_id,corner,vreg,temp,pmon,gt_pvtp,gt_pvtn,ml_pvtp,ml_pvtn,err_p,err_n,sim_pup,sim_pdn,gt_pup,gt_pdn\\n")',
        'drain(out_file)',
        '',
    ]

    for idx, row in enumerate(rows):
        test_id = str(row['Test_ID'])
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

        p_bits = int_to_14bits(ml_p)
        n_bits = int_to_14bits(ml_n)

        lines.extend([
            f'; --- Sim {idx+1}/{len(rows)}: [{test_id}] {corner}, V={vreg}V, T={temp}C | ML=({ml_p},{ml_n}) GT=({gt_p},{gt_n}) ---',
            f'printf("\\n>>> [{job_name}] Sim {idx+1}/{len(rows)}: {test_id} ({corner}) V={vreg}V, T={temp}C | ML=({ml_p},{ml_n}) <<<\\n")',
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
        f'printf("\\n=== {job_name.upper()} COMPLETED! Results in {csv_out} ===\\n")',
        'exit()',
        ''
    ])
    return '\n'.join(lines)


def build_single_monolithic_ocean(rows):
    lines = [
        '; =============================================================================',
        '; ALL 80 WORKING CORNER MISMATCHES - SINGLE MONOLITHIC OCEAN SCRIPT',
        '; Corners: TT (38 cases), FF (21 cases), SS (21 cases)',
        '; PDK Model: 1.8V (crn28hpcp_1d8_elk...)',
        '; Simulates ML PREDICTED TRIM to verify 48-52 Ohm Spec Compliance',
        '; Output CSV: results_all_80_mismatches.csv',
        '; Total Runtime: ~100 seconds',
        '; =============================================================================',
        "simulator('spectre)",
        'design("tsmc28_tx_tb" "tx_drv_ML" "schematic_seriliazer_top")',
        'resultsDir("./ocean_results_all80")',
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
    for idx, row in enumerate(rows):
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
            f'printf("\\n>>> Running Sim {idx+1}/80: {test_id} ({corner}) V={vreg}V, T={temp}C | ML=({ml_p},{ml_n}) <<<\\n")',
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
    return '\n'.join(lines)


def generate_parallel_runner():
    content = """#!/bin/bash
# ==============================================================================
# run_4_jobs_parallel.sh
# Runs 4 parallel OCEAN simulation jobs in isolated subdirectories (zero lock clashes).
# Total Runtime: ~25 to 30 seconds for all 80 simulations!
# ==============================================================================

echo "================================================================="
echo " LAUNCHING 4 PARALLEL JOBS FOR 80 MISMATCHES (TT, FF, SS)"
echo " PDK Model: 1.8V (crn28hpcp_1d8_elk...)"
echo " Timestamp: $(date)"
echo "================================================================="

SCRIPT_DIR=$(pwd)
mkdir -p logs_parallel

echo ">>> [1/4] Starting Job 1: TT (Part 1, 19 cases) in background..."
(cd job1_TT_pt1 && ocean -nograph < job1_TT_pt1.ocn > "$SCRIPT_DIR/logs_parallel/job1.log" 2>&1) &
PID_1=$!

echo ">>> [2/4] Starting Job 2: TT (Part 2, 19 cases) in background..."
(cd job2_TT_pt2 && ocean -nograph < job2_TT_pt2.ocn > "$SCRIPT_DIR/logs_parallel/job2.log" 2>&1) &
PID_2=$!

echo ">>> [3/4] Starting Job 3: FF (21 cases) in background..."
(cd job3_FF && ocean -nograph < job3_FF.ocn > "$SCRIPT_DIR/logs_parallel/job3.log" 2>&1) &
PID_3=$!

echo ">>> [4/4] Starting Job 4: SS (21 cases) in background..."
(cd job4_SS && ocean -nograph < job4_SS.ocn > "$SCRIPT_DIR/logs_parallel/job4.log" 2>&1) &
PID_4=$!

echo ""
echo ">>> All 4 parallel jobs spawned! Waiting for completion (~25 seconds)..."
wait $PID_1
echo ">>> Job 1 (TT part 1) finished."
wait $PID_2
echo ">>> Job 2 (TT part 2) finished."
wait $PID_3
echo ">>> Job 3 (FF) finished."
wait $PID_4
echo ">>> Job 4 (SS) finished."

echo ""
echo "================================================================="
echo " MERGING CSVs AND EVALUATING ALL 80 SIMULATION RESULTS..."
echo "================================================================="
cp job1_TT_pt1/results_job1_TT_pt1.csv .
cp job2_TT_pt2/results_job2_TT_pt2.csv .
cp job3_FF/results_job3_FF.csv .
cp job4_SS/results_job4_SS.csv .

python compare_80_fast.py
"""
    sh_path = os.path.join(BASE_OUT, "run_4_jobs_parallel.sh")
    with open(sh_path, 'wb') as f:
        f.write(content.encode('utf-8'))
    os.chmod(sh_path, 0o755)


def generate_comparator():
    comp_content = """#!/usr/bin/env python3
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
print(f"Average Delta vs Ground Truth: Pup={df['err_pup_vs_gt'].mean():.2f} Ohm, Pdn={df['err_pdn_vs_gt'].mean():.2f} Ohm\\n")

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
"""
    comp_path = os.path.join(BASE_OUT, "compare_80_fast.py")
    with open(comp_path, 'wb') as f:
        f.write(comp_content.encode('utf-8'))
    os.chmod(comp_path, 0o755)


def main():
    tt_rows = df[df['Corner'] == 'TT'].to_dict('records')
    ff_rows = df[df['Corner'] == 'FF'].to_dict('records')
    ss_rows = df[df['Corner'] == 'SS'].to_dict('records')

    # TT split into 2 parts of 19 cases each
    tt_pt1 = tt_rows[:19]
    tt_pt2 = tt_rows[19:]

    jobs = [
        ("job1_TT_pt1", "TT", tt_pt1),
        ("job2_TT_pt2", "TT", tt_pt2),
        ("job3_FF", "FF", ff_rows),
        ("job4_SS", "SS", ss_rows)
    ]

    for j_name, corner, rows in jobs:
        j_dir = os.path.join(BASE_OUT, j_name)
        os.makedirs(j_dir, exist_ok=True)
        ocn_content = build_ocean_script(j_name, corner, rows)
        ocn_path = os.path.join(j_dir, f"{j_name}.ocn")
        with open(ocn_path, 'wb') as f:
            f.write(ocn_content.encode('utf-8'))
        print(f"Generated {j_name}/{j_name}.ocn ({len(rows)} cases)")

    # Also generate single continuous monolithic script
    mono_ocn = build_single_monolithic_ocean(df.to_dict('records'))
    with open(os.path.join(BASE_OUT, "run_all_80_mismatches.ocn"), 'wb') as f:
        f.write(mono_ocn.encode('utf-8'))
    print("Generated run_all_80_mismatches.ocn (80 cases continuous)")

    generate_parallel_runner()
    generate_comparator()
    print("Generated run_4_jobs_parallel.sh and compare_80_fast.py")
    print(f"\nAll files prepared in: {BASE_OUT}")

if __name__ == '__main__':
    main()
