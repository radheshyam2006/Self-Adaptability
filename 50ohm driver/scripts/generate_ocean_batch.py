"""
generate_ocean_batch.py
=======================
Complete automation pipeline:
1. Load all_predictions.csv (15,884 rows with ML-predicted trim codes)
2. Recreate the train/test split (test_size=0.2, random_state=42, stratify by corner)
3. Take ONLY the test set rows (3,177 rows)
4. Generate batched Ocean scripts grouped by corner
5. Generate a shell script to run them with parallelism

Uses the ontimereduction settings:
- Model: crn28hpcp_1d8_elk_v1d0_2p2_shrink0d9_embedded_usage.scs
- Tran: 100n (5x faster than 500n)
- Resistance measured at t=80ns (single point, no averaging)
- Includes pre_simu section
"""

import pandas as pd
import numpy as np
import os
from sklearn.model_selection import train_test_split

# ===== CONFIGURATION =====
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
PREDICTIONS_CSV = os.path.join(SCRIPT_DIR, "all_predictions.csv")
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "ocean_batch")
SIMS_PER_BATCH = 50  # Number of simulations per .ocn file

MODEL_FILE = "/data/cad/pdk_all/pdk_tsmc/pdk_tsmc_28/PDK/TSMC_new_iPDK/models/spectre/crn28hpcp_1d8_elk_v1d0_2p2_shrink0d9_embedded_usage.scs"

# Model section mapping per process corner
CORNER_SECTIONS = {
    'TT': ('ttmacro_mos_moscap', 'tt_res_bip_dio_disres'),
    'SS': ('ssmacro_mos_moscap', 'ss_res_bip_dio_disres'),
    'FF': ('ffmacro_mos_moscap', 'ff_res_bip_dio_disres'),
    'FS': ('fsmacro_mos_moscap', 'fs_res_bip_dio_disres'),
    'SF': ('sfmacro_mos_moscap', 'sf_res_bip_dio_disres'),
}

def load_and_split():
    """Load predictions and recreate the exact same train/test split."""
    df = pd.read_csv(PREDICTIONS_CSV)
    print(f"Loaded {len(df)} total predictions")
    
    # Recreate split using same parameters as final_model.py
    corners = df['corner_label'].values
    indices = np.arange(len(df))
    
    train_idx, test_idx = train_test_split(
        indices, test_size=0.2, random_state=42, stratify=corners
    )
    
    test_df = df.iloc[test_idx].reset_index(drop=True)
    print(f"Test set: {len(test_df)} rows")
    print(f"Per corner: {test_df['corner_label'].value_counts().to_dict()}")
    return test_df


def get_pvt_bits(row):
    """Extract pvt0..pvt13 and pvtn0..pvtn13 from the row."""
    pvtp_bits = {}
    pvtn_bits = {}
    for i in range(14):
        pvtp_bits[f'pvt{i}'] = int(row.get(f'pvt{i}', 0))
        pvtn_bits[f'pvtn{i}'] = int(row.get(f'pvtn{i}', 0))
    return pvtp_bits, pvtn_bits


