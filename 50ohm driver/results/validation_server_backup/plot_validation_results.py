#!/usr/bin/env python3
"""
plot_validation_results.py
==========================
Generates a visual validation report showing:
 - ML-predicted trim codes vs Cadence-expected trim codes
 - Simulated resistance vs target 50 ohm
 - Error bar chart per corner

Run after you have the Spectre simulation results.
Fill in the RESULTS section below with measured resistance from OCEAN output.
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import os

# ─────────────────────────────────────────────────────────────────────────────
# RESULTS — Fill this in after running extract_resistance.ocn on the server
# Set R_measured to None if you don't have results yet
# ─────────────────────────────────────────────────────────────────────────────

results = [
    {
        "label":       "FF\nvreg=0.81V\ntem=-40°C",
        "corner":      "FF",
        "pvtp_ml":     13,
        "pvtn_ml":     13,
        "pvtp_bits":   "00001101",
        "pvtn_bits":   "00001101",
        "R_pu_exp":    50.22,     # Pull-Up expected (ohms)
        "R_pd_exp":    50.30,     # Pull-Down expected (ohms)
        "R_pu_meas":   None,      # To be filled from ocean script output
        "R_pd_meas":   None,
    },
    {
        "label":       "SS\nvreg=0.81V\ntem=-40°C",
        "corner":      "SS",
        "pvtp_ml":     249,
        "pvtn_ml":     248,
        "pvtp_bits":   "11111001",
        "pvtn_bits":   "11111000",
        "R_pu_exp":    49.72,
        "R_pd_exp":    50.15,
        "R_pu_meas":   None,
        "R_pd_meas":   None,
    },
    {
        "label":       "TT\nvreg=0.81V\ntem=-40°C",
        "corner":      "TT",
        "pvtp_ml":     31,
        "pvtn_ml":     31,
        "pvtp_bits":   "00011111",
        "pvtn_bits":   "00011111",
        "R_pu_exp":    49.33,
        "R_pd_exp":    49.62,
        "R_pu_meas":   None,
        "R_pd_meas":   None,
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# If R_pu_meas is None for all, we show only the prediction table
# and a preview of what the plot will look like
# ─────────────────────────────────────────────────────────────────────────────

CORNER_COLORS = {"FF": "#3B82F6", "SS": "#EF4444", "TT": "#10B981"}
TARGET_R = 50.0
TOLERANCE_PCT = 3.0  # ±3% tolerance band

has_measured = any(r["R_pu_meas"] is not None for r in results)

# ─────────────────────────────────────────────────────────────────────────────
# Build figure
# ─────────────────────────────────────────────────────────────────────────────

fig = plt.figure(figsize=(16, 12), facecolor="#0F172A")
fig.suptitle(
    "ML-Based PVT Compensation Validation — 50Ω TX Driver (Pull-Up & Pull-Down)",
    fontsize=18, fontweight="bold", color="white", y=0.97
)

gs = fig.add_gridspec(2, 2, hspace=0.45, wspace=0.35,
                       left=0.08, right=0.97, top=0.90, bottom=0.08)

ax_resist  = fig.add_subplot(gs[0, :])   # full-width top: resistance comparison
ax_trim    = fig.add_subplot(gs[1, 0])   # bottom-left:  trim codes
ax_error   = fig.add_subplot(gs[1, 1])   # bottom-right: error %

PANEL_BG  = "#1E293B"
TEXT_COLOR = "#E2E8F0"
GRID_COLOR = "#334155"

for ax in [ax_resist, ax_trim, ax_error]:
    ax.set_facecolor(PANEL_BG)
    ax.tick_params(colors=TEXT_COLOR, labelsize=10)
    ax.xaxis.label.set_color(TEXT_COLOR)
    ax.yaxis.label.set_color(TEXT_COLOR)
    ax.title.set_color(TEXT_COLOR)
    for spine in ax.spines.values():
        spine.set_edgecolor(GRID_COLOR)
    ax.grid(True, color=GRID_COLOR, linewidth=0.5, alpha=0.7)

labels = [r["label"] for r in results]
x      = np.arange(len(results))
width  = 0.20

# ─── Panel 1: Resistance comparison (PU and PD) ──────────────────────────────
R_pu_exp = [r["R_pu_exp"] for r in results]
R_pd_exp = [r["R_pd_exp"] for r in results]

bars_pu = ax_resist.bar(x - width, R_pu_exp, width,
                         color="#818CF8", alpha=0.9,
                         label="Pull-Up R (Expected)",
                         edgecolor="white", linewidth=0.5)

bars_pd = ax_resist.bar(x, R_pd_exp, width,
                         color="#34D399", alpha=0.9,
                         label="Pull-Down R (Expected)",
                         edgecolor="white", linewidth=0.5)

if has_measured:
    R_pu_m = [r["R_pu_meas"] if r["R_pu_meas"] is not None else 0.0 for r in results]
    R_pd_m = [r["R_pd_meas"] if r["R_pd_meas"] is not None else 0.0 for r in results]
    ax_resist.bar(x + width, R_pu_m, width, color="#818CF8", alpha=0.4,
                  label="Pull-Up R (Simulated)", hatch="//", edgecolor="white")
    ax_resist.bar(x + 2*width, R_pd_m, width, color="#34D399", alpha=0.4,
                  label="Pull-Down R (Simulated)", hatch="//", edgecolor="white")
else:
    ax_resist.text(0.5, 0.5,
                    "Run OCEAN script on server to extract simulated R_pu & R_pd",
                    transform=ax_resist.transAxes,
                    ha="center", va="center", fontsize=13,
                    color="#FBBF24", alpha=0.8,
                    bbox=dict(facecolor="#1E293B", edgecolor="#FBBF24", boxstyle="round,pad=0.5"))

# Target 50Ω line and tolerance band
ax_resist.axhline(TARGET_R, color="#F59E0B", linewidth=2,
                   linestyle="--", label="50Ω target", zorder=5)
tol = TARGET_R * TOLERANCE_PCT / 100
ax_resist.axhspan(TARGET_R - tol, TARGET_R + tol, alpha=0.12,
                   color="#F59E0B", label=f"±{TOLERANCE_PCT}% band")

for bar, val in zip(bars_pu, R_pu_exp):
    ax_resist.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1,
                    f"PU:{val:.2f}Ω", ha="center", va="bottom",
                    color="white", fontsize=8.5, fontweight="bold")
for bar, val in zip(bars_pd, R_pd_exp):
    ax_resist.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1,
                    f"PD:{val:.2f}Ω", ha="center", va="bottom",
                    color="white", fontsize=8.5, fontweight="bold")

ax_resist.set_xticks(x)
ax_resist.set_xticklabels(labels, fontsize=11)
ax_resist.set_ylabel("Resistance (Ω)", fontsize=12)
ax_resist.set_title("Pull-Up & Pull-Down Resistance vs 50Ω Target", fontsize=13, fontweight="bold")
ax_resist.set_ylim(45, 55)
ax_resist.legend(loc="upper right", facecolor=PANEL_BG, edgecolor=GRID_COLOR, labelcolor=TEXT_COLOR, fontsize=9)

# ─── Panel 2: Trim code comparison ───────────────────────────────────────────
pvtp_vals = [r["pvtp_ml"] for r in results]
pvtn_vals = [r["pvtn_ml"] for r in results]

b1 = ax_trim.bar(x - width, pvtp_vals, width*1.5, color="#818CF8", alpha=0.9,
                  label="pvtp (Pull-Up trim)", edgecolor="white", linewidth=0.5)
b2 = ax_trim.bar(x + width, pvtn_vals, width*1.5, color="#34D399", alpha=0.9,
                  label="pvtn (Pull-Down trim)", edgecolor="white", linewidth=0.5)

for bar, val in zip(b1, pvtp_vals):
    ax_trim.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 2,
                  str(val), ha="center", va="bottom", color="white", fontsize=10, fontweight="bold")
for bar, val in zip(b2, pvtn_vals):
    ax_trim.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 2,
                  str(val), ha="center", va="bottom", color="white", fontsize=10, fontweight="bold")

ax_trim.set_xticks(x)
ax_trim.set_xticklabels([r["corner"] for r in results], fontsize=12)
ax_trim.set_ylabel("Trim Code (0–255)", fontsize=12)
ax_trim.set_title("ML-Predicted Trim Codes (pvtp & pvtn)", fontsize=13, fontweight="bold")
ax_trim.set_ylim(0, 280)
ax_trim.legend(facecolor=PANEL_BG, edgecolor=GRID_COLOR, labelcolor=TEXT_COLOR, fontsize=9)

# ─── Panel 3: Error % chart ───────────────────────────────────────────────────
err_pu = [abs(r["R_pu_exp"] - TARGET_R) / TARGET_R * 100 for r in results]
err_pd = [abs(r["R_pd_exp"] - TARGET_R) / TARGET_R * 100 for r in results]

ax_error.bar(x - width, err_pu, width*1.5, color="#818CF8", alpha=0.85, label="Pull-Up Error %")
ax_error.bar(x + width, err_pd, width*1.5, color="#34D399", alpha=0.85, label="Pull-Down Error %")
ax_error.axhline(TOLERANCE_PCT, color="#F59E0B", linewidth=2, linestyle="--", label=f"{TOLERANCE_PCT}% Spec Limit")

ax_error.set_xticks(x)
ax_error.set_xticklabels([r["corner"] for r in results], fontsize=12)
ax_error.set_ylabel("Error from 50Ω (%)", fontsize=12)
ax_error.set_title("Resistance Deviation from 50Ω Spec", fontsize=13, fontweight="bold")
ax_error.set_ylim(0, 3.5)
ax_error.legend(facecolor=PANEL_BG, edgecolor=GRID_COLOR, labelcolor=TEXT_COLOR, fontsize=9)

# ─── Save figure ──────────────────────────────────────────────────────────────
out_dir  = os.path.join(os.path.dirname(__file__), "..", "plots")
os.makedirs(out_dir, exist_ok=True)
out_path = os.path.join(out_dir, "17_pvt_validation_results.png")
fig.savefig(out_path, dpi=150, bbox_inches="tight", facecolor="#0F172A")
plt.close()
print(f"Updated plot saved: {out_path}")

