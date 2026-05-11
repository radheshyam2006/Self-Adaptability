# ML-Based Self-Adaptive 50Ω TX Driver — Complete Setup Guide

> **Purpose:** This document tells any new user exactly how to reproduce and run the Cadence AMS simulation for the ML-based 50Ω output driver trim predictor on the IIIT Hyderabad EECS server.

---

## 1. Server Access & Environment Setup

### 1.1 SSH Connection
```bash
ssh -X username@10.2.20.16
# Enter password when prompted
```

### 1.2 Shell & Cadence Setup
```bash
csh                                        # Switch to C-shell (required)
source /home/cadence-2023/cadence2.csh     # Load Cadence tools (IC618, Incisive 15.2, Spectre 20.1)
setenv PATH ~/bin:${PATH}                  # Load irun wrapper (see Section 2)
virtuoso &                                 # Launch Virtuoso
```

> [!IMPORTANT]
> The `setenv PATH ~/bin:${PATH}` line is **critical**. Without it, the simulation will crash with `+logstatus` error. Add this to `~/.cshrc` for persistence.

### 1.3 Key Server Paths

| Item | Path |
|------|------|
| Working directory | `/data/proj/Low_power_design/tech_tsmc128nm/work/users/user13/` |
| RTL import folder | `.../user13/rtl_import/` |
| Cadence library | `.../user13/tsmc28_tx_tb/` |
| Simulation output | `.../user13/simulation/tsmc28_tx_tb/ams/maestro/results/` |
| irun wrapper | `~/bin/irun` |
| Cadence tools | `/home/cadence-2023/IC618/`, `INCISIVE152/`, `SPECTRE201/`, `XCELIUM2009/` |

### 1.4 Cadence Tool Versions
- **IC618** — Schematic editor, Virtuoso GUI
- **INCISIVE 15.2** — Digital simulator (`irun`, `ncsim`, `ncelab`, `ncvlog`)
- **SPECTRE 20.1** — Analog SPICE solver
- **PDK** — TSMC 28nm (`tsmcN28`) at `/data/cad/pdk_all/pdk_tsmc/pdk_tsmc_28/PDK/TSMC_new_iPDK/`

---

## 2. The `irun` Wrapper Script (Critical Fix)

### 2.1 Problem
Cadence's AMS netlister automatically injects `-spectre_args +logstatus` into the simulation command. The Incisive 15.2 version of `ncsim` rejects this flag with:
```
AMSD encountered an error: Invalid command-line arguments for spectre solver: +logstatus
ncsim: *F,RNAERR: The simulator terminated with an analog initialization error.
```

This flag **cannot** be disabled through any GUI checkbox or SKILL command. It is hardcoded into the AMS netlister's argument generation.

### 2.2 Solution
A wrapper script at `~/bin/irun` intercepts the call and removes the offending flag before calling the real `irun`:

```bash
#!/bin/bash
prev=""
for arg in "$@"; do
    if [ "$prev" = "-f" ] && [ -f "$arg" ]; then
        sed -i '/-spectre_args +logstatus/d' "$arg"
    fi
    prev="$arg"
done
exec /home/cadence-2023/INCISIVE152/tools/bin/irun "$@"
```

### 2.3 Installation
```bash
mkdir -p ~/bin
# Upload irun_wrapper.sh from Windows via SCP, OR create manually:
# (paste the script above into ~/bin/irun)
chmod +x ~/bin/irun
echo 'setenv PATH ~/bin:${PATH}' >> ~/.cshrc   # Make permanent
```

### 2.4 Verification
```bash
which irun
# Must show: /home/user13/bin/irun  (NOT /home/cadence-2023/INCISIVE152/...)
```

---

## 3. RTL Code Structure

### 3.1 Files (on Windows)
```
50ohm driver/
├── rtl/
│   ├── dt_trim_predictor.v      # Top-level: 3 sensor inputs → 14-bit pvtp/pvtn
│   ├── tree_traversal_fsm.v     # FSM engine (traverses SRAM-based decision tree)
│   ├── pvtp_tree_rom.v          # SRAM init for pvtp tree (789 nodes)
│   ├── pvtn_tree_rom.v          # SRAM init for pvtn tree (653 nodes)
│   └── tb_dt_trim_predictor.v   # Testbench
├── dummy_sensors.v              # Generates fake PVT sensor values for simulation
├── ml/
│   ├── final_model.py           # ML training script (Decision Tree, depth=14)
│   └── best_model_pvtp_d14.pkl  # Trained model (pickle)
└── scripts/
    └── export_tree_to_rom.py    # Converts sklearn tree → Verilog SRAM hex files
```

