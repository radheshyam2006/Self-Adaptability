"""
BGR Data Visualization Pipeline
================================
Generates 10+ plots analyzing Cadence simulation data for
Bandgap Reference (BGR) PVT trim bit prediction.

Inputs:  vdd, temperature, PMON_RING_CMOS_res
Outputs: pctrl<3:0> (4-bit), nctrl<5:0> (6-bit)
Target:  Constant vbgr ≈ 0.60V across all PVT conditions

Author: Auto-generated for AI Self-Adaptive Chip project
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
from mpl_toolkits.mplot3d import Axes3D
import os
import sys

# ─── Configuration ────────────────────────────────────────────────────
XLSX_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                         "BGR_ML_DATA_JAN9_testsample_2023_MAR6.xlsx")
PLOTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "plots")
os.makedirs(PLOTS_DIR, exist_ok=True)

SHEET_MAP = {
    'TT': 'TT-VDD_TEMP',
    'SS': 'SS_VDD_TEMP',
    'FF': 'FF_VDD_TEMP',
}

CORNER_COLORS = {'TT': '#2196F3', 'SS': '#F44336', 'FF': '#4CAF50'}


# ─── Data Loading ─────────────────────────────────────────────────────
def parse_trim_bits(val):
    """Convert dash-separated binary string to integer.
    e.g., '0-111' -> 0111 -> 7, '1000-01' -> 100001 -> 33
    """
    if pd.isna(val):
        return np.nan
    s = str(val).replace('-', '').replace(' ', '')
    try:
        return int(s, 2)
    except ValueError:
        try:
            return int(s)
        except ValueError:
            return np.nan


def load_all_corners():
    """Load and combine data from all process corners."""
    frames = []
    for corner_name, sheet_name in SHEET_MAP.items():
        df = pd.read_excel(XLSX_PATH, sheet_name=sheet_name)
        df = df.dropna(subset=['vdd', 'temperature'])

        # Standardize column names (TT sheet has ' ' instead of 'vbgr')
        col_map = {}
        for c in df.columns:
            cl = c.strip().lower()
            if cl == '' or cl == 'vbgr':
                col_map[c] = 'vbgr'
            elif 'measured' in cl:
                col_map[c] = 'measured'
        df = df.rename(columns=col_map)

        # Drop unnamed columns
        df = df[[c for c in df.columns if not c.startswith('Unnamed')]]

        # Parse trim bits
        df['pctrl_int'] = df['pctrl<3:0>'].apply(parse_trim_bits)
        df['nctrl_int'] = df['nctrl<5:0>'].apply(parse_trim_bits)
        df['corner'] = corner_name

        # Keep only relevant columns
        keep = ['corner', 'vdd', 'temperature', 'PMON_RING_CMOS_res',
                'pctrl<3:0>', 'nctrl<5:0>', 'pctrl_int', 'nctrl_int']
        if 'vbgr' in df.columns:
            keep.append('vbgr')
        if 'measured' in df.columns:
            keep.append('measured')
        if 'PMON_RING_CMOS' in df.columns:
            keep.append('PMON_RING_CMOS')

        df = df[[c for c in keep if c in df.columns]]
        frames.append(df)
        print(f"  Loaded {corner_name}: {len(df)} samples, "
              f"pctrl unique={df['pctrl_int'].nunique()}, "
              f"nctrl unique={df['nctrl_int'].nunique()}")

    data = pd.concat(frames, ignore_index=True)
    print(f"\nTotal samples: {len(data)}")
    print(f"Total unique pctrl values: {sorted(data['pctrl_int'].dropna().unique().astype(int))}")
    print(f"Total unique nctrl values: {sorted(data['nctrl_int'].dropna().unique().astype(int))}")
    return data


def save_plot(fig, name):
    path = os.path.join(PLOTS_DIR, name)
    fig.savefig(path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    print(f"  Saved: {name}")


# ─── Plot Functions ───────────────────────────────────────────────────

def plot_01_vbgr_distribution(data):
    """Plot 01: vbgr voltage distribution across corners."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    fig.suptitle('Plot 01: BGR Output Voltage (vbgr) Distribution', fontsize=14, fontweight='bold')

    # Left: vbgr histogram per corner
    ax = axes[0]
    for corner in ['TT', 'SS', 'FF']:
        subset = data[(data['corner'] == corner) & data['vbgr'].notna()]
        if len(subset) > 0:
            ax.hist(subset['vbgr'], bins=50, alpha=0.6, label=corner,
                    color=CORNER_COLORS[corner], edgecolor='white', linewidth=0.5)
    ax.axvline(x=0.600, color='black', linestyle='--', linewidth=2, label='Target 0.600V')
    ax.set_xlabel('vbgr (V)')
    ax.set_ylabel('Count')
    ax.set_title('vbgr Distribution Per Corner')
    ax.legend()
    ax.grid(alpha=0.3)

    # Right: vbgr boxplot per corner
    ax = axes[1]
    corner_data = []
    labels = []
    for corner in ['FF', 'TT', 'SS']:
        subset = data[(data['corner'] == corner) & data['vbgr'].notna()]['vbgr']
        if len(subset) > 0:
            corner_data.append(subset.values)
            labels.append(f"{corner}\n({len(subset)} pts)")
    bp = ax.boxplot(corner_data, labels=labels, patch_artist=True)
    for patch, corner in zip(bp['boxes'], ['FF', 'TT', 'SS']):
        patch.set_facecolor(CORNER_COLORS[corner])
        patch.set_alpha(0.6)
    ax.axhline(y=0.600, color='black', linestyle='--', linewidth=2, label='Target 0.600V')
    ax.set_ylabel('vbgr (V)')
    ax.set_title('vbgr Box Plot Per Corner')
    ax.legend()
    ax.grid(alpha=0.3)

    fig.tight_layout()
    save_plot(fig, '01_vbgr_distribution.png')


