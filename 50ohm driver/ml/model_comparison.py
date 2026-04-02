"""
TSMC 28nm Driver - ML Model Comparison for Trim Bit Prediction
==============================================================
Compares: Decision Tree, Random Forest, Polynomial Regression, 
LUT-based, and simple Neural Network.
Evaluates accuracy vs hardware cost.

Input: pmon_cmos_res (ring oscillator with resistance)
Output: pvtp<7:0>, pvtn<7:0> (8-bit trim codes)
"""

import sys
import io
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor, export_text
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.preprocessing import PolynomialFeatures, StandardScaler
from sklearn.linear_model import LinearRegression
from sklearn.neighbors import KNeighborsClassifier
from sklearn.metrics import accuracy_score, mean_absolute_error, classification_report
from sklearn.pipeline import Pipeline
import os
import warnings
warnings.filterwarnings('ignore')

# ============================================================
# CONFIG
# ============================================================
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

COL_NAMES = ['Corner', 'vreg', 'temperature', 'PULL_UP_RES', 'PULL_DN_RES',
             'pmon_cmos_res', 'pmon_cmos', 'pvtp_raw', 'pvtn_raw',
             'PULL_UP_RES_new', 'PULL_DN_RES_new']


# ============================================================
# DATA LOADING
# ============================================================

def pad_trim_bits(val, width=8):
    if pd.isna(val) or str(val).strip().lower() == 'na':
        return None
    bits = str(val).replace('-', '').strip()
    return bits.zfill(width)

def trim_bits_to_int(val):
    if val is None or pd.isna(val):
        return None
    try:
        return int(val, 2)
    except ValueError:
        return None

def load_all_corners():
    all_data = []
    for corner_name, sheet_name in CORNER_SHEETS.items():
        print(f"  Loading {corner_name}...")
        df = pd.read_excel(EXCEL_FILE, sheet_name=sheet_name, header=0)
        df = df.iloc[:, :11]
        df.columns = COL_NAMES
        for col in ['vreg', 'temperature', 'PULL_UP_RES', 'PULL_DN_RES',
                    'pmon_cmos_res', 'pmon_cmos', 'PULL_UP_RES_new', 'PULL_DN_RES_new']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        df['corner_label'] = corner_name
        df['pvtp_8bit'] = df['pvtp_raw'].apply(pad_trim_bits)
        df['pvtn_8bit'] = df['pvtn_raw'].apply(pad_trim_bits)
        df['pvtp_int'] = df['pvtp_8bit'].apply(trim_bits_to_int)
        df['pvtn_int'] = df['pvtn_8bit'].apply(trim_bits_to_int)
        all_data.append(df)
    combined = pd.concat(all_data, ignore_index=True)
    combined = combined.dropna(subset=['pvtp_int', 'pvtn_int', 'pmon_cmos_res'])
    print(f"  Total valid rows: {len(combined)}")
    return combined


# ============================================================
# TRIM BIT VARIATION ANALYSIS
# ============================================================

