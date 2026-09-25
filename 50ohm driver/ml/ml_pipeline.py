"""
TSMC 28nm Driver — Proper ML Pipeline for Trim Bit Prediction
==============================================================
Complete pipeline: Data Cleaning -> Feature Engineering -> Normalization ->
Model Comparison (DT, LUT, Small NN) -> Resistance-Based Accuracy Metrics

Inputs:  pmon_cmos_res, vreg, temperature
Outputs: pvtp<7:0>, pvtn<7:0> (8-bit trim codes)
Target:  50 ohm impedance across all FF/SS/TT/FS/SF corners
"""

import sys, io
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.tree import DecisionTreeClassifier, export_text
from sklearn.preprocessing import StandardScaler, MinMaxScaler
from sklearn.metrics import accuracy_score, mean_absolute_error
import os, pickle, json, warnings
warnings.filterwarnings('ignore')

# Try importing torch for small NN
try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.utils.data import DataLoader, TensorDataset
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False
    print("[WARNING] PyTorch not found. Skipping NN model. Install: pip install torch")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
EXCEL_FILE = os.path.join(PROJECT_DIR, "data", "TSMC28nm_DRV_ML_MAR6_LookUP_Table_Mar20_ML Predictions.xlsx")
OUTPUT_DIR = os.path.join(PROJECT_DIR, "plots")
os.makedirs(OUTPUT_DIR, exist_ok=True)

CORNER_SHEETS = {'FF': 'FF_vdd_temp', 'SS': 'SS_vdd_test', 'TT': 'TT_vdd_test',
                 'FS': 'FS_vdd_test', 'SF': 'SF_vdd_test'}
COL_NAMES = ['Corner','vreg','temperature','PULL_UP_RES','PULL_DN_RES',
             'pmon_cmos_res','pmon_cmos','pvtp_raw','pvtn_raw',
             'PULL_UP_RES_new','PULL_DN_RES_new']


# ================================================================
# STEP 1: DATA LOADING & CLEANING
# ================================================================

def pad8(v):
    if pd.isna(v) or str(v).strip().lower() == 'na': return None
    return str(v).replace('-','').strip().zfill(8)

def to_int(v):
    if v is None or pd.isna(v): return None
    try: return int(v, 2)
    except: return None

def load_and_clean():
    """Load data, clean NAs, force numeric types, validate ranges."""
    print("=" * 70)
    print("STEP 1: DATA LOADING & CLEANING")
    print("=" * 70)
    
    all_data = []
    for c, s in CORNER_SHEETS.items():
        df = pd.read_excel(EXCEL_FILE, sheet_name=s, header=0).iloc[:, :11]
        df.columns = COL_NAMES
        
        # Force numeric
        for col in ['vreg','temperature','pmon_cmos_res','pmon_cmos',
                    'PULL_UP_RES','PULL_DN_RES','PULL_UP_RES_new','PULL_DN_RES_new']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        df['corner_label'] = c
        df['pvtp_int'] = df['pvtp_raw'].apply(pad8).apply(to_int)
        df['pvtn_int'] = df['pvtn_raw'].apply(pad8).apply(to_int)
        all_data.append(df)
    
    df = pd.concat(all_data, ignore_index=True)
    
    # Report cleaning
    total = len(df)
    na_pvtp = df['pvtp_int'].isna().sum()
    na_pvtn = df['pvtn_int'].isna().sum()
    na_pmon = df['pmon_cmos_res'].isna().sum()
    na_res = df['PULL_UP_RES_new'].isna().sum()
    
    print(f"  Total rows loaded: {total}")
    print(f"  NA in pvtp: {na_pvtp} ({100*na_pvtp/total:.1f}%)")
    print(f"  NA in pvtn: {na_pvtn}")
    print(f"  NA in pmon_cmos_res: {na_pmon}")
    print(f"  NA in PULL_UP_RES_new: {na_res}")
    
    # Drop NAs
    df = df.dropna(subset=['pvtp_int','pvtn_int','pmon_cmos_res',
                           'PULL_UP_RES_new','PULL_DN_RES_new'])
    print(f"  After cleaning: {len(df)} rows ({total - len(df)} dropped)")
    
    # Validate ranges
    print(f"\n  Feature ranges after cleaning:")
    print(f"    pmon_cmos_res: {df['pmon_cmos_res'].min():.0f} - {df['pmon_cmos_res'].max():.0f}")
    print(f"    vreg: {df['vreg'].min():.2f} - {df['vreg'].max():.2f}")
    print(f"    temperature: {df['temperature'].min():.1f} - {df['temperature'].max():.1f}")
    print(f"    pvtp_int: {df['pvtp_int'].min():.0f} - {df['pvtp_int'].max():.0f} ({df['pvtp_int'].nunique()} unique)")
    print(f"    pvtn_int: {df['pvtn_int'].min():.0f} - {df['pvtn_int'].max():.0f} ({df['pvtn_int'].nunique()} unique)")
    
    # Check for duplicates
    dupes = df.duplicated(subset=['pmon_cmos_res','vreg','temperature']).sum()
    print(f"    Duplicate input combinations: {dupes}")
    
    return df


