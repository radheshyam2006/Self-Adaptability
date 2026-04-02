# BGR Trim Bit Prediction — ML-to-RTL Pipeline

**ML-driven digital calibration for Bandgap Reference (BGR) circuits across PVT corners.**

> Predicts optimal `pctrl<3:0>` and `nctrl<5:0>` trim codes to maintain constant BGR output voltage (~0.60V) across Process, Voltage, and Temperature variations.

---

## Overview

| Item | Value |
|---|---|
| **Target Circuit** | Bandgap Reference (BGR) |
| **Goal** | Constant vbgr ≈ 0.60V across PVT |
| **ML Model** | Decision Tree (depth 11 / 16) |
| **ML Accuracy** | pctrl: 99.57%, nctrl: 98.88% |
| **RTL Accuracy** | pctrl: 100%, nctrl: 99% (200 vectors) |
| **Hardware** | 3.88 KB SRAM, 0 multipliers |
| **Latency** | ~18 clock cycles average |
| **Technology** | SRAM-reprogrammable FSM DT traversal |

### Architecture

```
  ┌─────────────┐     ┌─────────────────────────┐     ┌──────────────┐
  │ PVT Sensors  │────▶│  bgr_trim_predictor.v   │────▶│  BGR Circuit │
  │              │     │                         │     │              │
  │ pmon_count   │     │  ┌──────────────────┐   │     │  pctrl<3:0>  │
  │ vdd_code     │     │  │ pctrl DT FSM     │   │     │  nctrl<5:0>  │
  │ temp_code    │     │  │ (151 nodes, 1KB)  │   │     │              │
  │              │     │  └──────────────────┘   │     │  vbgr ≈ 0.60V│
  │              │     │  ┌──────────────────┐   │     │              │
  │              │     │  │ nctrl DT FSM     │   │     │              │
  │              │     │  │ (397 nodes, 2.9KB)│   │     │              │
  │              │     │  └──────────────────┘   │     │              │
  └─────────────┘     └─────────────────────────┘     └──────────────┘
```

---

## Table of Contents

