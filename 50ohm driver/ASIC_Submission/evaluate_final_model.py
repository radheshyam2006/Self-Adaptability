import pandas as pd
import numpy as np
import pickle
import os
import matplotlib.pyplot as plt

script_dir = os.path.dirname(os.path.abspath(__file__))
EXCEL_FILE = os.path.join(script_dir, "data.xlsx")
OUTPUT_DIR = os.path.join(script_dir, "plots")

CORNER_SHEETS = {'FF': 'FF_vdd_temp', 'SS': 'SS_vdd_test', 'TT': 'TT_vdd_test', 'FS': 'FS_vdd_test', 'SF': 'SF_vdd_test'}
COL_NAMES = ['Corner', 'vreg', 'temperature', 'PULL_UP_RES', 'PULL_DN_RES', 'pmon_cmos_res', 'pmon_cmos', 'pvtp_raw', 'pvtn_raw', 'PULL_UP_RES_new', 'PULL_DN_RES_new']

def pad8(val):
    if pd.isna(val) or str(val).strip().lower() == 'na': return None
    return str(val).replace('-','').strip().zfill(8)

def to_int(val):
    if val is None or pd.isna(val): return None
    try: return int(val, 2)
    except: return None

def encode_vreg(vreg_float):
    if pd.isna(vreg_float): return np.nan
    return int(round((vreg_float - 0.80) * 100))

def encode_temp(temp_float):
    if pd.isna(temp_float): return np.nan
    return int(round((temp_float + 40.0) * 4))

def encode_pmon(pmon_float):
    if pd.isna(pmon_float): return np.nan
    return int(round(pmon_float))

def load_data():
    all_data = []
    for c, s in CORNER_SHEETS.items():
        df = pd.read_excel(EXCEL_FILE, sheet_name=s, header=0).iloc[:,:11]
        df.columns = COL_NAMES
        for col in ['vreg','temperature','pmon_cmos_res']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Apply Hardware Quantization
        df['vreg'] = df['vreg'].apply(encode_vreg)
        df['temperature'] = df['temperature'].apply(encode_temp)
        df['pmon_cmos_res'] = df['pmon_cmos_res'].apply(encode_pmon)
        
        df['corner_label'] = c
        df['pvtp_int'] = df['pvtp_raw'].apply(pad8).apply(to_int)
        df['pvtn_int'] = df['pvtn_raw'].apply(pad8).apply(to_int)
        all_data.append(df)
    
    return pd.concat(all_data, ignore_index=True).dropna(subset=['pvtp_int','pvtn_int','pmon_cmos_res'])

def load_model(path):
    with open(path, 'rb') as f:
        return pickle.load(f)

if __name__ == '__main__':
    print(f"Loading data from {EXCEL_FILE}...")
    df = load_data()
    total_loaded = len(df)
    print(f"Loaded {total_loaded} rows.")

    X = df[['pmon_cmos_res', 'vreg', 'temperature']].values
    y_p = df['pvtp_int'].values.astype(int)
    y_n = df['pvtn_int'].values.astype(int)

    model_p = load_model(os.path.join(script_dir, 'model_pvtp.pkl'))
    model_n = load_model(os.path.join(script_dir, 'model_pvtn.pkl'))

    pred_p = model_p.predict(X)
    pred_n = model_n.predict(X)

    diff_p = np.abs(pred_p - y_p)
    diff_n = np.abs(pred_n - y_n)

    def print_stats(name, diffs):
        print(f"\n--- {name} Prediction Stats ---")
        exact_matches = np.sum(diffs == 0)
        print(f"Predicting well (Exact Match): {exact_matches} / {total_loaded} ({exact_matches/total_loaded*100:.2f}%)")
        
        # Calculate how many are off by 1, 2, etc. (ignoring 0)
        unique_diffs, counts = np.unique(diffs, return_counts=True)
        for offset, count in zip(unique_diffs, counts):
            if offset == 0:
                continue
            print(f"Offset {offset} number: {count} rows")

    print_stats("PVTP (Pull-up)", diff_p)
    print_stats("PVTN (Pull-down)", diff_n)
    
    # Save a pair of simple actual vs predicted plots
    plt.figure(figsize=(10, 5))
    plt.subplot(1, 2, 1)
    plt.scatter(y_p, pred_p, alpha=0.1, color='red', s=5) # Transparency handles density 
    plt.plot([y_p.min(), y_p.max()], [y_p.min(), y_p.max()], 'k--', label='Perfect Match')
    plt.xlabel('Actual pvtp_int')
    plt.ylabel('Predicted pvtp_int')
    plt.title('PVTP: Actual vs Predicted')
    plt.legend()
    
    plt.subplot(1, 2, 2)
    plt.scatter(y_n, pred_n, alpha=0.1, color='blue', s=5)
    plt.plot([y_n.min(), y_n.max()], [y_n.min(), y_n.max()], 'k--', label='Perfect Match')
    plt.xlabel('Actual pvtn_int')
    plt.ylabel('Predicted pvtn_int')
    plt.title('PVTN: Actual vs Predicted')
    plt.legend()
    
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, 'actual_vs_predicted.png'), dpi=150)
    print(f"\nSaved plot to {OUTPUT_DIR}\\actual_vs_predicted.png")
