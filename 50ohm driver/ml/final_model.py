"""
TSMC 28nm Driver - FINAL Optimized Model Analysis
==================================================
Uses all 3 available inputs: pmon_cmos_res + vreg + temperature
Finds optimal Decision Tree depth for best accuracy/hardware tradeoff.
"""

import sys, io
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeClassifier, export_text
from sklearn.metrics import accuracy_score, confusion_matrix
from sklearn.ensemble import RandomForestClassifier
import os, warnings, pickle, json
warnings.filterwarnings('ignore')

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
EXCEL_FILE = os.path.join(PROJECT_DIR, "data", "TSMC28nm_DRV_ML_MAR6_LookUP_Table_Mar20_ML Predictions.xlsx")
OUTPUT_DIR = os.path.join(PROJECT_DIR, "plots")
os.makedirs(OUTPUT_DIR, exist_ok=True)

CORNER_SHEETS = {'FF': 'FF_vdd_temp', 'SS': 'SS_vdd_test', 'TT': 'TT_vdd_test', 'FS': 'FS_vdd_test', 'SF': 'SF_vdd_test'}
COL_NAMES = ['Corner', 'vreg', 'temperature', 'PULL_UP_RES', 'PULL_DN_RES', 'pmon_cmos_res', 'pmon_cmos', 'pvtp_raw', 'pvtn_raw', 'PULL_UP_RES_new', 'PULL_DN_RES_new']

def pad8(val):
    if pd.isna(val) or str(val).strip().lower() == 'na': return None
    return str(val).replace('-','').strip().zfill(8)
def to_int(val):
    if val is None or pd.isna(val): return None
    try: return int(val, 2)
    except: return None

def load_data():
    all_data = []
    for c, s in CORNER_SHEETS.items():
        df = pd.read_excel(EXCEL_FILE, sheet_name=s, header=0).iloc[:,:11]
        df.columns = COL_NAMES
        for col in ['vreg','temperature','pmon_cmos_res','pmon_cmos','PULL_UP_RES','PULL_DN_RES','PULL_UP_RES_new','PULL_DN_RES_new']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        df['corner_label'] = c
        df['pvtp_int'] = df['pvtp_raw'].apply(pad8).apply(to_int)
        df['pvtn_int'] = df['pvtn_raw'].apply(pad8).apply(to_int)
        all_data.append(df)
    return pd.concat(all_data, ignore_index=True).dropna(subset=['pvtp_int','pvtn_int','pmon_cmos_res'])


def sweep_tree_depths(df):
    """Find optimal depth with accuracy and hardware tradeoff."""
    print("\n" + "="*70)
    print("DECISION TREE DEPTH SWEEP (3 inputs: pmon_cmos_res + vreg + temp)")
    print("="*70)
    
    X = df[['pmon_cmos_res', 'vreg', 'temperature']].values
    y_p = df['pvtp_int'].values.astype(int)
    y_n = df['pvtn_int'].values.astype(int)
    corners = df['corner_label'].values
    
    X_tr, X_te, yp_tr, yp_te, yn_tr, yn_te, c_tr, c_te = \
        train_test_split(X, y_p, y_n, corners, test_size=0.2, random_state=42, stratify=corners)
    
    results = []
    print(f"\n{'Depth':<7} {'pvtp_acc':<10} {'pvtn_acc':<10} {'Leaves_p':<10} {'Leaves_n':<10} {'Total_leaves':<14} {'Est_gates':<10}")
    print("-"*71)
    
    for depth in range(3, 20):
        dt_p = DecisionTreeClassifier(max_depth=depth, random_state=42).fit(X_tr, yp_tr)
        dt_n = DecisionTreeClassifier(max_depth=depth, random_state=42).fit(X_tr, yn_tr)
        
        acc_p = accuracy_score(yp_te, dt_p.predict(X_te))
        acc_n = accuracy_score(yn_te, dt_n.predict(X_te))
        leaves_p = dt_p.get_n_leaves()
        leaves_n = dt_n.get_n_leaves()
        total = leaves_p + leaves_n
        est_gates = total * 25  # comparator + register per leaf
        
        results.append({
            'depth': depth, 'pvtp_acc': acc_p, 'pvtn_acc': acc_n,
            'leaves_p': leaves_p, 'leaves_n': leaves_n, 'total_leaves': total,
            'est_gates': est_gates
        })
        
        marker = ""
        if depth == 10: marker = " <-- SWEET SPOT"
        if depth == 12: marker = " <-- HIGH ACCURACY"
        print(f"{depth:<7} {acc_p:<10.4f} {acc_n:<10.4f} {leaves_p:<10} {leaves_n:<10} {total:<14} {est_gates:<10}{marker}")
    
    return results, X_tr, X_te, yp_tr, yp_te, yn_tr, yn_te, c_tr, c_te