def plot_02_trim_distributions(data):
    """Plot 02: Trim code distributions per corner."""
    fig, axes = plt.subplots(2, 3, figsize=(16, 10))
    fig.suptitle('Plot 02: Trim Code Distributions Per Corner', fontsize=14, fontweight='bold')

    for i, corner in enumerate(['TT', 'SS', 'FF']):
        subset = data[data['corner'] == corner]

        # pctrl
        ax = axes[0, i]
        vals = subset['pctrl_int'].dropna()
        unique_vals = sorted(vals.unique())
        counts = [len(vals[vals == v]) for v in unique_vals]
        ax.bar([str(int(v)) for v in unique_vals], counts,
               color=CORNER_COLORS[corner], alpha=0.7, edgecolor='black')
        ax.set_title(f'{corner} — pctrl<3:0>')
        ax.set_xlabel('pctrl (decimal)')
        ax.set_ylabel('Count')
        for j, (v, c) in enumerate(zip(unique_vals, counts)):
            ax.text(j, c + 10, f'bin:{int(v):04b}', ha='center', fontsize=8)

        # nctrl
        ax = axes[1, i]
        vals = subset['nctrl_int'].dropna()
        unique_vals = sorted(vals.unique())
        counts = [len(vals[vals == v]) for v in unique_vals]
        ax.bar([str(int(v)) for v in unique_vals], counts,
               color=CORNER_COLORS[corner], alpha=0.7, edgecolor='black')
        ax.set_title(f'{corner} — nctrl<5:0>')
        ax.set_xlabel('nctrl (decimal)')
        ax.set_ylabel('Count')
        for j, (v, c) in enumerate(zip(unique_vals, counts)):
            ax.text(j, c + 10, f'bin:{int(v):06b}', ha='center', fontsize=7)

    fig.tight_layout()
    save_plot(fig, '02_trim_distributions.png')


def plot_03_pmon_vs_trim(data):
    """Plot 03: PMON_RING_CMOS_res vs Trim Codes."""
    fig, axes = plt.subplots(2, 1, figsize=(14, 10))
    fig.suptitle('Plot 03: PMON_RING_CMOS_res vs Trim Codes', fontsize=14, fontweight='bold')

    for ax_idx, (trim_col, trim_name) in enumerate([('pctrl_int', 'pctrl'), ('nctrl_int', 'nctrl')]):
        ax = axes[ax_idx]
        for corner in ['TT', 'SS', 'FF']:
            subset = data[data['corner'] == corner]
            ax.scatter(subset['PMON_RING_CMOS_res'] / 1e6, subset[trim_col],
                       alpha=0.3, s=5, label=corner, color=CORNER_COLORS[corner])
        ax.set_xlabel('PMON_RING_CMOS_res (×10⁶)')
        ax.set_ylabel(f'{trim_name} (decimal)')
        ax.set_title(f'Ring Oscillator Count vs {trim_name}')
        ax.legend(markerscale=3)
        ax.grid(alpha=0.3)

    fig.tight_layout()
    save_plot(fig, '03_pmon_vs_trim.png')


