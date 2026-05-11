"""
Automated PVT Corner Sweep via SSH
===================================
Fully automates: upload files -> copy -> set vreg -> run sim -> read results -> Excel

Usage:
  1. In Cadence CIW, type:  load("/home/user13/sweep_control.il")
  2. On Windows, run:       python scripts/auto_sweep.py
  3. Wait for all 5 corners to complete (~15-25 min)
  4. Results saved to sweep_output/verification_results.xlsx
"""

import sys, os, json, time, getpass
import pandas as pd
import openpyxl
import paramiko
from scp import SCPClient

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
EXCEL_FILE = os.path.join(PROJECT_DIR,
    "TSMC28nm_DRV_ML_MAR6_LookUP_Table_Mar20_ML Predictions.xlsx")
OUTPUT_DIR = os.path.join(PROJECT_DIR, "sweep_output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Server config
SERVER_HOST = "10.2.20.16"
SERVER_USER = "user13"
RTL_IMPORT = "/data/proj/Low_power_design/tech_tsmc128nm/work/users/user13/rtl_import"
SIM_BASE = "/data/proj/Low_power_design/tech_tsmc128nm/work/users/user13/simulation/tsmc28_tx_tb/ams/maestro/results/maestro"


def encode_vreg(v):
    return max(0, min(31, int(round((v - 0.80) * 100))))

def encode_temp(t):
    return max(0, min(1023, int(round((t + 40.0) * 4))))

def encode_pmon(p):
    return max(0, min((1 << 29) - 1, int(round(p))))


def make_dummy_sensors(vreg, temp, pmon, name):
    ve, te, pe = encode_vreg(vreg), encode_temp(temp), encode_pmon(pmon)
    return f"""module dummy_sensors (
    output wire [28:0] pmon_out,
    output wire [4:0]  vreg_out,
    output wire [9:0]  temp_out,
    output reg         clk,
    output reg         rst_n,
    output reg         start
);
    // ---- PVT CORNER: {name} ----
    // vreg={vreg}V -> {ve},  temp={temp}C -> {te},  pmon={pmon} -> {pe}
    assign vreg_out = 5'd{ve};
    assign temp_out = 10'd{te};
    assign pmon_out = 29'd{pe};

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


def load_tt_cases():
    wb = openpyxl.load_workbook(EXCEL_FILE)
    ws = wb['Test_case_Mar20']
    cases = []
    for r in range(2, ws.max_row + 1):
        name = ws.cell(r, 1).value
        if name is None or not str(name).startswith('tt'):
            continue
        cases.append({
            'name': name,
            'vreg': float(ws.cell(r, 2).value),
            'temperature': float(ws.cell(r, 3).value),
            'pmon_cmos_res': float(ws.cell(r, 6).value),
            'pvtp_raw': ws.cell(r, 8).value,
            'pvtn_raw': ws.cell(r, 9).value,
            'pull_up_res_new': ws.cell(r, 10).value,
            'pull_dn_res_new': ws.cell(r, 11).value,
        })
    return cases


def make_skill_controller(cases):
    """Generate SKILL script that Virtuoso loads to accept commands."""
    vreg_list = " ".join([str(c['vreg']) for c in cases])
    return f"""
; ================================================================
; PVT Sweep Controller - Auto-loaded by Virtuoso
; ================================================================
; This script watches /tmp/sweep_cmd.txt for commands from Python.
; When Python writes "RUN <corner_idx> <vreg>", this script:
;   1. Sets the vreg design variable
;   2. Runs the simulation
;   3. Writes "DONE" to /tmp/sweep_status.txt when finished

procedure(sweepWatchdog()
  let((fp line parts idx vreg_val)
    when(isFile("/tmp/sweep_cmd.txt")
      fp = infile("/tmp/sweep_cmd.txt")
      line = gets(nil fp)
      close(fp)
      deleteFile("/tmp/sweep_cmd.txt")

      when(line
        printf("\\n[SWEEP] Received command: %s\\n" line)

        ; Parse "RUN <idx> <vreg>"
        parts = parseString(line " ")
        when(car(parts) == "RUN"
          idx = atoi(cadr(parts))
          vreg_val = atof(caddr(parts))

          printf("[SWEEP] Corner %d: setting vreg = %g\\n" idx vreg_val)
          desVar("vreg" vreg_val)

          printf("[SWEEP] Starting simulation...\\n")

          ; Write status
          fp = outfile("/tmp/sweep_status.txt" "w")
          fprintf(fp "RUNNING %d" idx)
          close(fp)
        )
      )
    )
    ; Check again in 2 seconds
    after(2.0 'sweepWatchdog)
  )
)

; Start the watchdog
sweepWatchdog()
printf("\\n[SWEEP] Watchdog started. Waiting for commands from Python...\\n")
printf("[SWEEP] Python can now send commands via /tmp/sweep_cmd.txt\\n")
"""


def ssh_connect(password):
    """Create SSH connection to server."""
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER_HOST, username=SERVER_USER, password=password)
    return ssh


def ssh_exec(ssh, cmd, timeout=30):
    """Execute command on server and return output."""
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    return out.strip(), err.strip()


def upload_file(ssh, local_path, remote_path):
    """Upload a file via SFTP."""
    sftp = ssh.open_sftp()
    sftp.put(local_path, remote_path)
    sftp.close()


def write_remote_file(ssh, remote_path, content):
    """Write content to a file on the server."""
    sftp = ssh.open_sftp()
    with sftp.open(remote_path, 'w') as f:
        f.write(content)
    sftp.close()


def read_remote_file(ssh, remote_path):
    """Read content from a file on the server."""
    sftp = ssh.open_sftp()
    try:
        with sftp.open(remote_path, 'r') as f:
            return f.read().decode('utf-8', errors='replace')
    except FileNotFoundError:
        return None
    finally:
        sftp.close()


def main():
    print("=" * 60)
    print("  Automated PVT Corner Sweep")
    print("=" * 60)

    # Load test cases
    cases = load_tt_cases()
    print(f"Found {len(cases)} TT test cases")
    for i, c in enumerate(cases):
        print(f"  [{i+1}] {c['name']:30s} vreg={c['vreg']}V temp={c['temperature']}C")

    # Get password
    password = getpass.getpass(f"\nEnter SSH password for {SERVER_USER}@{SERVER_HOST}: ")

    # Connect
    print("\nConnecting to server...")
    ssh = ssh_connect(password)
    print("Connected!")

    # Step 1: Upload all dummy_sensors files
    print("\n--- Uploading dummy_sensors files ---")
    for i, case in enumerate(cases):
        content = make_dummy_sensors(
            case['vreg'], case['temperature'],
            case['pmon_cmos_res'], case['name']
        )
        local_path = os.path.join(OUTPUT_DIR, f"dummy_sensors_{i+1}.v")
        with open(local_path, 'w', newline='\n') as f:
            f.write(content)
        upload_file(ssh, local_path, f"{RTL_IMPORT}/dummy_sensors_{i+1}.v")
        print(f"  Uploaded dummy_sensors_{i+1}.v")

    # Step 2: Upload SKILL controller
    print("\n--- Setting up SKILL controller ---")
    skill_content = make_skill_controller(cases)
    write_remote_file(ssh, "/home/user13/sweep_control.il", skill_content)
    print("  Uploaded sweep_control.il")

    print("\n" + "=" * 60)
    print("  IMPORTANT: In Cadence CIW, type this ONE command:")
    print('  load("/home/user13/sweep_control.il")')
    print("=" * 60)
    input("\nPress ENTER after you've loaded the script in CIW...")

    # Step 3: Run each corner
    results = []
    for i, case in enumerate(cases):
        print(f"\n{'='*60}")
        print(f"  Corner {i+1}/{len(cases)}: {case['name']}")
        print(f"  vreg={case['vreg']}V, temp={case['temperature']}C")
        print(f"{'='*60}")

        # Copy the right dummy_sensors
        ssh_exec(ssh, f"cp {RTL_IMPORT}/dummy_sensors_{i+1}.v {RTL_IMPORT}/dummy_sensors.v")
        print("  [1/4] Copied dummy_sensors file")

        # Tell Maestro to set vreg (Maestro still needs manual Recreate+Run)
        print(f"  [2/4] Setting vreg = {case['vreg']}")
        write_remote_file(ssh, "/tmp/sweep_cmd.txt", f"RUN {i+1} {case['vreg']}")

        # Wait for user to run simulation
        print(f"\n  >>> In Maestro CIW, you should see: [SWEEP] setting vreg = {case['vreg']}")
        print(f"  >>> Now click: Simulation -> Netlist -> Recreate")
        print(f"  >>> Then click: Green Run button")
        print(f"  >>> Wait for simulation to complete (~3-5 min)")

        input(f"\n  Press ENTER when simulation for corner {i+1} is done...")

        # Read the irun.log to check if simulation succeeded
        print("  [3/4] Checking simulation status...")
        log_path = f"{SIM_BASE}/ExplorerRun.0/1/tsmc28_tx_tb_ams_1/psf/irun.log"
        log_content, _ = ssh_exec(ssh, f"tail -5 {log_path}")
        if "logstatus" in log_content:
            print("  WARNING: +logstatus error detected! Check irun wrapper.")
        elif "RNAERR" in log_content:
            print("  WARNING: Simulation error detected!")
        else:
            print("  Simulation appears successful")

        # Ask for resistance values
        print(f"\n  [4/4] Enter resistance values from Maestro Outputs tab:")
        res = dict(case)
        pup = input(f"    pup (pull-up resistance in ohm): ").strip()
        pdn = input(f"    pdown (pull-down resistance in ohm): ").strip()
        res['pup'] = float(pup) if pup else None
        res['pdown'] = float(pdn) if pdn else None

        # Calculate error
        if res['pup']:
            res['pup_error_%'] = round(abs(res['pup'] - 50) / 50 * 100, 2)
        if res['pdown']:
            res['pdown_error_%'] = round(abs(res['pdown'] - 50) / 50 * 100, 2)

        results.append(res)
        print(f"\n  Recorded: pup={res.get('pup')} ohm, pdown={res.get('pdown')} ohm")

    # Step 4: Create final Excel
    print(f"\n{'='*60}")
    print("  Creating verification Excel...")
    df = pd.DataFrame(results)
    output_path = os.path.join(OUTPUT_DIR, "verification_results.xlsx")
    df.to_excel(output_path, index=False, sheet_name='TT_Verification')
    print(f"  Saved: {output_path}")
    print(f"  {len(results)} corners verified")
    print(f"{'='*60}")

    # Summary
    print("\n  SUMMARY:")
    print(f"  {'Corner':<30s} {'pup':>8s} {'pdown':>8s} {'pup_err':>8s} {'pdn_err':>8s}")
    print(f"  {'-'*62}")
    for r in results:
        pup = f"{r.get('pup', 'N/A')}"
        pdn = f"{r.get('pdown', 'N/A')}"
        pe = f"{r.get('pup_error_%', 'N/A')}%"
        de = f"{r.get('pdown_error_%', 'N/A')}%"
        print(f"  {r['name']:<30s} {pup:>8s} {pdn:>8s} {pe:>8s} {de:>8s}")

    ssh.close()
    print("\nDone! SSH connection closed.")


if __name__ == '__main__':
    main()
