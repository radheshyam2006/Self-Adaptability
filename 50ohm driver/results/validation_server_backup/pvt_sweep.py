"""
PVT Corner Sweep - Generate dummy_sensors.v files + Post-process results
=========================================================================
Phase 1: Generates one dummy_sensors.v per corner + a shell script for the server
Phase 2: After simulation, reads results and creates final verification Excel

Usage:
  python scripts/pvt_sweep.py generate      # Phase 1: generate all files
  python scripts/pvt_sweep.py results       # Phase 2: compile results into Excel
"""

import sys, os, json, math
import pandas as pd
import openpyxl

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
EXCEL_FILE = os.path.join(PROJECT_DIR, "data",
    "TSMC28nm_DRV_ML_MAR6_LookUP_Table_Mar20_ML Predictions.xlsx")
OUTPUT_DIR = os.path.join(PROJECT_DIR, "sweep_output")

# Server paths
SERVER_USER = "user13"
SERVER_HOST = "10.1.73.18"
SERVER_RTL_IMPORT = "/data/proj/Low_power_design/tech_tsmc128nm/work/users/user13/rtl_import"
SERVER_SIM_BASE = "/data/proj/Low_power_design/tech_tsmc128nm/work/users/user13/simulation/tsmc28_tx_tb/ams/maestro/results/maestro"

# ============================================================
# Sensor encoding (must match RTL dt_trim_predictor inputs)
# ============================================================
def encode_vreg(vreg_float):
    """vreg float to 5-bit: round((V - 0.80) * 100), clamp to [0, 31]"""
    val = int(round((vreg_float - 0.80) * 100))
    return max(0, min(31, val))

def encode_temp(temp_float):
    """temperature float to 10-bit: round((C + 40) * 4), clamp to [0, 1023]"""
    val = int(round((temp_float + 40.0) * 4))
    return max(0, min(1023, val))

def encode_pmon(pmon_float):
    """pmon_cmos_res to 29-bit: raw integer, clamp to [0, 2^29 - 1]"""
    val = int(round(pmon_float))
    return max(0, min((1 << 29) - 1, val))


def generate_dummy_sensors(vreg, temp, pmon, corner_name):
    """Generate a dummy_sensors.v file for a specific PVT corner."""
    vreg_enc = encode_vreg(vreg)
    temp_enc = encode_temp(temp)
    pmon_enc = encode_pmon(pmon)

    return f"""module dummy_sensors (
    output wire [28:0] pmon_out,
    output wire [4:0]  vreg_out,
    output wire [9:0]  temp_out,
    output reg         clk,
    output reg         rst_n,
    output reg         start
);
    // ---- PVT CORNER: {corner_name} ----
    // vreg = {vreg}V  => round(({vreg} - 0.80) * 100) = {vreg_enc}
    // temp = {temp}C  => round(({temp} + 40) * 4)      = {temp_enc}
    // pmon = {pmon}   => (raw integer)                  = {pmon_enc}
    assign vreg_out = 5'd{vreg_enc};
    assign temp_out = 10'd{temp_enc};
    assign pmon_out = 29'd{pmon_enc};

    initial begin
        clk = 0;
        rst_n = 0;
        start = 0;
        #100 rst_n = 1;
        #50  start = 1;
        #20  start = 0;
    end
    always #5 clk = ~clk; // 100MHz clock
endmodule
"""


def load_test_cases(corner_filter=None):
    """Load test cases from the Test_case_Mar20 Excel sheet."""
    wb = openpyxl.load_workbook(EXCEL_FILE)
    ws = wb['Test_case_Mar20']

    cases = []
    for r in range(2, ws.max_row + 1):
        name = ws.cell(r, 1).value
        if name is None:
            continue

        prefix = name.split('_')[0].lower()
        if corner_filter and prefix not in corner_filter:
            continue

        cases.append({
            'name': name,
            'corner': prefix,
            'vreg': float(ws.cell(r, 2).value),
            'temperature': float(ws.cell(r, 3).value),
            'pull_up_res': ws.cell(r, 4).value,
            'pull_dn_res': ws.cell(r, 5).value,
            'pmon_cmos_res': float(ws.cell(r, 6).value),
            'pmon_cmos': float(ws.cell(r, 7).value) if ws.cell(r, 7).value else None,
            'pvtp_raw': ws.cell(r, 8).value,
            'pvtn_raw': ws.cell(r, 9).value,
            'pull_up_res_new': ws.cell(r, 10).value,
            'pull_dn_res_new': ws.cell(r, 11).value,
        })

    return cases