def plot_04_trim_heatmaps(data):
    """Plot 04: Trim heatmaps (VDD × Temperature) per corner."""
    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    fig.suptitle('Plot 04: Trim Code Heatmaps (VDD × Temperature)', fontsize=14, fontweight='bold')

    for i, corner in enumerate(['TT', 'SS', 'FF']):
        subset = data[data['corner'] == corner]

        for row, (trim_col, trim_name) in enumerate([('pctrl_int', 'pctrl'), ('nctrl_int', 'nctrl')]):
            ax = axes[row, i]
            pivot = subset.pivot_table(values=trim_col, index='vdd',
                                       columns='temperature', aggfunc='first')
            im = ax.imshow(pivot.values, aspect='auto', cmap='viridis',
                          extent=[pivot.columns.min(), pivot.columns.max(),
                                  pivot.index.min(), pivot.index.max()],
                          origin='lower')
            ax.set_xlabel('Temperature (°C)')
            ax.set_ylabel('VDD (V)')
            ax.set_title(f'{corner} — {trim_name}')
            plt.colorbar(im, ax=ax, label=f'{trim_name} (decimal)')

    fig.tight_layout()
    save_plot(fig, '04_trim_heatmaps.png')


def plot_05_3d_pvt_clusters(data):
    """Plot 05: PVT space projections with trim bit clusters (2D projections)."""
    data_clean = data.dropna(subset=['pctrl_int', 'nctrl_int']).copy()
    data_clean['trim_combo'] = (data_clean['pctrl_int'].astype(int).astype(str) + '_' +
                                 data_clean['nctrl_int'].astype(int).astype(str))
    unique_combos = sorted(data_clean['trim_combo'].unique())

    fig, axes = plt.subplots(2, 3, figsize=(18, 11))
    fig.suptitle('Plot 05: PVT Space Projections with Trim Clusters', fontsize=14, fontweight='bold')

    pairs = [
        ('PMON_RING_CMOS_res', 'vdd', 'PMON_res (M)', 'VDD (V)', 1e6),
        ('PMON_RING_CMOS_res', 'temperature', 'PMON_res (M)', 'Temp (C)', 1e6),
        ('vdd', 'temperature', 'VDD (V)', 'Temp (C)', 1),
    ]

    cmap_tab = plt.cm.tab20
    for col_idx, (x_col, y_col, x_label, y_label, x_div) in enumerate(pairs):
        # Top row: colored by trim combo
        ax = axes[0, col_idx]
        for idx, combo in enumerate(unique_combos):
            subset = data_clean[data_clean['trim_combo'] == combo]
            color = cmap_tab(idx / max(len(unique_combos), 1))
            ax.scatter(subset[x_col].values / x_div, subset[y_col].values,
                       color=color, s=2, alpha=0.4,
                       label=f'p={combo.split("_")[0]},n={combo.split("_")[1]}')
        ax.set_xlabel(x_label)
        ax.set_ylabel(y_label)
        ax.set_title(f'{x_label} vs {y_label} (by Trim)')
        ax.grid(alpha=0.3)
        if col_idx == 2:
            ax.legend(fontsize=5, loc='best', markerscale=3, ncol=2)

        # Bottom row: colored by corner
        ax = axes[1, col_idx]
        for corner in ['TT', 'SS', 'FF']:
            subset = data_clean[data_clean['corner'] == corner]
            ax.scatter(subset[x_col].values / x_div, subset[y_col].values,
                       color=CORNER_COLORS[corner], s=2, alpha=0.3, label=corner)
        ax.set_xlabel(x_label)
        ax.set_ylabel(y_label)
        ax.set_title(f'{x_label} vs {y_label} (by Corner)')
        ax.legend(markerscale=3)
        ax.grid(alpha=0.3)

    fig.tight_layout()
    save_plot(fig, '05_pvt_projections.png')