def train_best_model(df, depth=10):
    """Train the best depth model and validate per corner."""
    print(f"\n{'='*70}")
    print(f"BEST MODEL: Decision Tree depth={depth}")
    print(f"{'='*70}")
    
    X = df[['pmon_cmos_res', 'vreg', 'temperature']].values
    y_p = df['pvtp_int'].values.astype(int)
    y_n = df['pvtn_int'].values.astype(int)
    corners = df['corner_label'].values
    
    X_tr, X_te, yp_tr, yp_te, yn_tr, yn_te, c_tr, c_te = \
        train_test_split(X, y_p, y_n, corners, test_size=0.2, random_state=42, stratify=corners)
    
    dt_p = DecisionTreeClassifier(max_depth=depth, random_state=42).fit(X_tr, yp_tr)
    dt_n = DecisionTreeClassifier(max_depth=depth, random_state=42).fit(X_tr, yn_tr)
    
    # Overall accuracy
    acc_p = accuracy_score(yp_te, dt_p.predict(X_te))
    acc_n = accuracy_score(yn_te, dt_n.predict(X_te))
    print(f"\nOverall: pvtp_acc={acc_p:.4f}, pvtn_acc={acc_n:.4f}")
    print(f"Leaves: pvtp={dt_p.get_n_leaves()}, pvtn={dt_n.get_n_leaves()}")
    
    # Per-corner breakdown
    print(f"\n{'Corner':<8} {'pvtp_acc':<10} {'pvtn_acc':<10} {'off_by_1_p':<12} {'off_by_1_n':<12} {'N':<6}")
    print("-"*58)
    
    pvtp_pred = dt_p.predict(X_te)
    pvtn_pred = dt_n.predict(X_te)
    
    for c in ['FF', 'SS', 'TT', 'FS', 'SF']:
        mask = c_te == c
        if mask.sum() == 0: continue
        ap = accuracy_score(yp_te[mask], pvtp_pred[mask])
        an = accuracy_score(yn_te[mask], pvtn_pred[mask])
        ob1_p = np.mean(np.abs(yp_te[mask].astype(float) - pvtp_pred[mask].astype(float)) <= 1)
        ob1_n = np.mean(np.abs(yn_te[mask].astype(float) - pvtn_pred[mask].astype(float)) <= 1)
        print(f"{c:<8} {ap:<10.4f} {an:<10.4f} {ob1_p:<12.4f} {ob1_n:<12.4f} {mask.sum():<6}")
    
    # Feature importance
    print(f"\nFeature Importance (pvtp tree):")
    for fname, imp in zip(['pmon_cmos_res', 'vreg', 'temperature'], dt_p.feature_importances_):
        print(f"  {fname}: {imp:.4f}")
    
    return dt_p, dt_n, X_tr, X_te, yp_tr, yp_te, yn_tr, yn_te, c_te