def phase1_generate():
    """Generate all dummy_sensors.v files and helper scripts."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Load TT test cases only
    cases = load_test_cases(corner_filter=['tt'])
    print(f"Found {len(cases)} TT test cases\n")

    # Generate dummy_sensors files
    for i, case in enumerate(cases):
        filename = f"dummy_sensors_{i+1}.v"
        filepath = os.path.join(OUTPUT_DIR, filename)
        content = generate_dummy_sensors(
            case['vreg'], case['temperature'],
            case['pmon_cmos_res'], case['name']
        )
        with open(filepath, 'w', newline='\n') as f:
            f.write(content)
        print(f"  [{i+1}] {filename:30s} vreg={case['vreg']}V temp={case['temperature']}C")

    # Generate the server-side shell script
    shell_script = generate_server_script(cases)
    shell_path = os.path.join(OUTPUT_DIR, "run_sweep.sh")
    with open(shell_path, 'w', newline='\n') as f:
        f.write(shell_script)

    # Generate the CIW SKILL commands cheat sheet
    cheat_sheet = generate_cheat_sheet(cases)
    cheat_path = os.path.join(OUTPUT_DIR, "CHEAT_SHEET.txt")
    with open(cheat_path, 'w') as f:
        f.write(cheat_sheet)

    # Save case info for Phase 2
    info_path = os.path.join(OUTPUT_DIR, "corners_info.json")
    with open(info_path, 'w') as f:
        json.dump(cases, f, indent=2)

    print(f"\n{'='*70}")
    print(f"Generated {len(cases)} files in: {OUTPUT_DIR}")
    print(f"\nNEXT STEPS:")
    print(f"  1. Upload ALL files to server:")
    print(f"     scp sweep_output/dummy_sensors_*.v {SERVER_USER}@{SERVER_HOST}:{SERVER_RTL_IMPORT}/")
    print(f"     scp sweep_output/run_sweep.sh {SERVER_USER}@{SERVER_HOST}:~/")
    print(f"")
    print(f"  2. Option A (Automated): On server, run:")
    print(f"     chmod +x ~/run_sweep.sh && ~/run_sweep.sh")
    print(f"")
    print(f"  3. Option B (Manual): Follow CHEAT_SHEET.txt")
    print(f"     Open: {cheat_path}")
    print(f"")
    print(f"  4. After all simulations complete, run:")
    print(f"     python scripts/pvt_sweep.py results")
    print(f"{'='*70}")


def generate_server_script(cases):
    """Generate a bash script for the server that runs all corners."""
    lines = [
        "#!/bin/bash",
        "# Auto-generated PVT corner sweep script",
        "# Run this on the IIIT server after uploading all dummy_sensors_*.v files",
        "",
        f'RTL_IMPORT="{SERVER_RTL_IMPORT}"',
        'RESULTS_FILE="$HOME/sweep_results.csv"',
        "",
        '# CSV header',
        'echo "corner_idx,corner_name,vreg,temperature,pmon,status" > $RESULTS_FILE',
        "",
    ]

    for i, case in enumerate(cases):
        lines.extend([
            f'echo ""',
            f'echo "================================================================"',
            f'echo "  Corner {i+1}/{len(cases)}: {case["name"]}"',
            f'echo "  vreg={case["vreg"]}V, temp={case["temperature"]}C"',
            f'echo "================================================================"',
            f'',
            f'# Copy the dummy_sensors for this corner',
            f'cp $RTL_IMPORT/dummy_sensors_{i+1}.v $RTL_IMPORT/dummy_sensors.v',
            f'echo "Copied dummy_sensors_{i+1}.v -> dummy_sensors.v"',
            f'',
            f'# Record that this corner is ready',
            f'echo "{i+1},{case["name"]},{case["vreg"]},{case["temperature"]},{case["pmon_cmos_res"]},ready" >> $RESULTS_FILE',
            f'',
            f'echo ">>> NOW: In Maestro CIW, type: desVar(\\"vreg\\" {case["vreg"]})"',
            f'echo ">>> THEN: Click Recreate Netlist -> Run"',
            f'echo ">>> Press ENTER here when simulation is done..."',
            f'read -p ""',
            f'',
        ])

    lines.extend([
        'echo ""',
        'echo "All corners complete! Results logged to $RESULTS_FILE"',
        'echo "Now record your pup/pdown values in the results file."',
    ])

    return '\n'.join(lines)


def generate_cheat_sheet(cases):
    """Generate a human-readable cheat sheet for manual runs."""
    lines = [
        "=" * 70,
        "  PVT CORNER SWEEP - CHEAT SHEET",
        "  For each corner: SCP file -> Set vreg in CIW -> Run in Maestro",
        "=" * 70,
        "",
    ]

    for i, case in enumerate(cases):
        vreg_enc = encode_vreg(case['vreg'])
        temp_enc = encode_temp(case['temperature'])
        pmon_enc = encode_pmon(case['pmon_cmos_res'])

        lines.extend([
            f"--- Corner {i+1}/{len(cases)}: {case['name']} ---",
            f"  vreg = {case['vreg']}V (encoded: {vreg_enc})",
            f"  temp = {case['temperature']}C (encoded: {temp_enc})",
            f"  pmon = {case['pmon_cmos_res']} (encoded: {pmon_enc})",
            f"  Expected pvtp: {case['pvtp_raw']}",
            f"  Expected pvtn: {case['pvtn_raw']}",
            f"  Excel pull_up_res_new: {case['pull_up_res_new']}",
            f"  Excel pull_dn_res_new: {case['pull_dn_res_new']}",
            f"",
            f"  Step 1 (Windows PowerShell):",
            f'    scp "sweep_output\\dummy_sensors_{i+1}.v" {SERVER_USER}@{SERVER_HOST}:{SERVER_RTL_IMPORT}/dummy_sensors.v',
            f"",
            f"  Step 2 (Cadence CIW — type at the bottom command line):",
            f'    desVar("vreg" {case["vreg"]})',
            f"",
            f"  Step 3 (Maestro):",
            f"    Click: Simulation -> Netlist -> Recreate",
            f"    Click: Green Run button",
            f"",
            f"  Step 4 (Record results):",
            f"    pup_main   = _____ ohm",
            f"    pdown_main = _____ ohm",
            f"    pup_1090   = _____ ohm   (if available)",
            f"    pdown_1090 = _____ ohm   (if available)",
            f"    pup_3070   = _____ ohm   (if available)",
            f"    pdown_3070 = _____ ohm   (if available)",
            f"",
            "=" * 70,
            "",
        ])

    return '\n'.join(lines)


def phase2_results():
    """Compile simulation results into a final Excel file."""
    info_path = os.path.join(OUTPUT_DIR, "corners_info.json")
    if not os.path.exists(info_path):
        print("ERROR: Run 'python scripts/pvt_sweep.py generate' first!")
        return

    with open(info_path) as f:
        cases = json.load(f)

    print("Enter simulation results for each corner:")
    print("(Type the resistance values from Maestro Outputs tab)")
    print("(Press Enter to skip a driver if not available)")
    print()

    results = []
    for i, case in enumerate(cases):
        print(f"--- Corner {i+1}: {case['name']} (vreg={case['vreg']}V, temp={case['temperature']}C) ---")

        res = dict(case)
        for driver in ['main', '1090', '3070']:
            pup = input(f"  pup_{driver} (ohm): ").strip()
            pdn = input(f"  pdown_{driver} (ohm): ").strip()
            res[f'pup_{driver}'] = float(pup) if pup else None
            res[f'pdown_{driver}'] = float(pdn) if pdn else None

        results.append(res)
        print()

    # Create final Excel
    df = pd.DataFrame(results)

    # Calculate errors vs 50 ohm target
    for driver in ['main', '1090', '3070']:
        pup_col = f'pup_{driver}'
        pdn_col = f'pdown_{driver}'
        if pup_col in df.columns:
            df[f'pup_{driver}_error_%'] = df[pup_col].apply(
                lambda x: round(abs(x - 50) / 50 * 100, 2) if x else None)
            df[f'pdown_{driver}_error_%'] = df[pdn_col].apply(
                lambda x: round(abs(x - 50) / 50 * 100, 2) if x else None)

    output_excel = os.path.join(OUTPUT_DIR, "verification_results.xlsx")
    df.to_excel(output_excel, index=False, sheet_name='TT_Verification')
    print(f"\n[OK] Results saved to: {output_excel}")
    print(f"  {len(results)} corners x 3 drivers = {len(results)*3} resistance measurements")


# ============================================================
# Main
# ============================================================
if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python scripts/pvt_sweep.py generate   # Generate all files")
        print("  python scripts/pvt_sweep.py results    # Enter results -> Excel")
        sys.exit(1)

    cmd = sys.argv[1].lower()
    if cmd == 'generate':
        phase1_generate()
    elif cmd == 'results':
        phase2_results()
    else:
        print(f"Unknown command: {cmd}")
        print("Use 'generate' or 'results'")
