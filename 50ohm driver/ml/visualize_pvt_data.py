"""
TSMC 28nm Driver Impedance Matching - Comprehensive Data Visualization
=====================================================================
Visualizes the PVT lookup table data across all 5 process corners.
Includes 3D PVT space plots with trim bit clusters.
"""

import sys
import io
# Fix Windows encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import matplotlib.cm as cm
from matplotlib.colors import Normalize
import os
import warnings
warnings.filterwarnings('ignore')

# ─── CONFIG ────────────────────────────────────────────────────────────
EXCEL_FILE = r"TSMC28nm_DRV_ML_MAR6_LookUP_Table_Mar20_ML Predictions.xlsx"
OUTPUT_DIR = r"plots"
os.makedirs(OUTPUT_DIR, exist_ok=True)

CORNER_SHEETS = {
    'FF': 'FF_vdd_temp',
    'SS': 'SS_vdd_test',
    'TT': 'TT_vdd_test',
    'FS': 'FS_vdd_test',
    'SF': 'SF_vdd_test',
}

# Standard column names (the Excel headers differ slightly)
COL_NAMES = ['Corner', 'vreg', 'temperature', 'PULL_UP_RES', 'PULL_DN_RES',
             'pmon_cmos_res', 'pmon_cmos', 'pvtp_raw', 'pvtn_raw',
             'PULL_UP_RES_new', 'PULL_DN_RES_new']


# ─── HELPER FUNCTIONS ──────────────────────────────────────────────────

def pad_trim_bits(val, width=8):
    """Pad binary string to 8 bits by adding leading zeros."""
    if pd.isna(val) or str(val).strip().lower() == 'na':
        return None
    # Remove dashes (formatting separator)
    bits = str(val).replace('-', '').strip()
    # Pad to 8 bits
    return bits.zfill(width)


def trim_bits_to_int(val):
    """Convert binary string to integer."""
    if val is None or pd.isna(val):
        return None
    try:
        return int(val, 2)
    except ValueError:
        return None


def load_all_corners():
    """Load all corner data into a combined DataFrame."""
    all_data = []
    
    for corner_name, sheet_name in CORNER_SHEETS.items():
        print(f"Loading {corner_name} from sheet '{sheet_name}'...")
        df = pd.read_excel(EXCEL_FILE, sheet_name=sheet_name, header=0)
        
        # Take only first 11 columns (some sheets have extra empty cols)
        df = df.iloc[:, :11]
        df.columns = COL_NAMES
        
        # Force numeric conversion on all expected numeric columns
        for col in ['vreg', 'temperature', 'PULL_UP_RES', 'PULL_DN_RES',
                    'pmon_cmos_res', 'pmon_cmos', 'PULL_UP_RES_new', 'PULL_DN_RES_new']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Add corner label
        df['corner_label'] = corner_name
        
        # Process trim bits — pad to 8 bits
        df['pvtp_8bit'] = df['pvtp_raw'].apply(pad_trim_bits)
        df['pvtn_8bit'] = df['pvtn_raw'].apply(pad_trim_bits)
        
        # Convert to integer
        df['pvtp_int'] = df['pvtp_8bit'].apply(trim_bits_to_int)
        df['pvtn_int'] = df['pvtn_8bit'].apply(trim_bits_to_int)
        
        # Count NAs
        na_pvtp = df['pvtp_int'].isna().sum()
        na_pvtn = df['pvtn_int'].isna().sum()
        print(f"  {corner_name}: {len(df)} rows, pvtp NAs: {na_pvtp}, pvtn NAs: {na_pvtn}")
        
        all_data.append(df)
    
    combined = pd.concat(all_data, ignore_index=True)
    
    # Drop rows with NA trim bits
    before = len(combined)
    combined = combined.dropna(subset=['pvtp_int', 'pvtn_int'])
    after = len(combined)
    print(f"\nDropped {before - after} rows with NA values. Total: {after} rows")
    
    return combined


# ─── VISUALIZATION FUNCTIONS ───────────────────────────────────────────

