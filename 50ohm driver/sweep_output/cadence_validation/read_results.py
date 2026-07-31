#!/usr/bin/env python3
"""
read_results.py
Reads Spectre .log files from cadence_validation/ and extracts
pull-up and pull-down resistance values.
Run AFTER you have SCP'd the .log files back from the server.
"""
import os, re, glob
import pandas as pd

LOG_DIR = r"c:\Users\radhe\OneDrive\Documents\AI_Self-adaptive_Chip\Self Adaptability\50ohm driver\sweep_output\cadence_validation"

records = []
for log_file in sorted(glob.glob(os.path.join(LOG_DIR, "*.log"))):
    basename = os.path.basename(log_file)
    text = open(log_file).read()

    # Spectre DC oppoint writes V(outp), V(vdd), I(xdrv_p:out) to the log
    # Typical format: "outp  voltage =  X.XXX"
    v_outp = re.search(r"outp.*?voltage\s*=\s*([\d\.eE+-]+)", text)
    v_vdd  = re.search(r"vdd.*?voltage\s*=\s*([\d\.eE+-]+)", text)
    i_xdrv = re.search(r"xdrv_p:62.*?current\s*=\s*([\d\.eE+-]+)", text)

    R_pu = "N/A"
    if v_outp and v_vdd and i_xdrv:
        try:
            vout = float(v_outp.group(1))
            vvdd = float(v_vdd.group(1))
            curr = float(i_xdrv.group(1))
            if curr != 0:
                R_pu = f"{(vvdd - vout) / abs(curr):.3f}"
        except:
            pass

    records.append({"file": basename, "R_pu_ohm": R_pu})

df = pd.DataFrame(records)
print(df.to_string(index=False))
out = os.path.join(LOG_DIR, "resistance_results.csv")
df.to_csv(out, index=False)
print(f"\nSaved: {out}")