def generate_ocean_script(corner, rows_df, batch_id, output_dir):
    """Generate one .ocn file for a batch of rows from the same corner."""
    mos_section, res_section = CORNER_SECTIONS[corner]
    csv_filename = f"results_{corner}_batch{batch_id:03d}.csv"
    script_name = f"run_{corner}_batch{batch_id:03d}.ocn"
    
    lines = []
    lines.append(f'; {script_name}')
    lines.append(f'; Auto-generated: {corner} corner, batch {batch_id}, {len(rows_df)} simulations')
    lines.append('')
    lines.append("simulator('spectre)")
    lines.append('design("tsmc28_tx_tb" "tx_drv_ML" "schematic_seriliazer_top")')
    lines.append(f'resultsDir("./ocean_batch_results/{corner}_batch{batch_id:03d}")')
    lines.append('')
    lines.append('modelFile(')
    lines.append(f'    \'("{MODEL_FILE}" "{mos_section}")')
    lines.append(f'    \'("{MODEL_FILE}" "{res_section}")')
    lines.append(f'    \'("{MODEL_FILE}" "pre_simu")')
    lines.append(')')
    lines.append('analysis(\'tran ?stop "100n")')
    lines.append('')
    lines.append("envOption('firstRun t 'termDirectionMismatch \"ignore\" 'termMismatch \"ignore\")")
    lines.append('saveOption( ?infoOptions list(list("modelParameter" "models" "rawfile" "" "" "" t) list("element" "inst" "rawfile" "" "" "" t) list("outputParameter" "output" "rawfile" "" "" "" t) list("designParamVals" "parameters" "rawfile" "" "" "" t) list("primitives" "primitives" "rawfile" "" "" "" t) list("subckts" "subckts" "rawfile" "" "" "" t) list("asserts" "assert" "rawfile" "" "" "" nil) list("extremeinfo" "all" "logfile" "" "yes" "" nil) list("allcap" "allcap" "file" "" "" "" nil) list("<Click_To_Add>" "none" "rawfile" "" "" "" nil) ) )')
    lines.append("save('i \"/xdrv_p/out\")")
    lines.append('')
    lines.append(f'out_file = outfile("{csv_filename}")')
    lines.append('fprintf(out_file "row_idx,corner,vreg,temperature,pmon_cmos_res,pvtp_int_pred,pvtn_int_pred,pvtp_match,pvtn_match,sim_pup,sim_pdn,excel_pup_uncal,excel_pdn_uncal,excel_pup_cal,excel_pdn_cal\\n")')
    lines.append('')
    
    for sim_idx, (_, row) in enumerate(rows_df.iterrows()):
        vreg = row['vreg']
        temp = row['temperature']
        pmon = row['pmon_cmos_res']
        pvtp_pred = int(row['pvtp_int_pred'])
        pvtn_pred = int(row['pvtn_int_pred'])
        pvtp_match = row['pvtp_match']
        pvtn_match = row['pvtn_match']
        pup_uncal = row['PULL_UP_RES']
        pdn_uncal = row['PULL_DN_RES']
        pup_cal = row['PULL_UP_RES_new']
        pdn_cal = row['PULL_DN_RES_new']
        row_idx = row.name if hasattr(row, 'name') else sim_idx
        
        pvtp_bits, pvtn_bits = get_pvt_bits(row)
        
        lines.append(f'; --- Sim {sim_idx+1}/{len(rows_df)}: Temp={temp}, Vreg={vreg} ---')
        lines.append(f'printf("\\n[{corner} batch{batch_id}] Sim {sim_idx+1}/{len(rows_df)}: T={temp}, V={vreg}\\n")')
        
        lines.append(f'desVar("tem" {temp})')
        lines.append(f'desVar("vreg" {vreg})')
        lines.append(f'temp({temp})')
        
        for i in range(14):
            lines.append(f'desVar("pvt{i}" {pvtp_bits[f"pvt{i}"]})')
        for i in range(14):
            lines.append(f'desVar("pvtn{i}" {pvtn_bits[f"pvtn{i}"]})')
        
        lines.append('')
        lines.append('run()')
        lines.append("selectResults('tran)")
        lines.append('')
        # Use the ontimereduction expression: measure at t=80ns
        lines.append('pup_val = value(((v("/vdd" ?result "tran") - v("/outn" ?result "tran")) / i("/xdrv_p/out" ?result "tran")) 8e-08)')
        lines.append('pdn_val = value((v("/outp" ?result "tran") / i("/xdrv_p/out" ?result "tran")) 8e-08)')
        lines.append('')
        lines.append(f'fprintf(out_file "{row_idx}, {corner}, {vreg}, {temp}, {pmon}, {pvtp_pred}, {pvtn_pred}, {pvtp_match}, {pvtn_match}, %f, %f, {pup_uncal}, {pdn_uncal}, {pup_cal}, {pdn_cal}\\n" pup_val pdn_val)')
        lines.append('')
    
    lines.append('close(out_file)')
    lines.append(f'printf("\\n=== {corner} batch {batch_id} COMPLETE ({len(rows_df)} sims) ===\\n")')
    
    script_path = os.path.join(output_dir, script_name)
    with open(script_path, 'w', newline='\n') as f:
        f.write('\n'.join(lines))
    
    return script_name, csv_filename