def compare_1_vs_3_inputs(df):
    """Side-by-side comparison: 1 input vs 3 inputs."""
    print(f"\n{'='*70}")
    print("COMPARISON: 1 INPUT (pmon_cmos_res) vs 3 INPUTS (pmon + vreg + temp)")
    print(f"{'='*70}")
    
    y_p = df['pvtp_int'].values.astype(int)
    y_n = df['pvtn_int'].values.astype(int)
    corners = df['corner_label'].values
    
    configs = [
        ('pmon_cmos_res ONLY', df[['pmon_cmos_res']].values),
        ('pmon + vreg', df[['pmon_cmos_res', 'vreg']].values),
        ('pmon + temp', df[['pmon_cmos_res', 'temperature']].values),
        ('pmon + vreg + temp', df[['pmon_cmos_res', 'vreg', 'temperature']].values),
    ]
    
    print(f"\n{'Config':<25} {'Depth':<7} {'pvtp_acc':<10} {'pvtn_acc':<10} {'Leaves':<8}")
    print("-"*60)
    
    for name, X in configs:
        X_tr, X_te, yp_tr, yp_te, yn_tr, yn_te = \
            train_test_split(X, y_p, y_n, test_size=0.2, random_state=42, stratify=corners)
        
        for depth in [5, 10]:
            dt_p = DecisionTreeClassifier(max_depth=depth, random_state=42).fit(X_tr, yp_tr)
            dt_n = DecisionTreeClassifier(max_depth=depth, random_state=42).fit(X_tr, yn_tr)
            ap = accuracy_score(yp_te, dt_p.predict(X_te))
            an = accuracy_score(yn_te, dt_n.predict(X_te))
            leaves = dt_p.get_n_leaves() + dt_n.get_n_leaves()
            print(f"{name:<25} {depth:<7} {ap:<10.4f} {an:<10.4f} {leaves:<8}")


def plot_depth_sweep(results):
    """Plot accuracy vs depth and accuracy vs hardware cost."""
    fig, axes = plt.subplots(1, 3, figsize=(22, 7))
    fig.suptitle('Decision Tree Optimization (3 inputs: pmon_cmos_res + vreg + temp)', 
                 fontsize=14, fontweight='bold')
    
    depths = [r['depth'] for r in results]
    pvtp_accs = [r['pvtp_acc'] for r in results]
    pvtn_accs = [r['pvtn_acc'] for r in results]
    leaves = [r['total_leaves'] for r in results]
    gates = [r['est_gates'] for r in results]
    
    # Accuracy vs Depth
    ax = axes[0]
    ax.plot(depths, pvtp_accs, 'o-', color='#e74c3c', label='pvtp', linewidth=2, markersize=8)
    ax.plot(depths, pvtn_accs, 's-', color='#3498db', label='pvtn', linewidth=2, markersize=8)
    ax.axhline(0.95, color='green', linestyle='--', alpha=0.5, label='95% target')
    ax.axvline(10, color='orange', linestyle='--', alpha=0.5, label='Depth=10 sweet spot')
    ax.set_xlabel('Tree Depth', fontsize=12)
    ax.set_ylabel('Accuracy', fontsize=12)
    ax.set_title('Accuracy vs Tree Depth', fontweight='bold')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # Leaves vs Depth
    ax = axes[1]
    ax.plot(depths, leaves, 'o-', color='#2ecc71', linewidth=2, markersize=8)
    ax.axvline(10, color='orange', linestyle='--', alpha=0.5, label='Depth=10')
    ax.set_xlabel('Tree Depth', fontsize=12)
    ax.set_ylabel('Total Leaves (pvtp + pvtn)', fontsize=12)
    ax.set_title('Hardware Size vs Tree Depth', fontweight='bold')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # Accuracy vs Gates (the tradeoff plot)
    ax = axes[2]
    ax.plot(gates, pvtp_accs, 'o-', color='#e74c3c', label='pvtp', linewidth=2, markersize=8)
    ax.plot(gates, pvtn_accs, 's-', color='#3498db', label='pvtn', linewidth=2, markersize=8)
    ax.axhline(0.95, color='green', linestyle='--', alpha=0.5, label='95% target')
    ax.set_xlabel('Estimated Gate Count', fontsize=12)
    ax.set_ylabel('Accuracy', fontsize=12)
    ax.set_title('Accuracy vs Hardware Cost', fontweight='bold')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # Annotate key points
    for r in results:
        if r['depth'] in [5, 10, 12, 15]:
            axes[2].annotate(f"d={r['depth']}", (r['est_gates'], r['pvtp_acc']),
                           textcoords="offset points", xytext=(10, -10), fontsize=9,
                           arrowprops=dict(arrowstyle='->', color='gray'))
    
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, '13_depth_sweep.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("[OK] Plot 13: Depth sweep saved")


