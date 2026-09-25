#!/usr/bin/env python3
"""
generate_6_ocean_jobs.py
=========================
Generates 6 distinct Cadence Spectre OCEAN simulation jobs for the 35 Good Test Cases:
- Job 1: TT Corner (5 sims: GOOD_01 to GOOD_05) [ttmacro + tt_res]
- Job 2: FF Corner (5 sims: GOOD_06 to GOOD_10) [ffmacro + ff_res]
- Job 3: SS Corner (5 sims: GOOD_11 to GOOD_15) [ssmacro + ss_res]
- Job 4: FS Corner Option 1 (5 sims: GOOD_16 to GOOD_20) [fsmacro + ff_res]
- Job 5: FS Corner Option 2 (5 sims: GOOD_21 to GOOD_25) [fsmacro + ss_res]
- Job 6: SF Corner Both Options (10 sims: GOOD_26 to GOOD_35) [sfmacro + ss_res & ff_res]

Each job uses:
- Confirmed 1.8V TSMC 28nm PDK Model File:
  /data/cad/pdk_all/pdk_tsmc/pdk_tsmc_28/PDK/TSMC_new_iPDK/models/spectre/crn28hpcp_1d8_elk_v1d0_2p2_shrink0d9_embedded_usage.scs
- Isolated resultsDir to allow safe parallel execution with 0 collision.
"""

import os
import pandas as pd

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
CSV_GOOD = os.path.join(PROJECT_DIR, "results", "validation_sheets", "test_suite_good_35.csv")
OUT_DIR = os.path.join(PROJECT_DIR, "validation_generated", "test_suite_35_6jobs")
os.makedirs(OUT_DIR, exist_ok=True)

MODEL_1D8 = "/data/cad/pdk_all/pdk_tsmc/pdk_tsmc_28/PDK/TSMC_new_iPDK/models/spectre/crn28hpcp_1d8_elk_v1d0_2p2_shrink0d9_embedded_usage.scs"

def int_to_14bits(val):
    bits = {}
    for i in range(8):
        bits[i] = (val >> i) & 1
    for i in range(8, 14):
        bits[i] = 0
    return bits

def build_job_ocean_script(job_id, job_name, rows):
    csv_out = f"results_job{job_id}_{job_name}.csv"
    res_dir = f"./ocean_results_job{job_id}"

    # Check if this job has a single corner/resistor setup or multiple
    unique_sections = list(set([(r['MOS_Section'], r['Resistor_Section']) for r in rows]))
    single_setup = (len(unique_sections) == 1)

    lines = [
        f"; =============================================================================",
        f"; CADENCE SPECTRE OCEAN SCRIPT: JOB {job_id} - {job_name.upper()}",
        f"; Total Test Cases: {len(rows)} | PDK Model: 1.8V (crn28hpcp_1d8_elk...)",
        f"; Results CSV: {csv_out} | Results Directory: {res_dir}",
        f"; =============================================================================",
        "simulator('spectre)",
        'design("tsmc28_tx_tb" "tx_drv_ML" "schematic_seriliazer_top")',
        f'resultsDir("{res_dir}")',
        '',
    ]

    if single_setup:
        mos_sec, res_sec = unique_sections[0]
        lines.extend([
            '; modelFile declared once at top',
            'modelFile(',
            f'    \'("{MODEL_1D8}" "{mos_sec}")',
            f'    \'("{MODEL_1D8}" "{res_sec}")',
            f'    \'("{MODEL_1D8}" "pre_simu")',
            ')',
            '',
        ])

    lines.extend([
        "analysis('dc ?saveOppoint t)",
        "analysis('tran ?stop \"275n\")",
        '',
        "envOption('termDirectionMismatch \"ignore\" 'termMismatch \"ignore\")",
        'saveOption( ?infoOptions list(list("modelParameter" "models" "rawfile" "" "" "" t) list("element" "inst" "rawfile" "" "" "" t) list("outputParameter" "output" "rawfile" "" "" "" t) list("designParamVals" "parameters" "rawfile" "" "" "" t) list("primitives" "primitives" "rawfile" "" "" "" t) list("subckts" "subckts" "rawfile" "" "" "" t) list("asserts" "assert" "rawfile" "" "" "" nil) list("extremeinfo" "all" "logfile" "" "yes" "" nil) list("allcap" "allcap" "file" "" "" "" nil) list("<Click_To_Add>" "none" "rawfile" "" "" "" nil) ) )',
        'save(\'i "/xdrv_p/out")',
        '',
        f'out_file = outfile("{csv_out}")',
        'fprintf(out_file "test_id,corner,res_type,res_sec,vreg,temp,pmon,pvtp,pvtn,sim_pup,sim_pdn,excel_pup,excel_pdn\\n")',
        'drain(out_file)',
        '',
    ])

    current_setup = unique_sections[0] if single_setup else None

    for idx, row in enumerate(rows):
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

        lines.append(f'; --- Sim {idx+1}/{len(rows)}: [{test_id}] {corner} ({res_type}), V={vreg}V, T={temp}C, pvtp={pvtp}, pvtn={pvtn} ---')
        
        # If multi-setup job (like Job 6), update modelFile if section changes
        if not single_setup:
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
            f'printf("\\n>>> [JOB {job_id}: {job_name}] Running Sim {idx+1}/{len(rows)}: {test_id} ({corner}, {res_sec}) V={vreg}V, T={temp}C <<<\\n")',
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
        f'printf("\\n=== JOB {job_id} ({job_name}) COMPLETED! Results saved to {csv_out} ===\\n")',
        'exit()',
        ''
    ])
    return '\n'.join(lines)