def plot_1_resistance_distributions(df):
    """Distribution of original pull-up/down resistances across corners."""
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle('Resistance Distributions Across Process Corners', fontsize=16, fontweight='bold')
    
    corners = df['corner_label'].unique()
    colors = {'FF': '#e74c3c', 'SS': '#3498db', 'TT': '#2ecc71', 'FS': '#f39c12', 'SF': '#9b59b6'}
    
    # Original Pull-Up
    ax = axes[0, 0]
    for c in corners:
        data = df[df['corner_label'] == c]['PULL_UP_RES'].abs()
        ax.hist(data, bins=50, alpha=0.5, label=c, color=colors[c])
    ax.set_title('|PULL_UP_RES| (Original)', fontweight='bold')
    ax.set_xlabel('Resistance (Ω)')
    ax.legend()
    ax.axvline(50, color='red', linestyle='--', linewidth=2, label='50Ω target')
    
    # Original Pull-Down
    ax = axes[0, 1]
    for c in corners:
        data = df[df['corner_label'] == c]['PULL_DN_RES']
        ax.hist(data, bins=50, alpha=0.5, label=c, color=colors[c])
    ax.set_title('PULL_DN_RES (Original)', fontweight='bold')
    ax.set_xlabel('Resistance (Ω)')
    ax.legend()
    ax.axvline(50, color='red', linestyle='--', linewidth=2)
    
    # New Pull-Up (after trimming)
    ax = axes[1, 0]
    for c in corners:
        data = df[df['corner_label'] == c]['PULL_UP_RES_new'].abs()
        ax.hist(data, bins=50, alpha=0.5, label=c, color=colors[c])
    ax.set_title('|PULL_UP_RES_new| (After Trimming)', fontweight='bold')
    ax.set_xlabel('Resistance (Ω)')
    ax.legend()
    ax.axvline(50, color='red', linestyle='--', linewidth=2)
    
    # New Pull-Down (after trimming)
    ax = axes[1, 1]
    for c in corners:
        data = df[df['corner_label'] == c]['PULL_DN_RES_new'].abs()
        ax.hist(data, bins=50, alpha=0.5, label=c, color=colors[c])
    ax.set_title('|PULL_DN_RES_new| (After Trimming)', fontweight='bold')
    ax.set_xlabel('Resistance (Ω)')
    ax.legend()
    ax.axvline(50, color='red', linestyle='--', linewidth=2)
    
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, '01_resistance_distributions.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("✓ Plot 1: Resistance distributions saved")


def plot_2_trim_bit_distributions(df):
    """Distribution of trim bit integer values across corners."""
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))
    fig.suptitle('Trim Bit Value Distributions (8-bit padded)', fontsize=16, fontweight='bold')
    
    corners = df['corner_label'].unique()
    colors = {'FF': '#e74c3c', 'SS': '#3498db', 'TT': '#2ecc71', 'FS': '#f39c12', 'SF': '#9b59b6'}
    
    ax = axes[0]
    for c in corners:
        data = df[df['corner_label'] == c]['pvtp_int']
        ax.hist(data, bins=range(0, 260, 1), alpha=0.5, label=c, color=colors[c])
    ax.set_title('pvtp<7:0> Distribution', fontweight='bold')
    ax.set_xlabel('Trim bit value (decimal)')
    ax.set_ylabel('Count')
    ax.legend()
    
    ax = axes[1]
    for c in corners:
        data = df[df['corner_label'] == c]['pvtn_int']
        ax.hist(data, bins=range(0, 260, 1), alpha=0.5, label=c, color=colors[c])
    ax.set_title('pvtn<7:0> Distribution', fontweight='bold')
    ax.set_xlabel('Trim bit value (decimal)')
    ax.set_ylabel('Count')
    ax.legend()
    
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, '02_trim_bit_distributions.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("✓ Plot 2: Trim bit distributions saved")


def plot_3_pmon_vs_trim(df):
    """pmon_cmos_res vs trim bits — the core relationship."""
    fig, axes = plt.subplots(1, 2, figsize=(16, 7))
    fig.suptitle('pmon_cmos_res vs Trim Bits (Key Relationship)', fontsize=16, fontweight='bold')
    
    colors = {'FF': '#e74c3c', 'SS': '#3498db', 'TT': '#2ecc71', 'FS': '#f39c12', 'SF': '#9b59b6'}
    
    for c in df['corner_label'].unique():
        mask = df['corner_label'] == c
        axes[0].scatter(df.loc[mask, 'pmon_cmos_res'], df.loc[mask, 'pvtp_int'],
                       s=3, alpha=0.3, label=c, color=colors[c])
        axes[1].scatter(df.loc[mask, 'pmon_cmos_res'], df.loc[mask, 'pvtn_int'],
                       s=3, alpha=0.3, label=c, color=colors[c])
    
    axes[0].set_title('pmon_cmos_res → pvtp<7:0>', fontweight='bold')
    axes[0].set_xlabel('pmon_cmos_res')
    axes[0].set_ylabel('pvtp (decimal)')
    axes[0].legend(markerscale=5)
    
    axes[1].set_title('pmon_cmos_res → pvtn<7:0>', fontweight='bold')
    axes[1].set_xlabel('pmon_cmos_res')
    axes[1].set_ylabel('pvtn (decimal)')
    axes[1].legend(markerscale=5)
    
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, '03_pmon_vs_trim.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("✓ Plot 3: pmon_cmos_res vs trim bits saved")


