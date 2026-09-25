#!/usr/bin/env python3
"""
generate_simulation_suites.py
==============================
Generates production-grade Cadence Spectre OCEAN test suites:
1. Good Test Suite (35 sims):
   - TT (5 sims, tt_res)
   - FF (5 sims, ff_res)
   - SS (5 sims, ss_res)
   - FS (10 sims: 5 with ff_res + 5 with ss_res)
   - SF (10 sims: 5 with ss_res + 5 with ff_res)
2. Bad Test Suite (Validation Mismatches):
   - TT (38 sims)
   - FF (21 sims)
   - SS (21 sims)
   - FS (10 sims with ff_res and 10 with ss_res)
   - SF (9 sims with ss_res and 9 with ff_res)

Uses the CONFIRMED 1.8V TSMC 28nm PDK Model:
'crn28hpcp_1d8_elk_v1d0_2p2_shrink0d9_embedded_usage.scs'
"""

import os
import pandas as pd

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
CSV_GOOD = os.path.join(PROJECT_DIR, "results", "validation_sheets", "test_suite_good_35.csv")
CSV_BAD = os.path.join(PROJECT_DIR, "results", "validation_sheets", "validation_bad_99.csv")

OUT_GOOD_DIR = os.path.join(PROJECT_DIR, "validation_generated", "test_suite_good_35")
OUT_BAD_DIR = os.path.join(PROJECT_DIR, "validation_generated", "test_suite_bad_99")
os.makedirs(OUT_GOOD_DIR, exist_ok=True)
os.makedirs(OUT_BAD_DIR, exist_ok=True)

MODEL_1D8 = "/data/cad/pdk_all/pdk_tsmc/pdk_tsmc_28/PDK/TSMC_new_iPDK/models/spectre/crn28hpcp_1d8_elk_v1d0_2p2_shrink0d9_embedded_usage.scs"

def int_to_14bits(val):
    bits = {}
    for i in range(8):
        bits[i] = (val >> i) & 1
    for i in range(8, 14):
        bits[i] = 0
    return bits

def generate_ocean_script(tag, suite_name, mos_sec, res_sec, rows, is_bad=False):
    csv_out = f"results_{tag}_{suite_name}.csv"
    res_dir = f"./ocean_{tag}_{suite_name}"

    lines = [
        f"; -----------------------------------------------------------------------------",
        f"; Cadence Spectre OCEAN Script: {tag.upper()} - {suite_name}",
        f"; PDK Model: TSMC 28nm 1.8V (crn28hpcp_1d8_elk...)",
        f"; MOS Section: {mos_sec} | Resistor Section: {res_sec}",
        f"; -----------------------------------------------------------------------------",
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
        'fprintf(out_file "suite,corner,res_sec,vreg,temp,pmon,pvtp_sim,pvtn_sim,gt_pvtp,gt_pvtn,sim_pup,sim_pdn,excel_pup,excel_pdn\\n")',
        'drain(out_file)',
        '',
    ]

    for idx, row in enumerate(rows):
        vreg = float(row['Voltage_V'])
        temp = float(row['Temp_C'])
        pmon = int(row['Ring_Osc_Freq_PMON_Hz'])
        
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
        corner = row['Corner']

        p_bits = int_to_14bits(pvtp_sim)
        n_bits = int_to_14bits(pvtn_sim)

        lines.extend([
            f'; --- Sim {idx+1}/{len(rows)}: {corner} ({res_sec}), Vreg={vreg}V, Temp={temp}C, pvtp={pvtp_sim}, pvtn={pvtn_sim} ---',
            f'printf("\\n>>> [{tag.upper()}] Running {suite_name} Sim {idx+1}/{len(rows)}: V={vreg}V, T={temp}C, pvtp={pvtp_sim}, pvtn={pvtn_sim} <<<\\n")',
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
            f'fprintf(out_file "{suite_name},{corner},{res_sec},{vreg},{temp},{pmon},{pvtp_sim},{pvtn_sim},{gt_p},{gt_n},%f,%f,{excel_pup},{excel_pdn}\\n" pup_val pdn_val)',
            'drain(out_file)',
            f'printf("Result -> pup=%f, pdn=%f (Excel: pup={excel_pup}, pdn={excel_pdn})\\n" pup_val pdn_val)',
            '',
        ])

    lines.extend([
        'close(out_file)',
        f'printf("\\n=== {tag.upper()} {suite_name} Complete! Results in {csv_out} ===\\n")',
        'exit()',
        ''
    ])
    return '\n'.join(lines)