def generate_run_script(all_scripts, output_dir):
    """Generate shell script to run all Ocean batches with parallelism."""
    lines = []
    lines.append('#!/bin/bash')
    lines.append('# run_all_batches.sh — Run all Ocean batch scripts with parallelism')
    lines.append('# Usage: ./run_all_batches.sh [MAX_PARALLEL]')
    lines.append('# Example: ./run_all_batches.sh 3')
    lines.append('')
    lines.append('MAX_PARALLEL=${1:-3}  # Default: 3 parallel jobs')
    lines.append('RESULTS_DIR="ocean_batch_results"')
    lines.append('LOG_DIR="ocean_batch_logs"')
    lines.append('')
    lines.append('# Source Cadence environment')
    lines.append('# source /home/cadence-2023/cadence2.csh')
    lines.append('')
    lines.append('mkdir -p $RESULTS_DIR $LOG_DIR')
    lines.append('')
    lines.append('running=0')
    lines.append('total=0')
    lines.append(f'grand_total={len(all_scripts)}')
    lines.append('')
    
    # Group by corner for clarity
    by_corner = {}
    for script_name, csv_name, corner in all_scripts:
        by_corner.setdefault(corner, []).append((script_name, csv_name))
    
    for corner in ['TT', 'SS', 'FF', 'FS', 'SF']:
        if corner not in by_corner:
            continue
        scripts = by_corner[corner]
        lines.append(f'echo "========== {corner} Corner: {len(scripts)} batches =========="')
        
        for script_name, csv_name in scripts:
            # Create results subdirectory
            batch_id = script_name.replace(f'run_{corner}_batch', '').replace('.ocn', '')
            lines.append(f'mkdir -p $RESULTS_DIR/{corner}_batch{batch_id}')
            lines.append('')
            lines.append(f'# Run {script_name}')
            lines.append(f'total=$((total + 1))')
            lines.append(f'echo "[$total/$grand_total] Starting {script_name}..."')
            lines.append(f'ocean -nograph -restore ocean_batch/{script_name} > $LOG_DIR/{script_name}.log 2>&1 &')
            lines.append(f'running=$((running + 1))')
            lines.append('')
            lines.append('if [ $running -ge $MAX_PARALLEL ]; then')
            lines.append('    echo "  Waiting for a batch to finish (max $MAX_PARALLEL parallel)..."')
            lines.append('    wait -n')
            lines.append('    running=$((running - 1))')
            lines.append('fi')
            lines.append('')
    
    lines.append('# Wait for all remaining jobs')
    lines.append('echo "Waiting for final jobs to complete..."')
    lines.append('wait')
    lines.append('')
    lines.append('echo ""')
    lines.append('echo "=========================================="')
    lines.append('echo "ALL BATCHES COMPLETE!"')
    lines.append('echo "=========================================="')
    lines.append('')
    lines.append('# Merge all result CSVs')
    lines.append('echo "Merging results..."')
    lines.append('head -1 $(ls results_*_batch*.csv | head -1) > calibrated_results_all.csv')
    lines.append('for f in results_*_batch*.csv; do')
    lines.append('    tail -n +2 "$f" >> calibrated_results_all.csv')
    lines.append('done')
    lines.append('echo "Final results: calibrated_results_all.csv"')
    lines.append('wc -l calibrated_results_all.csv')
    
    script_path = os.path.join(output_dir, '..', 'run_all_batches.sh')
    with open(script_path, 'w', newline='\n') as f:
        f.write('\n'.join(lines))
    
    return script_path


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Step 1: Load data and split
    test_df = load_and_split()
    
    # Step 2: Check that pvt bit columns exist
    if 'pvt0' not in test_df.columns:
        print("\nWARNING: pvt0-pvt13 columns not in all_predictions.csv!")
        print("Loading per-corner prediction files instead...")
        
        dfs = []
        for corner in ['FF', 'SS', 'TT', 'FS', 'SF']:
            cdf = pd.read_csv(rf"c:\Users\radhe\OneDrive\Documents\AI_Self-adaptive_Chip\Self Adaptability\50ohm driver\scripts\predictions_{corner}.csv")
            dfs.append(cdf)
        full_df = pd.concat(dfs, ignore_index=True)
        
        # Recreate split
        corners = full_df['corner_label'].values
        indices = np.arange(len(full_df))
        _, test_idx = train_test_split(indices, test_size=0.2, random_state=42, stratify=corners)
        test_df = full_df.iloc[test_idx].reset_index(drop=True)
        print(f"Test set from per-corner files: {len(test_df)} rows")
    
    # Step 3: Generate batched Ocean scripts, grouped by corner
    all_scripts = []
    
    for corner in ['TT', 'SS', 'FF', 'FS', 'SF']:
        corner_df = test_df[test_df['corner_label'] == corner].reset_index(drop=True)
        n_batches = (len(corner_df) + SIMS_PER_BATCH - 1) // SIMS_PER_BATCH
        
        print(f"\n{corner}: {len(corner_df)} test rows -> {n_batches} batches of {SIMS_PER_BATCH}")
        
        for batch_id in range(n_batches):
            start = batch_id * SIMS_PER_BATCH
            end = min(start + SIMS_PER_BATCH, len(corner_df))
            batch_df = corner_df.iloc[start:end]
            
            script_name, csv_name = generate_ocean_script(corner, batch_df, batch_id, OUTPUT_DIR)
            all_scripts.append((script_name, csv_name, corner))
    
    # Step 4: Generate the run script
    run_script = generate_run_script(all_scripts, OUTPUT_DIR)
    
    # Summary
    print(f"\n{'='*60}")
    print(f"GENERATION COMPLETE!")
    print(f"{'='*60}")
    print(f"Total test rows:     {len(test_df)}")
    print(f"Total Ocean scripts: {len(all_scripts)}")
    print(f"Sims per batch:      {SIMS_PER_BATCH}")
    print(f"Output directory:    {OUTPUT_DIR}")
    print(f"Run script:          {run_script}")
    print(f"\nEstimated time at ~2 min/sim:")
    print(f"  Sequential:      {len(test_df)*2/60:.0f} hours")
    print(f"  3 parallel:      {len(test_df)*2/60/3:.0f} hours")
    print(f"  5 parallel:      {len(test_df)*2/60/5:.0f} hours")
    print(f"\nNext steps:")
    print(f"  1. scp ocean_batch/ folder to server")
    print(f"  2. scp run_all_batches.sh to server")
    print(f"  3. On server: chmod +x run_all_batches.sh && ./run_all_batches.sh 3")


if __name__ == '__main__':
    main()