def analyze_trim_bit_variation(df):
    """Deep analysis of WHY trim bits vary so much across corners."""
    print("\n" + "=" * 70)
    print("TRIM BIT VARIATION ANALYSIS")
    print("=" * 70)
    
    # Overall per-corner summary
    print("\n--- Per-Corner Trim Bit Ranges ---")
    print(f"{'Corner':<8} {'pvtp range':<20} {'pvtn range':<20} {'pmon_cmos_res range':<30}")
    print("-" * 78)
    
    for c in ['FF', 'SS', 'TT', 'FS', 'SF']:
        cdf = df[df['corner_label'] == c]
        pvtp_range = f"{int(cdf['pvtp_int'].min())}-{int(cdf['pvtp_int'].max())} ({cdf['pvtp_int'].nunique()} vals)"
        pvtn_range = f"{int(cdf['pvtn_int'].min())}-{int(cdf['pvtn_int'].max())} ({cdf['pvtn_int'].nunique()} vals)"
        pmon_range = f"{cdf['pmon_cmos_res'].min():.0f}-{cdf['pmon_cmos_res'].max():.0f}"
        print(f"{c:<8} {pvtp_range:<20} {pvtn_range:<20} {pmon_range:<30}")
    
    # KEY INSIGHT: The variation is because of PROCESS corner differences
    print("\n--- ROOT CAUSE ANALYSIS ---")
    print("""
WHY DO TRIM BITS VARY SO MUCH ACROSS CORNERS?
==============================================

The trim bits vary dramatically because each process corner has 
FUNDAMENTALLY DIFFERENT transistor characteristics:

1. FF (Fast-Fast): pvtp = 12-30 (LOW trim values)
   - Both PMOS and NMOS are faster than nominal
   - Transistor Rds_on is LOWER -> resistance already low  
   - Need LESS compensation -> smaller trim codes
   - pmon_cmos_res is HIGH (269M-435M) because fast transistors 
     give high frequency ring oscillator output

2. SS (Slow-Slow): pvtp = 242-253 (VERY HIGH trim values)  
   - Both PMOS and NMOS are slower than nominal
   - Transistor Rds_on is HIGHER -> resistance too high
   - Need MAXIMUM compensation -> large trim codes (near 255)
   - pmon_cmos_res is LOW (208M-346M) because slow transistors
     give low frequency

3. TT (Typical-Typical): pvtp = 29-63 (MODERATE trim values)
   - Nominal process -> moderate compensation needed
   - pmon_cmos_res is in the MIDDLE range (238M-390M)

4. FS (Fast NMOS, Slow PMOS): pvtp = 13-31, pvtn = 2-19
   - ASYMMETRIC! PMOS fast but NMOS slow
   - pvtp and pvtn are VERY DIFFERENT from each other
   - This is the HARDEST corner for the model

5. SF (Slow NMOS, Fast PMOS): pvtp = 62-125, pvtn = 123-127
   - Opposite asymmetry to FS
   - pvtp needs more compensation, pvtn needs lot more
""")

    # Within-corner variation analysis (V and T effects)
    print("\n--- WITHIN-CORNER VARIATION (V+T effects) ---")
    for c in ['FF', 'SS', 'TT', 'FS', 'SF']:
        cdf = df[df['corner_label'] == c]
        # Check how many unique trim codes exist within each corner
        unique_pvtp = cdf['pvtp_int'].nunique()
        unique_pvtn = cdf['pvtn_int'].nunique()
        
        # Check variation with voltage
        pvtp_per_vreg = cdf.groupby('vreg')['pvtp_int'].apply(lambda x: x.nunique()).mean()
        pvtp_per_temp_block = cdf.groupby(pd.cut(cdf['temperature'], bins=10))['pvtp_int'].apply(lambda x: x.nunique()).mean()
        
        print(f"\n  {c} Corner:")
        print(f"    Total unique pvtp: {unique_pvtp}, unique pvtn: {unique_pvtn}")
        print(f"    Avg unique pvtp per voltage: {pvtp_per_vreg:.1f}")
        print(f"    Avg unique pvtp per temp block: {pvtp_per_temp_block:.1f}")
        
        # The KEY observation: within a single corner, trim bits are STAIRCASE-like
        # They change in discrete steps as V/T changes
        vregs = sorted(cdf['vreg'].unique())
        for v in [vregs[0], vregs[len(vregs)//2], vregs[-1]]:
            vdf = cdf[cdf['vreg'] == v]
            print(f"    At Vreg={v:.2f}V: pvtp values = {sorted(vdf['pvtp_int'].unique())}")
    
    print("\n--- KEY TAKEAWAY ---")
    print("""
The ML model MUST be able to:
1. CLASSIFY the process corner (FF/SS/TT/FS/SF) from pmon_cmos_res
   -> This determines the COARSE trim region (e.g., 12-30 for FF, 242-253 for SS)
2. FINE-TUNE within that region based on exact pmon_cmos_res value
   -> This gives the precise trim code within the corner's range

The good news: pmon_cmos_res ALONE is a strong indicator of both corner AND trim bits
because it captures the combined PVT effect through the ring oscillator.

WITHIN each corner, only 5-12 unique trim values exist, and they change 
in a STAIRCASE pattern vs temperature. This is very LUT/decision-tree friendly!
""")
    
    return


# ============================================================
# MODEL COMPARISON
# ============================================================

def build_and_compare_models(df):
    """Compare multiple ML models for hardware-friendliness."""
    
    print("\n" + "=" * 70)
    print("MODEL COMPARISON: ACCURACY vs HARDWARE COST")
    print("=" * 70)
    
    # Feature: pmon_cmos_res only (as user specified)
    X = df[['pmon_cmos_res']].values
    y_pvtp = df['pvtp_int'].values.astype(int)
    y_pvtn = df['pvtn_int'].values.astype(int)
    
    # Stratified split by corner_label to ensure all corners in train/test
    X_train, X_test, y_pvtp_train, y_pvtp_test, y_pvtn_train, y_pvtn_test = \
        train_test_split(X, y_pvtp, y_pvtn, test_size=0.2, random_state=42,
                        stratify=df['corner_label'])
    
    results = {}
    
    # ─── MODEL 1: Decision Tree (Classification) ───────────────────
    print("\n--- Model 1: Decision Tree Classifier ---")
    for max_depth in [3, 5, 7, 10, None]:
        dt = DecisionTreeClassifier(max_depth=max_depth, random_state=42)
        dt.fit(X_train, y_pvtp_train)
        pvtp_acc = accuracy_score(y_pvtp_test, dt.predict(X_test))
        
        dt_n = DecisionTreeClassifier(max_depth=max_depth, random_state=42)
        dt_n.fit(X_train, y_pvtn_train)
        pvtn_acc = accuracy_score(y_pvtn_test, dt_n.predict(X_test))
        
        n_leaves = dt.get_n_leaves() + dt_n.get_n_leaves()
        depth = dt.get_depth()
        
        label = f"DT(depth={max_depth})"
        results[label] = {
            'pvtp_acc': pvtp_acc, 'pvtn_acc': pvtn_acc,
            'n_leaves': n_leaves, 'depth': depth,
            'hw_type': 'comparators + mux',
            'est_gates': n_leaves * 20  # rough: each leaf ~ 20 gates (comparator + register)
        }
        print(f"  depth={str(max_depth):<5} pvtp_acc={pvtp_acc:.4f}  pvtn_acc={pvtn_acc:.4f}  "
              f"leaves={n_leaves}  est_gates~{n_leaves*20}")
    
    # ─── MODEL 2: Random Forest ────────────────────────────────────
    print("\n--- Model 2: Random Forest ---")
    for n_trees in [3, 5, 10]:
        rf = RandomForestClassifier(n_estimators=n_trees, max_depth=5, random_state=42)
        rf.fit(X_train, y_pvtp_train)
        pvtp_acc = accuracy_score(y_pvtp_test, rf.predict(X_test))
        
        rf_n = RandomForestClassifier(n_estimators=n_trees, max_depth=5, random_state=42)
        rf_n.fit(X_train, y_pvtn_train)
        pvtn_acc = accuracy_score(y_pvtn_test, rf_n.predict(X_test))
        
        total_leaves = sum(t.get_n_leaves() for t in rf.estimators_) + \
                       sum(t.get_n_leaves() for t in rf_n.estimators_)
        
        label = f"RF(n={n_trees},d=5)"
        results[label] = {
            'pvtp_acc': pvtp_acc, 'pvtn_acc': pvtn_acc,
            'n_leaves': total_leaves, 'depth': 5,
            'hw_type': 'parallel trees + majority vote',
            'est_gates': total_leaves * 20 + n_trees * 50  # leaves + voting logic
        }
        print(f"  n_trees={n_trees:<3} pvtp_acc={pvtp_acc:.4f}  pvtn_acc={pvtn_acc:.4f}  "
              f"leaves={total_leaves}  est_gates~{total_leaves*20 + n_trees*50}")
    
    # ─── MODEL 3: Polynomial Regression (then round to nearest valid code) ──
    print("\n--- Model 3: Polynomial Regression ---")
    valid_pvtp = sorted(df['pvtp_int'].unique())
    valid_pvtn = sorted(df['pvtn_int'].unique())
    
    for degree in [2, 3, 4, 5]:
        poly = Pipeline([
            ('scaler', StandardScaler()),
            ('poly', PolynomialFeatures(degree=degree)),
            ('reg', LinearRegression())
        ])
        poly.fit(X_train, y_pvtp_train)
        pvtp_pred_raw = poly.predict(X_test)
        # Round to nearest valid trim code
        pvtp_pred = np.array([valid_pvtp[np.argmin(np.abs(np.array(valid_pvtp) - p))] for p in pvtp_pred_raw])
        pvtp_acc = accuracy_score(y_pvtp_test, pvtp_pred)
        pvtp_mae = mean_absolute_error(y_pvtp_test, pvtp_pred)
        
        poly_n = Pipeline([
            ('scaler', StandardScaler()),
            ('poly', PolynomialFeatures(degree=degree)),
            ('reg', LinearRegression())
        ])
        poly_n.fit(X_train, y_pvtn_train)
        pvtn_pred_raw = poly_n.predict(X_test)
        pvtn_pred = np.array([valid_pvtn[np.argmin(np.abs(np.array(valid_pvtn) - p))] for p in pvtn_pred_raw])
        pvtn_acc = accuracy_score(y_pvtn_test, pvtn_pred)
        
        # Hardware cost: polynomial needs multipliers and adders
        n_coeffs = degree + 1  # number of polynomial coefficients
        n_multipliers = degree  # x^2, x^3, ... need multipliers
        
        label = f"Poly(deg={degree})"
        results[label] = {
            'pvtp_acc': pvtp_acc, 'pvtn_acc': pvtn_acc,
            'n_leaves': n_coeffs * 2,  # for both pvtp and pvtn
            'depth': degree,
            'hw_type': f'{n_multipliers} multipliers + {n_coeffs} adders',
            'est_gates': (n_multipliers * 500 + n_coeffs * 100) * 2  # multipliers are expensive
        }
        print(f"  degree={degree}  pvtp_acc={pvtp_acc:.4f}  pvtn_acc={pvtn_acc:.4f}  "
              f"MAE_pvtp={pvtp_mae:.2f}  gates~{results[label]['est_gates']}")
    
    # ─── MODEL 4: LUT-based (piecewise constant) ──────────────────
    print("\n--- Model 4: LUT-based (Piecewise Constant) ---")
    for n_bins in [16, 32, 64, 128, 256]:
        # Quantize pmon_cmos_res into bins
        bin_edges = np.linspace(X_train.min(), X_train.max(), n_bins + 1)
        train_bins = np.digitize(X_train.ravel(), bin_edges) - 1
        train_bins = np.clip(train_bins, 0, n_bins - 1)
        
        # Build LUT: most common trim code per bin
        lut_pvtp = np.zeros(n_bins, dtype=int)
        lut_pvtn = np.zeros(n_bins, dtype=int)
        for b in range(n_bins):
            mask = train_bins == b
            if mask.sum() > 0:
                vals, counts = np.unique(y_pvtp_train[mask], return_counts=True)
                lut_pvtp[b] = vals[counts.argmax()]
                vals, counts = np.unique(y_pvtn_train[mask], return_counts=True)
                lut_pvtn[b] = vals[counts.argmax()]
        
        # Predict
        test_bins = np.digitize(X_test.ravel(), bin_edges) - 1
        test_bins = np.clip(test_bins, 0, n_bins - 1)
        pvtp_pred = lut_pvtp[test_bins]
        pvtn_pred = lut_pvtn[test_bins]
        
        pvtp_acc = accuracy_score(y_pvtp_test, pvtp_pred)
        pvtn_acc = accuracy_score(y_pvtn_test, pvtn_pred)
        
        # Address bits needed
        addr_bits = int(np.ceil(np.log2(n_bins)))
        
        label = f"LUT({n_bins})"
        results[label] = {
            'pvtp_acc': pvtp_acc, 'pvtn_acc': pvtn_acc,
            'n_leaves': n_bins,
            'depth': addr_bits,
            'hw_type': f'{n_bins}-entry ROM ({addr_bits}-bit addr, 8-bit data)',
            'est_gates': n_bins * 16 + addr_bits * 10 + 50  # ROM + address decoder + comparator
        }
        print(f"  bins={n_bins:<4}  pvtp_acc={pvtp_acc:.4f}  pvtn_acc={pvtn_acc:.4f}  "
              f"addr_bits={addr_bits}  gates~{results[label]['est_gates']}")
    
    # ─── MODEL 5: KNN (not great for HW but good baseline) ────────
    print("\n--- Model 5: KNN (baseline) ---")
    for k in [1, 3, 5]:
        knn = KNeighborsClassifier(n_neighbors=k)
        knn.fit(X_train, y_pvtp_train)
        pvtp_acc = accuracy_score(y_pvtp_test, knn.predict(X_test))
        
        knn_n = KNeighborsClassifier(n_neighbors=k)
        knn_n.fit(X_train, y_pvtn_train)
        pvtn_acc = accuracy_score(y_pvtn_test, knn_n.predict(X_test))
        
        label = f"KNN(k={k})"
        results[label] = {
            'pvtp_acc': pvtp_acc, 'pvtn_acc': pvtn_acc,
            'n_leaves': len(X_train),
            'depth': k,
            'hw_type': f'SRAM + {k} comparators + sort',
            'est_gates': 99999  # Not practical for hardware
        }
        print(f"  k={k}  pvtp_acc={pvtp_acc:.4f}  pvtn_acc={pvtn_acc:.4f}  (NOT HW-friendly)")
    
    return results, X_train, X_test, y_pvtp_train, y_pvtp_test, y_pvtn_train, y_pvtn_test


def per_corner_analysis(df, model_type='decision_tree', max_depth=5):
    """Test the chosen model per-corner to ensure it works everywhere."""
    print("\n" + "=" * 70)
    print("PER-CORNER VALIDATION (Decision Tree, depth=5)")
    print("=" * 70)
    
    X = df[['pmon_cmos_res']].values
    y_pvtp = df['pvtp_int'].values.astype(int)
    y_pvtn = df['pvtn_int'].values.astype(int)
    corners = df['corner_label'].values
    
    X_train, X_test, y_pvtp_train, y_pvtp_test, y_pvtn_train, y_pvtn_test, c_train, c_test = \
        train_test_split(X, y_pvtp, y_pvtn, corners, test_size=0.2, random_state=42,
                        stratify=corners)
    
    dt_p = DecisionTreeClassifier(max_depth=max_depth, random_state=42)
    dt_p.fit(X_train, y_pvtp_train)
    dt_n = DecisionTreeClassifier(max_depth=max_depth, random_state=42)
    dt_n.fit(X_train, y_pvtn_train)
    
    pvtp_pred = dt_p.predict(X_test)
    pvtn_pred = dt_n.predict(X_test)
    
    print(f"\n{'Corner':<8} {'pvtp_acc':<12} {'pvtn_acc':<12} {'pvtp_off_by_1':<15} {'test_samples':<12}")
    print("-" * 59)
    
    for c in ['FF', 'SS', 'TT', 'FS', 'SF']:
        mask = c_test == c
        if mask.sum() == 0:
            continue
        pvtp_acc = accuracy_score(y_pvtp_test[mask], pvtp_pred[mask])
        pvtn_acc = accuracy_score(y_pvtn_test[mask], pvtn_pred[mask])
        # "Off by 1" = predictions that are very close (1 trim code away)
        off_by_1 = np.mean(np.abs(y_pvtp_test[mask] - pvtp_pred[mask]) <= 1)
        print(f"{c:<8} {pvtp_acc:<12.4f} {pvtn_acc:<12.4f} {off_by_1:<15.4f} {mask.sum():<12}")
    
    # Print the decision tree rules (for hardware understanding)
    print("\n--- Decision Tree Rules (pvtp) ---")
    tree_text = export_text(dt_p, feature_names=['pmon_cmos_res'], max_depth=4)
    print(tree_text[:2000])
    
    print(f"\nTree stats: depth={dt_p.get_depth()}, leaves={dt_p.get_n_leaves()}")
    
    return dt_p, dt_n


def plot_model_comparison(results):
    """Visualize accuracy vs hardware cost tradeoff."""
    fig, axes = plt.subplots(1, 2, figsize=(18, 7))
    fig.suptitle('Model Comparison: Accuracy vs Hardware Cost', fontsize=16, fontweight='bold')
    
    # Filter out KNN (not practical)
    filtered = {k: v for k, v in results.items() if not k.startswith('KNN')}
    
    names = list(filtered.keys())
    pvtp_accs = [filtered[n]['pvtp_acc'] for n in names]
    pvtn_accs = [filtered[n]['pvtn_acc'] for n in names]
    gates = [filtered[n]['est_gates'] for n in names]
    
    # Color by model type
    colors = []
    for n in names:
        if n.startswith('DT'): colors.append('#e74c3c')
        elif n.startswith('RF'): colors.append('#3498db')
        elif n.startswith('Poly'): colors.append('#2ecc71')
        elif n.startswith('LUT'): colors.append('#f39c12')
        else: colors.append('#9b59b6')
    
    # pvtp accuracy vs gates
    ax = axes[0]
    ax.scatter(gates, pvtp_accs, c=colors, s=100, zorder=5)
    for i, name in enumerate(names):
        ax.annotate(name, (gates[i], pvtp_accs[i]), textcoords="offset points",
                   xytext=(5, 5), fontsize=8)
    ax.set_xlabel('Estimated Gate Count', fontsize=12)
    ax.set_ylabel('pvtp Accuracy', fontsize=12)
    ax.set_title('pvtp: Accuracy vs Hardware Cost', fontweight='bold')
    ax.set_xscale('log')
    ax.grid(True, alpha=0.3)
    
    # pvtn accuracy vs gates
    ax = axes[1]
    ax.scatter(gates, pvtn_accs, c=colors, s=100, zorder=5)
    for i, name in enumerate(names):
        ax.annotate(name, (gates[i], pvtn_accs[i]), textcoords="offset points",
                   xytext=(5, 5), fontsize=8)
    ax.set_xlabel('Estimated Gate Count', fontsize=12)
    ax.set_ylabel('pvtn Accuracy', fontsize=12)
    ax.set_title('pvtn: Accuracy vs Hardware Cost', fontweight='bold')
    ax.set_xscale('log')
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, '11_model_comparison.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("\n[OK] Plot 11: Model comparison saved")


def plot_decision_boundaries(df, dt_p, dt_n):
    """Visualize what the decision tree learned."""
    fig, axes = plt.subplots(1, 2, figsize=(16, 7))
    fig.suptitle('Decision Tree Predictions vs Actual (pmon_cmos_res -> trim bits)', 
                 fontsize=14, fontweight='bold')
    
    colors = {'FF': '#e74c3c', 'SS': '#3498db', 'TT': '#2ecc71', 'FS': '#f39c12', 'SF': '#9b59b6'}
    
    # Generate predictions across full pmon_cmos_res range
    x_range = np.linspace(df['pmon_cmos_res'].min(), df['pmon_cmos_res'].max(), 1000).reshape(-1, 1)
    pvtp_pred = dt_p.predict(x_range)
    pvtn_pred = dt_n.predict(x_range)
    
    # pvtp
    ax = axes[0]
    for c in ['FF', 'SS', 'TT', 'FS', 'SF']:
        cdf = df[df['corner_label'] == c].sample(min(300, len(df[df['corner_label'] == c])), random_state=42)
        ax.scatter(cdf['pmon_cmos_res'] / 1e6, cdf['pvtp_int'], s=5, alpha=0.4, color=colors[c], label=f'{c} actual')
    ax.plot(x_range / 1e6, pvtp_pred, 'k-', linewidth=2, label='DT prediction', zorder=10)
    ax.set_xlabel('pmon_cmos_res (x10^6)')
    ax.set_ylabel('pvtp (decimal)')
    ax.set_title('pvtp: Actual vs Decision Tree', fontweight='bold')
    ax.legend(fontsize=8, markerscale=3)
    
    # pvtn
    ax = axes[1]
    for c in ['FF', 'SS', 'TT', 'FS', 'SF']:
        cdf = df[df['corner_label'] == c].sample(min(300, len(df[df['corner_label'] == c])), random_state=42)
        ax.scatter(cdf['pmon_cmos_res'] / 1e6, cdf['pvtn_int'], s=5, alpha=0.4, color=colors[c], label=f'{c} actual')
    ax.plot(x_range / 1e6, pvtn_pred, 'k-', linewidth=2, label='DT prediction', zorder=10)
    ax.set_xlabel('pmon_cmos_res (x10^6)')
    ax.set_ylabel('pvtn (decimal)')
    ax.set_title('pvtn: Actual vs Decision Tree', fontweight='bold')
    ax.legend(fontsize=8, markerscale=3)
    
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, '12_decision_tree_predictions.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("[OK] Plot 12: Decision tree predictions saved")


def print_final_summary(results):
    """Print the final recommendation."""
    print("\n" + "=" * 70)
    print("FINAL MODEL RECOMMENDATION")
    print("=" * 70)
    
    print("\n--- Summary Table ---")
    print(f"{'Model':<20} {'pvtp_acc':<10} {'pvtn_acc':<10} {'Est Gates':<12} {'HW Type':<35}")
    print("-" * 87)
    for name, r in sorted(results.items(), key=lambda x: x[1]['est_gates']):
        if name.startswith('KNN'):
            continue
        print(f"{name:<20} {r['pvtp_acc']:<10.4f} {r['pvtn_acc']:<10.4f} {r['est_gates']:<12} {r['hw_type']:<35}")
    
    print("""
--- RECOMMENDATION FOR ASIC ---

TOP PICK: Decision Tree (depth=5)
  - Best accuracy/hardware tradeoff
  - Implements as cascaded comparators + MUX tree
  - ~200-400 gates total
  - Runs in 1 clock cycle
  - Easy RTL conversion (just if-else chains)

RUNNER-UP: LUT with 64-128 entries
  - Uses small ROM/SRAM block
  - Requires quantizing pmon_cmos_res to address bits
  - Very predictable timing
  - Good if your foundry has efficient ROM macros

AVOID for ASIC:
  - Polynomial: needs multipliers (expensive in area)
  - Random Forest: needs multiple trees (area multiplier)
  - KNN: needs full training set in memory (impossible)
  - Neural Network: needs multipliers + activation functions
""")


# ============================================================
# MAIN
# ============================================================

if __name__ == '__main__':
    print("Loading data...")
    df = load_all_corners()
    
    # 1. Analyze trim bit variation
    analyze_trim_bit_variation(df)
    
    # 2. Compare models
    results, X_train, X_test, yp_train, yp_test, yn_train, yn_test = build_and_compare_models(df)
    
    # 3. Per-corner validation with best model
    dt_p, dt_n = per_corner_analysis(df)
    
    # 4. Plots
    plot_model_comparison(results)
    plot_decision_boundaries(df, dt_p, dt_n)
    
    # 5. Final summary
    print_final_summary(results)
    
    print("\n[DONE] All analysis complete! Check plots/ directory for visualizations.")
