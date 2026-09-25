#!/usr/bin/env python3
"""
analyze_results.py
==================
Post-processing and reporting script for Cadence Spectre validation results:
- Merges batch result CSV files (Phase 1 or Phase 2)
- Calculates pass rates against 50Ω ± 2Ω spec (48.0Ω to 52.0Ω)
- Computes mean, std, min, and max resistance per corner
- Generates markdown report table and summary CSV
"""

import os
import sys
import glob
import argparse
import pandas as pd
import numpy as np

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
RESULTS_DIR = os.path.join(PROJECT_DIR, "results")

TARGET_R = 50.0
SPEC_MIN = 48.0
SPEC_MAX = 52.0

def load_and_merge_csvs(pattern):
    files = glob.glob(pattern)
    if not files:
        # Also check current directory
        files = glob.glob(os.path.basename(pattern))
    if not files:
        return None, []

    dfs = []
    for f in sorted(files):
        try:
            df = pd.read_csv(f)
            df.columns = [c.strip() for c in df.columns]
            if len(df) > 0 and 'sim_pup' in df.columns:
                dfs.append(df)
        except Exception as e:
            print(f"Warning: could not read {f}: {e}")

    if not dfs:
        return None, files
    merged = pd.concat(dfs, ignore_index=True)
    return merged, files

def analyze(df):
    df['pup_pass'] = (df['sim_pup'] >= SPEC_MIN) & (df['sim_pup'] <= SPEC_MAX)
    df['pdn_pass'] = (df['sim_pdn'] >= SPEC_MIN) & (df['sim_pdn'] <= SPEC_MAX)
    df['both_pass'] = df['pup_pass'] & df['pdn_pass']

    df['pup_err_pct'] = (np.abs(df['sim_pup'] - TARGET_R) / TARGET_R) * 100.0
    df['pdn_err_pct'] = (np.abs(df['sim_pdn'] - TARGET_R) / TARGET_R) * 100.0

    summary_rows = []
    for corner, group in df.groupby('corner'):
        n = len(group)
        pup_pass_pct = (group['pup_pass'].sum() / n) * 100.0
        pdn_pass_pct = (group['pdn_pass'].sum() / n) * 100.0
        both_pass_pct = (group['both_pass'].sum() / n) * 100.0

        summary_rows.append({
            'Corner': corner,
            'Sims': n,
            'pup_pass%': pup_pass_pct,
            'pdn_pass%': pdn_pass_pct,
            'both_pass%': both_pass_pct,
            'avg_pup': group['sim_pup'].mean(),
            'avg_pdn': group['sim_pdn'].mean(),
            'min_pup': group['sim_pup'].min(),
            'max_pup': group['sim_pup'].max(),
            'min_pdn': group['sim_pdn'].min(),
            'max_pdn': group['sim_pdn'].max(),
        })

    summary_df = pd.DataFrame(summary_rows)

    # All row
    n_all = len(df)
    all_row = {
        'Corner': 'ALL',
        'Sims': n_all,
        'pup_pass%': (df['pup_pass'].sum() / n_all) * 100.0,
        'pdn_pass%': (df['pdn_pass'].sum() / n_all) * 100.0,
        'both_pass%': (df['both_pass'].sum() / n_all) * 100.0,
        'avg_pup': df['sim_pup'].mean(),
        'avg_pdn': df['sim_pdn'].mean(),
        'min_pup': df['sim_pup'].min(),
        'max_pup': df['sim_pup'].max(),
        'min_pdn': df['sim_pdn'].min(),
        'max_pdn': df['sim_pdn'].max(),
    }
    summary_df = pd.concat([summary_df, pd.DataFrame([all_row])], ignore_index=True)
    return summary_df

def print_report(summary_df):
    print("\n" + "=" * 88)
    print("                 CADENCE SPECTRE VALIDATION SUMMARY (50Ω ± 2Ω SPEC)")
    print("=" * 88)
    print(f"{'Corner':<8} | {'Sims':<6} | {'pup Pass%':<10} | {'pdn Pass%':<10} | {'Both Pass%':<10} | {'Avg pup':<9} | {'Avg pdn':<9}")
    print("-" * 88)
    for _, r in summary_df.iterrows():
        c = r['Corner']
        print(f"{c:<8} | {int(r['Sims']):<6} | {r['pup_pass%']:>9.1f}% | {r['pdn_pass%']:>9.1f}% | {r['both_pass%']:>9.1f}% | {r['avg_pup']:>7.2f}Ω | {r['avg_pdn']:>7.2f}Ω")
        if c in ['SF', 'TT']:
            pass
    print("=" * 88 + "\n")

def main():
    parser = argparse.ArgumentParser(description="Analyze Cadence Spectre Validation Results")
    parser.add_argument("--phase", type=str, default="1", help="Validation phase to analyze (1 or 2)")
    parser.add_argument("--pattern", type=str, default=None, help="Custom glob pattern for CSVs")
    args = parser.parse_args()

    if args.pattern:
        pat = args.pattern
    else:
        pat = os.path.join(RESULTS_DIR, f"results_phase{args.phase}_*.csv")

    df, files = load_and_merge_csvs(pat)
    if df is None or len(df) == 0:
        # Also check current folder
        pat2 = f"results_phase{args.phase}_*.csv"
        df, files = load_and_merge_csvs(pat2)

    if df is None or len(df) == 0:
        print(f"No valid results found matching pattern: {pat}")
        sys.exit(1)

    print(f"Loaded {len(df)} total simulation rows across {len(files)} files.")
    summary_df = analyze(df)
    print_report(summary_df)

    out_csv = os.path.join(RESULTS_DIR, f"validation_phase{args.phase}_summary.csv")
    summary_df.to_csv(out_csv, index=False)
    print(f"Summary saved to: {out_csv}")

if __name__ == "__main__":
    main()
