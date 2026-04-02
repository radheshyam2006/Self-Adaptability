"""
Export Decision Tree Models to Verilog HEX Files — UNIFIED FORMAT
=================================================================
Both pctrl and nctrl trees use the SAME 58-bit node format:

  Bit [57]    : is_leaf      (1 bit)
  Bit [56:55] : feature_id   (2 bits: 0=pmon, 1=vdd, 2=temp)
  Bit [54:26] : threshold    (29 bits)
  Bit [25:16] : left_child   (10 bits)
  Bit [15:6]  : right_child  (10 bits)
  Bit [5:0]   : leaf_value   (6 bits — pctrl uses lower 4 bits)

Total: 58 bits = 15 hex digits
"""

import pandas as pd
import numpy as np
import pickle, os, json

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
ML_DIR = os.path.join(BASE_DIR, "ml")
RTL_DIR = os.path.join(BASE_DIR, "rtl")
os.makedirs(RTL_DIR, exist_ok=True)

NODE_BITS = 58  # Unified format


def tree_to_flat_array(clf):
    """Convert sklearn DecisionTree to flat node array."""
    tree = clf.tree_
    nodes = []
    for i in range(tree.node_count):
        is_leaf = (tree.children_left[i] == -1)
        if is_leaf:
            leaf_value = int(clf.classes_[int(tree.value[i].argmax())])
            nodes.append({
                'is_leaf': 1, 'feature_id': 0, 'threshold': 0,
                'left_child': 0, 'right_child': 0, 'leaf_value': leaf_value
            })
        else:
            nodes.append({
                'is_leaf': 0,
                'feature_id': int(tree.feature[i]),
                'threshold': int(np.floor(tree.threshold[i])),
                'left_child': int(tree.children_left[i]),
                'right_child': int(tree.children_right[i]),
                'leaf_value': 0
            })
    return nodes


def encode_node_58bit(node):
    """Encode node as 58-bit integer -> 15 hex digit string.

    Layout (MSB to LSB):
      [57]    is_leaf
      [56:55] feature_id
      [54:26] threshold  (29 bits)
      [25:16] left_child (10 bits)
      [15:6]  right_child(10 bits)
      [5:0]   leaf_value (6 bits)
    """
    is_leaf    = (node['is_leaf'] & 0x1)
    feature_id = (node['feature_id'] & 0x3)
    threshold  = (node['threshold'] & 0x1FFFFFFF)
    left_child = (node['left_child'] & 0x3FF)
    right_child= (node['right_child'] & 0x3FF)
    leaf_value = (node['leaf_value'] & 0x3F)

    val = 0
    val = (val << 1)  | is_leaf       # bit 57
    val = (val << 2)  | feature_id    # bits 56:55
    val = (val << 29) | threshold     # bits 54:26
    val = (val << 10) | left_child    # bits 25:16
    val = (val << 10) | right_child   # bits 15:6
    val = (val << 6)  | leaf_value    # bits 5:0

    return f'{val:015X}'  # 15 hex digits = 60 bits but we use 58


def write_hex_file(nodes, filepath):
    with open(filepath, 'w') as f:
        for i, node in enumerate(nodes):
            hex_str = encode_node_58bit(node)
            if node['is_leaf']:
                f.write(f"{hex_str}  // [{i}] LEAF val={node['leaf_value']}\n")
            else:
                feat_names = ['pmon', 'vdd', 'temp']
                fname = feat_names[node['feature_id']] if node['feature_id'] < 3 else '?'
                f.write(f"{hex_str}  // [{i}] {fname} <= {node['threshold']} ? "
                        f"L={node['left_child']} : R={node['right_child']}\n")
    print(f"  Written {len(nodes)} nodes to {os.path.basename(filepath)}")


