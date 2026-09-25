#!/usr/bin/env python3
"""
validate_pvt_cadence.py
=======================
Automated PVT Validation Workflow for 50Ohm TX Driver
Author: AI Assistant + Radheshyam

WHAT THIS SCRIPT DOES:
1. Reads PVT rows from the Excel file  (pmon_cmos_res, vreg, temperature)
2. Runs each row through the trained ML model → predicts pvtp[7:0], pvtn[7:0]
3. Converts those 8-bit integers into individual parameter bits (pvt0..pvt7)
4. Patches those bits + vreg + temperature into the Spectre netlist
5. Saves one modified .scs netlist file per row in sweep_output/cadence_validation/
6. Prints the exact SCP + shell commands to run them on the server
7. After running, you SCP back the results and run read_results.py to measure R

HOW THE NETLIST PARAMETERISATION WORKS (from tx_netlist.txt):
  Line 9-12 of the netlist:
     parameters pvt0=0 pvt1=0 pvt2=1 pvt3=1 pvt4=1 pvt5=0 pvt6=0 pvt7=0  ...
                vreg=0.99 tem=10

  Each pvtp<bit> pin is driven by a voltage source:
     V35 (pvtp<0> 0) vsource dc=vreg*pvt0 type=dc
  So: pvt0=1  → pvtp<0> = HIGH (= vreg volts)
      pvt0=0  → pvtp<0> = LOW  (= 0 V)

  Temperature: simulatorOptions options temp=tem
  So: tem=25  →  Spectre simulates at 25°C

HOW TO RUN:
  cd "50ohm driver"
  python scripts/validate_pvt_cadence.py

THEN ON THE SERVER:
  scp "sweep_output/cadence_validation/*.scs" user13@10.2.20.16:~/cadence_val_runs/
  ssh user13@10.2.20.16
  csh
  source /home/cadence-2023/cadence2.csh
  cd ~/cadence_val_runs
  foreach f (*.scs)
    spectre $f =: $f:r_psf/ +log $f:r.log
  end
"""

import os, re, pickle, sys, datetime
import pandas as pd
import numpy as np

# ─────────────────────────────────────────────────────────────────────────────
# SETTINGS — edit these to match your file paths
# ─────────────────────────────────────────────────────────────────────────────

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)

EXCEL_PATH = os.path.join(PROJECT_DIR, "data",
    "TSMC28nm_DRV_ML_MAR6_LookUP_Table_Mar20_ML Predictions.xlsx")

BASE_NETLIST_PATH = os.path.join(PROJECT_DIR, "netlist", "netlist.txt")

MODEL_PVTP_PATH = os.path.join(PROJECT_DIR, "ml", "best_model_pvtp_d14.pkl")

MODEL_PVTN_PATH = os.path.join(PROJECT_DIR, "ml", "best_model_pvtn_d14.pkl")

OUTPUT_DIR = os.path.join(PROJECT_DIR, "sweep_output", "cadence_validation")

# Which Excel sheets to use (one per corner)
SHEETS_TO_TEST = ["FF_vdd_temp", "SS_vdd_test", "TT_vdd_test"]

# How many rows to test per sheet  (None = all rows — will be slow!)
ROWS_PER_SHEET = 5

# Corner → Spectre model section mapping
# These section names appear in the `include ... section=XXX` line of the netlist
CORNER_PDK_SECTION = {
    "FF_vdd_temp": "ffmacro_mos_moscap",
    "SS_vdd_test": "ssmacro_mos_moscap",
    "TT_vdd_test": "fsmacro_mos_moscap",   # TT uses fsmacro per original netlist
    "FS_vdd_test": "fsmacro_mos_moscap",
    "SF_vdd_test": "sfmacro_mos_moscap",
}

# Server details
SERVER_HOST = "10.1.73.18"
SERVER_USER = "user13"
SERVER_DIR  = "~/cadence_val_runs"

# ─────────────────────────────────────────────────────────────────────────────
# HELPER FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def int_to_bits(value: int, nbits: int) -> list:
    """Convert integer to list of bits, index 0 = LSB (pvt0), index 7 = MSB."""
    return [(value >> i) & 1 for i in range(nbits)]


