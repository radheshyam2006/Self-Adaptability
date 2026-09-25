import os
import pickle
import pandas as pd
import numpy as np

project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
excel_path = os.path.join(project_dir, "data", "TSMC28nm_DRV_ML_MAR6_LookUP_Table_Mar20_ML Predictions.xlsx")

model_p_path = os.path.join(project_dir, "ASIC_Submission", "model_pvtp.pkl")
model_n_path = os.path.join(project_dir, "ASIC_Submission", "model_pvtn.pkl")

with open(model_p_path, 'rb') as f:
    model_p = pickle.load(f)
with open(model_n_path, 'rb') as f:
    model_n = pickle.load(f)

xl = pd.ExcelFile(excel_path)
df = xl.parse("TT_vdd_test")

p_col = 'ML data up driver\npvtp<5:0>' if 'ML data up driver\npvtp<5:0>' in df.columns else 'ML data up driver\npvtp<7:0>'
n_col = 'ML data DN driver\npvtn<5:0>' if 'ML data DN driver\npvtn<5:0>' in df.columns else 'ML data DN driver\npvtn<7:0>'

def clean_int(val):
    if pd.isna(val) or str(val).strip().lower() in ['na', 'nan']: return None
    try: return int(str(val).replace('-','').strip().zfill(8), 2)
    except: return None

df['yp'] = df[p_col].apply(clean_int)
df['yn'] = df[n_col].apply(clean_int)
df = df.dropna(subset=['yp', 'yn', 'pmon_cmos_res', 'vreg', 'temperature'])

y_p = df['yp'].values.astype(int)
y_n = df['yn'].values.astype(int)

# Test 1: Quantized inputs
X_quant = np.column_stack([
    np.round(df['pmon_cmos_res'].values),
    np.round((df['vreg'].values - 0.80) * 100),
    np.round((df['temperature'].values + 40.0) * 4)
])
pred_p_quant = model_p.predict(X_quant)
pred_n_quant = model_n.predict(X_quant)

# Test 2: Raw inputs
X_raw = np.column_stack([
    df['pmon_cmos_res'].values,
    df['vreg'].values,
    df['temperature'].values
])
try:
    pred_p_raw = model_p.predict(X_raw)
    acc_raw_p = np.mean(pred_p_raw == y_p)
except Exception as e:
    acc_raw_p = str(e)

acc_quant_p = np.mean(pred_p_quant == y_p)
acc_quant_n = np.mean(pred_n_quant == y_n)

print(f"Quantized Accuracy: PVTP = {acc_quant_p*100:.2f}%, PVTN = {acc_quant_n*100:.2f}%")
print(f"Raw Accuracy PVTP: {acc_raw_p}")
