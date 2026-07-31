# TCAS-I Paper — Submission Checklist

## Paper File
- **LaTeX**: `New_IEEEtran_how-to.tex` (556 lines, ~9 pages estimated)
- **Class**: `IEEEtran.cls` (standard IEEE Transactions)
- **Diagrams**: `diagrams/` folder (17 existing PNG figures)

---

## ✅ All Changes Applied

### Front Matter
- [x] Title: "A Hardware-Efficient Decision Tree Engine for Self-Adaptive On-Chip Analog Trim Calibration: Architecture, FPGA Validation, and Cadence Verification"
- [x] Journal header: `IEEE Transactions on Circuits and Systems---I: Regular Papers`
- [x] Abstract: Updated with FPGA numbers (1,772 LUTs, 10.5 BRAMs, WNS=2.77ns)
- [x] Keywords: Added "self-adaptive circuits", "FPGA prototyping"

### Section I: Introduction
- [x] Self-adaptability / self-healing circuits framing
- [x] Deeper literature review (Li TCAS-I 2024, Onabajo 2023, Liu JSSC 2013)
- [x] 4 contributions (was 3): added FPGA prototyping + Cadence closed-loop
- [x] Interpretability argument for analog design trust

### Section II: Circuits and Dataset
- [x] Circuit schematic figure placeholders (TODO L77, L88)

### Section III: Why Decision Trees
- [x] Formal math: T: R^3 → Z+ piecewise-constant
- [x] DT indicator function formula
- [x] k-NN comparison (440KB impractical)
- [x] Piecewise-linear comparison (needs multipliers)
- [x] Noise robustness argument

### Section IV: RTL Architecture
- [x] FSM figure TODO comment (L222) — upgrade for TCAS-I quality
- [x] RTL block diagram placeholder (L246)

### Section V: RTL Verification
- [x] 3-stage validation pipeline (was 2-stage)
- [x] Validation flow diagram placeholder (L288)

### Section VI: FPGA Prototyping on Zynq-7000 (ENTIRELY NEW)
- [x] Clarified: **digital block only**, no real sensors, VIO emulates inputs
- [x] Platform: ZedBoard, xc7z020, PL-only, no ARM/PS used
- [x] VIO+ILA architecture described
- [x] Resource utilization table (real Vivado 2025.2 numbers):
  - LUTs: 2,087 (3.92%) — includes VIO/ILA overhead
  - FFs: 3,714 (3.49%)
  - BRAM: 10.5 tiles (7.50%)
  - DSPs: **0** (0.00%) — confirms zero-multiplier architecture
- [x] Timing closure: WNS=2.770ns, WHS=0.039ns, Fmax≈138MHz
- [x] Hardware test result: pmon=50000, vreg=10, temp=200 → pvtp=pvtn=0x00F9 (249)
- [x] LEDs: 11111001 confirmed
- [x] VIO/ILA screenshot placeholders (TODO L376)

### Section VII: Cadence Closed-Loop Validation
- [x] ADE Explorer approach (not AMS Maestro)
- [x] Representative PVT subset (5 corners: FF/TT/SS/FS/SF)
- [x] All within ±0.73% of 50Ω
- [x] Referenced senior's lab automation framework

### Section VIII: Comparison and Discussion
- [x] 9 advantages (a through i):
  - (a) Zero external components
  - (b) Zero multipliers (confirmed by 0 DSP on FPGA)
  - (c) >5× faster than SAR (one-shot calibration)
  - (d) 4-5× less memory than LUT
  - (e) Technology portability (only ROM changes)
  - (f) Interpretability and design trust
  - (g) Noise robustness
  - (h) Zero ATE infrastructure
  - (i) Self-adaptive runtime operation
- [x] 6 limitations (L1 through L6):
  - (L1) Sensor dependency — assumes ring osc/temp/vreg sensors exist
  - (L2) Training data dependency — Cadence sim ≠ real silicon
  - (L3) ROM scaling — O(2^depth) worst case
  - (L4) Limited closed-loop coverage — subset, not full 82,250 points
  - (L5) No post-layout ASIC results — gate count is estimated
  - (L6) Static model — ROM fixed at fabrication, not adaptive