def encode_inputs(pmon_cmos_res, vreg_v, temp_c) -> list:
    """
    Pass raw sensor values directly to the model.
    The model was trained on: pmon_cmos_res (raw int), vreg (float V), temp (float degC)
    NO encoding/scaling is done - the tree thresholds are in the same units as the data.
    Confirmed by checking tree.threshold values: 0.92 (voltage), 338M (pmon count).
    """
    pmon = float(pmon_cmos_res)
    vreg = float(vreg_v)     # e.g. 0.81  (raw volts)
    temp = float(temp_c)     # e.g. -40.0 (raw degC)
    return [pmon, vreg, temp]


def make_param_line(pvtp_int: int, pvtn_int: int, vreg_v: float, temp_c: float) -> str:
    """
    Build the replacement 'parameters ...' line for the Spectre netlist.
    Bits 0-7 come from the 8-bit ML prediction.
    Bits 8-13 are always 0 (upper 6 bits unused in the 8-bit model).
    """
    p = int_to_bits(pvtp_int, 8)   # p[0]=pvt0 (LSB) ... p[7]=pvt7 (MSB)
    n = int_to_bits(pvtn_int, 8)
    line = (
        f"parameters "
        f"pvt0={p[0]} pvt1={p[1]} pvt2={p[2]} pvt3={p[3]} "
        f"pvt4={p[4]} pvt5={p[5]} pvt6={p[6]} pvt7={p[7]} "
        f"pvt8=0 pvt9=0 pvt10=0 pvt11=0 pvt12=0 pvt13=0 "
        f"pvtn0={n[0]} pvtn1={n[1]} pvtn2={n[2]} pvtn3={n[3]} "
        f"pvtn4={n[4]} pvtn5={n[5]} pvtn6={n[6]} pvtn7={n[7]} "
        f"pvtn8=0 pvtn9=0 pvtn10=0 pvtn11=0 pvtn12=0 pvtn13=0 "
        f"vreg={vreg_v:.4f} tem={temp_c:.1f}"
    )
    return line


