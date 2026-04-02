import pandas as pd
import numpy as np
import pickle
import os
import matplotlib.pyplot as plt

script_dir = os.path.dirname(os.path.abspath(__file__))
EXCEL_FILE = os.path.join(script_dir, "data.xlsx")
OUTPUT_DIR = os.path.join(script_dir, "plots")
os.makedirs(OUTPUT_DIR, exist_ok=True)

SHEET_MAP = {'TT': 'TT-VDD_TEMP', 'SS': 'SS_VDD_TEMP', 'FF': 'FF_VDD_TEMP'}

def parse_trim_bits(val):
    if pd.isna(val): return np.nan
    s = str(val).replace('-', '').replace(' ', '')
    try: return int(s, 2)
    except:
        try: return int(s)
        except: return np.nan

def load_data():
    frames = []
    for corner_name, sheet_name in SHEET_MAP.items():
        df = pd.read_excel(EXCEL_FILE, sheet_name=sheet_name)
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
    X = pd.DataFrame()
    X['pmon'] = data['PMON_RING_CMOS_res'].astype(int)
    X['vdd_enc'] = ((data['vdd'] - 0.80) * 100).round().astype(int)
    X['temp_enc'] = ((data['temperature'] + 40.0) * 2).round().astype(int)
    return X.values

def load_model(path):
    with open(path, 'rb') as f:
        return pickle.load(f)

if __name__ == '__main__':
    print(f"Loading data from {EXCEL_FILE}...")
    df = load_data()
    total_loaded = len(df)
    print(f"Loaded {total_loaded} valid rows.")

    X = encode_features(df)
    y_p = df['pctrl_int'].values
    y_n = df['nctrl_int'].values

    model_p = load_model(os.path.join(script_dir, 'model_pctrl.pkl'))
    model_n = load_model(os.path.join(script_dir, 'model_nctrl.pkl'))

    pred_p = model_p.predict(X)
    pred_n = model_n.predict(X)

    diff_p = np.abs(pred_p - y_p)
    diff_n = np.abs(pred_n - y_n)

    def print_stats(name, diffs):
        print(f"\n--- {name} Prediction Stats ---")
        exact_matches = np.sum(diffs == 0)
        print(f"Predicting well (Exact Match): {exact_matches} / {total_loaded} ({exact_matches/total_loaded*100:.2f}%)")
        
        unique_diffs, counts = np.unique(diffs, return_counts=True)
        for offset, count in zip(unique_diffs, counts):
            if offset == 0: continue
            print(f"Offset {offset} number: {count} rows")

    print_stats("PCTRL (Pull-up)", diff_p)
    print_stats("NCTRL (Pull-down)", diff_n)
    
    plt.figure(figsize=(10, 5))
    plt.subplot(1, 2, 1)
    plt.scatter(y_p, pred_p, alpha=0.1, color='red', s=5)
    plt.plot([y_p.min(), y_p.max()], [y_p.min(), y_p.max()], 'k--', label='Perfect Match')
    plt.xlabel('Actual pctrl_int'); plt.ylabel('Predicted pctrl_int')
    plt.title('PCTRL: Actual vs Predicted'); plt.legend()
    
    plt.subplot(1, 2, 2)
    plt.scatter(y_n, pred_n, alpha=0.1, color='blue', s=5)
    plt.plot([y_n.min(), y_n.max()], [y_n.min(), y_n.max()], 'k--', label='Perfect Match')
    plt.xlabel('Actual nctrl_int'); plt.ylabel('Predicted nctrl_int')
    plt.title('NCTRL: Actual vs Predicted'); plt.legend()
    
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, 'actual_vs_predicted.png'), dpi=150)
    print(f"\nSaved plot to {OUTPUT_DIR}\\actual_vs_predicted.png")