def plot_06_trim_vs_temp(data):
    """Plot 06: Trim vs Temperature per corner, one line per VDD."""
    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    fig.suptitle('Plot 06: Trim Code vs Temperature (one line per VDD)', fontsize=14, fontweight='bold')

    for i, corner in enumerate(['TT', 'SS', 'FF']):
        subset = data[data['corner'] == corner]
        vdd_vals = sorted(subset['vdd'].unique())

        for row, (trim_col, trim_name) in enumerate([('pctrl_int', 'pctrl'), ('nctrl_int', 'nctrl')]):
            ax = axes[row, i]
            cmap = plt.cm.coolwarm
            for j, vdd in enumerate(vdd_vals):
                vdd_data = subset[subset['vdd'] == vdd].sort_values('temperature')
                color = cmap(j / max(len(vdd_vals) - 1, 1))
                ax.plot(vdd_data['temperature'], vdd_data[trim_col],
                        color=color, alpha=0.7, linewidth=0.8, label=f'{vdd:.2f}V')
            ax.set_xlabel('Temperature (°C)')
            ax.set_ylabel(f'{trim_name} (decimal)')
            ax.set_title(f'{corner} — {trim_name} vs Temp')
            ax.grid(alpha=0.3)
            if i == 2:
                ax.legend(fontsize=6, loc='best', ncol=2, title='VDD')

    fig.tight_layout()
    save_plot(fig, '06_trim_vs_temp.png')