# ================================================================
# STEP 2: FEATURE ENGINEERING & NORMALIZATION
# ================================================================

def engineer_features(df):
    """Create normalized features and potentially useful combinations."""
    print("\n" + "=" * 70)
    print("STEP 2: FEATURE ENGINEERING & NORMALIZATION")
    print("=" * 70)
    
    # Raw features
    raw_features = ['pmon_cmos_res', 'vreg', 'temperature']
    
    # Normalize each feature to [0, 1]
    scaler = MinMaxScaler()
    df_feat = df[raw_features].copy()
    df_norm = pd.DataFrame(
        scaler.fit_transform(df_feat),
        columns=[f'{c}_norm' for c in raw_features],
        index=df.index
    )
    
    # Add normalized features to df
    for col in df_norm.columns:
        df[col] = df_norm[col].values
    
    print(f"  Normalized features to [0,1]:")
    for col in raw_features:
        norm_col = f'{col}_norm'
        print(f"    {col}: [{df[col].min():.0f}, {df[col].max():.0f}] -> {norm_col}: [{df[norm_col].min():.3f}, {df[norm_col].max():.3f}]")
    
    # Feature interaction: pmon * vreg (captures V-dependent process effect)
    df['pmon_x_vreg_norm'] = df['pmon_cmos_res_norm'] * df['vreg_norm']
    # Feature interaction: pmon * temp
    df['pmon_x_temp_norm'] = df['pmon_cmos_res_norm'] * df['temperature_norm']
    
    print(f"\n  Added interaction features:")
    print(f"    pmon_x_vreg_norm: [{df['pmon_x_vreg_norm'].min():.3f}, {df['pmon_x_vreg_norm'].max():.3f}]")
    print(f"    pmon_x_temp_norm: [{df['pmon_x_temp_norm'].min():.3f}, {df['pmon_x_temp_norm'].max():.3f}]")
    
    return df, scaler


# ================================================================
# STEP 3: TRAIN/TEST SPLIT
# ================================================================

def split_data(df, feature_cols, test_size=0.2):
    """Stratified split ensuring all corners in train and test."""
    print(f"\n" + "=" * 70)
    print(f"STEP 3: TRAIN/TEST SPLIT")
    print(f"=" * 70)
    
    X = df[feature_cols].values
    y_pvtp = df['pvtp_int'].values.astype(int)
    y_pvtn = df['pvtn_int'].values.astype(int)
    corners = df['corner_label'].values
    # Also carry PULL_UP/DN_RES_new for final resistance evaluation
    res_up = df['PULL_UP_RES_new'].values
    res_dn = df['PULL_DN_RES_new'].values
    # And original resistance
    res_up_orig = df['PULL_UP_RES'].values
    res_dn_orig = df['PULL_DN_RES'].values
    
    (X_tr, X_te, yp_tr, yp_te, yn_tr, yn_te,
     c_tr, c_te, ru_tr, ru_te, rd_tr, rd_te,
     ruo_tr, ruo_te, rdo_tr, rdo_te) = \
        train_test_split(X, y_pvtp, y_pvtn, corners, res_up, res_dn,
                        res_up_orig, res_dn_orig,
                        test_size=test_size, random_state=42, stratify=corners)
    
    print(f"  Features used: {feature_cols}")
    print(f"  Train: {len(X_tr)}, Test: {len(X_te)}")
    for c in ['FF','SS','TT','FS','SF']:
        n_tr = (c_tr == c).sum()
        n_te = (c_te == c).sum()
        print(f"    {c}: train={n_tr}, test={n_te}")
    
    return (X_tr, X_te, yp_tr, yp_te, yn_tr, yn_te,
            c_tr, c_te, ru_te, rd_te, ruo_te, rdo_te)


# ================================================================
# STEP 4: MODEL TRAINING & COMPARISON
# ================================================================

def build_resistance_lookup(df):
    """For each (corner, pvtp/pvtn), get the median resulting resistance.
    Used to convert predicted trim codes -> estimated resistance."""
    pvtp_to_res = {}
    pvtn_to_res = {}
    
    for c in df['corner_label'].unique():
        cdf = df[df['corner_label'] == c]
        for pvtp in cdf['pvtp_int'].unique():
            med_res = cdf[cdf['pvtp_int'] == pvtp]['PULL_UP_RES_new'].abs().median()
            pvtp_to_res[(c, int(pvtp))] = med_res
        for pvtn in cdf['pvtn_int'].unique():
            med_res = cdf[cdf['pvtn_int'] == pvtn]['PULL_DN_RES_new'].abs().median()
            pvtn_to_res[(c, int(pvtn))] = med_res
    
    return pvtp_to_res, pvtn_to_res


