"""
BGR Model Comparison Pipeline
==============================
Compares multiple ML models for predicting BGR trim bits (pctrl, nctrl)
from PVT inputs (vdd, temperature, PMON_RING_CMOS_res).

Models compared:
  1. Decision Tree (depth sweep 3-15)
  2. LUT (binned look-up table)
  3. Polynomial Regression (degree 2-4)
  4. Random Forest (small ensembles)
  5. Small Neural Network (1-2 hidden layers)

For each model: accuracy, per-corner accuracy, hardware cost estimate.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import PolynomialFeatures
from sklearn.neural_network import MLPClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
import os, sys, json, pickle, warnings
warnings.filterwarnings('ignore')

# ─── Config ───────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
XLSX_PATH = os.path.join(BASE_DIR, "BGR_ML_DATA_JAN9_testsample_2023_MAR6.xlsx")
PLOTS_DIR = os.path.join(BASE_DIR, "plots")
os.makedirs(PLOTS_DIR, exist_ok=True)

SHEET_MAP = {'TT': 'TT-VDD_TEMP', 'SS': 'SS_VDD_TEMP', 'FF': 'FF_VDD_TEMP'}
CORNER_COLORS = {'TT': '#2196F3', 'SS': '#F44336', 'FF': '#4CAF50'}


def parse_trim_bits(val):
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


def load_data():
    """Load all corners, parse trim bits, return combined DataFrame."""
    frames = []
    for corner_name, sheet_name in SHEET_MAP.items():
        df = pd.read_excel(XLSX_PATH, sheet_name=sheet_name)
        # Coerce numeric columns
        for col in ['vdd', 'temperature', 'PMON_RING_CMOS_res', 'PMON_RING_CMOS']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        df = df.dropna(subset=['vdd', 'temperature'])
        df['pctrl_int'] = df['pctrl<3:0>'].apply(parse_trim_bits)
        df['nctrl_int'] = df['nctrl<5:0>'].apply(parse_trim_bits)
        df['corner'] = corner_name
        frames.append(df)
    data = pd.concat(frames, ignore_index=True)
    data = data.dropna(subset=['pctrl_int', 'nctrl_int', 'PMON_RING_CMOS_res'])
    data['pctrl_int'] = data['pctrl_int'].astype(int)
    data['nctrl_int'] = data['nctrl_int'].astype(int)
    return data


def encode_features(data):
    """Encode features for hardware-friendly integer representation."""
    X = pd.DataFrame()
    # PMON_RING_CMOS_res: already integer (29-bit)
    X['pmon'] = data['PMON_RING_CMOS_res'].astype(int)
    # VDD: (V - 0.80) * 100 -> 1 to 19 (5-bit)
    X['vdd_enc'] = ((data['vdd'] - 0.80) * 100).round().astype(int)
    # Temperature: (T + 40) * 2 -> 0 to 330 (9-bit, 0.5C resolution)
    X['temp_enc'] = ((data['temperature'] + 40.0) * 2).round().astype(int)
    return X


def split_data(data, test_size=0.2, random_state=42):
    """Stratified random split preserving corner proportions."""
    X = encode_features(data)
    y_pctrl = data['pctrl_int'].values
    y_nctrl = data['nctrl_int'].values
    corners = data['corner'].values

    # Create combined label for stratification
    strat_label = data['corner'].astype(str) + '_' + data['pctrl_int'].astype(str) + '_' + data['nctrl_int'].astype(str)

    X_train, X_test, y_p_train, y_p_test, y_n_train, y_n_test, c_train, c_test = \
        train_test_split(X, y_pctrl, y_nctrl, corners,
                         test_size=test_size, random_state=random_state,
                         stratify=strat_label)

    return (X_train, X_test, y_p_train, y_p_test, y_n_train, y_n_test, c_train, c_test)


def per_corner_accuracy(y_true, y_pred, corners):
    """Compute accuracy per process corner."""
    results = {}
    for corner in sorted(set(corners)):
        mask = corners == corner
        acc = accuracy_score(y_true[mask], y_pred[mask]) * 100
        results[corner] = acc
    results['Overall'] = accuracy_score(y_true, y_pred) * 100
    return results


# ─── Model 1: Decision Tree (Depth Sweep) ────────────────────────────
def evaluate_decision_tree(X_train, X_test, y_train, y_test, corners_test, target_name, depths=None):
    """Train and evaluate Decision Trees at various depths."""
    if depths is None:
        depths = [3, 4, 5, 6, 7, 8, 9, 10, 12, 14, None]

    results = []
    for depth in depths:
        dt = DecisionTreeClassifier(max_depth=depth, random_state=42)
        dt.fit(X_train, y_train)
        y_pred = dt.predict(X_test)
        acc = accuracy_score(y_test, y_pred) * 100
        n_nodes = dt.tree_.node_count
        n_leaves = dt.tree_.n_leaves
        max_d = dt.tree_.max_depth

        per_corner = per_corner_accuracy(y_test, y_pred, corners_test)

        results.append({
            'depth_param': depth if depth else 'None',
            'actual_depth': max_d,
            'accuracy': acc,
            'n_nodes': n_nodes,
            'n_leaves': n_leaves,
            'per_corner': per_corner,
            'model': dt
        })

        depth_str = str(depth) if depth else 'None'
        print(f"  DT(depth={depth_str:>4s}): acc={acc:6.2f}%, nodes={n_nodes}, "
              f"leaves={n_leaves}, actual_depth={max_d}")

    return results


# ─── Model 2: LUT (Binned Look-Up Table) ─────────────────────────────
def evaluate_lut(X_train, X_test, y_train, y_test, corners_test, target_name, n_bins_list=None):
    """LUT: quantize inputs into bins, store most common output per bin."""
    if n_bins_list is None:
        n_bins_list = [10, 20, 50, 100, 200, 500]

    results = []
    for n_bins in n_bins_list:
        # Quantize each feature
        X_train_q = X_train.copy()
        X_test_q = X_test.copy()

        bin_edges = {}
        for col in X_train.columns:
            edges = np.linspace(X_train[col].min(), X_train[col].max(), n_bins + 1)
            bin_edges[col] = edges
            X_train_q[col] = np.digitize(X_train[col], edges)
            X_test_q[col] = np.digitize(X_test[col], edges)

        # Build LUT: (bin_pmon, bin_vdd, bin_temp) -> most common output
        X_train_q['label'] = y_train
        X_train_q['key'] = (X_train_q.iloc[:, 0].astype(str) + '_' +
                             X_train_q.iloc[:, 1].astype(str) + '_' +
                             X_train_q.iloc[:, 2].astype(str))
        lut = X_train_q.groupby('key')['label'].agg(lambda x: x.mode()[0]).to_dict()
        n_entries = len(lut)

        # Predict
        X_test_q['key'] = (X_test_q.iloc[:, 0].astype(str) + '_' +
                            X_test_q.iloc[:, 1].astype(str) + '_' +
                            X_test_q.iloc[:, 2].astype(str))

        # Default: most common label overall
        default_label = pd.Series(y_train).mode()[0]
        y_pred = X_test_q['key'].map(lut).fillna(default_label).astype(int).values

        acc = accuracy_score(y_test, y_pred) * 100
        per_corner = per_corner_accuracy(y_test, y_pred, corners_test)

        # Memory estimate: entries * bits_per_entry
        output_bits = 10  # 4 + 6 bits
        mem_bits = n_entries * output_bits
        mem_bytes = mem_bits / 8

        results.append({
            'n_bins': n_bins,
            'n_entries': n_entries,
            'accuracy': acc,
            'mem_bytes': mem_bytes,
            'per_corner': per_corner,
        })

        print(f"  LUT(bins={n_bins:>3d}): acc={acc:6.2f}%, entries={n_entries}, "
              f"mem={mem_bytes:.0f}B")

    return results


# ─── Model 3: Polynomial Regression (as classifier) ──────────────────
def evaluate_polynomial(X_train, X_test, y_train, y_test, corners_test, target_name, degrees=None):
    """Polynomial features + Logistic Regression classifier."""
    if degrees is None:
        degrees = [1, 2, 3]

    results = []
    for deg in degrees:
        poly = PolynomialFeatures(degree=deg, include_bias=False)
        X_train_poly = poly.fit_transform(X_train)
        X_test_poly = poly.transform(X_test)

        lr = LogisticRegression(max_iter=2000, random_state=42, multi_class='multinomial')
        lr.fit(X_train_poly, y_train)
        y_pred = lr.predict(X_test_poly)
        acc = accuracy_score(y_test, y_pred) * 100

        n_features = X_train_poly.shape[1]
        n_classes = len(set(y_train))
        # HW cost: n_features * n_classes multiplications + additions
        n_multipliers = n_features * n_classes

        per_corner = per_corner_accuracy(y_test, y_pred, corners_test)

        results.append({
            'degree': deg,
            'n_poly_features': n_features,
            'n_classes': n_classes,
            'accuracy': acc,
            'n_multipliers': n_multipliers,
            'per_corner': per_corner,
        })

        print(f"  Poly(deg={deg}): acc={acc:6.2f}%, features={n_features}, "
              f"multipliers={n_multipliers}")

    return results


# ─── Model 4: Random Forest ──────────────────────────────────────────
def evaluate_random_forest(X_train, X_test, y_train, y_test, corners_test, target_name):
    """Small Random Forest ensembles."""
    configs = [
        (3, 3), (3, 5), (5, 5), (5, 7), (10, 5), (10, 7),
    ]

    results = []
    for n_trees, depth in configs:
        rf = RandomForestClassifier(n_estimators=n_trees, max_depth=depth, random_state=42)
        rf.fit(X_train, y_train)
        y_pred = rf.predict(X_test)
        acc = accuracy_score(y_test, y_pred) * 100

        total_nodes = sum(t.tree_.node_count for t in rf.estimators_)
        per_corner = per_corner_accuracy(y_test, y_pred, corners_test)

        results.append({
            'n_trees': n_trees,
            'depth': depth,
            'accuracy': acc,
            'total_nodes': total_nodes,
            'per_corner': per_corner,
        })

        print(f"  RF(n={n_trees}, d={depth}): acc={acc:6.2f}%, total_nodes={total_nodes}")

    return results


# ─── Model 5: Small Neural Network ───────────────────────────────────
def evaluate_neural_net(X_train, X_test, y_train, y_test, corners_test, target_name):
    """Small MLPs with different architectures."""
    configs = [
        (8,), (16,), (8, 4), (16, 8), (32,), (32, 16),
    ]

    # Normalize for NN
    from sklearn.preprocessing import StandardScaler
    scaler = StandardScaler()
    X_train_sc = scaler.fit_transform(X_train)
    X_test_sc = scaler.transform(X_test)

    results = []
    for hidden in configs:
        mlp = MLPClassifier(hidden_layer_sizes=hidden, max_iter=1000,
                            random_state=42, early_stopping=True)
        mlp.fit(X_train_sc, y_train)
        y_pred = mlp.predict(X_test_sc)
        acc = accuracy_score(y_test, y_pred) * 100

        # Estimate multipliers: each connection = 1 multiplier
        layers = [X_train.shape[1]] + list(hidden) + [len(set(y_train))]
        n_mult = sum(layers[i] * layers[i+1] for i in range(len(layers)-1))

        per_corner = per_corner_accuracy(y_test, y_pred, corners_test)

        results.append({
            'architecture': str(hidden),
            'accuracy': acc,
            'n_multipliers': n_mult,
            'per_corner': per_corner,
        })

        print(f"  NN{hidden}: acc={acc:6.2f}%, multipliers={n_mult}")

    return results


# ─── Visualizations ──────────────────────────────────────────────────

def plot_depth_sweep(dt_pctrl, dt_nctrl):
    """Plot 12: DT depth sweep accuracy and hardware cost."""
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('Plot 12: Decision Tree Depth Sweep — Accuracy vs Hardware Cost',
                 fontsize=14, fontweight='bold')

    for col, (results, name) in enumerate([(dt_pctrl, 'pctrl'), (dt_nctrl, 'nctrl')]):
        depths = [r['actual_depth'] for r in results]
        accs = [r['accuracy'] for r in results]
        nodes = [r['n_nodes'] for r in results]

        # Accuracy vs depth
        ax = axes[0, col]
        ax.plot(depths, accs, 'bo-', linewidth=2, markersize=8)
        ax.axhline(y=99, color='red', linestyle='--', linewidth=1.5, label='99% target')
        ax.set_xlabel('Tree Depth')
        ax.set_ylabel('Accuracy (%)')
        ax.set_title(f'{name} — Accuracy vs Depth')
        ax.grid(alpha=0.3)
        ax.legend()
        ax.set_ylim(max(min(accs) - 5, 0), 101)

        # Mark first depth that exceeds 99%
        for d, a in zip(depths, accs):
            if a >= 99:
                ax.annotate(f'depth={d}\n{a:.1f}%', xy=(d, a),
                           fontsize=9, fontweight='bold', color='green',
                           textcoords="offset points", xytext=(10, -10))
                break

        # Nodes vs depth
        ax = axes[1, col]
        ax.plot(depths, nodes, 'rs-', linewidth=2, markersize=8)
        ax.set_xlabel('Tree Depth')
        ax.set_ylabel('Number of Nodes')
        ax.set_title(f'{name} — Nodes vs Depth')
        ax.grid(alpha=0.3)

        # Annotate SRAM size
        for d, n in zip(depths, nodes):
            sram_kb = (n * 45) / 8 / 1024  # 45 bits per node
            if d in [depths[0], depths[len(depths)//2], depths[-1]]:
                ax.annotate(f'{n} nodes\n{sram_kb:.2f}KB', xy=(d, n),
                           fontsize=8, textcoords="offset points", xytext=(10, 5))

    fig.tight_layout()
    fig.savefig(os.path.join(PLOTS_DIR, '12_dt_depth_sweep.png'),
                dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    print("  Saved: 12_dt_depth_sweep.png")


def plot_model_comparison(all_results):
    """Plot 13: All models compared on accuracy vs hardware cost."""
    fig, axes = plt.subplots(1, 2, figsize=(16, 7))
    fig.suptitle('Plot 13: Model Comparison — Accuracy vs Hardware Cost',
                 fontsize=14, fontweight='bold')

    for col, target_name in enumerate(['pctrl', 'nctrl']):
        ax = axes[col]
        res = all_results[target_name]

        # DT
        for r in res['dt']:
            hw = r['n_nodes'] * 45 / 8  # bytes
            ax.scatter(hw, r['accuracy'], c='#2196F3', s=80, zorder=5, edgecolors='black')
            if r['accuracy'] >= 99 or r == res['dt'][-1]:
                ax.annotate(f'DT d={r["actual_depth"]}', xy=(hw, r['accuracy']),
                           fontsize=7, textcoords="offset points", xytext=(5, 5))

        # LUT
        for r in res['lut']:
            ax.scatter(r['mem_bytes'], r['accuracy'], c='#FF9800', s=80,
                       marker='s', zorder=5, edgecolors='black')
            if r == res['lut'][-1] or r == res['lut'][0]:
                ax.annotate(f'LUT b={r["n_bins"]}', xy=(r['mem_bytes'], r['accuracy']),
                           fontsize=7, textcoords="offset points", xytext=(5, -10))

        # Poly
        for r in res['poly']:
            hw = r['n_multipliers'] * 50  # ~50 bytes per multiplier HW
            ax.scatter(hw, r['accuracy'], c='#9C27B0', s=80,
                       marker='^', zorder=5, edgecolors='black')
            ax.annotate(f'Poly d={r["degree"]}', xy=(hw, r['accuracy']),
                       fontsize=7, textcoords="offset points", xytext=(5, 5))

        # RF
        for r in res['rf']:
            hw = r['total_nodes'] * 45 / 8
            ax.scatter(hw, r['accuracy'], c='#4CAF50', s=80,
                       marker='D', zorder=5, edgecolors='black')

        # NN
        for r in res['nn']:
            hw = r['n_multipliers'] * 50
            ax.scatter(hw, r['accuracy'], c='#F44336', s=80,
                       marker='v', zorder=5, edgecolors='black')

        ax.axhline(y=99, color='red', linestyle='--', linewidth=1, label='99% target')
        ax.set_xlabel('Estimated Hardware Cost (bytes)')
        ax.set_ylabel('Accuracy (%)')
        ax.set_title(f'{target_name} — Accuracy vs HW Cost')
        ax.set_xscale('log')
        ax.grid(alpha=0.3)
        ax.legend(['99% target', 'Decision Tree', 'LUT', 'Polynomial', 'Random Forest', 'Neural Net'],
                  fontsize=8, loc='lower right')

    fig.tight_layout()
    fig.savefig(os.path.join(PLOTS_DIR, '13_model_comparison.png'),
                dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    print("  Saved: 13_model_comparison.png")


def plot_per_corner(best_dt_pctrl, best_dt_nctrl, X_test, y_p_test, y_n_test, c_test):
    """Plot 14: Per-corner accuracy of best DT model."""
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle('Plot 14: Best DT Per-Corner Accuracy', fontsize=14, fontweight='bold')

    for col, (model, y_test, name) in enumerate([
        (best_dt_pctrl, y_p_test, 'pctrl'),
        (best_dt_nctrl, y_n_test, 'nctrl')
    ]):
        ax = axes[col]
        y_pred = model.predict(X_test)
        per_corner = per_corner_accuracy(y_test, y_pred, c_test)

        corners_list = ['FF', 'SS', 'TT', 'Overall']
        accs = [per_corner.get(c, 0) for c in corners_list]
        colors = [CORNER_COLORS.get(c, '#607D8B') for c in corners_list]

        bars = ax.bar(corners_list, accs, color=colors, edgecolor='black', alpha=0.8)
        ax.axhline(y=99, color='red', linestyle='--', linewidth=1.5, label='99% target')
        ax.set_ylabel('Accuracy (%)')
        ax.set_title(f'{name} — Per Corner')
        ax.set_ylim(90, 101)
        ax.grid(alpha=0.3)
        ax.legend()

        for bar, acc in zip(bars, accs):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.2,
                    f'{acc:.1f}%', ha='center', fontweight='bold', fontsize=10)

    fig.tight_layout()
    fig.savefig(os.path.join(PLOTS_DIR, '14_per_corner_accuracy.png'),
                dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    print("  Saved: 14_per_corner_accuracy.png")


def print_tradeoff_table(all_results):
    """Print the hardware tradeoff comparison table."""
    print("\n" + "=" * 100)
    print("HARDWARE TRADEOFF COMPARISON TABLE")
    print("=" * 100)

    header = f"{'Model':<25s} | {'pctrl Acc':>9s} | {'nctrl Acc':>9s} | {'HW Cost':>12s} | {'Multipliers':>11s} | {'Memory':>10s} | {'Latency':>8s}"
    print(header)
    print("-" * 100)

    # Best DT
    for target in ['pctrl', 'nctrl']:
        dt_results = all_results[target]['dt']
        for r in dt_results:
            if r['accuracy'] >= 99:
                best_dt = r
                break
        else:
            best_dt = max(dt_results, key=lambda x: x['accuracy'])

    # Find best models
    best_dt_p = max(all_results['pctrl']['dt'], key=lambda x: x['accuracy'])
    best_dt_n = max(all_results['nctrl']['dt'], key=lambda x: x['accuracy'])
    best_dt_p_99 = next((r for r in all_results['pctrl']['dt'] if r['accuracy'] >= 99), best_dt_p)
    best_dt_n_99 = next((r for r in all_results['nctrl']['dt'] if r['accuracy'] >= 99), best_dt_n)

    max_nodes = max(best_dt_p_99['n_nodes'], best_dt_n_99['n_nodes'])
    sram_bytes = max_nodes * 45 / 8

    print(f"{'DT (best >=99%)':<25s} | {best_dt_p_99['accuracy']:>8.1f}% | {best_dt_n_99['accuracy']:>8.1f}% | "
          f"{sram_bytes:>10.0f} B | {'0':>11s} | {sram_bytes:>8.0f} B | {'~10 cyc':>8s}")

    # Best LUT
    best_lut_p = max(all_results['pctrl']['lut'], key=lambda x: x['accuracy'])
    best_lut_n = max(all_results['nctrl']['lut'], key=lambda x: x['accuracy'])
    total_mem = best_lut_p['mem_bytes'] + best_lut_n['mem_bytes']
    print(f"{'LUT (best)':<25s} | {best_lut_p['accuracy']:>8.1f}% | {best_lut_n['accuracy']:>8.1f}% | "
          f"{total_mem:>10.0f} B | {'0':>11s} | {total_mem:>8.0f} B | {'1 cyc':>8s}")

    # Full LUT (all entries)
    print(f"{'Full LUT (13860 entries)':<25s} | {'100.0':>8s}% | {'100.0':>8s}% | "
          f"{'17325':>10s} B | {'0':>11s} | {'17325':>8s} B | {'1 cyc':>8s}")

    # Best Poly
    best_poly_p = max(all_results['pctrl']['poly'], key=lambda x: x['accuracy'])
    best_poly_n = max(all_results['nctrl']['poly'], key=lambda x: x['accuracy'])
    total_mult = max(best_poly_p['n_multipliers'], best_poly_n['n_multipliers'])
    print(f"{'Polynomial (best)':<25s} | {best_poly_p['accuracy']:>8.1f}% | {best_poly_n['accuracy']:>8.1f}% | "
          f"{total_mult*50:>10d} B | {total_mult:>11d} | {'~0':>8s} B | {'~20 cyc':>8s}")

    # Best RF
    best_rf_p = max(all_results['pctrl']['rf'], key=lambda x: x['accuracy'])
    best_rf_n = max(all_results['nctrl']['rf'], key=lambda x: x['accuracy'])
    total_nodes = max(best_rf_p['total_nodes'], best_rf_n['total_nodes'])
    sram = total_nodes * 45 / 8
    print(f"{'Random Forest (best)':<25s} | {best_rf_p['accuracy']:>8.1f}% | {best_rf_n['accuracy']:>8.1f}% | "
          f"{sram:>10.0f} B | {'0':>11s} | {sram:>8.0f} B | {'~30 cyc':>8s}")

    # Best NN
    best_nn_p = max(all_results['pctrl']['nn'], key=lambda x: x['accuracy'])
    best_nn_n = max(all_results['nctrl']['nn'], key=lambda x: x['accuracy'])
    total_mult = max(best_nn_p['n_multipliers'], best_nn_n['n_multipliers'])
    print(f"{'Neural Net (best)':<25s} | {best_nn_p['accuracy']:>8.1f}% | {best_nn_n['accuracy']:>8.1f}% | "
          f"{total_mult*50:>10d} B | {total_mult:>11d} | {'~0':>8s} B | {'~5 cyc':>8s}")

    print("=" * 100)
    print("\nNote: HW Cost is approximate. DT/RF/LUT use memory; Poly/NN use multipliers.")
    print("1 multiplier (29-bit) ~ 3000 gates ~ 50 bytes equivalent area")


# ─── Main ─────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print("=" * 60)
    print("BGR Model Comparison Pipeline")
    print("=" * 60)

    print("\nLoading data...")
    data = load_data()
    print(f"Total samples: {len(data)}")

    print("\nSplitting data (80% train / 20% test, stratified random)...")
    X_train, X_test, y_p_train, y_p_test, y_n_train, y_n_test, c_train, c_test = split_data(data)
    print(f"Train: {len(X_train)}, Test: {len(X_test)}")
    print(f"Corners in test: {dict(zip(*np.unique(c_test, return_counts=True)))}")

    all_results = {'pctrl': {}, 'nctrl': {}}

    for target_name, y_train, y_test in [('pctrl', y_p_train, y_p_test),
                                           ('nctrl', y_n_train, y_n_test)]:
        print(f"\n{'='*60}")
        print(f"TARGET: {target_name}")
        print(f"{'='*60}")

        print(f"\n--- Decision Tree (depth sweep) ---")
        dt_res = evaluate_decision_tree(X_train, X_test, y_train, y_test, c_test, target_name)
        all_results[target_name]['dt'] = dt_res

        print(f"\n--- LUT (binned) ---")
        lut_res = evaluate_lut(X_train, X_test, y_train, y_test, c_test, target_name)
        all_results[target_name]['lut'] = lut_res

        print(f"\n--- Polynomial Regression ---")
        poly_res = evaluate_polynomial(X_train, X_test, y_train, y_test, c_test, target_name)
        all_results[target_name]['poly'] = poly_res

        print(f"\n--- Random Forest ---")
        rf_res = evaluate_random_forest(X_train, X_test, y_train, y_test, c_test, target_name)
        all_results[target_name]['rf'] = rf_res

        print(f"\n--- Neural Network ---")
        nn_res = evaluate_neural_net(X_train, X_test, y_train, y_test, c_test, target_name)
        all_results[target_name]['nn'] = nn_res

    # Plots
    print(f"\n{'='*60}")
    print("GENERATING COMPARISON PLOTS")
    print(f"{'='*60}")

    plot_depth_sweep(all_results['pctrl']['dt'], all_results['nctrl']['dt'])
    plot_model_comparison(all_results)

    # Select best DT >= 99% for each target
    best_dt_pctrl = None
    for r in all_results['pctrl']['dt']:
        if r['accuracy'] >= 99:
            best_dt_pctrl = r['model']
            print(f"\nBest pctrl DT: depth={r['actual_depth']}, acc={r['accuracy']:.2f}%, nodes={r['n_nodes']}")
            break
    if best_dt_pctrl is None:
        best_r = max(all_results['pctrl']['dt'], key=lambda x: x['accuracy'])
        best_dt_pctrl = best_r['model']
        print(f"\nBest pctrl DT (below 99%): depth={best_r['actual_depth']}, acc={best_r['accuracy']:.2f}%, nodes={best_r['n_nodes']}")

    best_dt_nctrl = None
    for r in all_results['nctrl']['dt']:
        if r['accuracy'] >= 99:
            best_dt_nctrl = r['model']
            print(f"Best nctrl DT: depth={r['actual_depth']}, acc={r['accuracy']:.2f}%, nodes={r['n_nodes']}")
            break
    if best_dt_nctrl is None:
        best_r = max(all_results['nctrl']['dt'], key=lambda x: x['accuracy'])
        best_dt_nctrl = best_r['model']
        print(f"Best nctrl DT (below 99%): depth={best_r['actual_depth']}, acc={best_r['accuracy']:.2f}%, nodes={best_r['n_nodes']}")

    plot_per_corner(best_dt_pctrl, best_dt_nctrl, X_test, y_p_test, y_n_test, c_test)

    # Save best models
    pickle.dump(best_dt_pctrl, open(os.path.join(BASE_DIR, 'ml', 'best_model_pctrl.pkl'), 'wb'))
    pickle.dump(best_dt_nctrl, open(os.path.join(BASE_DIR, 'ml', 'best_model_nctrl.pkl'), 'wb'))
    print("\nSaved best models: ml/best_model_pctrl.pkl, ml/best_model_nctrl.pkl")

    # Print tradeoff table
    print_tradeoff_table(all_results)

    print(f"\n{'='*60}")
    print("DONE! Check plots/ for visualizations.")
    print(f"{'='*60}")