1. [Problem Statement](#problem-statement)
2. [Data Analysis](#data-analysis)
3. [ML Pipeline](#ml-pipeline)
4. [Model Comparison](#model-comparison)
5. [RTL Implementation](#rtl-implementation)
6. [Verification](#verification)
7. [Hardware Cost Analysis](#hardware-cost-analysis)
8. [Project Structure](#project-structure)
9. [How to Run](#how-to-run)
10. [Plots and Visualizations](#plots-and-visualizations)

---

## Problem Statement

BGR circuits generate a stable reference voltage independent of PVT (Process, Voltage, Temperature) variations. However, real silicon requires **trim bits** to compensate for these variations. Traditional methods use slow SAR-loop or large LUT-based calibration. This project uses **ML-based prediction** to:

1. **Input**: Read PVT sensor values (ring oscillator count, VDD, temperature)
2. **Predict**: Output optimal trim codes (`pctrl<3:0>`, `nctrl<5:0>`) in ~18 clock cycles
3. **Apply**: Set the trim bits in the BGR circuit for target voltage

### Inputs & Outputs

| Signal | Width | Range | Description |
|---|---|---|---|
| `pmon_count` | 29 bits | 222M – 462M | Ring oscillator counter (PMON_RING_CMOS_res) |
| `vdd_code` | 5 bits | 1 – 19 | VDD encoded: `(V - 0.80) × 100` |
| `temp_code` | 9 bits | 0 – 330 | Temperature encoded: `(°C + 40) × 2` |
| `pctrl<3:0>` | 4 bits | {6, 7, 10} | P-type transistor trim (3 unique values) |
| `nctrl<5:0>` | 6 bits | {24–51} | N-type transistor trim (15 unique values) |

---

## Data Analysis

### Dataset Summary

Training data from Cadence simulations across 3 process corners:

| Corner | Samples | VDD Range | Temp Range | pctrl Classes | nctrl Classes |
|---|---|---|---|---|---|
| **TT** | 4,620 | 0.81–0.99V | -40 to +125°C | 1 (val=7) | 5 |
| **SS** | 4,620 | 0.81–0.99V | -40 to +125°C | 2 (val=7,10) | 4 |
| **FF** | 4,620 | 0.81–0.99V | -40 to +125°C | 2 (val=6,7) | 7 |
| **Total** | **13,860** | | | **3** | **15** |

### Key Observations

- **Very few output classes**: Only 3 unique pctrl values and 15 unique nctrl values — much simpler than typical multi-class problems
- **PMON is the strongest predictor**: Feature importance ~48% for both outputs
- **Clear corner separation**: FF, TT, SS corners occupy distinct regions in PVT space
- **Target vbgr varies by corner**: TT≈607mV, SS≈623mV, FF≈590mV after trim

### Trim Bit Encoding

Trim bits in the Excel data use dash-separated binary notation:
- `0-111` → `0111` → decimal 7
- `10-1010` → `101010` → decimal 42
- The dash is a **separator** (not a don't-care)

---

## ML Pipeline

### Scripts

| Script | Purpose |
|---|---|
| `ml/visualize_bgr_data.py` | Generates 11 analysis plots |
| `ml/model_comparison.py` | Trains & compares 5 model types |
| `ml/final_model.py` | Trains final DT models, generates reports |
| `scripts/export_tree_to_rom.py` | Exports DT to Verilog HEX files |

### Data Split

- **80% training / 20% test** with stratified random split
- Stratification preserves corner × trim-combo proportions
- Random split (not sequential) avoids concentrated removal from continuous regions

### Feature Engineering

All features encoded as **hardware-friendly integers** (no floating point):

```
pmon      = PMON_RING_CMOS_res (raw 29-bit integer)
vdd_enc   = (VDD_volts - 0.80) × 100     (5-bit integer)
temp_enc  = (Temp_celsius + 40.0) × 2     (9-bit integer)
```

---

## Model Comparison

### Accuracy Results

| Model | pctrl Accuracy | nctrl Accuracy | Hardware Cost |
|---|---|---|---|
| **Decision Tree (depth 11/16)** | **99.57%** | **98.88%** | **3.88 KB SRAM** |
| LUT (50 bins) | 99.17% | 97.29% | 5.96 KB |
| Full LUT (13,860 entries) | 100% | 100% | 17.3 KB |
| Polynomial (deg 3) | 78.82% | 31.64% | 285 multipliers |
| Random Forest (10, d=7) | 98.67% | 92.93% | 9.5 KB |
| Neural Network (32,16) | 98.92% | 95.17% | 848 multipliers |

### Why Decision Tree Wins

1. **Smallest hardware**: 3.88 KB SRAM vs 17 KB for full LUT
2. **Zero multipliers**: Only comparators needed
3. **SRAM-reprogrammable**: New tree via config port, same silicon
4. **Near-optimal accuracy**: 99%+ on test set
5. **Deterministic latency**: Bounded by tree depth (~16 cycles worst case)

### Feature Importance

| Feature | pctrl Impact | nctrl Impact |
|---|---|---|
| PMON_RING_CMOS_res | 48.2% | 47.2% |
| VDD | 28.5% | 26.5% |
| Temperature | 23.3% | 26.4% |

The ring oscillator count (PMON) is the single most important feature — it captures process variation information, while VDD and temperature provide the remaining operating point context.

---

## RTL Implementation

### Module Hierarchy

```
bgr_trim_predictor.v          — Top level (parallel dual-tree)
  ├── tree_traversal_fsm.v    — Parameterized FSM engine (pctrl instance)
  └── tree_traversal_fsm.v    — Parameterized FSM engine (nctrl instance)
```

### FSM Design

```
    IDLE ──start──▶ FETCH ──1 cycle──▶ COMPARE
     ▲                                    │
     │                    leaf? ◄──────── ┤
     │                     yes            no
     └─── done ◄────── output          ──▶ FETCH (next node)
```

Each clock cycle: read one SRAM node → compare input vs threshold → branch left/right.

### SRAM Node Format (58 bits)

```
 ┌──────┬──────────┬───────────────┬────────────┬─────────────┬────────────┐
 │ [57] │ [56:55]  │   [54:26]     │  [25:16]   │   [15:6]    │   [5:0]    │
 │is_leaf│feat_id  │  threshold    │ left_child  │ right_child │ leaf_value │
 │ 1 bit│ 2 bits   │  29 bits      │  10 bits    │  10 bits    │  6 bits    │
 └──────┴──────────┴───────────────┴────────────┴─────────────┴────────────┘
```

### Configuration Port

The SRAM is writable via a configuration interface (`cfg_wr_en`, `cfg_wr_addr`, `cfg_wr_data`), enabling:
- **Post-silicon re-training**: Upload new tree learned from actual silicon data
- **Multi-circuit reuse**: Same hardware, different trees for different analog blocks
- **FPGA prototyping**: Load trees at runtime

---

## Verification

### RTL Simulation Results

```
============================================================
  RESULTS (200 test vectors from held-out test set)
============================================================
  pctrl: 200/200 PASS (0 FAIL) — Accuracy: 100%
  nctrl: 199/200 PASS (1 FAIL) — Accuracy: 99%
  Both correct: 199/200 — Combined: 99%
  Avg cycles per prediction: 18
============================================================
```

### Excel Test Samples (11 Cadence verification samples)

```
All 11/11 samples: PASS (100%)
```

### Verification Tools

| Tool | Command |
|---|---|
| Compile RTL | `iverilog -g2005 -o tb_sim.vvp *.v` |
| Run simulation | `vvp tb_sim.vvp` |
| View waveform | `gtkwave waveform.vcd` |

---

## Hardware Cost Analysis

### This Project (BGR) vs Mixer Project

| Metric | BGR (this) | Mixer (previous) |
|---|---|---|
| SRAM | 3.88 KB | 6.3 KB |
| Tree Depth | 11/16 | 14 |
| Multipliers | 0 | 0 |
| Output Classes | 3 + 15 | 256 + 256 |
| Input Bits | 29+5+9 = 43 | 29+5+9 = 43 |
| Latency | ~18 cycles | ~14 cycles |

### vs Traditional Methods

| Method | Memory | Latency | Multipliers | Adapt? |
|---|---|---|---|---|
| **DT FSM (ours)** | **3.88 KB** | **~18 cyc** | **0** | **Yes (SRAM)** |
| Full LUT | 17.3 KB | 1 cyc | 0 | Partial |
| SAR-loop | ~0 | 100+ cyc | 0 | No |
| Polynomial | ~0 | ~20 cyc | 45+ | No |

---

## Project Structure

```
BGR/
├── BGR_ML_DATA_JAN9_testsample_2023_MAR6.xlsx   # Cadence simulation data
│
├── ml/                            # ML pipeline
│   ├── visualize_bgr_data.py      # 11 data analysis plots
│   ├── model_comparison.py        # 5-model comparison
│   ├── final_model.py             # Final DT training + reports
│   ├── best_model_pctrl.pkl       # Trained pctrl DT model
│   ├── best_model_nctrl.pkl       # Trained nctrl DT model
│   └── encoding_params.json       # Feature encoding parameters
│
├── scripts/                       # Export & utility scripts
│   └── export_tree_to_rom.py      # DT → Verilog HEX converter
│
├── rtl/                           # Verilog RTL
│   ├── tree_traversal_fsm.v       # Parameterized FSM engine
│   ├── bgr_trim_predictor.v       # Top-level module
│   ├── tb_bgr_trim_predictor.v    # Main testbench (200 vectors)
│   ├── tb_debug.v                 # Debug testbench
│   ├── pctrl_tree.hex             # SRAM init for pctrl tree
│   ├── nctrl_tree.hex             # SRAM init for nctrl tree
│   ├── test_vectors.hex           # Test stimuli
│   └── test_vectors_readable.txt  # Human-readable test data
│
├── plots/                         # Generated visualizations (16 plots)
│   ├── 01_vbgr_distribution.png
│   ├── 02_trim_distributions.png
│   ├── ...
│   └── 16_error_distribution.png
│
└── README.md                      # This file
```

---

## How to Run

### Prerequisites

```bash
pip install pandas numpy matplotlib scikit-learn openpyxl
# For RTL: iverilog, vvp, gtkwave
```

### Step 1: Generate Plots

```bash
python ml/visualize_bgr_data.py
```

### Step 2: Compare Models

```bash
python ml/model_comparison.py
```

### Step 3: Train Final Model

```bash
python ml/final_model.py
```

### Step 4: Export to Verilog

```bash
python scripts/export_tree_to_rom.py
```

### Step 5: Simulate RTL

```bash
cd rtl
iverilog -g2005 -o tb_sim.vvp tree_traversal_fsm.v bgr_trim_predictor.v tb_bgr_trim_predictor.v
vvp tb_sim.vvp
gtkwave waveform.vcd  # Optional: view waveform
```

---

## Plots and Visualizations

Generated by `ml/visualize_bgr_data.py` and `ml/model_comparison.py`:

| Plot | Description |
|---|---|
| 01 | vbgr voltage distribution across corners |
| 02 | Trim code distributions per corner |
| 03 | PMON_RING_CMOS_res vs trim codes |
| 04 | Trim heatmaps (VDD × Temperature) |
| 05 | PVT space projections with trim clusters |
| 06 | Trim vs temperature (per VDD line) |
| 07 | PMON overlap analysis between corners |
| 08 | vbgr stability after trim compensation |
| 09 | Feature correlation matrix |
| 10 | pctrl vs nctrl relationship |
| 11 | Data summary dashboard |
| 12 | DT depth sweep — accuracy vs cost |
| 13 | All models accuracy vs hardware cost |
| 14 | Best DT per-corner accuracy |
| 15 | Confusion matrices |
| 16 | Prediction error distribution |

---

## Citation

This is the **2nd circuit** (after the mixer) in a planned TCAS paper on ML-driven ASIC calibration. The shared methodology demonstrates generalizability across different analog circuit types using the same SRAM-reprogrammable DT hardware architecture.

---

*Generated for the AI Self-Adaptive Chip project*