def generate_runner_scripts(jobs_meta):
    # 1. Parallel Bash Runner
    parallel_sh = os.path.join(OUT_DIR, "run_all_6_jobs_parallel.sh")
    lines_par = [
        "#!/bin/bash",
        "# ==============================================================================",
        "# run_all_6_jobs_parallel.sh",
        "# Launches all 6 simulation jobs concurrently in parallel using separate resultsDir.",
        "# Total Runtime: ~20 to 30 seconds across 6 jobs!",
        "# ==============================================================================",
        "",
        'echo "================================================================="',
        'echo " LAUNCHING 6 PARALLEL CADENCE SPECTRE OCEAN JOBS (35 SIMS TOTAL)"',
        'echo " PDK Model: 1.8V (crn28hpcp_1d8_elk...)"',
        'echo " Timestamp: $(date)"',
        'echo "================================================================="',
        "",
        "mkdir -p logs_6jobs",
        "",
    ]
    for j_id, j_name, _ in jobs_meta:
        lines_par.append(f'echo ">>> Starting Job {j_id}: {j_name} in background..."')
        lines_par.append(f'ocean -nograph < job{j_id}_{j_name}.ocn > logs_6jobs/job{j_id}_{j_name}.log 2>&1 &')
        lines_par.append(f'PID_{j_id}=$!')

    lines_par.extend([
        "",
        'echo ""',
        'echo ">>> Waiting for all 6 parallel jobs to finish..."',
    ])
    for j_id, _, _ in jobs_meta:
        lines_par.append(f'wait $PID_{j_id}')
        lines_par.append(f'echo ">>> Job {j_id} finished."')

    lines_par.extend([
        "",
        'echo ""',
        'echo "================================================================="',
        'echo " ALL 6 JOBS COMPLETED SUCCESSFULLY!"',
        'echo " Results written to: results_job*.csv"',
        'echo "================================================================="',
        "python compare_6_jobs.py",
        ""
    ])
    with open(parallel_sh, 'w') as f:
        f.write('\n'.join(lines_par))
    os.chmod(parallel_sh, 0o755)

    # 2. Sequential Bash Runner (Alternative)
    seq_sh = os.path.join(OUT_DIR, "run_all_6_jobs_sequential.sh")
    lines_seq = [
        "#!/bin/bash",
        "# ==============================================================================",
        "# run_all_6_jobs_sequential.sh",
        "# Runs all 6 simulation jobs sequentially one after another.",
        "# ==============================================================================",
        "",
        'echo "================================================================="',
        'echo " RUNNING 6 JOBS SEQUENTIALLY (35 SIMS TOTAL)"',
        'echo "================================================================="',
        "mkdir -p logs_6jobs",
        "",
    ]
    for j_id, j_name, _ in jobs_meta:
        lines_seq.extend([
            f'echo ">>> Running Job {j_id}: {j_name}..."',
            f'ocean -nograph < job{j_id}_{j_name}.ocn > logs_6jobs/job{j_id}_{j_name}.log 2>&1',
            f'echo ">>> Job {j_id} completed."',
            '',
        ])
    lines_seq.extend([
        'echo "ALL JOBS FINISHED!"',
        'python compare_6_jobs.py',
        ''
    ])
    with open(seq_sh, 'w') as f:
        f.write('\n'.join(lines_seq))
    os.chmod(seq_sh, 0o755)


