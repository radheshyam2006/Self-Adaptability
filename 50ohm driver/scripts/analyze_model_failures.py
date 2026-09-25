import os
import pandas as pd
import numpy as np

csv_path = r'results/validation_sheets/HeldOut_TestSet_3177.csv'
df = pd.read_csv(csv_path)

print("=== HELD-OUT TEST SET (3,177 points) ===")
p_exact = (df['PVTP_Trim_Error_LSB'] == 0).mean()
n_exact = (df['PVTN_Trim_Error_LSB'] == 0).mean()
both_exact = ((df['PVTP_Trim_Error_LSB'] == 0) & (df['PVTN_Trim_Error_LSB'] == 0)).mean()
within_1 = ((df['PVTP_Trim_Error_LSB'] <= 1) & (df['PVTN_Trim_Error_LSB'] <= 1)).mean()

print(f"PVTP Exact: {p_exact*100:.2f}% ({sum(df['PVTP_Trim_Error_LSB'] == 0)}/{len(df)})")
print(f"PVTN Exact: {n_exact*100:.2f}% ({sum(df['PVTN_Trim_Error_LSB'] == 0)}/{len(df)})")
print(f"Both Exact: {both_exact*100:.2f}% ({sum((df['PVTP_Trim_Error_LSB'] == 0) & (df['PVTN_Trim_Error_LSB'] == 0))}/{len(df)})")
print(f"Within +/- 1 LSB: {within_1*100:.2f}%\n")

print("=== MISMATCH BREAKDOWN BY CORNER ===")
for c in ['TT', 'FF', 'SS', 'FS', 'SF']:
    cdf = df[df['Corner'] == c]
    mismatches = cdf[(cdf['PVTP_Trim_Error_LSB'] > 0) | (cdf['PVTN_Trim_Error_LSB'] > 0)]
    print(f"{c}: {len(mismatches)} mismatches out of {len(cdf)} ({len(mismatches)/len(cdf)*100:.2f}% error)")

print("\n=== FAILURE DETAILS (WHAT FAILED & HOW MUCH) ===")
bad = df[(df['PVTP_Trim_Error_LSB'] > 0) | (df['PVTN_Trim_Error_LSB'] > 0)]
print(f"Total failed points in test set: {len(bad)}")
print("\nError magnitude distribution for PVTP:")
print(bad['PVTP_Trim_Error_LSB'].value_counts())
print("\nError magnitude distribution for PVTN:")
print(bad['PVTN_Trim_Error_LSB'].value_counts())

print("\nSample of failed cases:")
print(bad[['Corner', 'Voltage_V', 'Temp_C', 'Ground_Truth_PVTP_Int', 'ML_Predicted_PVTP_Int', 'PVTP_Trim_Error_LSB', 'Ground_Truth_PVTN_Int', 'ML_Predicted_PVTN_Int', 'PVTN_Trim_Error_LSB']].head(15))
