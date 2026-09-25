#!/usr/bin/env python3
"""
generate_10_test_suite.py
==========================
Generates rock-solid test suites matching run_corners_final.ocn structure:
1. test_10_correct: 10 test cases where ML model predicted 100% exact match.
   Verifies Cadence Spectre simulation vs Excel ground truth.
2. test_10_bad: 10 test cases where ML model differed from golden.
   Simulates in Spectre with the ML PREDICTED trim to verify if resistance still meets 48-52 Ohm spec.

Each corner script has modelFile set ONCE at the top and calls exit() at the bottom.
Runs sequentially with 0% risk of netlist collision or MPSC failure.
"""

import os
import pandas as pd

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
CORRECT_CSV = os.path.join(PROJECT_DIR, "results", "validation_sheets", "test_10_correct.csv")
BAD_CSV = os.path.join(PROJECT_DIR, "results", "validation_sheets", "test_10_bad.csv")

OUT_CORRECT_DIR = os.path.join(PROJECT_DIR, "validation_generated", "test_10_correct")
OUT_BAD_DIR = os.path.join(PROJECT_DIR, "validation_generated", "test_10_bad")
os.makedirs(OUT_CORRECT_DIR, exist_ok=True)
os.makedirs(OUT_BAD_DIR, exist_ok=True)

MODEL_1D8 = "/data/cad/pdk_all/pdk_tsmc/pdk_tsmc_28/PDK/TSMC_new_iPDK/models/spectre/crn28hpcp_1d8_elk_v1d0_2p2_shrink0d9_embedded_usage.scs"

CORNER_SECTIONS = {
    'TT': ('ttmacro_mos_moscap', 'tt_res_bip_dio_disres'),
    'FF': ('ffmacro_mos_moscap', 'ff_res_bip_dio_disres'),
    'SS': ('ssmacro_mos_moscap', 'ss_res_bip_dio_disres'),
    'FS': ('fsmacro_mos_moscap', 'ff_res_bip_dio_disres'),
    'SF': ('sfmacro_mos_moscap', 'ss_res_bip_dio_disres'),
}

def int_to_14bits(val):
    bits = {}
    for i in range(8):
        bits[i] = (val >> i) & 1
    for i in range(8, 14):
        bits[i] = 0
    return bits

def generate_corner_ocn(corner, rows, is_bad=False):
    mos_sec, res_sec = CORNER_SECTIONS[corner]
    tag = "bad" if is_bad else "correct"
    csv_out = f"results_{tag}_{corner}.csv"
    res_dir = f"./ocean_{tag}_{corner}"

    lines = [
        f"; -------------------------------------------------------------",
        f"; Test Suite: {tag.upper()} - Corner {corner}",
        f"; modelFile declared ONCE at top (matching run_corners_final.ocn)",
        f"; -------------------------------------------------------------",
        "simulator('spectre)",
        'design("tsmc28_tx_tb" "tx_drv_ML" "schematic_seriliazer_top")',
        f'resultsDir("{res_dir}")',
        '',
        'modelFile(',
        f'    \'("{MODEL_1D8}" "{mos_sec}")',
        f'    \'("{MODEL_1D8}" "{res_sec}")',
        f'    \'("{MODEL_1D8}" "pre_simu")',
        ')',
        "analysis('dc ?saveOppoint t)",
        "analysis('tran ?stop \"275n\")",
        '',
        "envOption('termDirectionMismatch \"ignore\" 'termMismatch \"ignore\")",
        'saveOption( ?infoOptions list(list("modelParameter" "models" "rawfile" "" "" "" t) list("element" "inst" "rawfile" "" "" "" t) list("outputParameter" "output" "rawfile" "" "" "" t) list("designParamVals" "parameters" "rawfile" "" "" "" t) list("primitives" "primitives" "rawfile" "" "" "" t) list("subckts" "subckts" "rawfile" "" "" "" t) list("asserts" "assert" "rawfile" "" "" "" nil) list("extremeinfo" "all" "logfile" "" "yes" "" nil) list("allcap" "allcap" "file" "" "" "" nil) list("<Click_To_Add>" "none" "rawfile" "" "" "" nil) ) )',
        'save(\'i "/xdrv_p/out")',
        '',
        f'out_file = outfile("{csv_out}")',
        'fprintf(out_file "corner,vreg,temp,pmon,pvtp_sim,pvtn_sim,gt_pvtp,gt_pvtn,sim_pup,sim_pdn,excel_pup,excel_pdn\\n")',
        'drain(out_file)',
        '',
    ]

    for idx, row in enumerate(rows):
        vreg = float(row['Voltage_V'])
        temp = float(row['Temp_C'])
        pmon = int(row['Ring_Osc_Freq_PMON_Hz'])
        
        # If testing "bad", use ML predicted trim! If "correct", use Ground truth
        if is_bad:
            pvtp_sim = int(row['ML_Predicted_PVTP_Int'])
            pvtn_sim = int(row['ML_Predicted_PVTN_Int'])
        else:
            pvtp_sim = int(row['Ground_Truth_PVTP_Int'])
            pvtn_sim = int(row['Ground_Truth_PVTN_Int'])

        gt_p = int(row['Ground_Truth_PVTP_Int'])
        gt_n = int(row['Ground_Truth_PVTN_Int'])
        excel_pup = float(row['Ground_Truth_Target_Pup_Ohm'])
        excel_pdn = float(row['Ground_Truth_Target_Pdn_Ohm'])

        p_bits = int_to_14bits(pvtp_sim)
        n_bits = int_to_14bits(pvtn_sim)

        lines.extend([
            f'; --- Sim {idx+1}: {corner}, Vreg={vreg}V, Temp={temp}C, pvtp={pvtp_sim}, pvtn={pvtn_sim} ---',
            f'printf("\\n>>> [{tag.upper()}] Running {corner} Sim {idx+1}: Vreg={vreg}V, Temp={temp}C, pvtp={pvtp_sim}, pvtn={pvtn_sim} <<<\\n")',
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
            f'fprintf(out_file "{corner},{vreg},{temp},{pmon},{pvtp_sim},{pvtn_sim},{gt_p},{gt_n},%f,%f,{excel_pup},{excel_pdn}\\n" pup_val pdn_val)',
            'drain(out_file)',
            f'printf("Sim {idx+1} Result -> pup=%f, pdn=%f (Excel: pup={excel_pup}, pdn={excel_pdn})\\n" pup_val pdn_val)',
            '',
        ])

    lines.extend([
        'close(out_file)',
        f'printf("\\n=== {tag.upper()} {corner} Complete! Results in {csv_out} ===\\n")',
        'exit()',
        ''
    ])
    return '\n'.join(lines)


