#!/usr/bin/env python3
"""
generate_validation.py
======================
Master generator for Cadence Spectre validation scripts:
- Phase 0: Model File Discrimination Benchmark (5 test cases x 2 model files = 10 sims)
- Phase 1: Sanity Check (5 test cases x 5 corners = 25 sims)
- Phase 2: Full Test-Set Validation (3,177 test cases batched by 50)

Features:
- Pure Spectre transient simulation (analog only, no mixed-signal AMS overhead)
- Exact steady-state impedance extraction: average(clip(..., 200ns, 250ns))
- Configurable tran stop time (default 275ns, optional 500ns)
- Valid PDK resistor sections (TSMC 28nm: FS uses ff_res, SF uses ss_res matching Maestro)
- Independent resultsDir per script to prevent parallel PSF collision
- Real-time disk flushing (drain(out_file)) after every single row
"""

import os
import sys
import argparse
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
EXCEL_PATH = os.path.join(PROJECT_DIR, "data", "TSMC28nm_DRV_ML_MAR6_LookUP_Table_Mar20_ML Predictions.xlsx")
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "validation_generated")

# Server model paths
MODEL_2D5 = "/data/cad/pdk_all/pdk_tsmc/pdk_tsmc_28/PDK/TSMC_new_iPDK/models/spectre/crn28hpcp_2d5_elk_v1d0_2p2_shrink0d9_embedded_usage.scs"
MODEL_1D8 = "/data/cad/pdk_all/pdk_tsmc/pdk_tsmc_28/PDK/TSMC_new_iPDK/models/spectre/crn28hpcp_1d8_elk_v1d0_2p2_shrink0d9_embedded_usage.scs"

# Valid TSMC 28nm PDK sections:
# (Resistors only have tt, ff, ss sections; FS pairs with ff_res, SF pairs with ss_res)
CORNER_SECTIONS = {
    'TT': ('ttmacro_mos_moscap', 'tt_res_bip_dio_disres'),
    'FF': ('ffmacro_mos_moscap', 'ff_res_bip_dio_disres'),
    'SS': ('ssmacro_mos_moscap', 'ss_res_bip_dio_disres'),
    'FS': ('fsmacro_mos_moscap', 'ff_res_bip_dio_disres'),
    'SF': ('sfmacro_mos_moscap', 'ss_res_bip_dio_disres'),
}

CORNER_SHEETS = {
    'TT': 'TT_vdd_test',
    'FF': 'FF_vdd_temp',
    'SS': 'SS_vdd_test',
    'FS': 'FS_vdd_test',
    'SF': 'SF_vdd_test',
}


def pad8(val):
    if pd.isna(val) or str(val).strip().lower() == 'na':
        return None
    return str(val).replace('-', '').strip().zfill(8)


def int_to_14bits(val):
    """Convert integer to 14 bits (bits 0..7 from integer, bits 8..13 zero)."""
    bits = {}
    for i in range(8):
        bits[i] = (val >> i) & 1
    for i in range(8, 14):
        bits[i] = 0
    return bits


def generate_ocean_header(model_file, mos_section, res_section, results_dir="./ocean_results", tran_stop="275n"):
    lines = [
        "simulator('spectre)",
        'design("tsmc28_tx_tb" "tx_drv_ML" "schematic_seriliazer_top")',
        f'resultsDir("{results_dir}")',
        '',
        'modelFile(',
        f'    \'("{model_file}" "{mos_section}")',
        f'    \'("{model_file}" "{res_section}")',
        f'    \'("{model_file}" "pre_simu")',
        ')',
        f'analysis(\'tran ?stop "{tran_stop}")',
        '',
        "envOption('termDirectionMismatch \"ignore\" 'termMismatch \"ignore\")",
        'saveOption( ?infoOptions list(list("modelParameter" "models" "rawfile" "" "" "" t) list("element" "inst" "rawfile" "" "" "" t) list("outputParameter" "output" "rawfile" "" "" "" t) list("designParamVals" "parameters" "rawfile" "" "" "" t) list("primitives" "primitives" "rawfile" "" "" "" t) list("subckts" "subckts" "rawfile" "" "" "" t) list("asserts" "assert" "rawfile" "" "" "" nil) list("extremeinfo" "all" "logfile" "" "yes" "" nil) list("allcap" "allcap" "file" "" "" "" nil) list("<Click_To_Add>" "none" "rawfile" "" "" "" nil) ) )',
        'save(\'i "/xdrv_p/out")',
        '',
    ]
    return lines