def plot_4_temp_voltage_heatmaps(df):
    """Heatmaps of trim bits vs temperature and voltage for each corner."""
    fig, axes = plt.subplots(5, 2, figsize=(18, 30))
    fig.suptitle('Trim Bit Heatmaps: Temperature × Voltage (pvtp)', fontsize=18, fontweight='bold')
    
    corners = ['FF', 'SS', 'TT', 'FS', 'SF']
    
    for i, c in enumerate(corners):
        cdf = df[df['corner_label'] == c]
        
        # pvtp heatmap
        pivot_p = cdf.pivot_table(index='temperature', columns='vreg', values='pvtp_int', aggfunc='mean')
        im = axes[i, 0].imshow(pivot_p.values, aspect='auto', cmap='viridis',
                               extent=[pivot_p.columns.min(), pivot_p.columns.max(),
                                       pivot_p.index.max(), pivot_p.index.min()])
        axes[i, 0].set_title(f'{c} — pvtp<7:0>', fontweight='bold')
        axes[i, 0].set_xlabel('Vreg (V)')
        axes[i, 0].set_ylabel('Temperature (°C)')
        plt.colorbar(im, ax=axes[i, 0], label='pvtp (dec)')
        
        # pvtn heatmap
        pivot_n = cdf.pivot_table(index='temperature', columns='vreg', values='pvtn_int', aggfunc='mean')
        im = axes[i, 1].imshow(pivot_n.values, aspect='auto', cmap='plasma',
                               extent=[pivot_n.columns.min(), pivot_n.columns.max(),
                                       pivot_n.index.max(), pivot_n.index.min()])
        axes[i, 1].set_title(f'{c} — pvtn<7:0>', fontweight='bold')
        axes[i, 1].set_xlabel('Vreg (V)')
        axes[i, 1].set_ylabel('Temperature (°C)')
        plt.colorbar(im, ax=axes[i, 1], label='pvtn (dec)')
    
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, '04_trim_heatmaps.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("✓ Plot 4: Temperature × Voltage heatmaps saved")