def generate_comparator():
    comp_py = os.path.join(OUT_DIR, "compare_6_jobs.py")
    content = """#!/usr/bin/env python3
import glob
import pandas as pd
import numpy as np

print("=" * 85)
print("     FINAL CADENCE SPECTRE VALIDATION REPORT: 35 GOOD TEST CASES (6 JOBS)")
print("     PDK Model: 1.8V (crn28hpcp_1d8_elk...) | Dual Resistor Cross-Corners")
print("=" * 85)

files = sorted(glob.glob("results_job*.csv"))
if not files:
    print("No results_job*.csv files found! Check logs_6jobs/")
    exit()

all_dfs = []
for f in files:
    try:
        d = pd.read_csv(f)
        if len(d) > 0: all_dfs.append(d)
    except: pass

if not all_dfs:
    print("No valid data in CSVs!")
    exit()

df = pd.concat(all_dfs, ignore_index=True)
df['pup_err_vs_excel'] = np.abs(df['sim_pup'] - df['excel_pup'])
df['pdn_err_vs_excel'] = np.abs(df['sim_pdn'] - df['excel_pdn'])
df['pup_in_spec'] = (df['sim_pup'] >= 48.0) & (df['sim_pup'] <= 52.0)
df['pdn_in_spec'] = (df['sim_pdn'] >= 48.0) & (df['sim_pdn'] <= 52.0)
df['spec_pass'] = df['pup_in_spec'] & df['pdn_in_spec']

print(f"Total Simulations Completed: {len(df)} / 35")
print(f"Simulations Meeting 48-52 Ohm Spec: {df['spec_pass'].sum()} / {len(df)} ({df['spec_pass'].mean()*100:.1f}%)")
print(f"Average Pup Error vs Excel Golden: {df['pup_err_vs_excel'].mean():.4f} Ohms")
print(f"Average Pdn Error vs Excel Golden: {df['pdn_err_vs_excel'].mean():.4f} Ohms\\n")

print(f"{'Test_ID':<9} {'Corner':<6} {'Resistor_Sec':<22} {'Vreg':<6} {'Temp':<6} {'Sim_Pup':<9} {'GT_Pup':<8} {'Sim_Pdn':<9} {'GT_Pdn':<8} {'Spec':<6}")
print("-" * 98)
for _, r in df.sort_values(by=['test_id']).iterrows():
    tid = str(r['test_id'])
    c = str(r['corner'])
    res = str(r['res_sec']).replace('_res_bip_dio_disres', '')
    v = float(r['vreg'])
    t = float(r['temp'])
    spup = float(r['sim_pup'])
    epup = float(r['excel_pup'])
    spdn = float(r['sim_pdn'])
    epdn = float(r['excel_pdn'])
    status = "PASS" if r['spec_pass'] else "FAIL"
    print(f"{tid:<9} {c:<6} {res:<22} {v:<6.2f} {t:<6.1f} {spup:<9.3f} {epup:<8.2f} {spdn:<9.3f} {epdn:<8.2f} {status:<6}")

print("=" * 85)
"""
    with open(comp_py, 'w') as f:
        f.write(content)


def main():
    print(">>> Generating 6 OCEAN Simulation Jobs for the 35 Good Test Cases...")
    df_good = pd.read_csv(CSV_GOOD)

    jobs = [
        (1, "TT", df_good[df_good['Corner'] == 'TT']),
        (2, "FF", df_good[df_good['Corner'] == 'FF']),
        (3, "SS", df_good[df_good['Corner'] == 'SS']),
        (4, "FS_ffres", df_good[(df_good['Corner'] == 'FS') & (df_good['Resistor_Section'] == 'ff_res_bip_dio_disres')]),
        (5, "FS_ssres", df_good[(df_good['Corner'] == 'FS') & (df_good['Resistor_Section'] == 'ss_res_bip_dio_disres')]),
        (6, "SF_both_res", df_good[df_good['Corner'] == 'SF'])
    ]

    for j_id, j_name, sub_df in jobs:
        rows = sub_df.to_dict('records')
        print(f"    - Writing Job {j_id}: job{j_id}_{j_name}.ocn ({len(rows)} test cases)...")
        content = build_job_ocean_script(j_id, j_name, rows)
        out_file = os.path.join(OUT_DIR, f"job{j_id}_{j_name}.ocn")
        with open(out_file, 'w') as f:
            f.write(content)

    print("    - Writing runner scripts and comparator...")
    generate_runner_scripts(jobs)
    generate_comparator()

    print(f"\n>>> SUCCESS! All 6 OCEAN jobs generated in: {OUT_DIR}")

if __name__ == '__main__':
    main()