### 3.2 RTL Input/Output Ports

| Port | Width | Encoding |
|------|-------|----------|
| `pmon_in` | 29 bits | Raw ring oscillator count = `pmon_cmos_res` from Excel |
| `vreg_in` | 5 bits | `round((V - 0.80) × 100)` |
| `temp_in` | 10 bits | `round((°C + 40) × 4)` |
| `pvtp_out` | 14 bits | `{6'b000000, 8-bit ML prediction}` — upper 6 bits tied to 0 |
| `pvtn_out` | 14 bits | `{6'b000000, 8-bit ML prediction}` — upper 6 bits tied to 0 |

> [!NOTE]
> The ML model was trained on **`pmon_cmos_res`** (column 6 in Excel), NOT `pmon_cmos` (column 7). See [final_model.py](file:///c:/Users/radhe/OneDrive/Documents/AI_Self-adaptive_Chip/Self%20Adaptability/50ohm%20driver/ml/final_model.py#L59) line 59: `X = df[['pmon_cmos_res', 'vreg', 'temperature']].values`

### 3.3 14-bit Port Expansion
The original RTL had 8-bit outputs (`pvtp_out[7:0]`, `pvtn_out[7:0]`). The analog driver has 14-bit inputs. We expanded to 14-bit by zero-padding the upper 6 bits. This eliminated the "Split-Domain Bus" crash.

### 3.4 Uploading RTL to Server
```powershell
# From Windows PowerShell:
scp "path\to\dt_trim_predictor.v" user13@10.2.20.16:/data/proj/Low_power_design/tech_tsmc128nm/work/users/user13/rtl_import/
```

### 3.5 Updating the Cadence Symbol After RTL Change
1. In Virtuoso Library Manager, navigate to `tsmc28_tx_tb` → `dt_trim_predictor` → `functional`
2. Open the text editor view
3. Paste the new Verilog code (or it auto-reads from `rtl_import/`)
4. **Save and Check** → Cadence will print:
   ```
   Deleted pins: pvtn_out<7:0>  pvtp_out<7:0>
   Added output pins: pvtp_out<13:0>  pvtn_out<13:0>
   ```
5. This means the symbol was updated successfully. `errors: 0` is required.

---

## 4. Cadence Schematic Setup

### 4.1 Library & Cell Hierarchy
```
tsmc28_tx_tb (library)
├── ams (config view — top-level for simulation)
├── tx_drv_ML (schematic — contains everything)
│   ├── dt_trim_predictor (functional — your RTL block)
│   ├── dummy_sensors (functional — PVT sensor stub)
│   ├── tx_drv_top × 3 (schematic — analog drivers: 1090Ω, main, 3070Ω)
│   └── vdc sources for vreg, vdd, etc.
```

### 4.2 Wiring the 14-bit Buses
After symbol update, the new pins `pvtp_out<13:0>` and `pvtn_out<13:0>` appear as floating red squares. You must:
1. Draw thick wires from these pins to the analog driver's `pvtp<13:0>` and `pvtn<13:0>` inputs
2. Label the wires with matching bus names
3. **Delete the 12 old VDC sources** (pvt8–pvt13, pvtn8–pvtn13) that previously drove the upper bits

### 4.3 Model Library Setup
Currently configured for **TT corner only**:
- Section: `top_tt`
- Model files: `tsmcN28/../models/spectre/toplevel.scs`
- Additional: `cro_mos_moscap`, `res_bip_dio_disres`, `pre_simu`

> [!WARNING]
> For SS/FF/FS/SF corners, you must change the model section from `top_tt` to `top_ss`, `top_ff`, etc. This is done in **Simulation → Model Library Setup**.

### 4.4 Maestro Design Variables
| Variable | Current Value | Purpose |
|----------|--------------|---------|
| `vreg` | 0.99 | Controls the `vdc` source voltage for the analog `vreg` rail |
| `pvt8`–`pvt13` | 0 | Legacy variables (safe to ignore — now driven by RTL) |
| `pvtn8`–`pvtn13` | 0 | Legacy variables (safe to ignore — now driven by RTL) |

---

## 5. Running the Simulation

### 5.1 From Maestro GUI
1. Open Maestro (ADE Explorer)
2. Verify test: `tsmc28_tx_tb_ams_1`
3. Click green **Run** button
4. Netlisting takes ~10s, simulation takes 2–5 minutes
5. Results appear in the **Results** tab

### 5.2 Output Expressions (Resistance Measurement)

| Name | Expression | Measures |
|------|-----------|----------|
| `pup` | `average((clip((v("/vdd") - v("/outp")) / i("/xdrv_p/out"), 4.5e-07, 4.9e-07)))` | Pull-up resistance (Ω) |
| `pdown` | `(average((clip(v("/outn") / i("/xdrv_p/out"), 4.5e-07, 4.9e-07))) * -1)` | Pull-down resistance (Ω) |

Target: both should be ~50Ω after ML trim prediction.

### 5.3 Waveform Signals to Plot
`/pvtp<13:0>`, `/pvtn<13:0>`, `/outp`, `/outn`, `/clk`, `/done`, `/start`

---

## 6. Known Issues & Fixes

### Issue 1: `+logstatus` Fatal Error
- **Symptom:** `AMSD encountered an error: Invalid command-line arguments for spectre solver: +logstatus`
- **Cause:** Cadence AMS netlister auto-injects this flag; Incisive 15.2 doesn't support it
- **Fix:** irun wrapper script (Section 2)

### Issue 2: Split-Domain Bus Crash
- **Symptom:** `Exit 1` during netlisting, split-domain bus error
- **Cause:** RTL had 8-bit output but analog driver expected 14-bit input
- **Fix:** Expanded RTL to 14-bit output with `{6'b000000, 8-bit}` zero-padding

### Issue 3: `WIA-1175` No Waveform Data
- **Symptom:** `ERROR (WIA-1175): Cannot plot waveform signals`
- **Cause:** Old output expressions reference deleted 8-bit wires (`/pvtp<7:0>`)
- **Fix:** Delete old output rows in Maestro Outputs Setup; add new 14-bit signals

### Issue 4: `connectLib` Warning
- **Symptom:** `Invalid path .../affirma_ams/etc/connect_lib/connectLib`
- **Cause:** Missing connector library in IC618 installation
- **Fix:** Harmless warning; does not affect simulation

### Issue 5: `DLCPTH` Warnings (8+)
- **Symptom:** `cds.lib Invalid path '/home/user2/work/...'`
- **Cause:** Stale library paths from other users in shared `cds.lib`
- **Fix:** Harmless; can be cleaned up by editing `cds.lib`

### Issue 6: `tx_drv_ML/schematic has no ports`
- **Symptom:** `WARNING (VLOGNET-110): The cell has no ports`
- **Cause:** Normal for a testbench top-level cell
- **Fix:** Expected behavior; not an error

---

## 7. ML Pipeline Overview

### 7.1 Training Data
- **Source:** Excel file `TSMC28nm_DRV_ML_MAR6_LookUP_Table_Mar20_ML Predictions.xlsx`
- **Sheets:** FF, SS, TT, FS, SF corners (~3300 rows each, ~16,500 total)
- **Features:** `pmon_cmos_res` (29-bit), `vreg` (float), `temperature` (float)
- **Labels:** `pvtp<7:0>` and `pvtn<7:0>` (8-bit binary trim codes)

### 7.2 Model
- **Algorithm:** Decision Tree Classifier (sklearn)
- **Depth:** 14 (for hardware: depth=10 sweet spot, depth=14 for max accuracy)
- **Two separate trees:** One for pvtp, one for pvtn
- **Accuracy:** >95% on held-out test set

### 7.3 RTL Export Pipeline
```
final_model.py → trains model → best_model_pvtp_d14.pkl
export_tree_to_rom.py → converts to hex → pvtp_tree.hex, pvtn_tree.hex
dt_trim_predictor.v → loads hex into SRAM → runs tree traversal FSM
```

### 7.4 Sensor Encoding (for dummy_sensors.v)
```verilog
vreg_out = round((V - 0.80) * 100);    // e.g., 0.99V → 19
temp_out = round((°C + 40) * 4);        // e.g., 10°C → 200
pmon_out = pmon_cmos_res;               // Raw integer from Excel
```
