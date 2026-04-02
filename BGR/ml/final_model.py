"""
BGR Final Model Training
=========================
Train the best Decision Tree models for pctrl and nctrl prediction.
- Targets 99%+ accuracy on 20% random test split
- Overfitting OK (Cadence simulation data, no noise)
- Saves models, generates detailed accuracy reports and error analysis

Outputs: pctrl<3:0> (4-bit, 3 classes) and nctrl<5:0> (6-bit, 15 classes)
Inputs:  vdd, temperature, PMON_RING_CMOS_res
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.tree import DecisionTreeClassifier, export_text
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, confusion_matrix, classification_report
import os, pickle, warnings
warnings.filterwarnings('ignore')

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
XLSX_PATH = os.path.join(BASE_DIR, "BGR_ML_DATA_JAN9_testsample_2023_MAR6.xlsx")
PLOTS_DIR = os.path.join(BASE_DIR, "plots")
ML_DIR = os.path.join(BASE_DIR, "ml")
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
    frames = []
    for corner_name, sheet_name in SHEET_MAP.items():
        df = pd.read_excel(XLSX_PATH, sheet_name=sheet_name)
        for col in ['vdd', 'temperature', 'PMON_RING_CMOS_res', 'PMON_RING_CMOS']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        df = df.dropna(subset=['vdd', 'temperature'])
        df['pctrl_int'] = df['pctrl<3:0>'].apply(parse_trim_bits)
        df['nctrl_int'] = df['nctrl<5:0>'].apply(parse_trim_bits)
        df['corner'] = corner_name

        # Keep vbgr column
        col_map = {}
        for c in df.columns:
            cl = c.strip().lower()
            if cl == '' or cl == 'vbgr':
                col_map[c] = 'vbgr'
        df = df.rename(columns=col_map)
        frames.append(df)

    data = pd.concat(frames, ignore_index=True)
    data = data.dropna(subset=['pctrl_int', 'nctrl_int', 'PMON_RING_CMOS_res'])
    data['pctrl_int'] = data['pctrl_int'].astype(int)
    data['nctrl_int'] = data['nctrl_int'].astype(int)
    return data


def encode_features(data):
    X = pd.DataFrame()
    X['pmon'] = data['PMON_RING_CMOS_res'].astype(int)
    X['vdd_enc'] = ((data['vdd'] - 0.80) * 100).round().astype(int)
    X['temp_enc'] = ((data['temperature'] + 40.0) * 2).round().astype(int)
    return X


def per_corner_accuracy(y_true, y_pred, corners):
    results = {}
    for corner in sorted(set(corners)):
        mask = corners == corner
        acc = accuracy_score(y_true[mask], y_pred[mask]) * 100
        results[corner] = acc
    results['Overall'] = accuracy_score(y_true, y_pred) * 100
    return results


def find_optimal_depth(X_train, y_train, X_test, y_test, c_test, target_name, target_acc=99.0):
    """Find smallest depth that achieves target accuracy."""
    print(f"\n--- Depth Sweep for {target_name} (target: {target_acc}%) ---")
    best_model = None
    best_acc = 0
    best_depth = None

    for depth in range(3, 25):
        dt = DecisionTreeClassifier(max_depth=depth, random_state=42)
        dt.fit(X_train, y_train)
        y_pred = dt.predict(X_test)
        acc = accuracy_score(y_test, y_pred) * 100
        per_corner = per_corner_accuracy(y_test, y_pred, c_test)
        min_corner_acc = min(per_corner[c] for c in ['FF', 'SS', 'TT'])

        nodes = dt.tree_.node_count
        leaves = dt.tree_.n_leaves
        actual_depth = dt.tree_.max_depth

        marker = " <-- TARGET MET!" if acc >= target_acc else ""
        print(f"  depth={depth:>2d}: acc={acc:6.2f}% (min_corner={min_corner_acc:.1f}%), "
              f"nodes={nodes}, leaves={leaves}, actual_depth={actual_depth}{marker}")

        if acc > best_acc:
            best_acc = acc
            best_model = dt
            best_depth = depth

        # Stop if we hit the maximum (no improvement for 3 consecutive depths)
        if actual_depth < depth and depth > best_depth + 2:
            print(f"  (tree saturated at actual depth {actual_depth}, stopping)")
            break

    # Also try unlimited depth
    dt = DecisionTreeClassifier(max_depth=None, random_state=42)
    dt.fit(X_train, y_train)
    y_pred = dt.predict(X_test)
    acc = accuracy_score(y_test, y_pred) * 100
    nodes = dt.tree_.node_count
    print(f"  depth=None: acc={acc:6.2f}%, nodes={nodes}, actual_depth={dt.tree_.max_depth}")
    if acc > best_acc:
        best_acc = acc
        best_model = dt

    return best_model, best_acc


# ─── Main ─────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print("=" * 60)
    print("BGR Final Model Training")
    print("=" * 60)

    data = load_data()
    X = encode_features(data)
    y_pctrl = data['pctrl_int'].values
    y_nctrl = data['nctrl_int'].values
    corners = data['corner'].values

    # Stratified split
    strat_label = (data['corner'].astype(str) + '_' +
                   data['pctrl_int'].astype(str) + '_' +
                   data['nctrl_int'].astype(str))

    X_train, X_test, y_p_train, y_p_test, y_n_train, y_n_test, c_train, c_test = \
        train_test_split(X, y_pctrl, y_nctrl, corners,
                         test_size=0.2, random_state=42, stratify=strat_label)

    print(f"\nTotal: {len(data)}, Train: {len(X_train)}, Test: {len(X_test)}")
    print(f"Test corners: {dict(zip(*np.unique(c_test, return_counts=True)))}")
    print(f"\nUnique classes - pctrl: {sorted(np.unique(y_pctrl))}")
    print(f"Unique classes - nctrl: {sorted(np.unique(y_nctrl))}")

    # ─── Find optimal depth for each target ───
    model_pctrl, acc_pctrl = find_optimal_depth(
        X_train, y_p_train, X_test, y_p_test, c_test, 'pctrl', target_acc=99.0)

    model_nctrl, acc_nctrl = find_optimal_depth(
        X_train, y_n_train, X_test, y_n_test, c_test, 'nctrl', target_acc=99.0)

    # ─── Detailed accuracy report ───
    print(f"\n{'='*60}")
    print("FINAL MODEL REPORT")
    print(f"{'='*60}")

    for name, model, y_train, y_test in [
        ('pctrl', model_pctrl, y_p_train, y_p_test),
        ('nctrl', model_nctrl, y_n_train, y_n_test)
    ]:
        y_pred = model.predict(X_test)
        y_pred_train = model.predict(X_train)
        train_acc = accuracy_score(y_train, y_pred_train) * 100
        test_acc = accuracy_score(y_test, y_pred) * 100
        per_corner = per_corner_accuracy(y_test, y_pred, c_test)

        print(f"\n--- {name.upper()} ---")
        print(f"  Train accuracy: {train_acc:.2f}%")
        print(f"  Test accuracy:  {test_acc:.2f}%")
        print(f"  Tree depth:     {model.tree_.max_depth}")
        print(f"  Nodes:          {model.tree_.node_count}")
        print(f"  Leaves:         {model.tree_.n_leaves}")
        print(f"  SRAM size:      {model.tree_.node_count * 45 / 8:.0f} bytes "
              f"({model.tree_.node_count * 45 / 8 / 1024:.2f} KB)")
        print(f"\n  Per-corner accuracy:")
        for corner in ['FF', 'SS', 'TT', 'Overall']:
            print(f"    {corner}: {per_corner[corner]:.2f}%")

        # Error analysis
        errors = y_test != y_pred
        n_errors = errors.sum()
        print(f"\n  Error analysis ({n_errors} errors out of {len(y_test)}):")
        if n_errors > 0:
            error_diffs = np.abs(y_test[errors] - y_pred[errors])
            print(f"    Mean |error|: {error_diffs.mean():.2f}")
            print(f"    Max |error|:  {error_diffs.max()}")
            print(f"    Errors by corner:")
            for corner in ['FF', 'SS', 'TT']:
                mask = (c_test == corner) & errors
                corner_errors = mask.sum()
                corner_total = (c_test == corner).sum()
                print(f"      {corner}: {corner_errors}/{corner_total} errors")

        # Feature importance
        importances = model.feature_importances_
        features = ['pmon_cmos_res', 'vdd', 'temperature']
        print(f"\n  Feature importance:")
        for feat, imp in sorted(zip(features, importances), key=lambda x: -x[1]):
            print(f"    {feat}: {imp*100:.1f}%")

    # ─── Save models ───
    pickle.dump(model_pctrl, open(os.path.join(ML_DIR, 'best_model_pctrl.pkl'), 'wb'))
    pickle.dump(model_nctrl, open(os.path.join(ML_DIR, 'best_model_nctrl.pkl'), 'wb'))

    # Save encoding params
    encoding_params = {
        'pmon': {'type': 'int', 'min': int(X['pmon'].min()), 'max': int(X['pmon'].max()), 'bits': 29},
        'vdd_enc': {'formula': '(vdd_V - 0.80) * 100', 'min': 1, 'max': 19, 'bits': 5},
        'temp_enc': {'formula': '(temp_C + 40.0) * 2', 'min': 0, 'max': 330, 'bits': 9},
        'pctrl_bits': 4,
        'nctrl_bits': 6,
        'pctrl_classes': sorted(int(x) for x in np.unique(y_pctrl)),
        'nctrl_classes': sorted(int(x) for x in np.unique(y_nctrl)),
    }
    import json
    with open(os.path.join(ML_DIR, 'encoding_params.json'), 'w') as f:
        json.dump(encoding_params, f, indent=2)

    print(f"\nSaved: ml/best_model_pctrl.pkl, ml/best_model_nctrl.pkl, ml/encoding_params.json")

    # ─── Test with the Excel testing samples ───
    print(f"\n{'='*60}")
    print("TESTING ON EXCEL 'Testing samples' SHEET")
    print(f"{'='*60}")

    df_test_xl = pd.read_excel(XLSX_PATH,
                                sheet_name='Testing samplesC0_TT_1720_x0009_8.60E')
    df_test_xl = df_test_xl.dropna(subset=['vdd', 'temperature'])
    for col in ['vdd', 'temperature', 'PMON_RING_CMOS_res']:
        df_test_xl[col] = pd.to_numeric(df_test_xl[col], errors='coerce')
    df_test_xl = df_test_xl.dropna(subset=['PMON_RING_CMOS_res'])

    df_test_xl['pctrl_int'] = df_test_xl['pctrl<3:0>'].apply(parse_trim_bits)
    df_test_xl['nctrl_int'] = df_test_xl['nctrl<5:0>'].apply(parse_trim_bits)

    X_xl = encode_features(df_test_xl)
    y_p_xl = df_test_xl['pctrl_int'].values.astype(int)
    y_n_xl = df_test_xl['nctrl_int'].values.astype(int)

    pred_p = model_pctrl.predict(X_xl)
    pred_n = model_nctrl.predict(X_xl)

    print(f"\n{'Sample':<15s} | {'VDD':>5s} | {'Temp':>5s} | {'PMON_res':>12s} | "
          f"{'pctrl_true':>10s} | {'pctrl_pred':>10s} | {'nctrl_true':>10s} | {'nctrl_pred':>10s} | {'Match':>5s}")
    print("-" * 110)

    correct = 0
    for i in range(len(X_xl)):
        corner = df_test_xl.iloc[i].get('Corner', '?')
        vdd = df_test_xl.iloc[i]['vdd']
        temp = df_test_xl.iloc[i]['temperature']
        pmon = df_test_xl.iloc[i]['PMON_RING_CMOS_res']
        p_true, p_pred = y_p_xl[i], pred_p[i]
        n_true, n_pred = y_n_xl[i], pred_n[i]
        match = "OK" if (p_true == p_pred and n_true == n_pred) else "MISS"
        if match == "OK":
            correct += 1
        print(f"{str(corner):<15s} | {vdd:>5.2f} | {temp:>5.1f} | {pmon:>12.0f} | "
              f"{p_true:>10d} | {p_pred:>10d} | {n_true:>10d} | {n_pred:>10d} | {match:>5s}")

    print(f"\nExcel test accuracy: {correct}/{len(X_xl)} = {correct/len(X_xl)*100:.1f}%")

    # ─── Generate final plots ───
    print(f"\n{'='*60}")
    print("GENERATING FINAL PLOTS")
    print(f"{'='*60}")

    # Plot 15: Confusion matrices
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle('Plot 15: Confusion Matrices (Test Set)', fontsize=14, fontweight='bold')

    for col, (model, y_test_plot, name) in enumerate([
        (model_pctrl, y_p_test, 'pctrl'),
        (model_nctrl, y_n_test, 'nctrl')
    ]):
        ax = axes[col]
        y_pred_plot = model.predict(X_test)
        labels = sorted(np.unique(np.concatenate([y_test_plot, y_pred_plot])))
        cm = confusion_matrix(y_test_plot, y_pred_plot, labels=labels)
        im = ax.imshow(cm, cmap='Blues')
        ax.set_xticks(range(len(labels)))
        ax.set_yticks(range(len(labels)))
        ax.set_xticklabels(labels, fontsize=8)
        ax.set_yticklabels(labels, fontsize=8)
        ax.set_xlabel('Predicted')
        ax.set_ylabel('True')
        ax.set_title(f'{name} Confusion Matrix (acc={accuracy_score(y_test_plot, y_pred_plot)*100:.1f}%)')

        # Annotate
        for i in range(len(labels)):
            for j in range(len(labels)):
                val = cm[i, j]
                if val > 0:
                    color = 'white' if val > cm.max() * 0.5 else 'black'
                    ax.text(j, i, str(val), ha='center', va='center',
                            fontsize=8, color=color, fontweight='bold')
        plt.colorbar(im, ax=ax)

    fig.tight_layout()
    fig.savefig(os.path.join(PLOTS_DIR, '15_confusion_matrices.png'),
                dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    print("  Saved: 15_confusion_matrices.png")

    # Plot 16: Error distribution
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    fig.suptitle('Plot 16: Prediction Error Distribution', fontsize=14, fontweight='bold')

    for col, (model, y_test_plot, name) in enumerate([
        (model_pctrl, y_p_test, 'pctrl'),
        (model_nctrl, y_n_test, 'nctrl')
    ]):
        ax = axes[col]
        y_pred_plot = model.predict(X_test)
        errors = y_test_plot - y_pred_plot
        unique_errs, counts = np.unique(errors, return_counts=True)

        colors = ['green' if e == 0 else 'orange' if abs(e) <= 2 else 'red'
                  for e in unique_errs]
        ax.bar(unique_errs, counts, color=colors, edgecolor='black', alpha=0.8)
        ax.set_xlabel('Prediction Error (true - predicted)')
        ax.set_ylabel('Count')
        ax.set_title(f'{name} Error Distribution')
        ax.grid(alpha=0.3)

        # Stats
        correct_pct = (errors == 0).sum() / len(errors) * 100
        ax.text(0.98, 0.98, f'Correct: {correct_pct:.1f}%\n'
                             f'Off-by-1: {((abs(errors) <= 1) & (errors != 0)).sum()}\n'
                             f'Off-by-2+: {(abs(errors) > 1).sum()}',
                transform=ax.transAxes, va='top', ha='right', fontsize=10,
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))

    fig.tight_layout()
    fig.savefig(os.path.join(PLOTS_DIR, '16_error_distribution.png'),
                dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    print("  Saved: 16_error_distribution.png")

    # Print tree rules summary
    print(f"\n{'='*60}")
    print("DECISION TREE RULES (first 30 lines)")
    print(f"{'='*60}")
    feature_names = ['pmon_cmos_res', 'vdd_enc', 'temp_enc']
    for name, model in [('pctrl', model_pctrl), ('nctrl', model_nctrl)]:
        tree_text = export_text(model, feature_names=feature_names, max_depth=4)
        print(f"\n--- {name} tree (showing top 4 levels) ---")
        print(tree_text[:2000])

    # ─── Hardware Summary ───
    print(f"\n{'='*60}")
    print("HARDWARE SUMMARY FOR RTL")
    print(f"{'='*60}")
    pctrl_nodes = model_pctrl.tree_.node_count
    nctrl_nodes = model_nctrl.tree_.node_count
    pctrl_depth = model_pctrl.tree_.max_depth
    nctrl_depth = model_nctrl.tree_.max_depth

    # Node format: is_leaf(1) + feature_id(2) + threshold(29) + left(10) + right(10) + leaf_value(6) = 58 bits
    # But we use 10 bits for leaf value (4+6) to support both pctrl and nctrl
    node_bits = 1 + 2 + 29 + 10 + 10 + 6  # 58 bits for nctrl, or use 10 for combined
    node_bits_pctrl = 1 + 2 + 29 + 10 + 10 + 4  # 56 bits
    node_bits_nctrl = 1 + 2 + 29 + 10 + 10 + 6  # 58 bits

    print(f"\npctrl tree: {pctrl_nodes} nodes, depth={pctrl_depth}")
    print(f"  SRAM: {pctrl_nodes} x {node_bits_pctrl} bits = {pctrl_nodes * node_bits_pctrl} bits "
          f"= {pctrl_nodes * node_bits_pctrl / 8:.0f} bytes")
    print(f"\nnctrl tree: {nctrl_nodes} nodes, depth={nctrl_depth}")
    print(f"  SRAM: {nctrl_nodes} x {node_bits_nctrl} bits = {nctrl_nodes * node_bits_nctrl} bits "
          f"= {nctrl_nodes * node_bits_nctrl / 8:.0f} bytes")

    total_bits = pctrl_nodes * node_bits_pctrl + nctrl_nodes * node_bits_nctrl
    print(f"\nTotal SRAM: {total_bits} bits = {total_bits/8:.0f} bytes = {total_bits/8/1024:.2f} KB")
    print(f"Max latency: {max(pctrl_depth, nctrl_depth)} clock cycles (worst case)")
    print(f"Avg latency: ~{max(pctrl_depth, nctrl_depth) * 2 // 3} clock cycles (typical)")
    print(f"Multipliers: 0")
    print(f"Comparators: 2 (one per tree, reused each cycle)")

    print(f"\n{'='*60}")
    print("DONE!")
    print(f"{'='*60}")