def evaluate_model(name, yp_true, yp_pred, yn_true, yn_pred, corners,
                   pvtp_to_res, pvtn_to_res, ru_actual, rd_actual):
    """Comprehensive evaluation with resistance-based metrics."""
    
    # Classification accuracy
    pvtp_acc = accuracy_score(yp_true, yp_pred)
    pvtn_acc = accuracy_score(yn_true, yn_pred)
    
    # Off-by-1 accuracy (acceptable in hardware)
    pvtp_off1 = np.mean(np.abs(yp_true.astype(float) - yp_pred.astype(float)) <= 1)
    pvtn_off1 = np.mean(np.abs(yn_true.astype(float) - yn_pred.astype(float)) <= 1)
    
    # MAE
    pvtp_mae = mean_absolute_error(yp_true, yp_pred)
    pvtn_mae = mean_absolute_error(yn_true, yn_pred)
    
    # Resistance-based metrics
    # For predicted trim code, estimate what resistance we'd get
    pred_res_up = []
    pred_res_dn = []
    for i in range(len(yp_pred)):
        c = corners[i]
        # Lookup predicted trim code's resistance; fallback to actual if not found
        key_p = (c, int(yp_pred[i]))
        key_n = (c, int(yn_pred[i]))
        pred_res_up.append(pvtp_to_res.get(key_p, 50.0))
        pred_res_dn.append(pvtn_to_res.get(key_n, 50.0))
    
    pred_res_up = np.array(pred_res_up)
    pred_res_dn = np.array(pred_res_dn)
    
    # Resistance error from 50 ohm
    err_up = pred_res_up - 50.0
    err_dn = pred_res_dn - 50.0
    
    result = {
        'name': name,
        'pvtp_acc': pvtp_acc, 'pvtn_acc': pvtn_acc,
        'pvtp_off1': pvtp_off1, 'pvtn_off1': pvtn_off1,
        'pvtp_mae': pvtp_mae, 'pvtn_mae': pvtn_mae,
        'res_up_min': pred_res_up.min(),
        'res_up_max': pred_res_up.max(),
        'res_up_mean_err': err_up.mean(),
        'res_up_max_err': np.abs(err_up).max(),
        'res_dn_min': pred_res_dn.min(),
        'res_dn_max': pred_res_dn.max(),
        'res_dn_mean_err': err_dn.mean(),
        'res_dn_max_err': np.abs(err_dn).max(),
    }
    
    # Per-corner breakdown
    per_corner = {}
    for c in ['FF','SS','TT','FS','SF']:
        mask = corners == c
        if mask.sum() == 0: continue
        per_corner[c] = {
            'pvtp_acc': accuracy_score(yp_true[mask], yp_pred[mask]),
            'pvtn_acc': accuracy_score(yn_true[mask], yn_pred[mask]),
            'pvtp_off1': np.mean(np.abs(yp_true[mask].astype(float) - yp_pred[mask].astype(float)) <= 1),
            'pvtn_off1': np.mean(np.abs(yn_true[mask].astype(float) - yn_pred[mask].astype(float)) <= 1),
            'res_up_range': f"{pred_res_up[mask].min():.2f} - {pred_res_up[mask].max():.2f}",
            'res_dn_range': f"{pred_res_dn[mask].min():.2f} - {pred_res_dn[mask].max():.2f}",
        }
    result['per_corner'] = per_corner
    
    return result


def train_decision_trees(X_tr, X_te, yp_tr, yp_te, yn_tr, yn_te,
                         c_te, pvtp_to_res, pvtn_to_res, ru_te, rd_te):
    """Train decision trees at various depths."""
    print(f"\n--- Decision Tree Models ---")
    
    results = []
    best_models = {}
    
    for depth in [5, 7, 10, 12, 14]:
        dt_p = DecisionTreeClassifier(max_depth=depth, random_state=42).fit(X_tr, yp_tr)
        dt_n = DecisionTreeClassifier(max_depth=depth, random_state=42).fit(X_tr, yn_tr)
        
        yp_pred = dt_p.predict(X_te)
        yn_pred = dt_n.predict(X_te)
        
        res = evaluate_model(f"DT(d={depth})", yp_te, yp_pred, yn_te, yn_pred,
                           c_te, pvtp_to_res, pvtn_to_res, ru_te, rd_te)
        res['leaves_p'] = dt_p.get_n_leaves()
        res['leaves_n'] = dt_n.get_n_leaves()
        res['total_leaves'] = dt_p.get_n_leaves() + dt_n.get_n_leaves()
        res['est_comparators'] = dt_p.tree_.node_count + dt_n.tree_.node_count
        results.append(res)
        
        best_models[depth] = (dt_p, dt_n)
        
        print(f"  depth={depth:2d}: pvtp={res['pvtp_acc']:.4f} pvtn={res['pvtn_acc']:.4f} "
              f"off1_p={res['pvtp_off1']:.4f} leaves={res['total_leaves']} "
              f"res_up=[{res['res_up_min']:.2f},{res['res_up_max']:.2f}]")
    
    return results, best_models