def patch_netlist(base: str, pvtp_int: int, pvtn_int: int,
                  vreg_v: float, temp_c: float, corner: str) -> str:
    """
    Patch the base Spectre netlist with new parameter values for one PVT point.
    Returns the modified netlist as a string.
    """
    netlist = base

    # 1. Replace the ENTIRE parameters block including all continuation lines.
    #    In Spectre netlists, continuation lines ALWAYS start with whitespace.
    #    The original block is 4 lines (line 9 + lines 10-12 indented with spaces).
    #    Pattern: 'parameters ...' then zero-or-more lines starting with whitespace.
    new_param = make_param_line(pvtp_int, pvtn_int, vreg_v, temp_c)
    netlist = re.sub(
        r"^parameters\b[^\n]*(?:\n[ \t]+[^\n]*)*",
        new_param,
        netlist,
        count=1,
        flags=re.MULTILINE,
    )

    # 2. Replace ONLY the mos_moscap section (controls transistor corner).
    #    Do NOT touch the res_bip_dio_disres section — ff_res_bip_dio_disres
    #    is valid for all corners for passive devices and must stay unchanged.
    section = CORNER_PDK_SECTION.get(corner, "fsmacro_mos_moscap")
    netlist = re.sub(
        r"section=\w+macro_mos_moscap",
        f"section={section}",
        netlist,
    )

    # 3. Temperature is already handled via the 'tem' parameter above.
    #    simulatorOptions uses temp=tem which reads from parameters block.


    return netlist


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("=" * 68)
    print("   ML-Based PVT Validation -- 50ohm TX Driver")
    print(f"   {datetime.datetime.now().strftime('%Y-%m-%d  %H:%M:%S')}")
    print("=" * 68)

    # ── Load models ───────────────────────────────────────────────────────────
    print("\n[1/5]  Loading ML models …")
    with open(MODEL_PVTP_PATH, "rb") as f:
        model_pvtp = pickle.load(f)
    with open(MODEL_PVTN_PATH, "rb") as f:
        model_pvtn = pickle.load(f)
    print(f"       pvtp model  depth={model_pvtp.get_depth()}")
    print(f"       pvtn model  depth={model_pvtn.get_depth()}")

    # ── Load Excel ─────────────────────────────────────────────────────────────
    print("\n[2/5]  Reading Excel data …")
    xl  = pd.ExcelFile(EXCEL_PATH)
    frames = []
    for sheet in SHEETS_TO_TEST:
        if sheet not in xl.sheet_names:
            print(f"       ⚠  Sheet '{sheet}' not found, skipped.")
            continue
        df = xl.parse(sheet)
        # Normalise column names (headers can have \n line breaks)
        col_map = {}
        for c in df.columns:
            key = str(c).lower().replace("\n", " ").strip()
            if "pmon_cmos_res" in key:              col_map[c] = "pmon_cmos_res"
            elif "vreg" in key:                     col_map[c] = "vreg"
            elif "temperature" in key:              col_map[c] = "temperature"
            elif "pvtp" in key and "ml" in key:     col_map[c] = "pvtp_str"
            elif "pvtn" in key and "ml" in key:     col_map[c] = "pvtn_str"
            elif "pull_up_res" in key and "new" in key: col_map[c] = "R_pu_cad"
            elif "pull_dn_res" in key and "new" in key: col_map[c] = "R_pd_cad"
        df = df.rename(columns=col_map)
        df["corner"] = sheet
        if ROWS_PER_SHEET:
            df = df.head(ROWS_PER_SHEET)
        frames.append(df)
        print(f"       Sheet '{sheet}':  {len(df)} rows")
    data = pd.concat(frames, ignore_index=True)
    print(f"       Total: {len(data)} rows")

    # ── Predict ────────────────────────────────────────────────────────────────
    print("\n[3/5]  Running ML predictions …")
    X = np.array([
        encode_inputs(r["pmon_cmos_res"], r["vreg"], r["temperature"])
        for _, r in data.iterrows()
    ])
    data["pvtp_pred"] = model_pvtp.predict(X).astype(int)
    data["pvtn_pred"] = model_pvtn.predict(X).astype(int)
    print(f"       pvtp  min={data['pvtp_pred'].min()}  max={data['pvtp_pred'].max()}")
    print(f"       pvtn  min={data['pvtn_pred'].min()}  max={data['pvtn_pred'].max()}")

    # ── Load base netlist ──────────────────────────────────────────────────────
    print("\n[4/5]  Generating Spectre netlists …")
    with open(BASE_NETLIST_PATH, "r") as f:
        base_netlist = f.read()

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    report = []
    for idx, row in data.iterrows():
        pvtp_int = int(row["pvtp_pred"])
        pvtn_int = int(row["pvtn_pred"])
        vreg_v   = float(row["vreg"])
        temp_c   = float(row["temperature"])
        corner   = row["corner"]

        run_id  = f"{corner}_row{idx:04d}_Tp{pvtp_int}_Tn{pvtn_int}"
        scs_path = os.path.join(OUTPUT_DIR, f"{run_id}.scs")

        patched = patch_netlist(base_netlist, pvtp_int, pvtn_int,
                                vreg_v, temp_c, corner)
        with open(scs_path, "w") as f:
            f.write(patched)

        # Build bit strings for the report (MSB first for readability)
        p_bits = "".join(str(b) for b in reversed(int_to_bits(pvtp_int, 8)))
        n_bits = "".join(str(b) for b in reversed(int_to_bits(pvtn_int, 8)))

        report.append({
            "run_id":       run_id,
            "corner":       corner,
            "pmon":         row.get("pmon_cmos_res", ""),
            "vreg":         vreg_v,
            "temp_C":       temp_c,
            "pvtp_int":     pvtp_int,
            "pvtp_bits":    p_bits,
            "pvtn_int":     pvtn_int,
            "pvtn_bits":    n_bits,
            "R_pu_cadence": row.get("R_pu_cad", "N/A"),  # ground truth from Excel
            "R_pd_cadence": row.get("R_pd_cad", "N/A"),
            "netlist":      os.path.basename(scs_path),
        })

    print(f"       OK  {len(report)} netlist files written to:")
    print(f"          {OUTPUT_DIR}")

    # -- Save report ------------------------------------------------------------
    print("\n[5/5]  Saving CSV report ...")
    report_df  = pd.DataFrame(report)
    report_path = os.path.join(OUTPUT_DIR, "validation_report.csv")
    report_df.to_csv(report_path, index=False)
    print(f"       OK  {report_path}")

    # -- Print preview table ----------------------------------------------------
    print("\n" + "=" * 68)
    print("PREDICTION TABLE (pvtp/pvtn bits = what gets injected into Cadence):")
    print("=" * 68)
    preview = report_df[["corner", "vreg", "temp_C",
                          "pvtp_int", "pvtp_bits",
                          "pvtn_int", "pvtn_bits",
                          "R_pu_cadence"]]
    print(preview.to_string(index=False))

    # ── Print server commands ──────────────────────────────────────────────────
    print("\n" + "=" * 68)
    print("NOW RUN THESE COMMANDS:")
    print("=" * 68)
    print(f"""
1.  Copy netlists to server  (run from Windows PowerShell):
    scp "{OUTPUT_DIR}\\*.scs" {SERVER_USER}@{SERVER_HOST}:{SERVER_DIR}/

2.  SSH into the server:
    ssh {SERVER_USER}@{SERVER_HOST}

3.  On the server (csh shell):
    csh
    source /home/cadence-2023/cadence2.csh
    mkdir -p {SERVER_DIR}
    cd {SERVER_DIR}

    # Run ALL netlists in one loop:
    # NOTE: standalone Spectre uses  -raw <dir>  NOT  =:  (=: is irun/AMS only)
    foreach f (*.scs)
      echo "=== $f ==="
      mkdir -p ${{f:r}}_psf
      spectre $f -raw ${{f:r}}_psf +log ${{f:r}}.log
    end

4.  Collect the resistance from each .log file (quick check):
    grep -i "spectre completed" *.log
    grep -i "error" *.log

5.  SCP logs back to Windows:
    exit   (leave SSH)
    scp "{SERVER_USER}@{SERVER_HOST}:{SERVER_DIR}/*.log" "{OUTPUT_DIR}\\"
""")

    # ── Generate a results reader ──────────────────────────────────────────────
    reader_script = os.path.join(OUTPUT_DIR, "read_results.py")
    _write_reader_script(reader_script, OUTPUT_DIR)
    print(f"Also generated: {reader_script}")
    print("Run that after collecting .log files to see R vs 50ohm.")
    print("\n>>> DONE. <<<")


