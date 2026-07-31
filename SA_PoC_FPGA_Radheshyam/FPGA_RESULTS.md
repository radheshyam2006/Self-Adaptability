# FPGA Prototyping Results — Zynq-7000 ZedBoard

## What Was Validated
**Digital inference engine only** — no analog circuits or real PVT sensors.
VIO (Virtual I/O) debug cores substitute for on-chip sensors by injecting
test vectors via USB-JTAG.

## Platform
- **Board**: Digilent ZedBoard
- **FPGA**: Xilinx Zynq-7000 (xc7z020clg484-1)
- **Tool**: Vivado v2025.2 (win64)
- **Clock**: 200 MHz LVDS → IBUFDS → BUFR ÷2 → **100 MHz logic clock**
- **Date**: May 11, 2026

## Resource Utilization (Post-Implementation)

| Resource         | Used   | Available | Util (%) | Notes |
|------------------|--------|-----------|----------|-------|
| Slice LUTs       | 2,087  | 53,200    | 3.92     | Includes VIO+ILA overhead |
| └ LUT as Logic   | 1,348  | 53,200    | 2.53     | DT predictor core logic |
| └ LUT as ShiftReg| 424    | 17,400    | 2.44     | VIO/ILA shift registers |
| Slice Registers  | 3,714  | 106,400   | 3.49     | Includes VIO+ILA FFs |
| Block RAM (36Kb) | 10     | 140       | 7.14     | pvtp + pvtn tree data |
| Block RAM (18Kb) | 1      | 280       | 0.36     | |
| **DSP Blocks**   | **0**  | 220       | **0.00** | **Zero multipliers confirmed** |

## Timing
| Metric | Value |
|--------|-------|
| Worst Negative Slack (WNS) | **2.770 ns** |
| Worst Hold Slack (WHS) | 0.039 ns |
| Total Failing Endpoints | **0** |
| Target Clock Period | 10.0 ns (100 MHz) |
| Estimated Fmax | **≈138 MHz** |
| Prediction Latency (worst) | 28 cycles = 280 ns |

## VIO Test Result

| Probe | Signal | Value | Hex |
|-------|--------|-------|-----|
| probe_out0 | pmon_in | 50,000 | 0x0000C350 |
| probe_out1 | vreg_in | 10 | 0x0A |
| probe_out2 | temp_in | 200 | 0xC8 |
| probe_out3 | start | 1→0 | pulse |
| **probe_in0** | **pvtp_out** | **249** | **0x00F9** |
| **probe_in1** | **pvtn_out** | **249** | **0x00F9** |
| probe_in2 | done | 1 | asserted |

**LED Display**: LD7-LD0 = **1111 1001** = 0xF9 (pvtp_out[7:0])

## Missing (Board Not Connected)
- [ ] VIO dashboard screenshot from Vivado Hardware Manager
- [ ] ILA waveform capture showing FSM traversal at 100 MHz