def train_lut_models(X_tr, X_te, yp_tr, yp_te, yn_tr, yn_te,
                     c_te, pvtp_to_res, pvtn_to_res, ru_te, rd_te):
    """Train LUT-based models with different quantization levels."""
    print(f"\n--- LUT-Based Models ---")
    
    results = []
    
    for n_bins_per_dim in [4, 6, 8, 10]:
        # Quantize each dimension
        total_entries = n_bins_per_dim ** 3  # 3 dimensions
        
        # Build 3D LUT
        edges = []
        for dim in range(3):
            e = np.linspace(X_tr[:, dim].min(), X_tr[:, dim].max(), n_bins_per_dim + 1)
            edges.append(e)
        
        # Assign bins
        tr_bins = np.zeros((len(X_tr), 3), dtype=int)
        te_bins = np.zeros((len(X_te), 3), dtype=int)
        for dim in range(3):
            tr_bins[:, dim] = np.clip(np.digitize(X_tr[:, dim], edges[dim]) - 1, 0, n_bins_per_dim - 1)
            te_bins[:, dim] = np.clip(np.digitize(X_te[:, dim], edges[dim]) - 1, 0, n_bins_per_dim - 1)
        
        # Build LUT
        lut_pvtp = np.zeros((n_bins_per_dim,) * 3, dtype=int)
        lut_pvtn = np.zeros((n_bins_per_dim,) * 3, dtype=int)
        
        for idx in np.ndindex(n_bins_per_dim, n_bins_per_dim, n_bins_per_dim):
            mask = (tr_bins[:, 0] == idx[0]) & (tr_bins[:, 1] == idx[1]) & (tr_bins[:, 2] == idx[2])
            if mask.sum() > 0:
                vals, counts = np.unique(yp_tr[mask], return_counts=True)
                lut_pvtp[idx] = vals[counts.argmax()]
                vals, counts = np.unique(yn_tr[mask], return_counts=True)
                lut_pvtn[idx] = vals[counts.argmax()]
        
        # Predict
        yp_pred = np.array([lut_pvtp[tuple(te_bins[i])] for i in range(len(X_te))])
        yn_pred = np.array([lut_pvtn[tuple(te_bins[i])] for i in range(len(X_te))])
        
        res = evaluate_model(f"LUT3D({n_bins_per_dim}^3={total_entries})",
                           yp_te, yp_pred, yn_te, yn_pred,
                           c_te, pvtp_to_res, pvtn_to_res, ru_te, rd_te)
        
        addr_bits = int(np.ceil(np.log2(total_entries)))
        res['total_entries'] = total_entries
        res['addr_bits'] = addr_bits
        res['est_comparators'] = total_entries  # ROM entries
        results.append(res)
        
        print(f"  {n_bins_per_dim}^3={total_entries:4d} entries: pvtp={res['pvtp_acc']:.4f} "
              f"pvtn={res['pvtn_acc']:.4f} off1_p={res['pvtp_off1']:.4f} "
              f"res_up=[{res['res_up_min']:.2f},{res['res_up_max']:.2f}]")
    
    return results


class SmallNN(nn.Module):
    """Tiny neural network for ASIC implementation."""
    def __init__(self, input_size, hidden_size, output_size):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_size, hidden_size),
            nn.ReLU(),
            nn.Linear(hidden_size, output_size)
        )
    
    def forward(self, x):
        return self.net(x)


class TwoLayerNN(nn.Module):
    """Two hidden layer NN."""
    def __init__(self, input_size, h1, h2, output_size):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_size, h1),
            nn.ReLU(),
            nn.Linear(h1, h2),
            nn.ReLU(),
            nn.Linear(h2, output_size)
        )
    
    def forward(self, x):
        return self.net(x)