def plot_5_3d_pvt_trim_clusters(df):
    """
    3D visualization: P (pmon_cmos_res), V (vreg), T (temperature) as axes,
    trim bits as color — visualize the PVT space clusters.
    """
    fig = plt.figure(figsize=(20, 16))
    
    corners = ['FF', 'SS', 'TT', 'FS', 'SF']
    
    # ─── 3D plot for pvtp ───
    ax1 = fig.add_subplot(2, 2, 1, projection='3d')
    for c in corners:
        cdf = df[df['corner_label'] == c]
        # Subsample for visibility
        sample = cdf.sample(min(500, len(cdf)), random_state=42)
        sc = ax1.scatter(sample['pmon_cmos_res'] / 1e6, sample['vreg'], sample['temperature'],
                        c=sample['pvtp_int'], cmap='viridis', s=8, alpha=0.6)
    ax1.set_xlabel('pmon_cmos_res (×10⁶)', fontsize=10)
    ax1.set_ylabel('Vreg (V)', fontsize=10)
    ax1.set_zlabel('Temp (°C)', fontsize=10)
    ax1.set_title('3D PVT Space — pvtp Color', fontweight='bold', fontsize=12)
    plt.colorbar(sc, ax=ax1, shrink=0.5, label='pvtp (dec)')
    
    # ─── 3D plot for pvtn ───
    ax2 = fig.add_subplot(2, 2, 2, projection='3d')
    for c in corners:
        cdf = df[df['corner_label'] == c]
        sample = cdf.sample(min(500, len(cdf)), random_state=42)
        sc = ax2.scatter(sample['pmon_cmos_res'] / 1e6, sample['vreg'], sample['temperature'],
                        c=sample['pvtn_int'], cmap='plasma', s=8, alpha=0.6)
    ax2.set_xlabel('pmon_cmos_res (×10⁶)', fontsize=10)
    ax2.set_ylabel('Vreg (V)', fontsize=10)
    ax2.set_zlabel('Temp (°C)', fontsize=10)
    ax2.set_title('3D PVT Space — pvtn Color', fontweight='bold', fontsize=12)
    plt.colorbar(sc, ax=ax2, shrink=0.5, label='pvtn (dec)')
    
    # ─── 3D plot colored by CORNER ───
    ax3 = fig.add_subplot(2, 2, 3, projection='3d')
    corner_colors = {'FF': '#e74c3c', 'SS': '#3498db', 'TT': '#2ecc71', 'FS': '#f39c12', 'SF': '#9b59b6'}
    for c in corners:
        cdf = df[df['corner_label'] == c]
        sample = cdf.sample(min(500, len(cdf)), random_state=42)
        ax3.scatter(sample['pmon_cmos_res'] / 1e6, sample['vreg'], sample['temperature'],
                   c=corner_colors[c], s=8, alpha=0.6, label=c)
    ax3.set_xlabel('pmon_cmos_res (×10⁶)', fontsize=10)
    ax3.set_ylabel('Vreg (V)', fontsize=10)
    ax3.set_zlabel('Temp (°C)', fontsize=10)
    ax3.set_title('3D PVT Space — Corner Clusters', fontweight='bold', fontsize=12)
    ax3.legend(loc='upper left', fontsize=9)
    
    # ─── 3D plot: pmon_cmos_res vs pvtp vs pvtn ───
    ax4 = fig.add_subplot(2, 2, 4, projection='3d')
    for c in corners:
        cdf = df[df['corner_label'] == c]
        sample = cdf.sample(min(500, len(cdf)), random_state=42)
        ax4.scatter(sample['pmon_cmos_res'] / 1e6, sample['pvtp_int'], sample['pvtn_int'],
                   c=corner_colors[c], s=8, alpha=0.6, label=c)
    ax4.set_xlabel('pmon_cmos_res (×10⁶)', fontsize=10)
    ax4.set_ylabel('pvtp (dec)', fontsize=10)
    ax4.set_zlabel('pvtn (dec)', fontsize=10)
    ax4.set_title('pmon vs Trim Bits — Corner Clusters', fontweight='bold', fontsize=12)
    ax4.legend(loc='upper left', fontsize=9)
    
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, '05_3d_pvt_clusters.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("✓ Plot 5: 3D PVT space clusters saved")


def plot_6_trim_vs_temp_per_voltage(df):
    """Line plots: trim bits vs temperature for each voltage, per corner."""
    fig, axes = plt.subplots(5, 2, figsize=(18, 28))
    fig.suptitle('Trim Bits vs Temperature (one line per Vreg)', fontsize=18, fontweight='bold')
    
    corners = ['FF', 'SS', 'TT', 'FS', 'SF']
    cmap = cm.get_cmap('coolwarm')
    
    for i, c in enumerate(corners):
        cdf = df[df['corner_label'] == c]
        vregs = sorted(cdf['vreg'].unique())
        norm = Normalize(vmin=min(vregs), vmax=max(vregs))
        
        for v in vregs:
            vdf = cdf[cdf['vreg'] == v].sort_values('temperature')
            color = cmap(norm(v))
            axes[i, 0].plot(vdf['temperature'], vdf['pvtp_int'], alpha=0.7, color=color, linewidth=1)
            axes[i, 1].plot(vdf['temperature'], vdf['pvtn_int'], alpha=0.7, color=color, linewidth=1)
        
        axes[i, 0].set_title(f'{c} — pvtp vs Temperature', fontweight='bold')
        axes[i, 0].set_xlabel('Temperature (°C)')
        axes[i, 0].set_ylabel('pvtp (dec)')
        
        axes[i, 1].set_title(f'{c} — pvtn vs Temperature', fontweight='bold')
        axes[i, 1].set_xlabel('Temperature (°C)')
        axes[i, 1].set_ylabel('pvtn (dec)')
        
        # Add Vreg colorbar
        sm = cm.ScalarMappable(cmap=cmap, norm=norm)
        sm.set_array([])
        plt.colorbar(sm, ax=axes[i, 1], label='Vreg (V)')
    
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, '06_trim_vs_temp_lines.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("✓ Plot 6: Trim vs Temperature per voltage saved")