def generate_test_vectors():
    """Generate test vectors from held-out test set."""
    XLSX_PATH = os.path.join(BASE_DIR, "BGR_ML_DATA_JAN9_testsample_2023_MAR6.xlsx")
    SHEET_MAP = {'TT': 'TT-VDD_TEMP', 'SS': 'SS_VDD_TEMP', 'FF': 'FF_VDD_TEMP'}

    def parse_trim(val):
        if pd.isna(val): return np.nan
        s = str(val).replace('-', '').replace(' ', '')
        try: return int(s, 2)
        except:
            try: return int(s)
            except: return np.nan

    frames = []
    for corner, sheet in SHEET_MAP.items():
        df = pd.read_excel(XLSX_PATH, sheet_name=sheet)
        for col in ['vdd', 'temperature', 'PMON_RING_CMOS_res']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        df = df.dropna(subset=['vdd', 'temperature', 'PMON_RING_CMOS_res'])
        df['pctrl_int'] = df['pctrl<3:0>'].apply(parse_trim)
        df['nctrl_int'] = df['nctrl<5:0>'].apply(parse_trim)
        df['corner'] = corner
        frames.append(df)

    data = pd.concat(frames, ignore_index=True).dropna(subset=['pctrl_int', 'nctrl_int'])

    from sklearn.model_selection import train_test_split
    strat = (data['corner'].astype(str) + '_' +
             data['pctrl_int'].astype(int).astype(str) + '_' +
             data['nctrl_int'].astype(int).astype(str))
    _, test_data = train_test_split(data, test_size=0.2, random_state=42, stratify=strat)

    n_vec = min(200, len(test_data))
    sample = test_data.sample(n=n_vec, random_state=42)

    vectors = []
    for _, row in sample.iterrows():
        pmon = int(row['PMON_RING_CMOS_res'])
        vdd = int(round((row['vdd'] - 0.80) * 100))
        temp = int(round((row['temperature'] + 40.0) * 2))
        pctrl = int(row['pctrl_int'])
        nctrl = int(row['nctrl_int'])
        vectors.append((pmon, vdd, temp, pctrl, nctrl))

    # Write hex: pmon(29) | vdd(5) | temp(9) | pctrl(4) | nctrl(6) = 53 bits -> 14 hex digits
    with open(os.path.join(RTL_DIR, "test_vectors.hex"), 'w') as f:
        for pmon, vdd, temp, pctrl, nctrl in vectors:
            val = ((pmon & 0x1FFFFFFF) << 24) | ((vdd & 0x1F) << 19) | \
                  ((temp & 0x1FF) << 10) | ((pctrl & 0xF) << 6) | (nctrl & 0x3F)
            f.write(f"{val:014X}\n")

    with open(os.path.join(RTL_DIR, "test_vectors_readable.txt"), 'w') as f:
        f.write(f"{'#':>4s} {'pmon':>12s} {'vdd':>5s} {'temp':>5s} {'pctrl':>6s} {'nctrl':>6s}\n")
        f.write("-" * 48 + "\n")
        for i, (pmon, vdd, temp, pctrl, nctrl) in enumerate(vectors):
            f.write(f"{i:>4d} {pmon:>12d} {vdd:>5d} {temp:>5d} {pctrl:>6d} {nctrl:>6d}\n")

    print(f"  Written {n_vec} test vectors")
    return vectors


if __name__ == '__main__':
    print("=" * 60)
    print("Export Decision Tree to Verilog HEX (58-bit unified format)")
    print("=" * 60)

    model_pctrl = pickle.load(open(os.path.join(ML_DIR, 'best_model_pctrl.pkl'), 'rb'))
    model_nctrl = pickle.load(open(os.path.join(ML_DIR, 'best_model_nctrl.pkl'), 'rb'))

    print(f"\npctrl: {model_pctrl.tree_.node_count} nodes, depth={model_pctrl.tree_.max_depth}")
    print(f"nctrl: {model_nctrl.tree_.node_count} nodes, depth={model_nctrl.tree_.max_depth}")

    pctrl_nodes = tree_to_flat_array(model_pctrl)
    nctrl_nodes = tree_to_flat_array(model_nctrl)

    print("\nWriting HEX files (58-bit per node)...")
    write_hex_file(pctrl_nodes, os.path.join(RTL_DIR, "pctrl_tree.hex"))
    write_hex_file(nctrl_nodes, os.path.join(RTL_DIR, "nctrl_tree.hex"))

    print("\nGenerating test vectors...")
    vectors = generate_test_vectors()

    # Verify
    X_v = pd.DataFrame({'pmon': [v[0] for v in vectors[:5]],
                         'vdd_enc': [v[1] for v in vectors[:5]],
                         'temp_enc': [v[2] for v in vectors[:5]]})
    pp = model_pctrl.predict(X_v)
    pn = model_nctrl.predict(X_v)
    print(f"\nVerification (first 5):")
    for i in range(5):
        print(f"  [{i}] pctrl: exp={vectors[i][3]}, pred={pp[i]} | nctrl: exp={vectors[i][4]}, pred={pn[i]}")

    p_sram = len(pctrl_nodes) * 58 // 8
    n_sram = len(nctrl_nodes) * 58 // 8
    print(f"\nSRAM: pctrl={p_sram}B, nctrl={n_sram}B, total={(p_sram+n_sram)}B ({(p_sram+n_sram)/1024:.2f}KB)")