def generate_bash_runner(tag, out_dir):
    script_path = os.path.join(out_dir, f"run_test_10_{tag}.sh")
    content = f"""#!/bin/bash
# ==============================================================================
# run_test_10_{tag}.sh
# Runs 10 {tag} simulations across 5 corners sequentially (no collisions).
# Total runtime: ~60 to 90 seconds.
# ==============================================================================

echo "================================================================="
echo " STARTING TEST: 10 {tag.upper()} SIMULATIONS ACROSS 5 CORNERS"
echo " Timestamp: $(date)"
echo "================================================================="

mkdir -p test_{tag}_logs

for corner in TT FF SS FS SF; do
    echo ""
    echo ">>> Running Corner $corner ({tag})..."
    ocean -nograph < run_{tag}_$corner.ocn > test_{tag}_logs/$corner.log 2>&1
    echo ">>> Corner $corner finished."
done

echo ""
echo "================================================================="
echo " ALL 10 {tag.upper()} SIMULATIONS FINISHED!"
echo " Results written to: results_{tag}_*.csv"
echo "================================================================="
python compare_10_{tag}.py
"""
    with open(script_path, 'w') as f:
        f.write(content)
    os.chmod(script_path, 0o755)
    return script_path


def generate_comparator(tag, out_dir):
    comp_path = os.path.join(out_dir, f"compare_10_{tag}.py")
    content = f"""#!/usr/bin/env python3
import glob
import pandas as pd
import numpy as np

print("=" * 70)
print("  EVALUATION REPORT: 10 {tag.upper()} SIMULATIONS")
print("=" * 70)

files = sorted(glob.glob("results_{tag}_*.csv"))
if not files:
    print("No result files found! Check test_{tag}_logs/")
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

print(f"Total Sims Completed: {{len(df)}} / 10")
print(f"Points meeting 48-52 Ohm spec: {{df['spec_pass'].sum()}} / {{len(df)}} ({{df['spec_pass'].mean()*100:.1f}}%)\\n")

print(f"{{'Corner':<8}} {{'Vreg':<6}} {{'Temp':<6}} {{'PVTP':<6}} {{'PVTN':<6}} {{'Sim_Pup':<9}} {{'Excel_Pup':<10}} {{'Sim_Pdn':<9}} {{'Excel_Pdn':<10}} {{'Spec':<6}}")
print("-" * 88)
for _, r in df.iterrows():
    c = str(r['corner'])
    v = float(r['vreg'])
    t = float(r['temp'])
    p = int(r['pvtp_sim'])
    n = int(r['pvtn_sim'])
    spup = float(r['sim_pup'])
    epup = float(r['excel_pup'])
    spdn = float(r['sim_pdn'])
    epdn = float(r['excel_pdn'])
    status = "PASS" if r['spec_pass'] else "FAIL"
    print(f"{{c:<8}} {{v:<6.2f}} {{t:<6.1f}} {{p:<6}} {{n:<6}} {{spup:<9.3f}} {{epup:<10.3f}} {{spdn:<9.3f}} {{epdn:<10.3f}} {{status:<6}}")

print("=" * 70)
"""
    with open(comp_path, 'w') as f:
        f.write(content)
    return comp_path


def main():
    print("Generating 10 Correct and 10 Bad Test Suites...")
    df_correct = pd.read_csv(CORRECT_CSV)
    df_bad = pd.read_csv(BAD_CSV)

    for corner in ['TT', 'FF', 'SS', 'FS', 'SF']:
        # 1. Correct
        c_rows = df_correct[df_correct['Corner'] == corner].to_dict('records')
        ocn_content = generate_corner_ocn(corner, c_rows, is_bad=False)
        ocn_file = os.path.join(OUT_CORRECT_DIR, f"run_correct_{corner}.ocn")
        with open(ocn_file, 'w') as f: f.write(ocn_content)

        # 2. Bad
        b_rows = df_bad[df_bad['Corner'] == corner].to_dict('records')
        b_ocn_content = generate_corner_ocn(corner, b_rows, is_bad=True)
        b_ocn_file = os.path.join(OUT_BAD_DIR, f"run_bad_{corner}.ocn")
        with open(b_ocn_file, 'w') as f: f.write(b_ocn_content)

    generate_bash_runner("correct", OUT_CORRECT_DIR)
    generate_comparator("correct", OUT_CORRECT_DIR)

    generate_bash_runner("bad", OUT_BAD_DIR)
    generate_comparator("bad", OUT_BAD_DIR)

    print(f"Done! Created suites in:")
    print(f"  - {OUT_CORRECT_DIR}")
    print(f"  - {OUT_BAD_DIR}")

if __name__ == '__main__':
    main()