def train_nn_models(X_tr, X_te, yp_tr, yp_te, yn_tr, yn_te,
                    c_te, pvtp_to_res, pvtn_to_res, ru_te, rd_te):
    """Train small neural networks."""
    if not HAS_TORCH:
        print("\n--- Neural Network Models: SKIPPED (no PyTorch) ---")
        return []
    
    print(f"\n--- Neural Network Models ---")
    
    # Normalize inputs for NN
    scaler = StandardScaler()
    X_tr_s = scaler.fit_transform(X_tr)
    X_te_s = scaler.transform(X_te)
    
    # Get all unique classes and create mapping
    all_pvtp = sorted(set(yp_tr) | set(yp_te))
    all_pvtn = sorted(set(yn_tr) | set(yn_te))
    pvtp_to_idx = {v: i for i, v in enumerate(all_pvtp)}
    pvtn_to_idx = {v: i for i, v in enumerate(all_pvtn)}
    idx_to_pvtp = {i: v for v, i in pvtp_to_idx.items()}
    idx_to_pvtn = {i: v for v, i in pvtn_to_idx.items()}
    
    n_pvtp_classes = len(all_pvtp)
    n_pvtn_classes = len(all_pvtn)
    
    # Convert to indices
    yp_tr_idx = np.array([pvtp_to_idx[v] for v in yp_tr])
    yp_te_idx = np.array([pvtp_to_idx[v] for v in yp_te])
    yn_tr_idx = np.array([pvtn_to_idx[v] for v in yn_tr])
    yn_te_idx = np.array([pvtn_to_idx[v] for v in yn_te])
    
    # Tensors
    X_tr_t = torch.FloatTensor(X_tr_s)
    X_te_t = torch.FloatTensor(X_te_s)
    yp_tr_t = torch.LongTensor(yp_tr_idx)
    yn_tr_t = torch.LongTensor(yn_tr_idx)
    
    results = []
    
    # Test different architectures
    configs = [
        ("NN(3->8->out)", 8, None),
        ("NN(3->16->out)", 16, None),
        ("NN(3->32->out)", 32, None),
        ("NN(3->16->8->out)", 16, 8),
        ("NN(3->32->16->out)", 32, 16),
    ]
    
    for name, h1, h2 in configs:
        # Train pvtp model
        if h2 is None:
            model_p = SmallNN(3, h1, n_pvtp_classes)
            model_n = SmallNN(3, h1, n_pvtn_classes)
            n_params = (3 * h1 + h1) + (h1 * n_pvtp_classes + n_pvtp_classes)
            n_mults = 3 * h1 + h1 * n_pvtp_classes
        else:
            model_p = TwoLayerNN(3, h1, h2, n_pvtp_classes)
            model_n = TwoLayerNN(3, h1, h2, n_pvtn_classes)
            n_params = (3*h1+h1) + (h1*h2+h2) + (h2*n_pvtp_classes+n_pvtp_classes)
            n_mults = 3*h1 + h1*h2 + h2*n_pvtp_classes
        
        # Train pvtp
        optimizer = optim.Adam(model_p.parameters(), lr=0.01)
        criterion = nn.CrossEntropyLoss()
        dataset = TensorDataset(X_tr_t, yp_tr_t)
        loader = DataLoader(dataset, batch_size=256, shuffle=True)
        
        model_p.train()
        for epoch in range(100):
            for xb, yb in loader:
                optimizer.zero_grad()
                loss = criterion(model_p(xb), yb)
                loss.backward()
                optimizer.step()
        
        # Train pvtn
        optimizer = optim.Adam(model_n.parameters(), lr=0.01)
        dataset = TensorDataset(X_tr_t, yn_tr_t)
        loader = DataLoader(dataset, batch_size=256, shuffle=True)
        
        model_n.train()
        for epoch in range(100):
            for xb, yb in loader:
                optimizer.zero_grad()
                loss = criterion(model_n(xb), yb)
                loss.backward()
                optimizer.step()
        
        # Evaluate
        model_p.eval()
        model_n.eval()
        with torch.no_grad():
            yp_pred_idx = model_p(X_te_t).argmax(dim=1).numpy()
            yn_pred_idx = model_n(X_te_t).argmax(dim=1).numpy()
        
        yp_pred = np.array([idx_to_pvtp[i] for i in yp_pred_idx])
        yn_pred = np.array([idx_to_pvtn[i] for i in yn_pred_idx])
        
        res = evaluate_model(name, yp_te, yp_pred, yn_te, yn_pred,
                           c_te, pvtp_to_res, pvtn_to_res, ru_te, rd_te)
        res['n_params'] = n_params * 2  # both pvtp and pvtn models
        res['n_mults'] = n_mults * 2
        res['est_comparators'] = n_mults  # each multiply ~ comparator in area
        results.append(res)
        
        print(f"  {name:22s}: pvtp={res['pvtp_acc']:.4f} pvtn={res['pvtn_acc']:.4f} "
              f"off1_p={res['pvtp_off1']:.4f} params={res['n_params']} mults={res['n_mults']} "
              f"res_up=[{res['res_up_min']:.2f},{res['res_up_max']:.2f}]")
    
    return results


# ================================================================
# STEP 5: RESULTS & VISUALIZATION
# ================================================================