def _write_reader_script(path: str, log_dir: str):
    """Write a small helper script that parses Spectre .log files for resistance."""
    code = f'''#!/usr/bin/env python3
"""
read_results.py
Reads Spectre .log files from cadence_validation/ and extracts
pull-up and pull-down resistance values.
Run AFTER you have SCP'd the .log files back from the server.
"""
import os, re, glob
import pandas as pd

LOG_DIR = r"{log_dir}"

records = []
for log_file in sorted(glob.glob(os.path.join(LOG_DIR, "*.log"))):
    basename = os.path.basename(log_file)
    text = open(log_file).read()

    # Spectre DC oppoint writes V(outp), V(vdd), I(xdrv_p:out) to the log
    # Typical format: "outp  voltage =  X.XXX"
    v_outp = re.search(r"outp.*?voltage\\s*=\\s*([\\d\\.eE+-]+)", text)
    v_vdd  = re.search(r"vdd.*?voltage\\s*=\\s*([\\d\\.eE+-]+)", text)
    i_xdrv = re.search(r"xdrv_p:62.*?current\\s*=\\s*([\\d\\.eE+-]+)", text)

    R_pu = "N/A"
    if v_outp and v_vdd and i_xdrv:
        try:
            vout = float(v_outp.group(1))
            vvdd = float(v_vdd.group(1))
            curr = float(i_xdrv.group(1))
            if curr != 0:
                R_pu = f"{{(vvdd - vout) / abs(curr):.3f}}"
        except:
            pass

    records.append({{"file": basename, "R_pu_ohm": R_pu}})

df = pd.DataFrame(records)
print(df.to_string(index=False))
out = os.path.join(LOG_DIR, "resistance_results.csv")
df.to_csv(out, index=False)
print(f"\\nSaved: {{out}}")
'''
    with open(path, "w") as f:
        f.write(code)


if __name__ == "__main__":
    main()
