# ML-Based PVT Compensation for TSMC 28nm Transmitter Impedance Matching

> **A hardware-efficient Decision Tree predictor for runtime trim code calibration, implemented in synthesizable Verilog.**

---

## Table of Contents

1. [The Problem](#1-the-problem)
2. [Our Solution — Overview](#2-our-solution--overview)
3. [Data Analysis & What the Plots Tell Us](#3-data-analysis--what-the-plots-tell-us)
4. [ML Pipeline](#4-ml-pipeline)
5. [Model Selection & Why Decision Trees](#5-model-selection--why-decision-trees)
6. [Depth Selection — Why 14, Not 12 or 7?](#6-depth-selection--why-14-not-12-or-7)
7. [RTL Implementation](#7-rtl-implementation)
8. [SRAM Reconfigurability — How and Why](#8-sram-reconfigurability--how-and-why)
9. [Results Summary](#9-results-summary)
10. [Hardware Cost: Traditional vs Our Approach](#10-hardware-cost-traditional-vs-our-approach)
11. [How to Run](#11-how-to-run)
12. [Project Structure](#12-project-structure)
13. [Is This Work Worth It?](#13-is-this-work-worth-it)

---

## 1. The Problem

### What is Impedance Matching?

In high-speed serial links (USB, PCIe, Ethernet), the transmitter must drive a signal through a channel with a characteristic impedance of **50Ω**. If the transmitter's output impedance doesn't match 50Ω, signal reflections occur, causing data errors.

```
    Transmitter                Channel (50Ω)              Receiver
   ┌──────────┐            ┌──────────────────┐         ┌──────────┐
   │  Must be  │───────────│   Transmission    │─────────│          │
   │   50Ω     │           │      Line         │         │          │
   └──────────┘            └──────────────────┘         └──────────┘
        ↑
   If not 50Ω → reflections → data corruption!
```

### Why Does Impedance Change?

Silicon transistors are affected by **PVT** (Process, Voltage, Temperature):

| Factor | What Changes | Effect on Impedance |
|--------|-------------|--------|
| **Process** | Manufacturing variation (transistor sizes, doping differ chip to chip) | Shifts impedance by **±30%** between chips |
| **Voltage** | Supply voltage fluctuation (0.81V to 0.99V) | Changes transistor drive strength |
| **Temperature** | Chip heating (-40°C to +125°C during operation) | Changes carrier mobility in silicon |

**Without any compensation**, the Cadence simulation data shows:

| Corner | Pull-Up Resistance (uncompensated) | Problem |
|--------|:---:|--------|
| FF (Fast-Fast) | 41.3 – 48.2Ω (mean 44.1Ω) | Too low — 12% below 50Ω |
| SS (Slow-Slow) | 54.1 – 62.7Ω (mean 58.0Ω) | Too high — 16% above 50Ω |
| TT (Typical) | 47.6 – 54.8Ω (mean 50.8Ω) | Close but still drifts |
| FS (Fast N, Slow P) | 42.9 – 52.2Ω (mean 46.7Ω) | Asymmetric |
| SF (Slow N, Fast P) | 52.4 – 58.4Ω (mean 55.2Ω) | Asymmetric |

This range of **41Ω to 63Ω** is **completely unacceptable** for a 50Ω target.

### The Industry Solution: Trim Bits

Chip designers add **digitally-programmable resistors** controlled by "trim bits":

```
   Pull-up network:     pvtp[7:0] → 8 switches → adjust pull-up resistance
   Pull-down network:   pvtn[7:0] → 8 switches → adjust pull-down resistance
```

The chip must figure out: **given the current PVT conditions, what trim codes achieve 50Ω?**

### Traditional Approach vs. Our Approach

| Method | How it Works | Drawbacks |
|--------|-------------|-----------|
| **External precision resistor** | Off-chip 50Ω reference on PCB, analog comparator loop | Needs extra IC pin, PCB component, analog circuits, calibration time |
| **Fixed LUT** | Pre-computed table of trim codes | Cannot adapt to real-time V/T changes |
| **Our ML approach** | 3 on-chip sensors → trained Decision Tree → trim codes | No extra pins, no external parts, adapts to live PVT, purely digital |

---

## 2. Our Solution — Overview

We use **three on-chip sensors** that are already present in most modern SoCs:

| Sensor | What it Measures | Encoding for Hardware | Bit Width |
|--------|-----------------|-------------|:---:|
| **pmon_cmos_res** | Ring oscillator frequency count | `int(round(value))` — already an integer | 29-bit |
| **vreg** | Regulated supply voltage (0.81V – 0.99V) | `round((V - 0.80) × 100)` → 1 to 19 | 5-bit |
| **temperature** | On-die temperature (-40°C to +125°C) | `round((°C + 40) × 4)` → 0 to 660 | 10-bit |

### How does pmon_cmos_res give a 29-bit integer?

The ring oscillator is a circuit that oscillates at a frequency determined by the transistor speed. A counter counts how many oscillations occur in a fixed time window. This count is already a raw integer — for example, 297,976,070. The maximum observed value in our data is **435,534,010**, which needs `ceil(log2(435534010))` = **29 bits** to represent. So we use 29 bits — just enough to hold the largest value.

### Why do we need all 3 inputs?

This was our **critical discovery**. Using `pmon_cmos_res` alone gives only **~35% accuracy**. The reason is explained in [Section 3.7 (Plot 07)](#37-why-1-input-fails-ring-oscillator-overlap-plot-07) — the ranges from different corners heavily overlap. Adding `vreg` and `temperature` disambiguates the overlapping cases, jumping accuracy to **98.2%**.

```
   ┌─────────────┐     ┌──────────────────┐     ┌──────────────┐
   │ Ring Osc     │────→│                  │────→│ pvtp[7:0]    │
   │ (29-bit cnt) │     │  Decision Tree   │     │ (pull-up R)  │
   ├─────────────┤     │  Traversal FSM   │     ├──────────────┤
   │ Vreg sensor  │────→│  (22 cycles avg) │────→│ pvtn[7:0]    │
   │ (5-bit code) │     │                  │     │ (pull-down R)│
   ├─────────────┤     └──────────────────┘     └──────────────┘
   │ Temp sensor  │────→        ↑
   │ (10-bit code)│     SRAM (configurable
   └─────────────┘      thresholds)
```

---

## 3. Data Analysis & What the Plots Tell Us

We have simulation data from **Cadence** covering 5 process corners × 10 voltages × ~329 temperatures = **~16,450 samples per corner**.

> **Note on negative resistance values**: In Cadence simulation, resistance can appear negative due to the current measurement direction convention. We take the **absolute value** to get the actual impedance in ohms.

### 3.1 Resistance Without Compensation (Plot 01)

![Resistance distributions across corners](plots/01_resistance_distributions.png)

**What this shows**: The pull-up and pull-down resistance before trim compensation. Each corner produces a different resistance range — FF is too low (~44Ω), SS is too high (~58Ω). Without trim bits, these would cause signal integrity failures.

**Takeaway**: The uncompensated resistance spans 41–63Ω — we must compensate to bring it within ±3% of 50Ω.

### 3.2 Trim Code Distributions (Plot 02)

![Trim bit distributions](plots/02_trim_bit_distributions.png)

**What this shows**: The trim codes needed by each corner.

| Corner | pvtp Range | Why |
|--------|-----------|-----|
| **FF** | 12–31 | Transistors already "fast" → resistance is too low → small trim to increase R |
| **SS** | 242–253 | Transistors "slow" → resistance too high → large trim to decrease R |
| **TT** | 29–63 | Middle ground |
| **FS/SF** | Asymmetric | P and N sides need different corrections |

**Takeaway**: Trim codes vary from 12 to 253 across corners — the model must predict across this entire range.

### 3.3 Ring Oscillator vs Trim Codes (Plot 03)

![pmon vs trim analysis](plots/03_pmon_vs_trim.png)

**What this shows**: How `pmon_cmos_res` (ring oscillator count) relates to the trim code. Higher pmon = faster transistors = lower resistance = need less compensation (lower trim codes).

**Key observation**: Notice how different corners form **vertical bands** that overlap on the x-axis. This is the fundamental reason a single input is not enough.

### 3.4 Trim Code Heatmaps — V × T Grid (Plot 04)

![Trim heatmaps](plots/04_trim_heatmaps.png)

**What this shows**: For each process corner, how trim codes change across the voltage-temperature grid. The "staircase" pattern is visible — trim codes change in **discrete steps**, not smoothly.

**Why staircase?** Because with 8-bit trim codes, each code corresponds to a specific resistance. When temperature or voltage crosses a threshold, the nearest-match trim code jumps to the next value. This is exactly the pattern Decision Trees are designed to capture — they split data at threshold boundaries.

### 3.5 3D PVT Space (Plot 05)

![3D PVT clusters](plots/05_3d_pvt_clusters.png)

**What this shows**: Each dot is one simulation point plotted in (pmon, vreg, temperature) space, colored by process corner.

**Why do we see "line" structures?** Because Cadence simulations use a regular grid — 10 voltages × 329 temperatures. Each "line" is one voltage swept across all temperatures. The lines for different corners occupy different regions of the 3D space, but some regions overlap — this is why all 3 dimensions are needed for disambiguation.

### 3.6 Trim vs Temperature Per Corner (Plot 06)

![Trim vs temperature lines](plots/06_trim_vs_temp_lines.png)

**What this shows**: Within each corner, how trim codes change with temperature at different voltages. The staircase pattern is very clear — within each corner, only **5–12 unique trim values** exist, and they switch at specific temperature thresholds.

**Why does this matter?** This proves that the underlying relationship is **piecewise constant** (flat regions with sharp steps), which is exactly what a Decision Tree models. Polynomial regression would try to fit a smooth curve through these steps and fail.

### 3.7 Why 1 Input Fails: Ring Oscillator Overlap (Plot 07)

![pmon analysis](plots/07_pmon_analysis.png)

**What this shows**: The `pmon_cmos_res` ranges from different process corners **significantly overlap**:

| Corner | pmon range |
|--------|-----------|
| FF | 269M – 435M |
| TT | 238M – 390M |
| SS | 209M – 346M |

A pmon value of 300M could be:
- **FF** at low voltage → needs trim code ~25
- **TT** at typical voltage → needs trim code ~50
- **SS** at high voltage → needs trim code ~245

**There is no way to distinguish these with pmon alone.** Adding `vreg` and `temperature` resolves the ambiguity — if pmon=300M AND vreg=0.99V AND temp=-10°C, it's clearly a different case than pmon=300M AND vreg=0.81V AND temp=100°C.

### 3.8 Impedance After Compensation (Plot 08)

![Impedance accuracy](plots/08_impedance_accuracy.png)

**What this shows**: The pull-up resistance after applying the Cadence-computed optimal trim codes. The y-axis shows resistance values.

**Why the zigzag pattern?** Because trim codes are **discrete 8-bit values** — they can only change in steps of 1 out of 256. Each trim code step corresponds to approximately **±0.2Ω** change in resistance. When temperature changes smoothly but the trim code must stay at a fixed integer, the resulting resistance oscillates ("zigzags") around 50Ω within the step size.

**Is the 0.123Ω error in ohms?** Yes. The SS corner has a mean pull-up resistance of 50.123Ω, so the mean error from the 50Ω target is 0.123Ω. This is excellent — well within the ±1.5Ω typical spec.

### 3.9 Correlation Matrix (Plot 09)

![Correlation matrix](plots/09_correlation_matrix.png)

**What this shows**: The Pearson correlation between all features and outputs.

**Actual correlation values from data**:

| Feature | Correlation with pvtp | Correlation with pvtn |
|---------|:---:|:---:|
| pmon_cmos_res | **-0.494** | **-0.497** |
| vreg | -0.001 | -0.011 |
| temperature | +0.069 | +0.048 |

**Important correction**: The correlation of pmon with trim is **-0.49, not 0.9**. Here's why:
- The minus sign means: higher pmon (faster process) → lower trim code. This makes physical sense.
- The value is only ~0.5, not 0.9, because the **relationship is non-linear** (staircase-shaped with overlapping corners). Pearson correlation only measures *linear* relationships.
- `vreg` and `temperature` have near-zero *global* correlation with trim — but this is misleading! They are critical for *within-corner* fine-tuning. Their effect is **conditional**: at a given pmon value, vreg and temp determine the exact trim code.

**So how do we know all 3 features matter?** Not from correlation — from **feature importance** (see [Section 9.4](#94-feature-importance)).

### 3.10 pvtp vs pvtn Relationship (Plot 10)

![pvtp-pvtn relationship](plots/10_pvtp_pvtn_relationship.png)

**What this shows**: pvtp and pvtn are highly correlated (they track together) but not identical — the pull-up and pull-down networks respond differently to PVT, especially in asymmetric corners (FS, SF). This is why we need **separate prediction models** for pvtp and pvtn.

---

## 4. ML Pipeline

### 4.1 Data Preprocessing

```python
# Input encoding (designed for direct use in hardware)
pmon_encoded = int(round(pmon_cmos_res))           # Already an integer counter value
vreg_encoded = int(round((vreg_V - 0.80) * 100))   # 0.81V → 1, 0.99V → 19
temp_encoded = int(round((temp_C + 40.0) * 4))     # -40°C → 0, +125°C → 660
```

**Why these specific encodings?**
- **pmon_cmos_res**: The ring oscillator outputs a raw count — just round it. No conversion needed.
- **vreg**: Maps 0.81–0.99V range to integers 1–19. The multiplication by 100 gives 0.01V resolution, which is sufficient since our data has 10 voltage steps.
- **temperature**: Maps -40°C to +125°C to unsigned integers 0–660. The factor of 4 gives 0.25°C resolution.

The key design choice: **these same integer values are used directly in the Verilog comparators**. No floating-point, no normalization, no scaling needed in hardware.

### 4.2 Why No Normalization?

We deliberately **did not** use StandardScaler or MinMaxScaler because:
1. **Decision Trees don't need it**: DTs split at absolute thresholds (e.g., "is pmon ≤ 300000000?"). Scaling doesn't change the split quality.
2. **Direct hardware mapping**: The raw integer encodings go straight into 29-bit, 5-bit, and 10-bit comparators. If we normalized, we'd need fixed-point multipliers to un-normalize in hardware.
3. Neural Networks DO need normalization, but we rejected NNs for hardware cost reasons.

### 4.3 Train/Test Split

```
Total data:     ~16,450 per corner × 5 = ~82,250 samples
Training set:   80% (stratified by corner — equal representation)
Test set:       20% (held-out — model has NEVER seen this data)
```

**Stratified split** ensures that each corner has proportional representation in both train and test sets. This prevents the model from performing well on common corners but failing on rare ones.

---

## 5. Model Selection & Why Decision Trees

### 5.1 What Plot 11 Shows (1-Input Model Comparison)

![Model comparison](plots/11_model_comparison.png)

**Critical context**: Plot 11 compares models using **only pmon_cmos_res as input** (1 feature). This was our initial exploration before discovering that 3 inputs are needed. The accuracy is 30–40% for all models because no single-input model can resolve the corner overlaps.

**What each model is:**

| Label in Plot | Full Name | What it Does |
|---------------|-----------|-------------|
| **DT(depth=N)** | Decision Tree | Binary tree of "if-else" comparisons. depth=5 means at most 5 levels of if-else. |
| **RF(n=10,d=5)** | Random Forest, 10 trees each depth 5 | An ensemble: trains 10 separate DTs on random subsets, then takes a **majority vote**. More accurate but needs 10× the hardware. |
| **Poly(deg=N)** | Polynomial Regression | Fits a polynomial curve (y = ax³ + bx² + cx + d). Requires **multipliers** in hardware. Accuracy is very low (~30%) because the data is staircase-shaped, not smooth. |
| **LUT(N)** | Look-Up Table | Divides pmon range into N equal bins. For each bin, stores the most common trim code from training data. Like a simplified nearest-neighbor. |

**Why is Polynomial accuracy so low?** Because the relationship between pmon and trim codes is **staircase-shaped with overlapping corners** — a polynomial tries to fit a smooth curve through discrete jumps, which doesn't work. It's like trying to draw a smooth line through scattered clusters.

**Why is LUT accuracy moderate but not great?** LUT with only 1 input cannot distinguish corners that share the same pmon range. Even with 256 bins, if bin #150 contains both FF samples (needing trim=25) and TT samples (needing trim=50), it can only pick one.

**Takeaway from Plot 11**: With 1 input, NO model works well. This motivated our switch to 3 inputs.

### 5.2 3-Input Model Results

After adding `vreg` and `temperature`, the Decision Tree jumps to **98.2% pvtp / 98.6% pvtn accuracy**.

### 5.3 Why Decision Trees Win Over Neural Networks for Hardware

```
Decision Tree in hardware:        Neural Network in hardware:
┌──────────────────┐              ┌──────────────────────────────┐
│ 1 Comparator     │              │ ~2,000 Multipliers           │
│ 1 MUX (3:1)      │              │ ~2,000 Accumulators          │
│ 1 SRAM (read)    │              │ Activation function LUTs     │
│ 1 FSM (3 states) │              │ Multiple pipeline stages     │
└──────────────────┘              └──────────────────────────────┘
  ~920 gates + 5.8KB SRAM            ~50,000+ gates
  0 multipliers                      ~2,000 multipliers
```

A single 29-bit multiplier costs ~3,000 gates. A neural network with 32 hidden neurons needs hundreds of multipliers. Our Decision Tree uses **zero multipliers** — only comparisons (≤), which cost ~100 gates each.

---

## 6. Depth Selection — Why 14, Not 12 or 7?

### 6.1 Depth Sweep Results (Plot 13)

![Depth sweep](plots/13_depth_sweep.png)

| Depth | pvtp Accuracy | pvtn Accuracy | Total Nodes | SRAM Size |
|:---:|:---:|:---:|:---:|:---:|
| 7 | 21.7% | 28.9% | ~200 | 1.5 KB |
| 10 | 84.8% | 90.0% | ~550 | 4.0 KB |
| 12 | 95.0% | 97.8% | ~1,100 | 8.1 KB |
| **14** | **98.2%** | **98.6%** | **1,442** | **10.6 KB** |
| 15+ | 98.3% | 98.4% | ~1,450 | 10.7 KB |

### 6.2 Is Depth=14 Overfitting Compared to Depth=12?

**No.** Overfitting means the model memorizes training data but fails on new data. Our accuracy numbers are on the **20% held-out test set** that the model has never seen during training. If depth=14 were overfitting:
- Training accuracy would be very high (e.g., 100%)
- Test accuracy would DROP compared to depth=12

But we see the opposite: test accuracy **increases** from 95.0% to 98.2% for pvtp (+3.2%), meaning the deeper tree is capturing genuine patterns, not noise. Depth 15+ gives no further improvement — the tree has fully learned the data at depth 14.

The +3.2% accuracy improvement costs only 342 extra nodes (2.5 KB more SRAM) — an excellent trade-off.

---

## 7. RTL Implementation

### 7.1 Architecture: FSM-Based Tree Traversal

Instead of building 789 comparators in parallel (combinational), we use a **serialized FSM** with a single reusable comparator:

```
┌────────────────────────────────────────────────────────────────┐
│                    dt_trim_predictor (top)                      │
│                                                                │
│   ┌─ tree_traversal_fsm (pvtp) ──────────────────────────┐    │
│   │   SRAM (789 nodes) → 1 Comparator ← Input MUX (3:1) │    │
│   │   FSM Controller → pvtp[7:0] + done_pvtp             │    │
│   └──────────────────────────────────────────────────────┘    │
│                                                                │
│   ┌─ tree_traversal_fsm (pvtn) ──────────────────────────┐    │
│   │   SRAM (653 nodes) → 1 Comparator ← Input MUX (3:1) │    │
│   │   FSM Controller → pvtn[7:0] + done_pvtn             │    │
│   └──────────────────────────────────────────────────────┘    │
│                                                                │
│   Both run in PARALLEL → total latency = max(pvtp, pvtn)       │
└────────────────────────────────────────────────────────────────┘
```

### 7.2 FSM State Machine (3 States)

```
         start pulse
           │
           ↓
      ┌─────────┐
      │  IDLE    │ ←──────────────────────────────────┐
      │          │  Latch all 3 inputs, set addr=0    │
      └────┬─────┘                                    │
           │                                          │
           ↓                                          │
      ┌─────────┐                                     │
      │  FETCH   │  Wait 1 cycle for SRAM read        │
      └────┬─────┘                                    │
           │                                          │
           ↓                                          │
      ┌─────────┐     internal node                   │
      │ COMPARE  │──────────────→ FETCH (next node)   │
      │          │                                    │
      └────┬─────┘                                    │
           │ leaf node found                          │
           ↓                                          │
      Output trim[7:0], assert done ─────────────────→┘
```

Each FETCH+COMPARE = 2 clock cycles. Max depth = 14, so worst case = 30 cycles. **Average: 22 cycles** (most tree paths are shorter than max depth).

### 7.3 SRAM Node Format (60 bits per node)

```
Bit [59]    : is_leaf      — 1 = leaf node (output result), 0 = internal node
Bit [58:57] : feature_id   — 00=pmon, 01=vreg, 10=temperature
Bit [56:28] : threshold    — 29-bit encoded threshold for comparison
Bit [27:18] : left_child   — 10-bit address of left child node
Bit [17:8]  : right_child  — 10-bit address of right child node
Bit [7:0]   : leaf_value   — 8-bit trim code (only used when is_leaf=1)
```

**Why 29 bits for threshold?** Because the largest input (pmon) needs 29 bits. When comparing vreg (5 bits) or temperature (10 bits), the input is zero-padded to 29 bits and compared against the threshold. This way, one comparator handles all three feature types.

### 7.4 Per-Corner RTL Predictions (Plot 14)

![Per-corner predictions](plots/14_per_corner_predictions.png)

**Why is TT accuracy slightly lower?** TT (Typical) corner sits in the middle of the PVT space, where its pmon/vreg/temp ranges partially overlap with EVERY other corner. The model must make the finest distinctions here. Still, 97.6% pvtp and 96.8% pvtn is very good — the "errors" are almost always off by just 1 trim code (±0.2Ω).

---

## 8. SRAM Reconfigurability — How and Why

### 8.1 Why SRAM Instead of Hardwired ROM?

If we hardwire the tree thresholds, the IP only works for THIS specific transmitter circuit. With SRAM:
- **Reuse for different circuits**: Train a new DT for a different transmitter, export to hex, load via config port
- **Field updates**: If PVT behavior drifts over chip lifetime, retrain and reconfigure
- **Multi-product**: Same silicon for multiple products, each with different trim characteristics

### 8.2 Does a Different Decision Tree Change the SRAM Structure?

**No — the SRAM structure stays the same.** Every node is always 60 bits with the same format. What changes:
- The **threshold values** (different circuits have different split points)
- The **left/right child addresses** (the tree shape differs)
- The **leaf values** (different optimal trim codes)
- The **number of nodes** used (up to 1024 max, since we have 10-bit addresses)

A depth-14 tree for circuit A might have 789 nodes. A depth-14 tree for circuit B might have 650 nodes. Both fit in the same 1024-entry SRAM — unused entries are simply never visited.

### 8.3 How Does Loading New Thresholds Work?

The config port has 4 signals:
```verilog
cfg_wr_en    → 1 bit:  "I want to write a node"
cfg_tree_sel → 1 bit:  "0 = write to pvtp tree, 1 = write to pvtn tree"
cfg_wr_addr  → 10 bits: "which node to write" (0 to 1023)
cfg_wr_data  → 60 bits: "the new node data"
```

**Writing one node takes 1 clock cycle.** To reprogram the entire pvtp tree (789 nodes), you need 789 clock cycles. At 100 MHz, that's **7.89 µs** — negligible.

### 8.4 Does This Need Extra IC Pins?

**No extra pins needed.** In a real SoC, this config port connects through an **existing bus** that already has pins:

```
Host CPU ──→ AXI/APB Bus (already exists) ──→ Config Port ──→ SRAM
```

The chip already has bus interfaces for register access. We just add this as another memory-mapped peripheral:
- Write to address `0x1000`: node 0 of pvtp tree
- Write to address `0x1001`: node 1 of pvtp tree
- etc.

**This adds zero extra IC pins.** The RTL just needs a small bus wrapper (AXI-Lite or APB slave), which is standard practice for any configurable IP block.

**Firmware at boot**: The microcontroller loads the `.hex` file from flash into SRAM. This happens once at power-up, before any transmission begins.

---

## 9. Results Summary

### 9.1 ML Model Accuracy (on 20% Unseen Test Data)

| Corner | pvtp Accuracy | pvtn Accuracy |
|--------|:---:|:---:|
| FF | 98.2% | 98.6% |
| SS | 97.9% | 99.2% |
| TT | 97.6% | 96.8% |
| FS | 97.8% | 99.4% |
| SF | 99.4% | 98.8% |
| **Overall** | **98.2%** | **98.6%** |

### 9.2 Resistance After ML-Predicted Compensation

![Resistance after compensation](plots/16_resistance_after_comp.png)

| Corner | Pull-Up R (mean, error) | Pull-Down R (mean, error) |
|--------|:---:|:---:|
| FF | 50.007Ω (0.007Ω error) | 49.957Ω (0.043Ω error) |
| SS | 50.123Ω (0.123Ω error) | 50.028Ω (0.028Ω error) |
| TT | 50.068Ω (0.068Ω error) | 50.035Ω (0.035Ω error) |
| FS | 50.202Ω (0.202Ω error) | 49.986Ω (0.014Ω error) |
| SF | 50.367Ω (0.367Ω error) | 49.982Ω (0.018Ω error) |

**All errors are in ohms.** The worst case (SF pull-up) is 0.367Ω off from 50Ω — that's only **0.7% error**, well within the typical ±3% spec.

### 9.3 Why Does Resistance "Move Around" 50Ω?

This is the **8-bit quantization effect**. Each trim code step changes resistance by approximately **0.2Ω** on average. Since trim codes are integers (you can't have trim = 62.3), the achievable resistances are discrete:
- trim=62 → 49.955Ω
- trim=63 → 49.612Ω

The model picks the nearest integer trim code, so the resistance will always be within ±0.2Ω of ideal, even with perfect prediction. This is inherent to the 8-bit resolution and cannot be improved without more trim bits.

### 9.4 Feature Importance — How is it Calculated?

The "feature importance" numbers come from scikit-learn's **Gini importance** (not correlation). When the Decision Tree is trained, each internal node splits on one feature. The importance of a feature is computed as:

```
importance(feature) = Σ (improvement in Gini impurity at nodes using this feature)
                      ÷ (total improvement across all nodes)
```

In simpler terms: **how much does each feature contribute to correctly classifying samples, across all nodes that use it?**

| Feature | pvtp Importance | pvtn Importance |
|---------|:---:|:---:|
| pmon_cmos_res | 43.5% | 46.9% |
| vreg | 30.1% | 25.8% |
| temperature | 26.4% | 27.3% |

All three features contribute significantly (~25–47%) — confirming the need for a 3-input design. Note: `vreg` has near-zero *linear correlation* with trim codes (-0.001), but **30% Gini importance** — the relationship is non-linear and conditional, which DTs capture but correlation misses.

### 9.5 RTL Simulation: 100% Pass

```
============================================================
  Decision Tree Trim Predictor — Testbench
  200 test vectors from held-out test set
============================================================
  pvtp: 200/200 PASS (0 FAIL) — Accuracy: 100%
  pvtn: 200/200 PASS (0 FAIL) — Accuracy: 100%
  Both correct: 200/200 — Combined: 100%
  Avg cycles per prediction: 22
  *** ALL TESTS PASSED — RTL matches Python model ***
============================================================
```

---

## 10. Hardware Cost: Traditional vs Our Approach

### 10.1 Traditional: External Precision Resistor Calibration

| Component | Cost / Impact |
|-----------|-------------|
| Extra IC pin | ~$0.01–0.05 per pin (package-dependent), plus ESD protection |
| 50Ω precision resistor on PCB | ~$0.02–0.10 per resistor |
| PCB area for resistor + trace | ~0.5mm² on PCB |
| Analog comparator on-chip | ~500–1,000 gates + careful analog design |
| Calibration FSM | ~200 gates |
| Calibration time | ~100–1000 clock cycles (successive approximation) |
| **On-chip area** | ~1,000–1,500 gates analog + digital |
| **Off-chip cost** | 1 extra pin + 1 PCB resistor **per product** |

**Key problem**: Every chip needs the external resistor. In high-volume production (millions of units), even $0.05/unit adds up. Also, the extra pin occupies valuable package space.

### 10.2 Our Approach: ML-Based Digital Predictor

| Component | Cost / Impact |
|-----------|-------------|
| 29-bit comparators | 2 × ~100 gates = **200 gates** |
| 3:1 MUX (29-bit) | 2 × ~90 gates = **180 gates** |
| FSM registers + control | 2 × ~75 gates = **150 gates** |
| Input latches (44-bit) | 2 × ~140 gates = **280 gates** |
| Done synchronization | **~20 gates** |
| Address + depth counters | 2 × ~45 gates = **90 gates** |
| **Logic total** | **~920 gates** |
| **SRAM** | 789 + 653 = 1,442 entries × 60 bits = **86,520 bits ≈ 10.6 KB** |
| **SRAM area (28nm)** | ~0.01–0.02 mm² |
| Extra IC pins | **ZERO** (uses existing bus interface) |
| PCB components | **ZERO** |
| Calibration time | **22 clock cycles** (~220ns at 100MHz) |

### 10.3 Comparison Summary

| Metric | Traditional | Our Approach |
|--------|:---:|:---:|
| Extra IC pins | 1 | **0** |
| PCB components | 1 resistor | **None** |
| On-chip gates | ~1,000–1,500 | **~920** |
| On-chip SRAM | 0 | 10.6 KB |
| Analog design needed | Yes (comparator) | **No (purely digital)** |
| Adapts to live PVT? | Yes (slower loop) | **Yes (22 cycles)** |
| Reusable for other circuits | No (fixed reference) | **Yes (SRAM reprogrammable)** |
| Per-unit BOM cost | $0.03–0.15 | **$0** |

**Bottom line**: We trade ~10 KB SRAM for eliminating an IC pin, a PCB component, and all analog design. In high-volume production, the savings per unit are small, but the elimination of analog circuitry and external components **greatly simplifies design and testing**, which is where the real cost savings are.

### 10.4 SRAM Size Calculation

```
pvtp tree:  789 nodes × 60 bits each = 47,340 bits = 5,917 bytes ≈ 5.78 KB
pvtn tree:  653 nodes × 60 bits each = 39,180 bits = 4,898 bytes ≈ 4.78 KB
Total SRAM: 1,442 nodes × 60 bits    = 86,520 bits = 10,815 bytes ≈ 10.56 KB
```

In 28nm CMOS, 10.6 KB SRAM takes approximately **0.01–0.02 mm²**, which is negligible compared to the core transmitter circuit.

---

## 11. How to Run

### 11.1 Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| **Python** | 3.8+ | ML pipeline, model export |
| **pip packages** | pandas, numpy, scikit-learn, matplotlib, openpyxl | Data processing and ML |
| **Icarus Verilog (iverilog)** | 12.0+ | Verilog simulation |
| **GTKWave** | 3.3+ | Waveform viewing (optional) |

```bash
pip install pandas numpy scikit-learn matplotlib openpyxl
```

### 11.2 Run the ML Pipeline

```bash
cd mixer

# Step 1: Visualize the data (generates 16 plots in plots/)
python ml/visualize_pvt_data.py

# Step 2: Compare models — DT, RF, Poly, LUT (Plot 11, 12)
python ml/model_comparison.py

# Step 3: Train the final depth=14 model with 3 inputs
python ml/final_model.py

# Step 4: Full pipeline with all preprocessing analysis
python ml/ml_pipeline.py
```

### 11.3 Export Model to Verilog

```bash
# Converts trained .pkl models → hex files for RTL SRAM initialization
python scripts/export_tree_to_rom.py
```

This generates:
- `rtl/pvtp_tree.hex` — 789 SRAM entries for pvtp tree
- `rtl/pvtn_tree.hex` — 653 SRAM entries for pvtn tree
- `rtl/test_vectors.hex` — 200 test vectors from held-out data

### 11.4 Run RTL Simulation

```bash
cd rtl

# Compile all Verilog files
iverilog -g2005 -o tb_sim.vvp tree_traversal_fsm.v dt_trim_predictor.v tb_dt_trim_predictor.v

# Run the simulation
vvp tb_sim.vvp
```

**Expected output:**
```
  pvtp: 200/200 PASS (0 FAIL) — Accuracy: 100%
  pvtn: 200/200 PASS (0 FAIL) — Accuracy: 100%
  *** ALL TESTS PASSED — RTL matches Python model ***
```

### 11.5 View Waveforms in GTKWave

```bash
cd rtl
gtkwave waveform.vcd
```

**How to use GTKWave:**
1. In the **left panel**, expand the module hierarchy (`tb_dt_trim_predictor` → `dut`)
2. **Select signals** and drag to the wave display:
   - `clk`, `rst_n`, `start`, `done` — control signals
   - `pvtp_out[7:0]`, `pvtn_out[7:0]` — predicted trim codes
   - `dut.u_pvtp_tree.state[1:0]` — FSM state (0=IDLE, 1=FETCH, 2=COMPARE)
   - `dut.u_pvtp_tree.node_addr[9:0]` — which tree node is being visited
3. **Zoom**: Ctrl + mouse scroll
4. **Measure timing**: Click to place markers, measure cycles between `start` and `done`

---

## 12. Project Structure

```
50ohm_driver/
│
├── README.md                              ← You are here
│
├── data/                                  # Dataset
│   └── TSMC28nm_DRV_ML_*.xlsx            # Source Cadence simulation data
│
├── ml/                                    # ML Pipeline
│   ├── visualize_pvt_data.py              # Data exploration (16 plots)
│   ├── model_comparison.py                # DT vs RF vs Poly vs LUT (1-input)
│   ├── final_model.py                     # Final 3-input depth=14 model
│   ├── ml_pipeline.py                     # Complete pipeline with metrics
│   ├── best_model_pvtp_d14.pkl            # Trained pvtp model (depth=14)
│   └── best_model_pvtn_d14.pkl            # Trained pvtn model (depth=14)
│
├── rtl/                                   # RTL Implementation
│   ├── tree_traversal_fsm.v               # Reusable FSM engine (core IP)
│   ├── dt_trim_predictor.v                # Top-level module
│   ├── dummy_sensors.v                    # PVT sensor stub for simulation
│   ├── tb_dt_trim_predictor.v             # Testbench (200 vectors + VCD)
│   ├── pvtp_tree.hex                      # SRAM init: pvtp (789 nodes)
│   ├── pvtn_tree.hex                      # SRAM init: pvtn (653 nodes)
│   ├── test_vectors.hex                   # 200 test vectors
│   └── zynq_vio_ila/                      # FPGA integration (Zedboard)
│
├── netlist/                               # Cadence Netlist & OCEAN scripts
│   ├── netlist.txt                        # Main Spectre netlist
│   ├── oceanscript.onc                    # OCEAN script
│   └── ontimereduction.onc                # On-time reduction script
│
├── scripts/                               # Automation & Analysis
│   ├── export_tree_to_rom.py              # Python model → Verilog hex export
│   ├── generate_ocean_batch.py            # OCEAN batch generator
│   ├── auto_sweep.py                      # Automated PVT sweep (SSH)
│   ├── pvt_sweep.py                       # PVT sweep controller
│   └── validate_pvt_cadence.py            # PVT validation against Cadence
│
├── plots/                                 # All generated visualization plots
│   ├── 01 - 10: Data exploration
│   ├── 11 - 12: Model comparison (1-input)
│   ├── 13 - 14: Depth sweep & per-corner (3-input)
│   └── 15 - 16: Final comparison & resistance
│
├── results/                               # Cadence simulation results
│   └── results_*_batch*.csv               # Per-corner batch results
│
├── references/                            # Reference papers
│
├── docs/                                  # Documentation
│   ├── walkthrough.md                     # Complete setup guide
│   ├── knowledge.md                       # Virtuoso integration notes
│   └── Plot_Explanations.md              # Plot explanations
│
└── ASIC_Submission/                       # Self-contained ASIC delivery package
```

---

## 13. Is This Work Worth It?

### For the End-User (Chip Buyer)

| Benefit | Impact |
|---------|--------|
| Eliminates external resistor | Saves $0.03–0.15 per unit BOM cost |
| Eliminates 1 IC pin | Saves package area or frees pin for other use |
| Faster calibration | 22 cycles vs 100–1000 cycles for analog loop |
| No analog design risk | Purely digital = easier to port to new nodes |
| Adapts to live PVT | Continuous compensation, not just power-up |

### For the Academic/Research Community

| Novelty | Why It Matters |
|---------|---------------|
| ML-based impedance prediction | First to show DT can replace analog calibration with 98%+ accuracy |
| Hardware-efficient implementation | FSM traversal with ~920 gates (smaller than prior NN approaches) |
| SRAM-configurable IP | Reusable across circuits — no re-tapeout |
| Complete ML-to-RTL pipeline | Reproducible from Python model to verified Verilog |
| Extensive PVT coverage | 5 corners × 10V × 329T = comprehensive validation |

### Does It Reduce Overall Cost?

**Yes**, in two ways:
1. **Direct savings**: No external resistor, no extra pin, no analog design effort
2. **Indirect savings**: Purely digital design is easier to verify, easier to port to new process nodes (you just retrain the model), and eliminates analog process dependencies

The 10.6 KB SRAM cost is the trade-off — but modern 28nm SoCs have megabytes of SRAM for caches; 10 KB is insignificant.

**Target publications**: IEEE TCAS-II, IEEE TVLSI, or conferences like ISCAS, VLSI-DAT.

---

*Built with scikit-learn (Python) + Icarus Verilog — no proprietary tools required for ML training or functional verification.*