def plot_7_pmon_res_distribution(df):
    """pmon_cmos_res distribution and its relationship with corner + trim bits."""
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle('Process Monitor (pmon_cmos_res) Analysis', fontsize=16, fontweight='bold')
    
    colors = {'FF': '#e74c3c', 'SS': '#3498db', 'TT': '#2ecc71', 'FS': '#f39c12', 'SF': '#9b59b6'}
    
    # Distribution per corner
    ax = axes[0, 0]
    for c in df['corner_label'].unique():
        data = df[df['corner_label'] == c]['pmon_cmos_res'] / 1e6
        ax.hist(data, bins=50, alpha=0.5, label=c, color=colors[c])
    ax.set_title('pmon_cmos_res Distribution by Corner', fontweight='bold')
    ax.set_xlabel('pmon_cmos_res (×10⁶)')
    ax.legend()
    
    # pmon_cmos_res vs Temperature
    ax = axes[0, 1]
    for c in df['corner_label'].unique():
        cdf = df[df['corner_label'] == c]
        # Just show one voltage (median)
        median_v = cdf['vreg'].median()
        vdf = cdf[cdf['vreg'] == sorted(cdf['vreg'].unique())[len(cdf['vreg'].unique())//2]]
        ax.plot(vdf['temperature'], vdf['pmon_cmos_res'] / 1e6, alpha=0.6, label=c, color=colors[c])
    ax.set_title('pmon_cmos_res vs Temperature (mid Vreg)', fontweight='bold')
    ax.set_xlabel('Temperature (°C)')
    ax.set_ylabel('pmon_cmos_res (×10⁶)')
    ax.legend()
    
    # pmon_cmos_res vs original resistance
    ax = axes[1, 0]
    for c in df['corner_label'].unique():
        cdf = df[df['corner_label'] == c].sample(min(500, len(df[df['corner_label'] == c])), random_state=42)
        ax.scatter(cdf['pmon_cmos_res'] / 1e6, cdf['PULL_UP_RES'].abs(),
                  s=5, alpha=0.4, label=c, color=colors[c])
    ax.set_title('pmon_cmos_res vs |PULL_UP_RES| (Original)', fontweight='bold')
    ax.set_xlabel('pmon_cmos_res (×10⁶)')
    ax.set_ylabel('|PULL_UP_RES| (Ω)')
    ax.legend(markerscale=5)
    
    # Correlation: pmon_cmos_res vs new resistance
    ax = axes[1, 1]
    for c in df['corner_label'].unique():
        cdf = df[df['corner_label'] == c].sample(min(500, len(df[df['corner_label'] == c])), random_state=42)
        ax.scatter(cdf['pmon_cmos_res'] / 1e6, cdf['PULL_UP_RES_new'].abs(),
                  s=5, alpha=0.4, label=c, color=colors[c])
    ax.set_title('pmon_cmos_res vs |PULL_UP_RES_new| (After Trim)', fontweight='bold')
    ax.set_xlabel('pmon_cmos_res (×10⁶)')
    ax.set_ylabel('|PULL_UP_RES_new| (Ω)')
    ax.axhline(50, color='red', linestyle='--', linewidth=2, label='50Ω target')
    ax.legend(markerscale=5)
    
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, '07_pmon_analysis.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("✓ Plot 7: pmon_cmos_res analysis saved")


def plot_8_impedance_accuracy(df):
    """How close are the trimmed resistances to 50Ω?"""
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle('Impedance Matching Accuracy (After Trimming)', fontsize=16, fontweight='bold')
    
    colors = {'FF': '#e74c3c', 'SS': '#3498db', 'TT': '#2ecc71', 'FS': '#f39c12', 'SF': '#9b59b6'}
    
    # Error distribution: Pull-Up
    ax = axes[0, 0]
    for c in df['corner_label'].unique():
        error = df[df['corner_label'] == c]['PULL_UP_RES_new'].abs() - 50
        ax.hist(error, bins=50, alpha=0.5, label=c, color=colors[c])
    ax.set_title('Pull-Up Error (|RES_new| - 50Ω)', fontweight='bold')
    ax.set_xlabel('Error (Ω)')
    ax.axvline(0, color='black', linestyle='--')
    ax.legend()
    
    # Error distribution: Pull-Down
    ax = axes[0, 1]
    for c in df['corner_label'].unique():
        error = df[df['corner_label'] == c]['PULL_DN_RES_new'].abs() - 50
        ax.hist(error, bins=50, alpha=0.5, label=c, color=colors[c])
    ax.set_title('Pull-Down Error (|RES_new| - 50Ω)', fontweight='bold')
    ax.set_xlabel('Error (Ω)')
    ax.axvline(0, color='black', linestyle='--')
    ax.legend()
    
    # Error vs Temperature
    ax = axes[1, 0]
    for c in df['corner_label'].unique():
        cdf = df[df['corner_label'] == c]
        mid_v = sorted(cdf['vreg'].unique())[len(cdf['vreg'].unique())//2]
        vdf = cdf[cdf['vreg'] == mid_v].sort_values('temperature')
        error = vdf['PULL_UP_RES_new'].abs() - 50
        ax.plot(vdf['temperature'], error, alpha=0.6, label=c, color=colors[c])
    ax.set_title('Pull-Up Error vs Temperature (mid Vreg)', fontweight='bold')
    ax.set_xlabel('Temperature (°C)')
    ax.set_ylabel('Error (Ω)')
    ax.axhline(0, color='black', linestyle='--')
    ax.legend()
    
    # Summary table as text
    ax = axes[1, 1]
    ax.axis('off')
    summary_data = []
    for c in ['FF', 'SS', 'TT', 'FS', 'SF']:
        cdf = df[df['corner_label'] == c]
        pu_err = (cdf['PULL_UP_RES_new'].abs() - 50)
        pd_err = (cdf['PULL_DN_RES_new'].abs() - 50)
        summary_data.append([c,
                            f'{pu_err.mean():.3f}', f'{pu_err.std():.3f}',
                            f'{pd_err.mean():.3f}', f'{pd_err.std():.3f}'])
    
    table = ax.table(cellText=summary_data,
                    colLabels=['Corner', 'PU Mean Err', 'PU Std', 'PD Mean Err', 'PD Std'],
                    loc='center', cellLoc='center')
    table.auto_set_font_size(False)
    table.set_fontsize(11)
    table.scale(1.2, 1.8)
    ax.set_title('Impedance Error Summary (Ω)', fontweight='bold', pad=20)
    
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, '08_impedance_accuracy.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("✓ Plot 8: Impedance accuracy analysis saved")


def plot_9_correlation_matrix(df):
    """Correlation matrix of all numeric features."""
    fig, ax = plt.subplots(figsize=(12, 10))
    
    numeric_cols = ['vreg', 'temperature', 'PULL_UP_RES', 'PULL_DN_RES', 
                    'pmon_cmos_res', 'pvtp_int', 'pvtn_int',
                    'PULL_UP_RES_new', 'PULL_DN_RES_new']
    
    corr = df[numeric_cols].corr()
    
    im = ax.imshow(corr, cmap='RdBu_r', vmin=-1, vmax=1)
    ax.set_xticks(range(len(numeric_cols)))
    ax.set_yticks(range(len(numeric_cols)))
    ax.set_xticklabels(numeric_cols, rotation=45, ha='right', fontsize=10)
    ax.set_yticklabels(numeric_cols, fontsize=10)
    
    for i in range(len(numeric_cols)):
        for j in range(len(numeric_cols)):
            ax.text(j, i, f'{corr.iloc[i, j]:.2f}', ha='center', va='center',
                   fontsize=9, color='white' if abs(corr.iloc[i, j]) > 0.5 else 'black')
    
    plt.colorbar(im, ax=ax, label='Correlation')
    ax.set_title('Feature Correlation Matrix', fontsize=16, fontweight='bold')
    
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, '09_correlation_matrix.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("✓ Plot 9: Correlation matrix saved")


def plot_10_pvtp_pvtn_relationship(df):
    """Relationship between pvtp and pvtn — are they correlated?"""
    fig, axes = plt.subplots(1, 2, figsize=(16, 7))
    fig.suptitle('pvtp vs pvtn Relationship', fontsize=16, fontweight='bold')
    
    colors = {'FF': '#e74c3c', 'SS': '#3498db', 'TT': '#2ecc71', 'FS': '#f39c12', 'SF': '#9b59b6'}
    
    ax = axes[0]
    for c in df['corner_label'].unique():
        cdf = df[df['corner_label'] == c].sample(min(500, len(df[df['corner_label'] == c])), random_state=42)
        ax.scatter(cdf['pvtp_int'], cdf['pvtn_int'], s=8, alpha=0.5, label=c, color=colors[c])
    ax.set_title('pvtp vs pvtn (all corners)', fontweight='bold')
    ax.set_xlabel('pvtp (decimal)')
    ax.set_ylabel('pvtn (decimal)')
    ax.legend(markerscale=5)
    
    # Difference
    ax = axes[1]
    for c in df['corner_label'].unique():
        cdf = df[df['corner_label'] == c]
        diff = cdf['pvtp_int'] - cdf['pvtn_int']
        ax.hist(diff, bins=30, alpha=0.5, label=f'{c} (μ={diff.mean():.1f})', color=colors[c])
    ax.set_title('pvtp - pvtn Difference', fontweight='bold')
    ax.set_xlabel('pvtp - pvtn')
    ax.legend()
    
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, '10_pvtp_pvtn_relationship.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("✓ Plot 10: pvtp vs pvtn relationship saved")


def print_data_summary(df):
    """Print comprehensive data summary."""
    print("\n" + "=" * 70)
    print("DATA SUMMARY")
    print("=" * 70)
    
    for c in ['FF', 'SS', 'TT', 'FS', 'SF']:
        cdf = df[df['corner_label'] == c]
        print(f"\n--- {c} Corner ({len(cdf)} rows) ---")
        print(f"  pmon_cmos_res: {cdf['pmon_cmos_res'].min():.0f} – {cdf['pmon_cmos_res'].max():.0f}")
        print(f"  vreg: {cdf['vreg'].min():.2f} – {cdf['vreg'].max():.2f}")
        print(f"  temperature: {cdf['temperature'].min():.1f} – {cdf['temperature'].max():.1f}")
        print(f"  pvtp: {cdf['pvtp_int'].min():.0f} – {cdf['pvtp_int'].max():.0f} ({cdf['pvtp_int'].nunique()} unique)")
        print(f"  pvtn: {cdf['pvtn_int'].min():.0f} – {cdf['pvtn_int'].max():.0f} ({cdf['pvtn_int'].nunique()} unique)")
        pu_err = (cdf['PULL_UP_RES_new'].abs() - 50)
        pd_err = (cdf['PULL_DN_RES_new'].abs() - 50)
        print(f"  PU impedance error: {pu_err.mean():.3f} ± {pu_err.std():.3f} Ω")
        print(f"  PD impedance error: {pd_err.mean():.3f} ± {pd_err.std():.3f} Ω")
    
    print(f"\n--- Overall ---")
    print(f"  Total rows: {len(df)}")
    print(f"  pvtp range: {df['pvtp_int'].min():.0f} – {df['pvtp_int'].max():.0f}")
    print(f"  pvtn range: {df['pvtn_int'].min():.0f} – {df['pvtn_int'].max():.0f}")
    
    # Analog vs Digital note
    print("\n--- Analog vs Digital Input Note ---")
    print("  If pmon_cmos_res is ANALOG: you'll need an ADC before the ML block")
    print("  If DIGITAL (frequency counter output): can feed directly to ML block")
    print("  Ring oscillator outputs are typically converted via frequency counters")
    print("  → The ADC resolution determines the quantization of pmon_cmos_res")
    print("  → This affects the granularity of trim bit prediction")


# ─── MAIN ──────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print("Loading data from all corners...")
    df = load_all_corners()
    
    print_data_summary(df)
    
    print("\n\nGenerating visualizations...\n")
    plot_1_resistance_distributions(df)
    plot_2_trim_bit_distributions(df)
    plot_3_pmon_vs_trim(df)
    plot_4_temp_voltage_heatmaps(df)
    plot_5_3d_pvt_trim_clusters(df)
    plot_6_trim_vs_temp_per_voltage(df)
    plot_7_pmon_res_distribution(df)
    plot_8_impedance_accuracy(df)
    plot_9_correlation_matrix(df)
    # plot_10_pvtp_pvtn_relationship(df)
    
    print(f"\n✅ All 10 plots saved to '{OUTPUT_DIR}/' directory!")
    print("Open them to explore the PVT space and trim bit patterns.")
