#!/usr/bin/env python3
"""
Generate Spectre .scs netlists for ALL PVT rows with ML-predicted trim codes.
Uses the existing validated netlist as a template.
Run on server: python3 generate_spectre_netlists.py
"""
import csv, os, sys

PREDICTIONS_CSV = "all_predictions.csv"
TEMPLATE_SCS = "template.scs"  # Copy your validated .scs file here
OUTPUT_DIR = "netlists"

# Corner -> model section mapping
CORNER_SECTIONS = {
    'FF': {'mos': 'ffmacro_mos_moscap', 'res': 'ff_res_bip_dio_disres'},
    'SS': {'mos': 'ssmacro_mos_moscap', 'res': 'ss_res_bip_dio_disres'},
    'TT': {'mos': 'ttmacro_mos_moscap', 'res': 'tt_res_bip_dio_disres'},
    'FS': {'mos': 'fsmacro_mos_moscap', 'res': 'fs_res_bip_dio_disres'},
    'SF': {'mos': 'sfmacro_mos_moscap', 'res': 'sf_res_bip_dio_disres'},
}

def make_param_line(row):
    """Build the Spectre parameters line from a prediction row."""
    pvtp = int(float(row['pvtp_int_pred']))
    pvtn = int(float(row['pvtn_int_pred']))
    vreg = float(row['vreg'])
    temp = float(row['temperature'])
    
    params = []
    for i in range(14):
        params.append(f"pvt{i}={(pvtp >> i) & 1 if i < 8 else 0}")
    for i in range(14):
        params.append(f"pvtn{i}={(pvtn >> i) & 1 if i < 8 else 0}")
    params.append(f"vreg={vreg:.4f}")
    params.append(f"tem={temp:.1f}")
    return "parameters " + " ".join(params)

def make_include_lines(corner):
    """Build the model include lines for the given corner."""
    base = '/data/cad/pdk_all/pdk_tsmc/pdk_tsmc_28/PDK/TSMC_new_iPDK/models/spectre/crn28hpcp_2d5_elk_v1d0_2p2_shrink0d9_embedded_usage.scs'
    sec = CORNER_SECTIONS[corner]
    return (f'include "{base}" section={sec["mos"]}\n'
            f'include "{base}" section={sec["res"]}')

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Read template (everything after line 11 in the validated .scs)
    with open(TEMPLATE_SCS, 'r') as f:
        lines = f.readlines()
    
    # Find where the subcircuit definitions start (after includes)
    body_start = 0
    for i, line in enumerate(lines):
        if line.strip().startswith('// Library name:'):
            body_start = i
            break
    template_body = ''.join(lines[body_start:])
    
    # Read predictions
    with open(PREDICTIONS_CSV, 'r') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    print(f"Generating {len(rows)} netlists...")
    
    for idx, row in enumerate(rows):
        corner = row['corner_label']
        filename = f"{corner}_row{idx:05d}.scs"
        filepath = os.path.join(OUTPUT_DIR, filename)
        
        header = (
            f"// Auto-generated netlist for PVT validation\n"
            f"// Row {idx}, Corner={corner}, vreg={row['vreg']}, temp={row['temperature']}\n"
            f"// Predicted pvtp={row['pvtp_int_pred']}, pvtn={row['pvtn_int_pred']}\n"
            f"simulator lang=spectre\n"
            f"global 0\n"
            f"{make_param_line(row)}\n"
            f"{make_include_lines(corner)}\n\n"
        )
        
        with open(filepath, 'w') as f:
            f.write(header)
            f.write(template_body)
        
        if idx % 1000 == 0:
            print(f"  {idx}/{len(rows)} done...")
    
    print(f"Done! Generated {len(rows)} netlists in {OUTPUT_DIR}/")

if __name__ == '__main__':
    main()