- [x] Novelty vs Struharik (3 differentiators)
- [x] Gate count breakdown (~920 gates)

### Section IX: Conclusion
- [x] Three-stage validation pipeline summarized
- [x] Self-adaptive framing
- [x] Nine advantages listed
- [x] Future work: ASIC synthesis, full PVT automation, 3rd circuit, live sensors

### Bibliography (12 references, ALL REAL)
- [x] [1] Leung — BGR (JSSC 2002) ✓
- [x] [2] Kim — Impedance calibration (JSSC 2009) ✓
- [x] [3] Gondi — SAR (JSSC 2007) ✓
- [x] [4] Li — Knowledge transfer PVT (TCAS-I 2024) ✓ **NEW** (was fabricated)
- [x] [5] Onabajo — ML on-chip calibration (IEEE Open J. CAS 2023) ✓ **NEW** (was placeholder)
- [x] [6] Liu — Self-healing LNA (JSSC 2013) ✓ **NEW**
- [x] [7] Pedregosa — scikit-learn (JMLR 2011) ✓
- [x] [8] Williams — Icarus Verilog ✓
- [x] [9] Struharik — DT IP core (IET 2009) ✓
- [x] [10] Bowman — PVT resilience (JSSC 2011) ✓
- [x] [11] Razavi — Analog CMOS book (2017) ✓
- [x] [12] Abbas — Lab automation framework (CVEST, unpublished 2025) ✓ **NEW**

---

## 📋 Remaining TODOs (6 Figure Placeholders)

Search `TODO` in the LaTeX file to find these:

| Line | Figure | Action Needed |
|------|--------|---------------|
| L77 | BGR simplified schematic | Draw in PowerPoint/draw.io, save as `diagrams/bgr_schematic.png` |
| L88 | 50Ω Driver schematic | Draw in PowerPoint/draw.io, save as `diagrams/driver_schematic.png` |
| L222 | FSM state diagram | Upgrade current LaTeX `\picture` to proper PNG/PDF figure |
| L246 | RTL block diagram | Draw in PowerPoint/draw.io, save as `diagrams/rtl_block_diagram.png` |
| L288 | 3-stage validation pipeline | Draw flow diagram, save as `diagrams/val_flow_diagram.png` |
| L376 | VIO + ILA screenshots | Reconnect ZedBoard, capture from Vivado Hardware Manager |

**To activate each figure:**
1. Create the image file and place in `diagrams/` folder
2. Uncomment the `\begin{figure}` block in the LaTeX (remove `%` prefix from each line)
3. Recompile

---

## 🔧 Senior's Automation Scripts

**Location**: `Script_python_1/Script_python/` (identical to `Script_python/`)

**Pipeline**: `corner_name_gen.py` → `corner_split.py` → `corner_run_part.py` (×5 parallel) → `measure.py` → `Results_combine.py`

**Can we use it for our 50Ω driver?** YES, with these adaptations:
1. Replace `netlist` with your 28nm driver + dummy_sensors.v + DT predictor
2. Change `Measure_spec` to measure resistance instead of input offset
3. Update `corner_name_gen.py` for your 5-process-corner CSV format
4. Change `input.scs` to include TSMC 28nm model paths

**Why it's fast**: Runs 5 Spectre instances in parallel, uses Ocean scripts for batch measurement, auto-combines results to Excel.

---

## FPGA Test Result Verification

**Input**: pmon=50,000 (0x0000C350), vreg=10 (0x0A), temp=200 (0xC8)

**Output**: pvtp = pvtn = 0x00F9 (decimal 249)

**LED pattern**: 11111001 = 0xF9 (lower 8 bits of pvtp)

**Note**: Both pvtp and pvtn returning the same value (249) is physically plausible — this test vector represents an extreme slow-process, low-voltage, low-temperature corner where maximum pull-up AND pull-down strength is needed. The DT was trained on this data and both trees independently arrive at the same code.