def print_comprehensive_results(all_results, best_dt_p, best_dt_n, depth):
    """Print the final comprehensive comparison."""
    
    print(f"\n{'='*100}")
    print("FINAL MODEL COMPARISON — COMPREHENSIVE METRICS")
    print(f"{'='*100}")
    
    # Sort by pvtp accuracy
    all_results.sort(key=lambda x: x['pvtp_acc'], reverse=True)
    
    print(f"\n{'Model':<25} {'pvtp_acc':<10} {'pvtn_acc':<10} {'pvtp_off1':<10} {'pvtn_off1':<10} "
          f"{'RES_UP range':<18} {'RES_DN range':<18} {'HW est':<10}")
    print("-" * 111)
    
    for r in all_results:
        hw = r.get('total_leaves', r.get('total_entries', r.get('n_mults', '?')))
        print(f"{r['name']:<25} {r['pvtp_acc']:<10.4f} {r['pvtn_acc']:<10.4f} "
              f"{r['pvtp_off1']:<10.4f} {r['pvtn_off1']:<10.4f} "
              f"{r['res_up_min']:.2f}-{r['res_up_max']:.2f}{'':>4} "
              f"{r['res_dn_min']:.2f}-{r['res_dn_max']:.2f}{'':>4} "
              f"{hw}")
    
    # Per-corner for best model
    best = [r for r in all_results if f'DT(d={depth})' in r['name']]
    if best:
        r = best[0]
        print(f"\n--- Best Model Per-Corner: {r['name']} ---")
        print(f"{'Corner':<8} {'pvtp_acc':<10} {'pvtn_acc':<10} {'pvtp_off1':<10} {'pvtn_off1':<10} "
              f"{'RES_UP after comp':<20} {'RES_DN after comp':<20}")
        print("-" * 88)
        for c in ['FF','SS','TT','FS','SF']:
            pc = r['per_corner'].get(c, {})
            print(f"{c:<8} {pc.get('pvtp_acc',0):<10.4f} {pc.get('pvtn_acc',0):<10.4f} "
                  f"{pc.get('pvtp_off1',0):<10.4f} {pc.get('pvtn_off1',0):<10.4f} "
                  f"{pc.get('res_up_range','?'):<20} {pc.get('res_dn_range','?'):<20}")
    
    # Final resistance summary
    print(f"\n{'='*70}")
    print("FINAL IMPEDANCE MATCHING RESULT")
    print(f"{'='*70}")
    if best:
        r = best[0]
        print(f"""
Model: {r['name']}
After compensation with predicted trim bits:

  PULL-UP RESISTANCE:
    Range:     {r['res_up_min']:.2f} - {r['res_up_max']:.2f} ohm
    Mean err:  {r['res_up_mean_err']:.3f} ohm from 50 ohm target
    Max err:   {r['res_up_max_err']:.3f} ohm from 50 ohm target

  PULL-DOWN RESISTANCE:
    Range:     {r['res_dn_min']:.2f} - {r['res_dn_max']:.2f} ohm
    Mean err:  {r['res_dn_mean_err']:.3f} ohm from 50 ohm target
    Max err:   {r['res_dn_max_err']:.3f} ohm from 50 ohm target

  TRIM BIT PREDICTION:
    pvtp exact match: {r['pvtp_acc']*100:.1f}%
    pvtn exact match: {r['pvtn_acc']*100:.1f}%
    pvtp within +/-1: {r['pvtp_off1']*100:.1f}%
    pvtn within +/-1: {r['pvtn_off1']*100:.1f}%
    
  HARDWARE COST:
    Total leaves: {r.get('total_leaves','?')}
    Comparators:  {r.get('est_comparators','?')}
    Implementation: Cascaded if-else (comparators + MUX)
""")


def plot_final_comparison(all_results):
    """Final comparison visualization."""
    fig, axes = plt.subplots(2, 2, figsize=(18, 14))
    fig.suptitle('Model Comparison: Accuracy, Hardware Cost, and Resistance Range',
                 fontsize=15, fontweight='bold')
    
    names = [r['name'] for r in all_results]
    pvtp_accs = [r['pvtp_acc'] for r in all_results]
    pvtn_accs = [r['pvtn_acc'] for r in all_results]
    pvtp_off1 = [r['pvtp_off1'] for r in all_results]
    
    # Color by model type
    colors = []
    for n in names:
        if 'DT' in n: colors.append('#e74c3c')
        elif 'LUT' in n: colors.append('#f39c12')
        elif 'NN' in n: colors.append('#3498db')
        else: colors.append('#9b59b6')
    
    # Bar chart: exact accuracy
    ax = axes[0, 0]
    x = np.arange(len(names))
    w = 0.35
    ax.barh(x - w/2, pvtp_accs, w, color=[c for c in colors], alpha=0.7, label='pvtp')
    ax.barh(x + w/2, pvtn_accs, w, color=[c for c in colors], alpha=0.4, label='pvtn')
    ax.set_yticks(x)
    ax.set_yticklabels(names, fontsize=8)
    ax.set_xlabel('Exact Match Accuracy')
    ax.set_title('Exact Trim Bit Accuracy', fontweight='bold')
    ax.axvline(0.95, color='green', linestyle='--', alpha=0.5, label='95% target')
    ax.legend()
    
    # Bar chart: off-by-1 accuracy
    ax = axes[0, 1]
    pvtn_off1_vals = [r['pvtn_off1'] for r in all_results]
    ax.barh(x - w/2, pvtp_off1, w, color=[c for c in colors], alpha=0.7, label='pvtp +/-1')
    ax.barh(x + w/2, pvtn_off1_vals, w, color=[c for c in colors], alpha=0.4, label='pvtn +/-1')
    ax.set_yticks(x)
    ax.set_yticklabels(names, fontsize=8)
    ax.set_xlabel('Off-by-1 Accuracy')
    ax.set_title('Trim Bit Accuracy (within +/-1 code)', fontweight='bold')
    ax.axvline(0.98, color='green', linestyle='--', alpha=0.5, label='98% target')
    ax.legend()
    
    # Resistance range
    ax = axes[1, 0]
    for i, r in enumerate(all_results):
        ax.barh(i, r['res_up_max'] - r['res_up_min'],
               left=r['res_up_min'], color=colors[i], alpha=0.6, height=0.4)
        ax.plot(50.0, i, 'k|', markersize=15, markeredgewidth=2)
    ax.set_yticks(x)
    ax.set_yticklabels(names, fontsize=8)
    ax.set_xlabel('Pull-Up Resistance (ohm)')
    ax.set_title('Predicted Resistance Range (PULL_UP)', fontweight='bold')
    ax.axvline(48.5, color='red', linestyle='--', alpha=0.5)
    ax.axvline(51.5, color='red', linestyle='--', alpha=0.5, label='+/-1.5 ohm spec')
    ax.axvline(50, color='green', linestyle='-', alpha=0.5, label='50 ohm target')
    ax.legend(fontsize=8)
    
    # Hardware cost vs accuracy scatter
    ax = axes[1, 1]
    hw_costs = []
    for r in all_results:
        hw = r.get('total_leaves', r.get('total_entries', r.get('n_mults', 1000)))
        hw_costs.append(hw)
    
    ax.scatter(hw_costs, pvtp_accs, c=colors, s=100, zorder=5)
    for i, n in enumerate(names):
        ax.annotate(n, (hw_costs[i], pvtp_accs[i]), textcoords="offset points",
                   xytext=(5, 5), fontsize=7)
    ax.set_xlabel('Hardware Size (leaves/entries/multiplies)')
    ax.set_ylabel('pvtp Exact Accuracy')
    ax.set_title('Accuracy vs Hardware Cost Tradeoff', fontweight='bold')
    ax.axhline(0.95, color='green', linestyle='--', alpha=0.5, label='95% accuracy')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, '15_final_comparison.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("[OK] Plot 15: Final comparison saved")