def plot_07_pmon_overlap(data):
    """Plot 07: PMON_RING_CMOS_res overlap analysis between corners."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    fig.suptitle('Plot 07: PMON_RING_CMOS_res Overlap Between Corners', fontsize=14, fontweight='bold')

    # Histogram overlap
    ax = axes[0]
    for corner in ['FF', 'TT', 'SS']:
        subset = data[data['corner'] == corner]['PMON_RING_CMOS_res'] / 1e6
        ax.hist(subset.dropna(), bins=80, alpha=0.5, label=corner,
                color=CORNER_COLORS[corner], edgecolor='white', linewidth=0.3)
    ax.set_xlabel('PMON_RING_CMOS_res (×10⁶)')
    ax.set_ylabel('Count')
    ax.set_title('PMON Distribution Overlap')
    ax.legend()
    ax.grid(alpha=0.3)

    # Range bars
    ax = axes[1]
    for i, corner in enumerate(['FF', 'TT', 'SS']):
        subset = data[data['corner'] == corner]['PMON_RING_CMOS_res'] / 1e6
        ax.barh(i, subset.max() - subset.min(), left=subset.min(), height=0.6,
                color=CORNER_COLORS[corner], alpha=0.7, edgecolor='black')
        ax.text(subset.mean(), i, f'{subset.min():.0f} – {subset.max():.0f}M',
                ha='center', va='center', fontsize=9, fontweight='bold')
    ax.set_yticks([0, 1, 2])
    ax.set_yticklabels(['FF', 'TT', 'SS'])
    ax.set_xlabel('PMON_RING_CMOS_res (×10⁶)')
    ax.set_title('PMON Range Per Corner')
    ax.grid(alpha=0.3)

    fig.tight_layout()
    save_plot(fig, '07_pmon_overlap.png')


def plot_08_vbgr_after_trim(data):
    """Plot 08: vbgr stability after applying trim codes."""
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))
    fig.suptitle('Plot 08: vbgr After Trim Compensation vs Temperature',
                 fontsize=14, fontweight='bold')

    for i, corner in enumerate(['TT', 'SS', 'FF']):
        ax = axes[i]
        subset = data[(data['corner'] == corner) & data['vbgr'].notna()]
        if len(subset) == 0:
            ax.text(0.5, 0.5, 'No vbgr data', transform=ax.transAxes, ha='center')
            continue

        vdd_vals = sorted(subset['vdd'].unique())
        cmap = plt.cm.coolwarm
        for j, vdd in enumerate(vdd_vals):
            vdd_data = subset[subset['vdd'] == vdd].sort_values('temperature')
            color = cmap(j / max(len(vdd_vals) - 1, 1))
            ax.plot(vdd_data['temperature'], vdd_data['vbgr'] * 1000,
                    color=color, alpha=0.7, linewidth=0.8, label=f'{vdd:.2f}V')

        ax.axhline(y=600, color='black', linestyle='--', linewidth=1.5, label='600mV')
        ax.set_xlabel('Temperature (°C)')
        ax.set_ylabel('vbgr (mV)')
        ax.set_title(f'{corner} — vbgr vs Temp')
        ax.grid(alpha=0.3)

        # Stats
        mean_err = abs(subset['vbgr'].mean() - 0.600) * 1000
        max_err = abs(subset['vbgr'] - 0.600).max() * 1000
        ax.text(0.02, 0.98, f'Mean err: {mean_err:.1f}mV\nMax err: {max_err:.1f}mV',
                transform=ax.transAxes, va='top', fontsize=9,
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
        if i == 2:
            ax.legend(fontsize=6, loc='best', ncol=2, title='VDD')

    fig.tight_layout()
    save_plot(fig, '08_vbgr_after_trim.png')


def plot_09_correlation_matrix(data):
    """Plot 09: Correlation matrix of all numeric features."""
    fig, ax = plt.subplots(figsize=(10, 8))
    fig.suptitle('Plot 09: Feature Correlation Matrix', fontsize=14, fontweight='bold')

    numeric_cols = ['vdd', 'temperature', 'PMON_RING_CMOS_res', 'pctrl_int', 'nctrl_int']
    if 'vbgr' in data.columns:
        numeric_cols.append('vbgr')

    corr = data[numeric_cols].corr()
    im = ax.imshow(corr, cmap='RdBu_r', vmin=-1, vmax=1)
    ax.set_xticks(range(len(numeric_cols)))
    ax.set_yticks(range(len(numeric_cols)))
    labels = ['VDD', 'Temp', 'PMON_res', 'pctrl', 'nctrl']
    if 'vbgr' in numeric_cols:
        labels.append('vbgr')
    ax.set_xticklabels(labels, rotation=45, ha='right')
    ax.set_yticklabels(labels)

    # Annotate
    for i in range(len(numeric_cols)):
        for j in range(len(numeric_cols)):
            val = corr.iloc[i, j]
            color = 'white' if abs(val) > 0.5 else 'black'
            ax.text(j, i, f'{val:.3f}', ha='center', va='center',
                    fontsize=10, color=color, fontweight='bold')

    plt.colorbar(im, ax=ax, label='Pearson Correlation')
    fig.tight_layout()
    save_plot(fig, '09_correlation_matrix.png')


def plot_10_pctrl_nctrl_relationship(data):
    """Plot 10: pctrl vs nctrl relationship."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle('Plot 10: pctrl vs nctrl Relationship', fontsize=14, fontweight='bold')

    # Scatter
    ax = axes[0]
    for corner in ['TT', 'SS', 'FF']:
        subset = data[data['corner'] == corner]
        ax.scatter(subset['pctrl_int'], subset['nctrl_int'],
                   alpha=0.3, s=10, label=corner, color=CORNER_COLORS[corner])
    ax.set_xlabel('pctrl (decimal)')
    ax.set_ylabel('nctrl (decimal)')
    ax.set_title('pctrl vs nctrl — Colored by Corner')
    ax.legend(markerscale=3)
    ax.grid(alpha=0.3)

    # Unique combo bar chart
    ax = axes[1]
    data_clean = data.dropna(subset=['pctrl_int', 'nctrl_int']).copy()
    data_clean['combo'] = ('p=' + data_clean['pctrl_int'].astype(int).astype(str) +
                           ' n=' + data_clean['nctrl_int'].astype(int).astype(str))
    combo_counts = data_clean.groupby(['combo', 'corner']).size().unstack(fill_value=0)

    combo_counts.plot(kind='bar', ax=ax, color=[CORNER_COLORS[c] for c in combo_counts.columns
                                                 if c in CORNER_COLORS],
                      edgecolor='black', linewidth=0.5)
    ax.set_xlabel('(pctrl, nctrl) Combination')
    ax.set_ylabel('Sample Count')
    ax.set_title(f'Unique Trim Combos ({len(combo_counts)} total)')
    ax.tick_params(axis='x', rotation=45)
    ax.grid(alpha=0.3)
    ax.legend(title='Corner')

    fig.tight_layout()
    save_plot(fig, '10_pctrl_nctrl_relationship.png')