def plot_per_corner_predictions(df, dt_p, dt_n, X_te, yp_te, yn_te, c_te):
    """Per-corner prediction visualization."""
    fig, axes = plt.subplots(5, 2, figsize=(18, 28))
    fig.suptitle('Per-Corner: Actual vs Predicted Trim Bits', fontsize=16, fontweight='bold')
    
    pvtp_pred = dt_p.predict(X_te)
    pvtn_pred = dt_n.predict(X_te)
    
    for i, c in enumerate(['FF', 'SS', 'TT', 'FS', 'SF']):
        mask = c_te == c
        
        # pvtp
        ax = axes[i, 0]
        ax.scatter(yp_te[mask], pvtp_pred[mask], s=10, alpha=0.5, color='#e74c3c')
        lims = [min(yp_te[mask].min(), pvtp_pred[mask].min()) - 2,
                max(yp_te[mask].max(), pvtp_pred[mask].max()) + 2]
        ax.plot(lims, lims, 'k--', alpha=0.5, label='Perfect')
        ax.set_xlabel('Actual pvtp')
        ax.set_ylabel('Predicted pvtp')
        acc = accuracy_score(yp_te[mask], pvtp_pred[mask])
        ax.set_title(f'{c} pvtp (acc={acc:.3f})', fontweight='bold')
        ax.legend()
        
        # pvtn
        ax = axes[i, 1]
        ax.scatter(yn_te[mask], pvtn_pred[mask], s=10, alpha=0.5, color='#3498db')
        lims = [min(yn_te[mask].min(), pvtn_pred[mask].min()) - 2,
                max(yn_te[mask].max(), pvtn_pred[mask].max()) + 2]
        ax.plot(lims, lims, 'k--', alpha=0.5, label='Perfect')
        ax.set_xlabel('Actual pvtn')
        ax.set_ylabel('Predicted pvtn')
        acc = accuracy_score(yn_te[mask], pvtn_pred[mask])
        ax.set_title(f'{c} pvtn (acc={acc:.3f})', fontweight='bold')
        ax.legend()
    
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, '14_per_corner_predictions.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("[OK] Plot 14: Per-corner predictions saved")


def export_tree_rules(dt_p, dt_n, depth):
    """Export decision tree rules for RTL conversion."""
    print(f"\n{'='*70}")
    print(f"DECISION TREE RULES FOR RTL (depth={depth})")
    print(f"{'='*70}")
    
    print("\n--- pvtp Tree Rules (top levels) ---")
    tree_text = export_text(dt_p, feature_names=['pmon_cmos_res', 'vreg', 'temperature'], max_depth=5)
    print(tree_text[:3000])
    
    # Save full rules to file
    full_pvtp = export_text(dt_p, feature_names=['pmon_cmos_res', 'vreg', 'temperature'])
    full_pvtn = export_text(dt_n, feature_names=['pmon_cmos_res', 'vreg', 'temperature'])
    
    with open(os.path.join(OUTPUT_DIR, 'decision_tree_pvtp_rules.txt'), 'w') as f:
        f.write(full_pvtp)
    with open(os.path.join(OUTPUT_DIR, 'decision_tree_pvtn_rules.txt'), 'w') as f:
        f.write(full_pvtn)
    
    print(f"\nFull rules saved to:")
    print(f"  plots/decision_tree_pvtp_rules.txt ({len(full_pvtp)} chars)")
    print(f"  plots/decision_tree_pvtn_rules.txt ({len(full_pvtn)} chars)")
    
    # Save model as pickle for later use
    with open('model_pvtp.pkl', 'wb') as f:
        pickle.dump(dt_p, f)
    with open('model_pvtn.pkl', 'wb') as f:
        pickle.dump(dt_n, f)
    print("  Models saved as model_pvtp.pkl, model_pvtn.pkl")
    
    # Export threshold values for RTL
    print(f"\n--- Key Thresholds for RTL Implementation ---")
    tree = dt_p.tree_
    thresholds = []
    features = ['pmon_cmos_res', 'vreg', 'temperature']
    for i in range(tree.node_count):
        if tree.children_left[i] != tree.children_right[i]:  # not a leaf
            feat = features[tree.feature[i]]
            thresh = tree.threshold[i]
            thresholds.append((feat, thresh))
    
    # Unique thresholds per feature
    for feat in features:
        feat_thresh = sorted(set(t for f, t in thresholds if f == feat))
        print(f"  {feat}: {len(feat_thresh)} unique thresholds")
        if len(feat_thresh) <= 15:
            print(f"    Values: {[f'{t:.2f}' for t in feat_thresh]}")
    
    # Summary for RTL
    print(f"\n--- RTL Summary ---")
    print(f"  pvtp tree: {dt_p.get_n_leaves()} leaves, depth {dt_p.get_depth()}")
    print(f"  pvtn tree: {dt_n.get_n_leaves()} leaves, depth {dt_n.get_depth()}")
    print(f"  Total comparators needed: ~{tree.node_count} (pvtp) + ~{dt_n.tree_.node_count} (pvtn)")
    print(f"  Output: 8 bits pvtp + 8 bits pvtn = 16 bits total")
    print(f"  Inputs: pmon_cmos_res (32-bit), vreg (fixed-point), temperature (signed fixed-point)")


