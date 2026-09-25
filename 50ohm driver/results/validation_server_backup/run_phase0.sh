#!/bin/bash
# ==============================================================================
# run_phase0.sh
# ==============================================================================
# Phase 0: Model File Discrimination Benchmark
# Runs both crn28hpcp_2d5 and crn28hpcp_1d8 on 5 identical test cases across corners,
# compares results against Excel ground truth, and identifies the correct model file.
# ==============================================================================

RESULTS_DIR="ocean_results"
LOG_DIR="phase0_logs"
mkdir -p "$RESULTS_DIR" "$LOG_DIR"

echo "================================================================="
echo " STARTING PHASE 0: MODEL FILE DISCRIMINATION BENCHMARK"
echo "================================================================="
echo "Comparing crn28hpcp_2d5 vs crn28hpcp_1d8 against Excel ground truth"
echo ""

# Run 2d5 and 1d8 in parallel
echo "[1/2] Launching run_phase0_2d5.ocn..."
ocean -nograph -restore validation_generated/phase0/run_phase0_2d5.ocn > "$LOG_DIR/phase0_2d5.log" 2>&1 &
pid_2d5=$!

echo "[2/2] Launching run_phase0_1d8.ocn..."
ocean -nograph -restore validation_generated/phase0/run_phase0_1d8.ocn > "$LOG_DIR/phase0_1d8.log" 2>&1 &
pid_1d8=$!

echo ""
echo "Both benchmark jobs running in background (PIDs: $pid_2d5, $pid_1d8)."
echo "Waiting for simulations to complete (~5-8 minutes at t=275ns)..."

wait $pid_2d5
echo ">>> crn28hpcp_2d5 run finished."

wait $pid_1d8
echo ">>> crn28hpcp_1d8 run finished."

echo ""
echo "================================================================="
echo " EVALUATING RESULTS AGAINST EXCEL GROUND TRUTH"
echo "================================================================="

if [ -f "results_phase0_2d5.csv" ] && [ -f "results_phase0_1d8.csv" ]; then
    python compare_phase0.py
else
    echo "ERROR: Result CSVs not found! Check logs in $LOG_DIR/"
fi