def generate_sim_block(sim_id, corner, vreg, temp, pmon, pvtp_int, pvtn_int, excel_pup, excel_pdn, out_var="out_file"):
    p_bits = int_to_14bits(pvtp_int)
    n_bits = int_to_14bits(pvtn_int)

    lines = [
        f'; --- Sim {sim_id}: Corner={corner}, Vreg={vreg}V, Temp={temp}C, pvtp={pvtp_int}, pvtn={pvtn_int} ---',
        f'printf("\\n[Sim {sim_id}] Running {corner} at Vreg={vreg}, Temp={temp}...\\n")',
        f'desVar("tem" {temp})',
        f'desVar("vreg" {vreg})',
        f'temp({temp})',
    ]

    for i in range(14):
        lines.append(f'desVar("pvt{i}" {p_bits[i]})')
    for i in range(14):
        lines.append(f'desVar("pvtn{i}" {n_bits[i]})')

    lines.extend([
        'run()',
        "selectResults('tran)",
        '',
        '; Steady-state 200ns-250ns time-average extraction (matching Maestro GUI)',
        'pup_val = average((clip((v("/vdd" ?result "tran") - v("/outn" ?result "tran")) 2e-07 2.5e-07) / clip(i("/xdrv_p/out" ?result "tran") 2e-07 2.5e-07)))',
        'pdn_val = (average((clip(v("/outp" ?result "tran") 2e-07 2.5e-07) / clip(i("/xdrv_p/out" ?result "tran") 2e-07 2.5e-07))) * -1)',
        '',
        f'fprintf({out_var} "{sim_id},{corner},{vreg},{temp},{pmon},{pvtp_int},{pvtn_int},%f,%f,{excel_pup},{excel_pdn}\\n" pup_val pdn_val)',
        f'drain({out_var})',  # Flush immediately to disk!
        f'printf("Result Sim {sim_id} -> pup=%f, pdn=%f (Excel: pup={excel_pup}, pdn={excel_pdn})\\n" pup_val pdn_val)',
        '',
    ])
    return lines


