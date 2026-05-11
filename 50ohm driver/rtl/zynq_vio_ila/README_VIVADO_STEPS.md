# ZedBoard VIO+ILA Implementation Guide
# DT Trim Predictor — Zero C Code, Pure Vivado

---

## 🧠 First: Understand What's Actually Happening

```
┌──────────────────────────────────────────────────────────────┐
│                     Your PC (Windows)                        │
│                                                              │
│   Vivado Hardware Manager  ←──USB cable──→  ZedBoard        │
│   ┌─────────────────┐                    ┌──────────────┐   │
│   │  VIO Dashboard  │  drives inputs →   │   Zynq PL    │   │
│   │                 │                    │  (FPGA fabric│   │
│   │  pmon =  50000  │ ──────────────────▶│              │   │
│   │  vreg =  10     │                    │ dt_trim_pred │   │
│   │  temp =  200    │                    │  (your RTL)  │   │
│   │  start = 1→0    │                    │              │   │
│   │                 │  ← reads outputs   │ 2 FSMs run   │   │
│   │  pvtp = 0x4B    │ ◀──────────────────│ at 100 MHz   │   │
│   │  pvtn = 0x52    │                    │              │   │
│   │  done = 1       │                    └──────────────┘   │
│   └─────────────────┘                                        │
│   ┌─────────────────┐                                        │
│   │  ILA Waveform   │  ← streams waveform data back via USB  │
│   │  viewer shows   │                                        │
│   │  every signal   │                                        │
│   └─────────────────┘                                        │
└──────────────────────────────────────────────────────────────┘
```

**Where does the compute happen?**
- 100% on the **FPGA fabric (PL side)** of the Zynq 7020 chip
- The ARM CPU (PS side) is completely powered OFF / unused
- The two FSMs (`u_pvtp_tree`, `u_pvtn_tree`) run at **100 MHz** in real silicon
- The BRAM arrays hold your decision tree nodes (pvtp_tree.hex, pvtn_tree.hex)
- A full prediction takes **~30 clock cycles = 300 nanoseconds!**

**What does USB do?**
- Vivado's JTAG-over-USB protocol sends input values to VIO registers ON the FPGA
- It reads output values back from VIO registers ON the FPGA
- ILA captures waveform samples into an on-chip buffer, then USB transfers them to your PC
- USB is ONLY for control/observation — NOT for computation

---

## 📁 Folder Structure

```
rtl/
├── dt_trim_predictor.v       ← Your original RTL (unchanged)
├── tree_traversal_fsm.v      ← Your original RTL (unchanged)
├── pvtp_tree.hex             ← Decision tree data (loaded to BRAM)
├── pvtn_tree.hex             ← Decision tree data (loaded to BRAM)
└── zynq_vio_ila/             ← NEW folder (everything FPGA-specific lives here)
    ├── top_zedboard.v        ← New top-level wrapper you connect things in
    ├── zedboard.xdc          ← Pin constraints (tells Vivado which FPGA pins = clock/LEDs)
    ├── create_project.tcl    ← Script to auto-create the Vivado project
    └── README_VIVADO_STEPS.md ← This file
```

---

## 🔧 Step-by-Step Vivado Setup

### STEP 1: Create the Vivado Project (TCL Script)

**Why:** Instead of clicking through 10 wizard screens, one TCL script does everything.

1. Open **Vivado 2022.2** (or any 2020+)
2. Click **Tcl Console** tab at the bottom
3. Type this command (update the path to match yours):

```tcl
source {C:/Users/radhe/OneDrive/Documents/AI_Self-adaptive_Chip/Self Adaptability/50ohm driver/rtl/zynq_vio_ila/create_project.tcl}
```