def generate_bash_runner(tag, out_dir, suites):
    script_path = os.path.join(out_dir, f"run_all_{tag}.sh")
    suite_names = " ".join([s[0] for s in suites])
    content = f"""#!/bin/bash
# ==============================================================================
# run_all_{tag}.sh
# Runs {tag.upper()} test suites sequentially with 1.8V PDK model.
# ==============================================================================

echo "================================================================="
echo " STARTING TEST: {tag.upper()} SIMULATIONS"
echo " PDK Model: TSMC 28nm 1.8V Model (crn28hpcp_1d8_elk...)"
echo " Timestamp: $(date)"
echo "================================================================="

mkdir -p {tag}_logs

for suite in {suite_names}; do
    echo ""
    echo ">>> Running Suite $suite ({tag})..."
    ocean -nograph < run_{tag}_$suite.ocn > {tag}_logs/$suite.log 2>&1
    echo ">>> Suite $suite finished."
done

echo ""
echo "================================================================="
echo " ALL {tag.upper()} SIMULATIONS FINISHED!"
echo " Results written to: results_{tag}_*.csv"
echo "================================================================="
python compare_{tag}.py
"""
    with open(script_path, 'w') as f:
        f.write(content)
    os.chmod(script_path, 0o755)
    return script_path


def generate_comparator(tag, out_dir):
    comp_path = os.path.join(out_dir, f"compare_{tag}.py")
    content = f"""#!/usr/bin/env python3
import glob
import pandas as pd
import numpy as np

print("=" * 75)
print("  EVALUATION REPORT: {tag.upper()} SIMULATION SUITE")
print("  PDK Model: 1.8V (crn28hpcp_1d8_elk...)")
print("=" * 75)

files = sorted(glob.glob("results_{tag}_*.csv"))
if not files:
    print("No result files found! Check {tag}_logs/")
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

print(f"Total Sims Completed: {{len(df)}}")
print(f"Points meeting 48-52 Ohm Spec: {{df['spec_pass'].sum()}} / {{len(df)}} ({{df['spec_pass'].mean()*100:.1f}}%)\\n")

print(f"{{'Suite':<16}} {{'Corner':<6}} {{'Res_Sec':<22}} {{'Vreg':<6}} {{'Temp':<6}} {{'Sim_Pup':<9}} {{'GT_Pup':<8}} {{'Sim_Pdn':<9}} {{'GT_Pdn':<8}} {{'Spec':<6}}")
print("-" * 105)
for _, r in df.iterrows():
    s = str(r['suite'])
    c = str(r['corner'])
    res = str(r['res_sec']).replace('_res_bip_dio_disres', '')
    v = float(r['vreg'])
    t = float(r['temp'])
    spup = float(r['sim_pup'])
    epup = float(r['excel_pup'])
    spdn = float(r['sim_pdn'])
    epdn = float(r['excel_pdn'])
    status = "PASS" if r['spec_pass'] else "FAIL"
    print(f"{{s:<16}} {{c:<6}} {{res:<22}} {{v:<6.2f}} {{t:<6.1f}} {{spup:<9.3f}} {{epup:<8.2f}} {{spdn:<9.3f}} {{epdn:<8.2f}} {{status:<6}}")

print("=" * 75)
"""
    with open(comp_path, 'w') as f:
        f.write(content)
    return comp_path


