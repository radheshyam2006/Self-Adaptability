#!/usr/bin/env python3
"""
generate_80_working_mismatch_suite.py
======================================
Prepares the 80 working corner mismatch test cases (TT: 38, FF: 21, SS: 21)
split across exactly 2 jobs for robust background execution:
- Job 1: TT Corner (38 test cases)
- Job 2: FF and SS Corners (42 test cases: 21 FF + 21 SS)

Simulates using the ML PREDICTED trim bits to verify whether the model's trim
still keeps the physical transmitter impedance inside the 48-52 Ohm specification!
"""

import os
import pandas as pd

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
ALL_BAD_CSV = os.path.join(PROJECT_DIR, "results", "validation_sheets", "all_mismatches_100.csv")
OUT_DIR = os.path.join(PROJECT_DIR, "validation_generated", "test_suite_mismatches_80_2jobs")
CSV_OUT = os.path.join(PROJECT_DIR, "results", "validation_sheets", "working_mismatches_80.csv")
os.makedirs(OUT_DIR, exist_ok=True)

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

def generate_ocean_job(job_id, job_name, rows):
    csv_out = f"results_job{job_id}_{job_name}.csv"
    res_dir = f"./ocean_results_bad_job{job_id}"

    lines = [
        f"; =============================================================================",
        f"; CADENCE SPECTRE OCEAN SCRIPT: JOB {job_id} - {job_name.upper()} (MISMATCH VALIDATION)",
        f"; Total Test Cases: {len(rows)} | PDK Model: 1.8V (crn28hpcp_1d8_elk...)",
        f"; Simulating with ML PREDICTED TRIM to verify 48-52 Ohm Spec Compliance",
        f"; Results CSV: {csv_out} | Results Directory: {res_dir}",
        f"; =============================================================================",
        "simulator('spectre)",
        'design("tsmc28_tx_tb" "tx_drv_ML" "schematic_seriliazer_top")',
        f'resultsDir("{res_dir}")',
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

        # Update modelFile if corner changes
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

        # Convert ML predicted trim to 14 bits
        p_bits = int_to_14bits(ml_p)
        n_bits = int_to_14bits(ml_n)

        lines.extend([
            f'; --- Sim {idx+1}/{len(rows)}: [{test_id}] {corner}, V={vreg}V, T={temp}C | ML=({ml_p},{ml_n}) vs GT=({gt_p},{gt_n}) ---',
            f'printf("\\n>>> [JOB {job_id}: {job_name}] Sim {idx+1}/{len(rows)}: {test_id} ({corner}) V={vreg}V, T={temp}C | ML=({ml_p},{ml_n}) GT=({gt_p},{gt_n}) <<<\\n")',
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
        f'printf("\\n=== JOB {job_id} ({job_name}) FINISHED! Results in {csv_out} ===\\n")',
        'exit()',
        ''
    ])
    return '\n'.join(lines)


def generate_runner_scripts():
    # 1. 2-Job Runner that survives disconnect (runs Job 1 then Job 2 sequentially, or in parallel)
    sh_path = os.path.join(OUT_DIR, "run_2_jobs.sh")
    content = """#!/bin/bash
# ==============================================================================
# run_2_jobs.sh
# Runs the 80 working corner mismatch simulations in 2 clean sequential jobs.
# Total runtime: ~120 seconds.
# ==============================================================================

echo "================================================================="
echo " RUNNING 80 MISMATCH SIMULATIONS IN 2 JOBS (TT, FF, SS CORNERS)"
echo " PDK Model: 1.8V (crn28hpcp_1d8_elk...)"
echo " Timestamp: $(date)"
echo "================================================================="

mkdir -p logs_mismatches

echo ""
echo ">>> [1/2] Running Job 1: TT Corner (38 test cases)..."
ocean -nograph < job1_TT_38.ocn > logs_mismatches/job1_TT.log 2>&1
echo ">>> Job 1 finished."

echo ""
echo ">>> [2/2] Running Job 2: FF & SS Corners (42 test cases: 21 FF + 21 SS)..."
ocean -nograph < job2_FF_SS_42.ocn > logs_mismatches/job2_FF_SS.log 2>&1
echo ">>> Job 2 finished."

echo ""
echo "================================================================="
echo " ALL 80 MISMATCH SIMULATIONS COMPLETED!"
echo " Results written to: results_job1_TT.csv and results_job2_FF_SS.csv"
echo "================================================================="
python compare_mismatches_80.py
"""
    with open(sh_path, 'wb') as f:
        f.write(content.encode('utf-8'))
    os.chmod(sh_path, 0o755)

    # 2. Python comparator
    comp_path = os.path.join(OUT_DIR, "compare_mismatches_80.py")
    comp_content = """#!/usr/bin/env python3
import glob
import pandas as pd
import numpy as np

print("=" * 95)
print("   EVALUATION REPORT: 80 WORKING CORNER MISMATCH SIMULATIONS (TT, FF, SS)")
print("   Testing ML Predicted Trim Bits vs 48 - 52 Ohm Specification")
print("=" * 95)

files = sorted(glob.glob("results_job*.csv"))
if not files:
    print("No result CSVs found! Check logs_mismatches/")
    exit()

all_dfs = []
for f in files:
    try:
        d = pd.read_csv(f)
        if len(d) > 0 and 'sim_pup' in d.columns:
            all_dfs.append(d)
    except: pass

if not all_dfs:
    print("No valid simulation data found in CSVs!")
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

print(f"Total Mismatch Simulations: {n_tot} / 80")
print(f"Points PASSING 48-52 Ohm Spec with ML Predicted Trim: {n_pass} / {n_tot} ({pass_pct:.1f}%)")
print(f"Average Error vs Ground Truth: Pup={df['err_pup_vs_gt'].mean():.2f} Ohm, Pdn={df['err_pdn_vs_gt'].mean():.2f} Ohm\\n")

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
    with open(comp_path, 'wb') as f:
        f.write(comp_content.encode('utf-8'))
    os.chmod(comp_path, 0o755)


def main():
    print(">>> Preparing 80 Working Corner Mismatches (TT, FF, SS)...")
    df_all = pd.read_csv(ALL_BAD_CSV)
    working_df = df_all[df_all['Corner'].isin(['TT', 'FF', 'SS'])].copy()
    working_df = working_df.sort_values(by=['Corner', 'Voltage_V', 'Temp_C']).reset_index(drop=True)
    working_df['Test_ID'] = [f"BAD_{i+1:02d}" for i in range(len(working_df))]

    working_df.to_csv(CSV_OUT, index=False)
    print(f"Exported {len(working_df)} cases to {CSV_OUT}")

    # Job 1: TT Corner (38 cases)
    tt_rows = working_df[working_df['Corner'] == 'TT'].to_dict('records')
    job1_ocn = generate_ocean_job(1, "TT", tt_rows)
    with open(os.path.join(OUT_DIR, "job1_TT_38.ocn"), 'wb') as f:
        f.write(job1_ocn.encode('utf-8'))
    print(f"Generated job1_TT_38.ocn ({len(tt_rows)} test cases)")

    # Job 2: FF and SS Corners (21 FF + 21 SS = 42 cases)
    ff_ss_rows = working_df[working_df['Corner'].isin(['FF', 'SS'])].to_dict('records')
    job2_ocn = generate_ocean_job(2, "FF_SS", ff_ss_rows)
    with open(os.path.join(OUT_DIR, "job2_FF_SS_42.ocn"), 'wb') as f:
        f.write(job2_ocn.encode('utf-8'))
    print(f"Generated job2_FF_SS_42.ocn ({len(ff_ss_rows)} test cases)")

    generate_runner_scripts()
    print("Generated run_2_jobs.sh and compare_mismatches_80.py")
    print(f"\nSUCCESS! All files prepared in: {OUT_DIR}")

if __name__ == '__main__':
    main()