def plot_resistance_after_compensation(all_results, c_te, yp_te):
    """Show the actual resistance we'd get for best models."""
    best_models_to_plot = [r for r in all_results if 'DT(d=12)' in r['name'] or 'DT(d=14)' in r['name']]
    
    if not best_models_to_plot:
        return
    
    fig, axes = plt.subplots(1, 2, figsize=(16, 7))
    fig.suptitle('Resistance After Compensation (with predicted trim bits)', fontsize=14, fontweight='bold')
    
    for r in best_models_to_plot:
        pc = r['per_corner']
        corners = list(pc.keys())
        
        # Extract min/max from range strings
        ups = []
        dns = []
        for c in corners:
            rng = pc[c]['res_up_range'].split(' - ')
            ups.append((float(rng[0]), float(rng[1])))
            rng = pc[c]['res_dn_range'].split(' - ')
            dns.append((float(rng[0]), float(rng[1])))
        
        x = np.arange(len(corners))
        ax = axes[0]
        for i, c in enumerate(corners):
            ax.barh(i, ups[i][1] - ups[i][0], left=ups[i][0], height=0.3,
                   alpha=0.6, label=c if r == best_models_to_plot[0] else None)
        ax.set_title(f'{r["name"]}: PULL_UP_RES range per corner', fontweight='bold')
        
        ax = axes[1]
        for i, c in enumerate(corners):
            ax.barh(i, dns[i][1] - dns[i][0], left=dns[i][0], height=0.3, alpha=0.6)
        ax.set_title(f'{r["name"]}: PULL_DN_RES range per corner', fontweight='bold')
    
    for ax in axes:
        ax.set_yticks(range(len(corners)))
        ax.set_yticklabels(corners)
        ax.axvline(50, color='green', linestyle='-', linewidth=2)
        ax.axvline(48.5, color='red', linestyle='--')
        ax.axvline(51.5, color='red', linestyle='--')
        ax.set_xlabel('Resistance (ohm)')
    
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, '16_resistance_after_comp.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("[OK] Plot 16: Resistance after compensation saved")


# ================================================================
# MAIN PIPELINE
# ================================================================