def generate_phase0(out_dir, tran_stop="275n"):
    """Phase 0: Run 5 benchmark rows against 2d5 and 1d8 model files."""
    print("\n--- Generating Phase 0 (Model Discrimination Benchmark) ---")
    p0_dir = os.path.join(out_dir, "phase0")
    os.makedirs(p0_dir, exist_ok=True)

    xl = pd.ExcelFile(EXCEL_PATH)
    benchmarks = []

    for corner, sheet in CORNER_SHEETS.items():
        df = xl.parse(sheet)
        sub = df[(df['vreg'].between(0.88, 0.92)) & (df['temperature'].between(18.0, 26.0))]
        if len(sub) == 0:
            sub = df.iloc[[len(df) // 2]]
        row = sub.iloc[0]

        p_col = 'ML data up driver\npvtp<7:0>' if 'ML data up driver\npvtp<7:0>' in df.columns else 'ML data up driver\npvtp<5:0>'
        n_col = 'ML data DN driver\npvtn<7:0>' if 'ML data DN driver\npvtn<7:0>' in df.columns else 'ML data DN driver\npvtn<5:0>'

        pvtp_raw = pad8(row[p_col])
        pvtn_raw = pad8(row[n_col])
        pvtp_int = int(pvtp_raw, 2)
        pvtn_int = int(pvtn_raw, 2)

        excel_pup = abs(float(row['PULL_UP_RES\nnew value']))
        excel_pdn = abs(float(row['PULL_DN_RES\nnew value']))

        benchmarks.append({
            'corner': corner,
            'vreg': float(row['vreg']),
            'temp': float(row['temperature']),
            'pmon': int(row['pmon_cmos_res']),
            'pvtp_int': pvtp_int,
            'pvtn_int': pvtn_int,
            'excel_pup': excel_pup,
            'excel_pdn': excel_pdn
        })

    # Save benchmark ground truth CSV
    pd.DataFrame(benchmarks).to_csv(os.path.join(p0_dir, "phase0_ground_truth.csv"), index=False)

    # Generate scripts for 2d5 and 1d8 with SEPARATE resultsDir!
    for model_tag, model_path in [('2d5', MODEL_2D5), ('1d8', MODEL_1D8)]:
        script_file = os.path.join(p0_dir, f"run_phase0_{model_tag}.ocn")
        csv_file = f"results_phase0_{model_tag}.csv"
        res_dir = f"./ocean_results_phase0_{model_tag}"

        lines = [
            f"; Phase 0 Benchmark Test: Model File {model_tag}",
            f"; Comparing against Excel ground truth across 5 corners",
            "",
        ]

        mos_sec, res_sec = CORNER_SECTIONS['TT']
        lines.extend(generate_ocean_header(model_path, mos_sec, res_sec, results_dir=res_dir, tran_stop=tran_stop))

        lines.extend([
            f'out_file = outfile("{csv_file}")',
            'fprintf(out_file "sim_id,corner,vreg,temperature,pmon,pvtp_int,pvtn_int,sim_pup,sim_pdn,excel_pup,excel_pdn\\n")',
            'drain(out_file)',
            '',
        ])

        for idx, item in enumerate(benchmarks):
            c = item['corner']
            mos, res = CORNER_SECTIONS[c]
            lines.extend([
                f'; Update model sections for corner {c}',
                'modelFile(',
                f'    \'("{model_path}" "{mos}")',
                f'    \'("{model_path}" "{res}")',
                f'    \'("{model_path}" "pre_simu")',
                ')',
            ])
            lines.extend(generate_sim_block(
                idx + 1, c, item['vreg'], item['temp'], item['pmon'],
                item['pvtp_int'], item['pvtn_int'], item['excel_pup'], item['excel_pdn']
            ))

        lines.extend([
            'close(out_file)',
            f'printf("\\n=== Phase 0 ({model_tag}) Complete! Check {csv_file} ===\\n")',
        ])

        with open(script_file, 'w') as f:
            f.write('\n'.join(lines))
        print(f"  Created: {script_file}")

    print(f"Phase 0 generation complete in: {p0_dir}")


def generate_phase1(out_dir, model_file, tran_stop="275n"):
    """Phase 1: 5 representative tests per corner (25 total) for sanity check."""
    print("\n--- Generating Phase 1 (Sanity Check: 25 Sims) ---")
    p1_dir = os.path.join(out_dir, "phase1")
    os.makedirs(p1_dir, exist_ok=True)

    xl = pd.ExcelFile(EXCEL_PATH)

    for corner, sheet in CORNER_SECTIONS.items():
        df = xl.parse(CORNER_SHEETS[corner])
        mos_sec, res_sec = CORNER_SECTIONS[corner]

        t_low = df[df['temperature'] <= -35].iloc[0]
        t_mid = df[df['temperature'].between(20, 30)].iloc[0]
        t_high = df[df['temperature'] >= 120].iloc[0]
        v_low = df[df['vreg'] <= 0.82].iloc[0]
        v_high = df[df['vreg'] >= 0.98].iloc[0]

        selected_rows = [t_low, t_mid, t_high, v_low, v_high]

        script_file = os.path.join(p1_dir, f"run_phase1_{corner}.ocn")
        csv_file = f"results_phase1_{corner}.csv"
        res_dir = f"./ocean_results_phase1_{corner}"

        lines = [
            f"; Phase 1 Sanity Check: Corner {corner} (5 test cases)",
            "",
        ]
        lines.extend(generate_ocean_header(model_file, mos_sec, res_sec, results_dir=res_dir, tran_stop=tran_stop))
        lines.extend([
            f'out_file = outfile("{csv_file}")',
            'fprintf(out_file "sim_id,corner,vreg,temperature,pmon,pvtp_int,pvtn_int,sim_pup,sim_pdn,excel_pup,excel_pdn\\n")',
            'drain(out_file)',
            '',
        ])

        p_col = 'ML data up driver\npvtp<7:0>' if 'ML data up driver\npvtp<7:0>' in df.columns else 'ML data up driver\npvtp<5:0>'
        n_col = 'ML data DN driver\npvtn<7:0>' if 'ML data DN driver\npvtn<7:0>' in df.columns else 'ML data DN driver\npvtn<5:0>'

        for idx, row in enumerate(selected_rows):
            pvtp_int = int(pad8(row[p_col]), 2)
            pvtn_int = int(pad8(row[n_col]), 2)
            excel_pup = abs(float(row['PULL_UP_RES\nnew value']))
            excel_pdn = abs(float(row['PULL_DN_RES\nnew value']))

            lines.extend(generate_sim_block(
                idx + 1, corner, float(row['vreg']), float(row['temperature']),
                int(row['pmon_cmos_res']), pvtp_int, pvtn_int, excel_pup, excel_pdn
            ))

        lines.extend([
            'close(out_file)',
            f'printf("\\n=== Phase 1 {corner} Complete! Check {csv_file} ===\\n")',
        ])

        with open(script_file, 'w') as f:
            f.write('\n'.join(lines))
        print(f"  Created: {script_file}")

    print(f"Phase 1 generation complete in: {p1_dir}")


def generate_phase2(out_dir, model_file, tran_stop="275n", batch_size=50):
    """Phase 2: Full 3,177 test set simulations batched by corner."""
    print("\n--- Generating Phase 2 (Full Validation: 3,177 Sims) ---")
    p2_dir = os.path.join(out_dir, "phase2")
    os.makedirs(p2_dir, exist_ok=True)

    xl = pd.ExcelFile(EXCEL_PATH)
    all_rows = []

    for c, s in CORNER_SHEETS.items():
        df = xl.parse(s)
        p_col = 'ML data up driver\npvtp<7:0>' if 'ML data up driver\npvtp<7:0>' in df.columns else 'ML data up driver\npvtp<5:0>'
        n_col = 'ML data DN driver\npvtn<7:0>' if 'ML data DN driver\npvtn<7:0>' in df.columns else 'ML data DN driver\npvtn<5:0>'

        for idx, r in df.iterrows():
            pvtp_raw = pad8(r[p_col])
            pvtn_raw = pad8(r[n_col])
            if pvtp_raw is None or pvtn_raw is None:
                continue
            all_rows.append({
                'corner': c,
                'vreg': float(r['vreg']),
                'temp': float(r['temperature']),
                'pmon': int(r['pmon_cmos_res']),
                'pvtp_int': int(pvtp_raw, 2),
                'pvtn_int': int(pvtn_raw, 2),
                'excel_pup': abs(float(r['PULL_UP_RES\nnew value'])),
                'excel_pdn': abs(float(r['PULL_DN_RES\nnew value'])),
            })

    full_df = pd.DataFrame(all_rows)
    print(f"Total dataset: {len(full_df)} rows")

    # Recreate the exact 80/20 train/test split from final_model.py
    corners = full_df['corner'].values
    indices = np.arange(len(full_df))
    _, test_idx = train_test_split(indices, test_size=0.2, random_state=42, stratify=corners)
    test_df = full_df.iloc[test_idx].reset_index(drop=True)
    print(f"Held-out test set: {len(test_df)} rows")

    # Save test set ground truth
    test_df.to_csv(os.path.join(p2_dir, "phase2_test_set.csv"), index=False)

    total_batches = 0
    for corner in ['TT', 'SS', 'FF', 'FS', 'SF']:
        c_df = test_df[test_df['corner'] == corner].reset_index(drop=True)
        mos_sec, res_sec = CORNER_SECTIONS[corner]
        n_batches = (len(c_df) + batch_size - 1) // batch_size
        print(f"  {corner}: {len(c_df)} test rows -> {n_batches} batches")

        for b_id in range(n_batches):
            start = b_id * batch_size
            end = min(start + batch_size, len(c_df))
            b_df = c_df.iloc[start:end]

            script_file = os.path.join(p2_dir, f"run_phase2_{corner}_batch{b_id:03d}.ocn")
            csv_file = f"results_phase2_{corner}_batch{b_id:03d}.csv"
            res_dir = f"./ocean_results_{corner}_b{b_id:03d}"

            lines = [
                f"; Phase 2: Corner {corner}, Batch {b_id} ({len(b_df)} simulations)",
                "",
            ]
            lines.extend(generate_ocean_header(model_file, mos_sec, res_sec, results_dir=res_dir, tran_stop=tran_stop))
            lines.extend([
                f'out_file = outfile("{csv_file}")',
                'fprintf(out_file "sim_id,corner,vreg,temperature,pmon,pvtp_int,pvtn_int,sim_pup,sim_pdn,excel_pup,excel_pdn\\n")',
                'drain(out_file)',
                '',
            ])

            for s_idx, (_, row) in enumerate(b_df.iterrows()):
                lines.extend(generate_sim_block(
                    start + s_idx + 1, corner, row['vreg'], row['temp'],
                    row['pmon'], row['pvtp_int'], row['pvtn_int'],
                    row['excel_pup'], row['excel_pdn']
                ))

            lines.extend([
                'close(out_file)',
                f'printf("\\n=== Phase 2 {corner} Batch {b_id} Complete! ===\\n")',
            ])

            with open(script_file, 'w') as f:
                f.write('\n'.join(lines))
            total_batches += 1

    print(f"Phase 2 generation complete: {total_batches} batch scripts in {p2_dir}")


def main():
    parser = argparse.ArgumentParser(description="Generate Cadence Spectre Validation Scripts")
    parser.add_argument("--phase", type=str, default="all", choices=["0", "1", "2", "all"], help="Validation phase to generate")
    parser.add_argument("--tran-stop", type=str, default="275n", help="Transient stop time (default: 275n, optional: 500n)")
    parser.add_argument("--model", type=str, default="2d5", choices=["2d5", "1d8"], help="Model file to use for Phase 1/2")
    parser.add_argument("--outdir", type=str, default=OUTPUT_DIR, help="Output directory")

    args = parser.parse_args()
    os.makedirs(args.outdir, exist_ok=True)

    chosen_model = MODEL_2D5 if args.model == "2d5" else MODEL_1D8

    if args.phase in ["0", "all"]:
        generate_phase0(args.outdir, tran_stop=args.tran_stop)

    if args.phase in ["1", "all"]:
        generate_phase1(args.outdir, chosen_model, tran_stop=args.tran_stop)

    if args.phase in ["2", "all"]:
        generate_phase2(args.outdir, chosen_model, tran_stop=args.tran_stop)

    print("\nAll requested phases generated successfully!")


if __name__ == "__main__":
    main()