def plot_11_data_summary(data):
    """Plot 11: Summary statistics dashboard."""
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('Plot 11: Data Summary Dashboard', fontsize=14, fontweight='bold')

    # Samples per corner
    ax = axes[0, 0]
    corner_counts = data['corner'].value_counts()
    ax.bar(corner_counts.index, corner_counts.values,
           color=[CORNER_COLORS.get(c, 'gray') for c in corner_counts.index],
           edgecolor='black')
    ax.set_ylabel('Sample Count')
    ax.set_title('Samples Per Corner')
    for i, (c, v) in enumerate(zip(corner_counts.index, corner_counts.values)):
        ax.text(i, v + 30, str(v), ha='center', fontsize=10, fontweight='bold')

    # VDD distribution
    ax = axes[0, 1]
    for corner in ['TT', 'SS', 'FF']:
        subset = data[data['corner'] == corner]
        vdd_counts = subset['vdd'].value_counts().sort_index()
        ax.plot(vdd_counts.index, vdd_counts.values, 'o-',
                color=CORNER_COLORS[corner], label=corner, alpha=0.7)
    ax.set_xlabel('VDD (V)')
    ax.set_ylabel('Count')
    ax.set_title('Samples Per VDD Level')
    ax.legend()
    ax.grid(alpha=0.3)

    # Temperature distribution
    ax = axes[1, 0]
    ax.hist(data['temperature'], bins=50, color='#9C27B0', alpha=0.7, edgecolor='white')
    ax.set_xlabel('Temperature (°C)')
    ax.set_ylabel('Count')
    ax.set_title('Temperature Distribution')
    ax.grid(alpha=0.3)

    # PMON range per corner
    ax = axes[1, 1]
    for i, corner in enumerate(['FF', 'TT', 'SS']):
        subset = data[data['corner'] == corner]['PMON_RING_CMOS_res'] / 1e6
        parts = ax.violinplot([subset.dropna().values], positions=[i], showmeans=True)
        for pc in parts['bodies']:
            pc.set_facecolor(CORNER_COLORS[corner])
            pc.set_alpha(0.6)
    ax.set_xticks([0, 1, 2])
    ax.set_xticklabels(['FF', 'TT', 'SS'])
    ax.set_ylabel('PMON_RING_CMOS_res (×10⁶)')
    ax.set_title('PMON Distribution Per Corner')
    ax.grid(alpha=0.3)

    fig.tight_layout()
    save_plot(fig, '11_data_summary.png')


# ─── Main ─────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print("=" * 60)
    print("BGR Data Visualization Pipeline")
    print("=" * 60)

    print("\nLoading data...")
    data = load_all_corners()

    # Print summary stats
    print("\n" + "=" * 60)
    print("DATA SUMMARY")
    print("=" * 60)
    for corner in ['TT', 'SS', 'FF']:
        subset = data[data['corner'] == corner]
        pctrl_vals = sorted(subset['pctrl_int'].dropna().unique().astype(int))
        nctrl_vals = sorted(subset['nctrl_int'].dropna().unique().astype(int))
        print(f"\n{corner}:")
        print(f"  pctrl unique: {pctrl_vals} ({len(pctrl_vals)} values)")
        print(f"  nctrl unique: {nctrl_vals} ({len(nctrl_vals)} values)")
        if 'vbgr' in subset.columns:
            vbgr = subset['vbgr'].dropna()
            if len(vbgr) > 0:
                print(f"  vbgr: {vbgr.min():.6f} – {vbgr.max():.6f}V "
                      f"(mean={vbgr.mean():.6f}V, std={vbgr.std()*1000:.2f}mV)")

    # Generate all plots
    print("\n" + "=" * 60)
    print("GENERATING PLOTS")
    print("=" * 60)

    plot_01_vbgr_distribution(data)
    plot_02_trim_distributions(data)
    plot_03_pmon_vs_trim(data)
    plot_04_trim_heatmaps(data)
    plot_05_3d_pvt_clusters(data)
    plot_06_trim_vs_temp(data)
    plot_07_pmon_overlap(data)
    plot_08_vbgr_after_trim(data)
    plot_09_correlation_matrix(data)
    plot_10_pctrl_nctrl_relationship(data)
    plot_11_data_summary(data)

    print("\n" + "=" * 60)
    print(f"ALL PLOTS SAVED TO: {PLOTS_DIR}")
    print("=" * 60)
