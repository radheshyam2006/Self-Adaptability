#!/usr/bin/env python3
"""
compare_phase0.py
=================
Compares Phase 0 simulation results between:
  - crn28hpcp_2d5 (results_phase0_2d5.csv)
  - crn28hpcp_1d8 (results_phase0_1d8.csv)
against the Excel ground truth.

Prints side-by-side error metrics and automatically writes the winning
model file into active_model.conf for subsequent phases.
"""

import os
import sys
import pandas as pd
import numpy as np

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

MODEL_2D5_PATH = "/data/cad/pdk_all/pdk_tsmc/pdk_tsmc_28/PDK/TSMC_new_iPDK/models/spectre/crn28hpcp_2d5_elk_v1d0_2p2_shrink0d9_embedded_usage.scs"
MODEL_1D8_PATH = "/data/cad/pdk_all/pdk_tsmc/pdk_tsmc_28/PDK/TSMC_new_iPDK/models/spectre/crn28hpcp_1d8_elk_v1d0_2p2_shrink0d9_embedded_usage.scs"


def evaluate_results(csv_path):
    if not os.path.exists(csv_path):
        return None
    df = pd.read_csv(csv_path)
    df.columns = [c.strip() for c in df.columns]
    
    # Calculate absolute differences against Excel ground truth
    df['pup_err'] = np.abs(df['sim_pup'] - df['excel_pup'])
    df['pdn_err'] = np.abs(df['sim_pdn'] - df['excel_pdn'])
    df['pup_err_pct'] = (df['pup_err'] / df['excel_pup']) * 100
    df['pdn_err_pct'] = (df['pdn_err'] / df['excel_pdn']) * 100
    df['total_mae'] = (df['pup_err'] + df['pdn_err']) / 2.0
    return df


def main():
    csv_2d5 = os.path.join(SCRIPT_DIR, "results_phase0_2d5.csv")
    csv_1d8 = os.path.join(SCRIPT_DIR, "results_phase0_1d8.csv")

    print("\n" + "=" * 78)
    print("PHASE 0: MODEL FILE DISCRIMINATION BENCHMARK EVALUATION")
    print("=" * 78)

    df_2d5 = evaluate_results(csv_2d5)
    df_1d8 = evaluate_results(csv_1d8)

    if df_2d5 is None and df_1d8 is None:
        print("\nNeither results_phase0_2d5.csv nor results_phase0_1d8.csv found in current directory.")
        print("Please run run_phase0_2d5.ocn and run_phase0_1d8.ocn on the server first.")
        sys.exit(1)

    print(f"\n{'Corner':<7} {'Vreg':<6} {'Temp':<6} | {'Excel pup':<10} {'2d5 pup':<10} {'1d8 pup':<10} | {'Excel pdn':<10} {'2d5 pdn':<10} {'1d8 pdn':<10}")
    print("-" * 78)

    n_rows = len(df_2d5) if df_2d5 is not None else len(df_1d8)
    for i in range(n_rows):
        c = df_2d5.iloc[i]['corner'] if df_2d5 is not None else df_1d8.iloc[i]['corner']
        v = df_2d5.iloc[i]['vreg'] if df_2d5 is not None else df_1d8.iloc[i]['vreg']
        t = df_2d5.iloc[i]['temperature'] if df_2d5 is not None else df_1d8.iloc[i]['temperature']
        exp_pup = df_2d5.iloc[i]['excel_pup'] if df_2d5 is not None else df_1d8.iloc[i]['excel_pup']
        exp_pdn = df_2d5.iloc[i]['excel_pdn'] if df_2d5 is not None else df_1d8.iloc[i]['excel_pdn']

        p_2d5 = f"{df_2d5.iloc[i]['sim_pup']:.2f}Ω" if df_2d5 is not None else "N/A"
        p_1d8 = f"{df_1d8.iloc[i]['sim_pup']:.2f}Ω" if df_1d8 is not None else "N/A"
        n_2d5 = f"{df_2d5.iloc[i]['sim_pdn']:.2f}Ω" if df_2d5 is not None else "N/A"
        n_1d8 = f"{df_1d8.iloc[i]['sim_pdn']:.2f}Ω" if df_1d8 is not None else "N/A"

        print(f"{c:<7} {v:<6.2f} {t:<6.1f} | {exp_pup:<10.2f} {p_2d5:<10} {p_1d8:<10} | {exp_pdn:<10.2f} {n_2d5:<10} {n_1d8:<10}")

    print("-" * 78)

    mae_2d5 = df_2d5['total_mae'].mean() if df_2d5 is not None else 999.0
    mae_1d8 = df_1d8['total_mae'].mean() if df_1d8 is not None else 999.0

    print(f"\nMean Absolute Error vs Excel Ground Truth:")
    print(f"  crn28hpcp_2d5 MAE: {mae_2d5:.3f} Ω")
    print(f"  crn28hpcp_1d8 MAE: {mae_1d8:.3f} Ω")

    if mae_2d5 < mae_1d8:
        winner = "2d5"
        winner_path = MODEL_2D5_PATH
        print("\n>>> WINNER: crn28hpcp_2d5 matches Excel data much closer! <<<")
    else:
        winner = "1d8"
        winner_path = MODEL_1D8_PATH
        print("\n>>> WINNER: crn28hpcp_1d8 matches Excel data much closer! <<<")

    conf_file = os.path.join(SCRIPT_DIR, "active_model.conf")
    with open(conf_file, "w") as f:
        f.write(f"MODEL_TAG={winner}\n")
        f.write(f"MODEL_PATH={winner_path}\n")
    print(f"Saved active model configuration to: {conf_file}\n")


if __name__ == "__main__":
    main()
