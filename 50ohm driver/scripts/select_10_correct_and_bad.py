import os
import pandas as pd

csv_path = r'results/validation_sheets/HeldOut_TestSet_3177.csv'
df = pd.read_csv(csv_path)

# 10 Correct: 2 per corner with error == 0
correct_list = []
for c in ['TT', 'FF', 'SS', 'FS', 'SF']:
    c_good = df[(df['Corner'] == c) & (df['PVTP_Trim_Error_LSB'] == 0) & (df['PVTN_Trim_Error_LSB'] == 0)]
    # Pick 1 room temp/nominal voltage, 1 extreme
    correct_list.append(c_good.iloc[len(c_good)//4])
    correct_list.append(c_good.iloc[3*len(c_good)//4])

df_10_correct = pd.DataFrame(correct_list).reset_index(drop=True)
df_10_correct.to_csv(r'results/validation_sheets/test_10_correct.csv', index=False)

# 10 Bad: Top mismatches across corners
bad_list = []
for c in ['TT', 'FF', 'SS', 'FS', 'SF']:
    c_bad = df[(df['Corner'] == c) & ((df['PVTP_Trim_Error_LSB'] > 0) | (df['PVTN_Trim_Error_LSB'] > 0))]
    if len(c_bad) >= 2:
        # Sort by largest error
        c_bad_sorted = c_bad.sort_values(by=['PVTP_Trim_Error_LSB', 'PVTN_Trim_Error_LSB'], ascending=False)
        bad_list.append(c_bad_sorted.iloc[0])
        bad_list.append(c_bad_sorted.iloc[1])
    elif len(c_bad) == 1:
        bad_list.append(c_bad.iloc[0])

df_10_bad = pd.DataFrame(bad_list).reset_index(drop=True)
df_10_bad.to_csv(r'results/validation_sheets/test_10_bad.csv', index=False)

print("=== 10 CORRECT TEST CASES (TO VERIFY CADENCE ACCURACY FIRST) ===")
print(df_10_correct[['Corner', 'Voltage_V', 'Temp_C', 'Ground_Truth_PVTP_Int', 'Ground_Truth_PVTN_Int', 'Ground_Truth_Target_Pup_Ohm', 'Ground_Truth_Target_Pdn_Ohm']])

print("\n=== 10 BAD TEST CASES (WHERE MODEL DIFFERED FROM GOLDEN) ===")
print(df_10_bad[['Corner', 'Voltage_V', 'Temp_C', 'Ground_Truth_PVTP_Int', 'ML_Predicted_PVTP_Int', 'PVTP_Trim_Error_LSB', 'Ground_Truth_PVTN_Int', 'ML_Predicted_PVTN_Int', 'PVTN_Trim_Error_LSB', 'Ground_Truth_Target_Pup_Ohm', 'Ground_Truth_Target_Pdn_Ohm']])