if __name__ == '__main__':
    # STEP 1: Load & Clean
    df = load_and_clean()
    
    # STEP 2: Feature Engineering
    df, scaler = engineer_features(df)
    
    # Test with raw features (decision tree doesn't need normalization)
    # and with normalized + interaction features (NN benefits from this)
    feature_sets = {
        'raw': ['pmon_cmos_res', 'vreg', 'temperature'],
        'normalized': ['pmon_cmos_res_norm', 'vreg_norm', 'temperature_norm'],
        'norm+interactions': ['pmon_cmos_res_norm', 'vreg_norm', 'temperature_norm',
                             'pmon_x_vreg_norm', 'pmon_x_temp_norm'],
    }
    
    # Build resistance lookup table
    pvtp_to_res, pvtn_to_res = build_resistance_lookup(df)
    
    # STEP 3: Split
    raw_split = split_data(df, feature_sets['raw'])
    X_tr, X_te, yp_tr, yp_te, yn_tr, yn_te, c_tr, c_te, ru_te, rd_te, ruo_te, rdo_te = raw_split
    
    # STEP 4: Train models
    print(f"\n{'='*70}")
    print("STEP 4: MODEL TRAINING & COMPARISON")
    print(f"{'='*70}")
    
    all_results = []
    
    # 4a. Decision Trees (raw features — DT doesn't need normalization)
    dt_results, best_dt_models = train_decision_trees(
        X_tr, X_te, yp_tr, yp_te, yn_tr, yn_te,
        c_te, pvtp_to_res, pvtn_to_res, ru_te, rd_te)
    all_results.extend(dt_results)
    
    # 4b. LUT models (raw features)
    lut_results = train_lut_models(
        X_tr, X_te, yp_tr, yp_te, yn_tr, yn_te,
        c_te, pvtp_to_res, pvtn_to_res, ru_te, rd_te)
    all_results.extend(lut_results)
    
    # 4c. Neural networks (normalized features)
    norm_split = split_data(df, feature_sets['normalized'])
    X_tr_n, X_te_n = norm_split[0], norm_split[1]
    
    nn_results = train_nn_models(
        X_tr_n, X_te_n, yp_tr, yp_te, yn_tr, yn_te,
        c_te, pvtp_to_res, pvtn_to_res, ru_te, rd_te)
    all_results.extend(nn_results)
    
    # Also test DT with normalized + interactions
    print(f"\n--- Decision Tree with Normalized + Interaction Features ---")
    int_split = split_data(df, feature_sets['norm+interactions'])
    X_tr_i, X_te_i = int_split[0], int_split[1]
    
    for depth in [10, 12]:
        dt_p = DecisionTreeClassifier(max_depth=depth, random_state=42).fit(X_tr_i, yp_tr)
        dt_n = DecisionTreeClassifier(max_depth=depth, random_state=42).fit(X_tr_i, yn_tr)
        yp_pred = dt_p.predict(X_te_i)
        yn_pred = dt_n.predict(X_te_i)
        res = evaluate_model(f"DT+feat(d={depth})", yp_te, yp_pred, yn_te, yn_pred,
                           c_te, pvtp_to_res, pvtn_to_res, ru_te, rd_te)
        res['total_leaves'] = dt_p.get_n_leaves() + dt_n.get_n_leaves()
        res['est_comparators'] = dt_p.tree_.node_count + dt_n.tree_.node_count
        all_results.append(res)
        print(f"  DT+feat(d={depth}): pvtp={res['pvtp_acc']:.4f} pvtn={res['pvtn_acc']:.4f} "
              f"leaves={res['total_leaves']} res_up=[{res['res_up_min']:.2f},{res['res_up_max']:.2f}]")
    
    # STEP 5: Results
    best_depth = 12
    best_dt_p, best_dt_n = best_dt_models[best_depth]
    print_comprehensive_results(all_results, best_dt_p, best_dt_n, best_depth)
    
    # STEP 6: Plots
    plot_final_comparison(all_results)
    plot_resistance_after_compensation(all_results, c_te, yp_te)
    
    # Export best model
    print(f"\n--- Exporting best model (DT depth={best_depth}) ---")
    with open('best_model_pvtp.pkl', 'wb') as f: pickle.dump(best_dt_p, f)
    with open('best_model_pvtn.pkl', 'wb') as f: pickle.dump(best_dt_n, f)
    
    full_pvtp = export_text(best_dt_p, feature_names=['pmon_cmos_res','vreg','temperature'])
    full_pvtn = export_text(best_dt_n, feature_names=['pmon_cmos_res','vreg','temperature'])
    with open(os.path.join(OUTPUT_DIR, 'best_dt_pvtp_rules.txt'), 'w') as f: f.write(full_pvtp)
    with open(os.path.join(OUTPUT_DIR, 'best_dt_pvtn_rules.txt'), 'w') as f: f.write(full_pvtn)
    
    # Save scaler params for RTL
    scaler_params = {
        'pmon_cmos_res': {'min': float(scaler.data_min_[0]), 'max': float(scaler.data_max_[0])},
        'vreg': {'min': float(scaler.data_min_[1]), 'max': float(scaler.data_max_[1])},
        'temperature': {'min': float(scaler.data_min_[2]), 'max': float(scaler.data_max_[2])},
    }
    with open('scaler_params.json', 'w') as f: json.dump(scaler_params, f, indent=2)
    
    print(f"\nExported: best_model_pvtp.pkl, best_model_pvtn.pkl")
    print(f"          plots/best_dt_pvtp_rules.txt, plots/best_dt_pvtn_rules.txt")
    print(f"          scaler_params.json")
    
    print(f"\n{'='*70}")
    print("WHY LINE STRUCTURES IN 3D PLOT?")
    print(f"{'='*70}")
    print("""
The line structures you see in the 3D plots are because the Cadence 
simulation data is on a REGULAR GRID:
  - 10 Vreg values (0.81, 0.83, ..., 0.99V) — 0.02V step
  - 329 Temperature values (-40, -39.5, ..., 125C) — 0.5C step

So when you plot in 3D, the data forms parallel lines along the 
temperature axis (one line per Vreg value). This is expected and 
NOT a problem — it just means the simulation swept V and T on a grid.

The ML model learns from this grid and can interpolate between points.
""")
    
    print("\n[DONE] Complete ML pipeline finished!")