def main():
    print(">>> Building OCEAN Simulation Suites for Good and Bad Cases...")
    df_good = pd.read_csv(CSV_GOOD)
    df_bad = pd.read_csv(CSV_BAD)

    # 1. Good Cases (35 runs)
    good_suites = [
        ('TT', 'ttmacro_mos_moscap', 'tt_res_bip_dio_disres', df_good[df_good['Corner'] == 'TT']),
        ('FF', 'ffmacro_mos_moscap', 'ff_res_bip_dio_disres', df_good[df_good['Corner'] == 'FF']),
        ('SS', 'ssmacro_mos_moscap', 'ss_res_bip_dio_disres', df_good[df_good['Corner'] == 'SS']),
        ('FS_ffres', 'fsmacro_mos_moscap', 'ff_res_bip_dio_disres', df_good[(df_good['Corner'] == 'FS') & (df_good['Resistor_Section'] == 'ff_res_bip_dio_disres')]),
        ('FS_ssres', 'fsmacro_mos_moscap', 'ss_res_bip_dio_disres', df_good[(df_good['Corner'] == 'FS') & (df_good['Resistor_Section'] == 'ss_res_bip_dio_disres')]),
        ('SF_ssres', 'sfmacro_mos_moscap', 'ss_res_bip_dio_disres', df_good[(df_good['Corner'] == 'SF') & (df_good['Resistor_Section'] == 'ss_res_bip_dio_disres')]),
        ('SF_ffres', 'sfmacro_mos_moscap', 'ff_res_bip_dio_disres', df_good[(df_good['Corner'] == 'SF') & (df_good['Resistor_Section'] == 'ff_res_bip_dio_disres')]),
    ]

    for s_name, mos, res, sub_df in good_suites:
        rows = sub_df.to_dict('records')
        content = generate_ocean_script("good", s_name, mos, res, rows, is_bad=False)
        with open(os.path.join(OUT_GOOD_DIR, f"run_good_{s_name}.ocn"), 'w') as f:
            f.write(content)

    generate_bash_runner("good", OUT_GOOD_DIR, good_suites)
    generate_comparator("good", OUT_GOOD_DIR)

    # 2. Bad Cases (Validation Mismatches)
    bad_suites = [
        ('TT', 'ttmacro_mos_moscap', 'tt_res_bip_dio_disres', df_bad[df_bad['Corner'] == 'TT']),
        ('FF', 'ffmacro_mos_moscap', 'ff_res_bip_dio_disres', df_bad[df_bad['Corner'] == 'FF']),
        ('SS', 'ssmacro_mos_moscap', 'ss_res_bip_dio_disres', df_bad[df_bad['Corner'] == 'SS']),
        ('FS_ffres', 'fsmacro_mos_moscap', 'ff_res_bip_dio_disres', df_bad[df_bad['Corner'] == 'FS']),
        ('FS_ssres', 'fsmacro_mos_moscap', 'ss_res_bip_dio_disres', df_bad[df_bad['Corner'] == 'FS']),
        ('SF_ssres', 'sfmacro_mos_moscap', 'ss_res_bip_dio_disres', df_bad[df_bad['Corner'] == 'SF']),
        ('SF_ffres', 'sfmacro_mos_moscap', 'ff_res_bip_dio_disres', df_bad[df_bad['Corner'] == 'SF']),
    ]

    for s_name, mos, res, sub_df in bad_suites:
        rows = sub_df.to_dict('records')
        if len(rows) > 0:
            content = generate_ocean_script("bad", s_name, mos, res, rows, is_bad=True)
            with open(os.path.join(OUT_BAD_DIR, f"run_bad_{s_name}.ocn"), 'w') as f:
                f.write(content)

    generate_bash_runner("bad", OUT_BAD_DIR, [s for s in bad_suites if len(s[3]) > 0])
    generate_comparator("bad", OUT_BAD_DIR)

    print(">>> All simulation test suites successfully created!")
    print(f"  - Good Suite: {OUT_GOOD_DIR}")
    print(f"  - Bad Suite:  {OUT_BAD_DIR}")

if __name__ == '__main__':
    main()