4. The script will:
   - Create a project targeting **xc7z020clg484-1** (ZedBoard's exact chip)
   - Add `top_zedboard.v`, `dt_trim_predictor.v`, `tree_traversal_fsm.v`
   - Add `pvtp_tree.hex` and `pvtn_tree.hex` as memory init files
   - Add `zedboard.xdc` as the constraints file
   - Set `top_zedboard` as the top module

---

### STEP 2: Add VIO IP Core

**Why VIO?** Your RTL ports (`pmon_in`, `vreg_in`, `start`, `pvtp_out`, etc.) are internal FPGA signals — they're NOT connected to physical board pins. VIO creates a "virtual wire" between those signals and Vivado's GUI dashboard. Think of it as a software-controlled pin header.

1. In Vivado: **IP Catalog** (left panel) → search **"VIO"** → double-click **"VIO (Virtual Input/Output)"**

2. In the VIO customizer, configure:

| Setting | Value | Why |
|---------|-------|-----|
| General Options → Input Probe Count | **3** | We READ: pvtp_out, pvtn_out, done |
| General Options → Output Probe Count | **4** | We DRIVE: pmon, vreg, temp, start |
| Probe_IN 0 width | **14** | pvtp_out is 14 bits |
| Probe_IN 1 width | **14** | pvtn_out is 14 bits |
| Probe_IN 2 width | **1**  | done is 1 bit |
| Probe_OUT 0 width | **29** | pmon_in is 29 bits |
| Probe_OUT 1 width | **5**  | vreg_in is 5 bits |
| Probe_OUT 2 width | **10** | temp_in is 10 bits |
| Probe_OUT 3 width | **1**  | start is 1 bit |
| Probe_OUT 0 Initial value | **0x00000000** | Start with pmon=0 |
| Probe_OUT 3 Initial value | **0x0** | Start with start=0 |

3. Click **OK** → Vivado generates `vio_0.xci`

4. ✅ The VIO is already instantiated in `top_zedboard.v` as `u_vio` — nothing else to wire up.

---

### STEP 3: Add ILA IP Core

**Why ILA?** Even after the FPGA is programmed, you can see every signal's waveform in real time — just like a logic analyzer connected to every wire inside the chip. It samples signals into an on-chip RAM buffer, then streams to your PC.

1. In Vivado: **IP Catalog** → search **"ILA"** → double-click **"ILA (Integrated Logic Analyzer)"**

2. Configure:

| Setting | Value | Why |
|---------|-------|-----|
| General Options → Monitor Type | **Native** | We connect manually |
| General Options → Number of Probes | **8** | 8 signals to watch |
| General Options → Sample Data Depth | **1024** | Captures 1024 clock cycles of data |
| All probe widths | **29** | Set all 8 probes to 29 bits wide |

> **Why 29 bits for all probes?** The ILA requires all probes to be the same width OR you configure each individually. We zero-pad narrower signals up to 29 bits in the top-level wrapper — simpler than custom widths.

3. Click **OK** → Vivado generates `ila_0.xci`

4. ✅ Already instantiated in `top_zedboard.v` as `u_ila`.

---

### STEP 4: Fix the HEX File Paths

**Why:** Your original RTL uses absolute Linux server paths (`/data/proj/...`). Vivado needs local paths.

In `top_zedboard.v`, the parameters are already set to relative names:
```verilog
.PVTP_INIT  ("pvtp_tree.hex"),
.PVTN_INIT  ("pvtn_tree.hex")
```

Vivado resolves these relative to the **simulation working directory**. To make synthesis also find them:

1. In Vivado: **Project Settings** → **Simulation** → Set "Simulation Root Directory" to your `rtl/` folder
2. OR simply copy `pvtp_tree.hex` and `pvtn_tree.hex` into the `vivado_proj/` folder

---

### STEP 5: Run Synthesis

**What synthesis does:** Converts your Verilog (`always`, `assign`, `if`) into a **netlist** — a description of which LUTs, flip-flops, and BRAM blocks to use. Like compiling C to assembly.

1. In Vivado Flow Navigator (left panel): Click **"Run Synthesis"**
2. Choose number of jobs (use 4 for speed) → **OK**
3. Wait ~2-5 minutes
4. When done, Vivado shows the **Synthesis Completed** dialog

**Check the synthesis report:**
- Open **Reports → Synthesis → Utilization** 
- You should see BRAM usage (for your hex trees) and LUT usage (for FSMs)
- Expected: ~2 BRAMs, ~500 LUTs, ~200 FFs out of the 7020's 53,200 LUTs

If you see **"INIT_FILE not found"** errors → fix hex file paths (Step 4).

---

### STEP 6: Run Implementation

**What implementation does:** Takes the synthesis netlist and physically places each LUT/FF onto a specific location on the FPGA die, then routes the wires between them. Like floor-planning a chip.

1. Click **"Run Implementation"**
2. Wait ~5-10 minutes
3. When done: check **Reports → Implementation → Timing Summary**

**Critical check — Timing:**
- Look for **"Worst Negative Slack (WNS)"**  
- If WNS ≥ 0 ns → ✅ Timing MET — your design runs at 100 MHz correctly  
- If WNS < 0 ns → ❌ Timing violated — some paths are too slow

For your design (simple FSM + BRAM lookup), you should easily meet 100 MHz timing.

---

### STEP 7: Generate Bitstream

**What a bitstream is:** A ~4 MB binary file (`.bit`) containing the complete configuration for every LUT, FF, and routing switch on the FPGA. Programming the FPGA with this file is like "flashing firmware" — it configures billions of transistors to implement your circuit.

1. Click **"Generate Bitstream"**
2. Wait ~2-3 minutes
3. Bitstream saved as: `vivado_proj/dt_predictor_zynq.runs/impl_1/top_zedboard.bit`

---

### STEP 8: Connect ZedBoard and Program It

**Hardware setup:**
1. Connect USB cable: ZedBoard's **"PROG"** micro-USB port → your PC
   - This is the JTAG programming port (different from the UART port)
2. Make sure the **JP9** jumper (JTAG/QSPI mode) is set to JTAG mode (pins 2-3)
3. Power on the ZedBoard (slide the power switch)
4. The "DONE" LED on the board will be OFF (not yet programmed)

**In Vivado:**
1. Click **"Open Hardware Manager"** (in Flow Navigator bottom)
2. Click **"Open Target"** → **"Auto Connect"**
3. Vivado discovers: `xc7z020_1` (your chip)
4. Click **"Program Device"** → select your `.bit` file → **"Program"**
5. The **DONE LED** on ZedBoard lights up GREEN = FPGA is programmed ✅

---

### STEP 9: Use VIO to Drive Inputs and Read Outputs

This is the payoff! No C code, no PuTTY, no terminal.

1. In Hardware Manager, you'll see the **VIO dashboard** with a table of probes

2. **Set input values** (double-click the "Value" cell to edit):

| Probe | Signal | Example value | What it means |
|-------|--------|---------------|---------------|
| probe_out0 | pmon_in | `50000` | Ring-osc count = 50,000 |
| probe_out1 | vreg_in | `10` | Vreg = 0.80 + 10/100 = 0.90V |
| probe_out2 | temp_in | `200` | Temp = (200/4) - 40 = +10°C |
| probe_out3 | start | `0` | Keep LOW initially |

3. **Trigger a prediction:**
   - Set `probe_out3` (start) = `1` → click **"Commit"**
   - Set `probe_out3` (start) = `0` → click **"Commit"**
   - (This creates the 1-cycle start pulse your FSM needs)

4. **Read the results** (these update automatically):
   - `probe_in0` = pvtp_out → your P-trim code (hex)
   - `probe_in1` = pvtn_out → your N-trim code (hex)  
   - `probe_in2` = done → pulses to 1 when prediction finishes (~300 ns later, looks like steady 1)

5. **Also look at the ZedBoard LEDs!**
   - LED0-7 show `pvtp_out[7:0]` in binary
   - Change the pmon/temp/vreg values and redo start → watch LEDs change!

---

### STEP 10: Use ILA to See Waveforms

1. In Hardware Manager → click **"Run Trigger"** on the ILA panel
2. Set trigger condition: **probe6 (done) == 1**
3. Toggle the `start` pulse via VIO
4. ILA auto-captures 1024 cycles and shows you the full waveform:
   - You can see the FSM traversing the tree cycle by cycle
   - See exactly when `done` pulses
   - See the BRAM read latency
   - Zoom in to count exactly 30 clock cycles of traversal

---

## 🧪 Test Vectors to Try

Use these known values from your Cadence simulation to verify correctness:

| pmon_in | vreg_in | temp_in | Expected pvtp | Expected pvtn |
|---------|---------|---------|---------------|---------------|
| 50000   | 10      | 200     | Check vs ML model output | Check vs ML model output |
| 100000  | 15      | 280     | (mid-range corner)       | (mid-range corner)       |
| 5000    | 5       | 120     | (cold, low-voltage)      | (cold, low-voltage)      |

> **Tip:** Use your `test_vectors_readable.txt` file in the `rtl/` folder — those are the exact test cases from your testbench simulation. Cross-check FPGA output vs simulation output!

---

## 🔍 Understanding VIO vs ILA

| Feature | VIO (Virtual I/O) | ILA (Integrated Logic Analyzer) |
|---------|-------------------|----------------------------------|
| Purpose | Drive & read signals | Capture waveforms |
| Analogy | Software signal generator + voltmeter | Digital oscilloscope |
| Timing | Static / snapshot | Time-continuous (cycle by cycle) |
| Data depth | Single current value | 1024 cycles of history |
| Use case | "Set pmon=50000, what's pvtp?" | "Show me the FSM state for 30 cycles" |
| Both connected via | USB JTAG | USB JTAG |

---

## ⚡ Why This is Better Than AXI-Lite + Vitis

| Aspect | AXI-Lite + Vitis | VIO + ILA (this approach) |
|--------|-----------------|--------------------------|
| New code to write | ~200 lines of C + AXI wrapper | Zero new code |
| Tools needed | Vivado + Vitis + PuTTY | Vivado only |
| Time to first result | 2-3 days | 2-3 hours |
| Debug visibility | printf statements | Full waveform viewer |
| Learning curve | AMBA protocol + SDK setup | Just Vivado GUI |
| When to use AXI | Production system, real-time control | — |
| When to use VIO+ILA | Verification, debugging, learning | ← You are here |

---

## 📌 Quick Reference: Signal Encodings

```
pmon_in  [28:0]  → Raw ring oscillator count (integer, no encoding)
                   Typical range: 1,000 to 300,000,000

vreg_in  [4:0]   → round((Voltage_in_Volts - 0.80) × 100)
                   Example: 0.90V → round((0.90-0.80)×100) = 10
                   Range: 0..31  (covers 0.80V to 1.11V)

temp_in  [9:0]   → round((Temp_in_Celsius + 40) × 4)
                   Example: +25°C → round((25+40)×4) = 260
                   Example: -40°C → 0,   +125°C → 660
                   Range: 0..679

pvtp_out [13:0]  → 14-bit trim code (upper 6 bits always 0, lower 8 are actual trim)
pvtn_out [13:0]  → Same format
```

---

## ❓ Common Errors and Fixes

| Error | Cause | Fix |
|-------|-------|-----|
| `INIT_FILE not found during synthesis` | Hex file path wrong | Copy `.hex` files into `vivado_proj/` folder |
| `Cannot find module vio_0` | VIO IP not generated yet | Add VIO IP in IP Catalog (Step 2) |
| `Cannot find module ila_0` | ILA IP not generated yet | Add ILA IP in IP Catalog (Step 3) |
| `Timing violation WNS < 0` | Clock too fast | Unlikely at 100MHz; check for latch inference |
| `DONE LED not lighting` | Wrong JTAG mode | Check JP9 jumper on ZedBoard |
| VIO shows `X` values | FPGA not programmed | Re-program the `.bit` file |
| `pvtp_out` always 0 | `start` never pulsed | Toggle probe_out3: 0→1→0 |
