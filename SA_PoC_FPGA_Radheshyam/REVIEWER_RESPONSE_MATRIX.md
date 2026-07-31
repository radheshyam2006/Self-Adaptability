# Reviewer Critique → Paper Response Matrix

This document maps EVERY reviewer comment and question to where it's addressed in the paper.

---

## CRITICAL Issues (C1-C3)

### C1. No closed-loop circuit validation
> "The authors claim their predicted trim codes are correct, but never verify that applying them to the actual circuit produces the desired output voltage/impedance."

**STATUS: ✅ ADDRESSED**
- **Section VII** (Cadence Closed-Loop Validation) — full section dedicated to this
- Table VIII shows ±0.73% impedance error across 5 process corners
- Fig. 8 shows resistance after compensation
- **Limitation L4** acknowledges subset coverage (not full 82,250 points)

### C2. Why Decision Trees? Not rigorous.
> "No analysis of WHY the data is well-suited for DTs from a mathematical/physical perspective."

**STATUS: ✅ ADDRESSED**
- **Section III-A** (Physical Justification) — formal math: T: R³ → Z⁺ piecewise-constant
- DT indicator function formula: T̂(x) = Σ cⱼ · 1[x ∈ Rⱼ]
- k-NN comparison (440KB memory, O(N) inference)
- Piecewise-linear comparison (needs multipliers, mismatched for discontinuous data)
- Noise robustness argument
- Fig. 4 shows staircase heatmaps as visual evidence

### C3. Fabricated references
> "References [3] and [4] do not appear in IEEE Xplore."

**STATUS: ✅ FIXED**
- Old [ml_analog_survey] → Replaced with **Li et al., TCAS-I 2024** (real, verified)
- Old [ml_pvt_comp] → Replaced with **Onabajo, IEEE Open J. CAS 2023** (real, verified)
- Added **Liu et al., JSSC 2013** (self-healing circuits, real)
- All 12 references are now verified real publications

---

## MAJOR Issues (M1-M5)

### M1. No synthesis results (~920 gates is a guess)
> "The authors claim ~920 gates but provide no synthesis report."

**STATUS: ✅ PARTIALLY ADDRESSED**
- **Section VI** provides real FPGA synthesis numbers (2,087 LUTs, 0 DSPs, timing closure)
- **Gate count breakdown** paragraph in Section VIII gives component-level estimate
- **Limitation L5** explicitly acknowledges no ASIC post-layout results
- Future work: Synopsys DC / Cadence Innovus synthesis planned

### M2. Novelty vs. Struharik 2009
> "How is this work different from existing DT IP cores?"

**STATUS: ✅ ADDRESSED**
- **"Novelty vs. prior DT hardware"** paragraph in Section VIII
- Three differentiators: (i) new application domain, (ii) heterogeneous sensor encoding, (iii) validated on real Cadence circuit data

### M3. Only 200 test vectors
> "Why not test on the full holdout set?"

**STATUS: ✅ ADDRESSED**
- Paragraph after Table VI explains: 200 limited by hex file capacity
- Full Python test on 2,772 (BGR) and 16,450 (driver) reported in Table VII
- **Limitation L10** explicitly acknowledges and suggests mitigation

### M4. No error analysis on mismatches
> "What is the circuit-level impact of the 1 FAIL?"

**STATUS: ✅ ADDRESSED**
- Paragraph after Table VI: "expected trim code was 38, predicted was 39. Both values produce V_BGR within 0.5 mV of each other—functionally equivalent."

### M5. Temperature encoding inconsistency
> "BGR uses k=2 (9-bit), driver uses k=4 (10-bit). Why?"

**STATUS: ✅ ADDRESSED**
- **Limitation L9** explains: driver requires finer temperature resolution due to sharper impedance-vs-temperature sensitivity

---

## MINOR Issues (m1-m5)

### m1. No circuit schematic shown
**STATUS: 🟡 PLACEHOLDER ADDED (TODO L77, L88)**
- Commented-out figure blocks ready for BGR and Driver schematics
- User needs to draw in PowerPoint/draw.io

### m2. Architecture diagram is LaTeX \picture
**STATUS: 🟡 PLACEHOLDER ADDED (TODO L222)**
- TODO comment added to upgrade FSM diagram
- Current \picture version still functional for draft

### m3. "Proof of Concept" in the title
**STATUS: ✅ FIXED**
- Title changed to "Architecture, FPGA Validation, and Cadence Verification"
- No more "Proof of Concept" language anywhere

### m4. Page budget (TCAS-II was 5 pages)
**STATUS: ✅ RESOLVED**
- Now targeting TCAS-I Regular Papers (9-14 pages)
- Current: 6 pages text + 3 figures = ~7 pages
- With 6 planned figures: will reach 9-10 pages ✓

### m5. Some tables have too many rows
**STATUS: ✅ ADDRESSED**
- Gate count is now a paragraph, not a table
- Tables are lean and necessary

---

## Reviewer Questions (Q1-Q5)

### Q1. How does the DT handle unseen PVT corners?
**STATUS: ✅ ADDRESSED → Limitation L7**
- DT outputs nearest partition's trim code
- ±1 trim code error possible at boundaries
- Finer PVT grid mitigates this

### Q2. Why not k-NN or piecewise-linear?
**STATUS: ✅ ADDRESSED → Section III-A**
- k-NN: 440KB memory, O(N) multiplier-heavy inference
- Piecewise-linear: needs multipliers, mismatched for discontinuous integer data

### Q3. What happens if sensor readings are noisy?
**STATUS: ✅ ADDRESSED → Advantage (g) + Section III-A**
- DT has finite-width constant regions → noise within region doesn't change output
- Only boundary crossings cause changes

### Q4. Power consumption of ROM reads?
**STATUS: ✅ ADDRESSED → Limitation L8**
- Dynamic: <1 mW per inference
- Static (FPGA BRAM leakage): ~5-10 mW
- ASIC SRAM would be significantly lower

### Q5. How does this scale to 16/32-bit trim codes?
**STATUS: ✅ ADDRESSED → Limitation L3**
- ROM grows O(2^depth) worst case
- 16-bit would need deeper trees → >100KB ROM
- Practical trim (4-8 bits) works fine with <11KB

---

## ALL 10 Limitations in Paper (L1-L10)

| # | Limitation | Reviewer Source | Mitigation |
|---|-----------|----------------|------------|
| L1 | Sensor dependency | Q1 (general) | Standard in SoCs; live sensor integration as future work |
| L2 | Training data ≠ silicon | General | Post-silicon validation with fabricated chips |
| L3 | ROM scaling | Q5 | Pruning, quantized thresholds, or ensemble compression |
| L4 | Limited closed-loop coverage | C1 | Automated Spectre sweeps (senior's framework) |
| L5 | No ASIC post-layout | M1 | Synopsys DC / Innovus synthesis planned |
| L6 | Static model (ROM fixed) | General | SRAM-based updateable model |
| L7 | Unseen PVT corners | Q1 | Finer PVT grid during training |
| L8 | ROM power consumption | Q4 | ASIC SRAM + power gating |
| L9 | Temp encoding inconsistency | M5 | Unified encoding scheme |
| L10 | Limited RTL test vectors | M3 | Larger hex file or file I/O testbench |

---

## BONUS: Fabrication Cost Note
Added in paper (after L10): MPW costs for TSMC 28nm are $15,000-30,000/mm² via MUSE/Europractice. DT engine adds <0.01 mm² overhead.