def analog_vs_digital_explanation():
    """Explain the analog vs digital input question."""
    print(f"\n{'='*70}")
    print("ANALOG vs DIGITAL INPUT: IMPLICATIONS")
    print(f"{'='*70}")
    print("""
In your ASIC, pmon_cmos_res comes from a ring oscillator. Here's what matters:

IF DIGITAL (most likely case):
  - Ring oscillator produces a frequency signal
  - A frequency counter converts it to a digital count
  - This count IS your pmon_cmos_res value
  - You can feed it DIRECTLY to the decision tree comparators
  - Resolution depends on counter bit-width and measurement time
  - RECOMMENDED: Use 20-24 bit counter for sufficient resolution
  - NO ADC needed!

IF ANALOG (unlikely for ring oscillator):
  - Would need an ADC to digitize the signal
  - ADC resolution determines trim bit precision
  - Extra area + power overhead
  - NOT recommended for this application

BOTTOM LINE: 
  Ring oscillators naturally produce digital output (frequency).
  You just need a frequency counter, which is a simple digital block.
  The counter output maps directly to the pmon_cmos_res values in your lookup table.
  
  Your ASIC would look like:
  
  [Ring Osc] -> [Freq Counter] -> [Decision Tree Logic] -> [pvtp, pvtn trim bits]
                                        ^
                                        |
                              [vreg, temp available 
                               from other sensors]
""")


if __name__ == '__main__':
    print("Loading data...")
    df = load_data()
    print(f"Loaded {len(df)} valid rows\n")
    
    # 1. Compare 1-input vs 3-input
    compare_1_vs_3_inputs(df)
    
    # 2. Sweep tree depths
    results, X_tr, X_te, yp_tr, yp_te, yn_tr, yn_te, c_tr, c_te = sweep_tree_depths(df)
    
    # 3. Train best model (depth=10 as sweet spot)
    dt_p, dt_n, X_tr2, X_te2, yp_tr2, yp_te2, yn_tr2, yn_te2, c_te2 = train_best_model(df, depth=10)
    
    # 4. Also show depth=12 for higher accuracy
    print("\n--- Also training depth=12 for higher accuracy ---")
    dt_p12, dt_n12, _, X_te12, _, yp_te12, _, yn_te12, c_te12 = train_best_model(df, depth=12)
    
    # 5. Plots
    plot_depth_sweep(results)
    plot_per_corner_predictions(df, dt_p, dt_n, X_te2, yp_te2, yn_te2, c_te2)
    
    # 6. Export rules for RTL
    export_tree_rules(dt_p, dt_n, depth=10)
    
    # 7. Analog vs digital
    analog_vs_digital_explanation()
    
    print("\n[DONE] Final analysis complete!")
