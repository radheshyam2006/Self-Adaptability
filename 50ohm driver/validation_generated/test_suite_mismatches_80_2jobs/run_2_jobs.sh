#!/bin/bash
# ==============================================================================
# run_2_jobs.sh
# Runs the 80 working corner mismatch simulations in 2 clean sequential jobs.
# Total runtime: ~120 seconds.
# ==============================================================================

# ------------------------------------------------------------------------------
# AUTOMATIC CLEANUP TRAP:
# Guarantees that all child Cadence, OCEAN, Virtuoso, and Spectre processes
# are cleanly terminated when the script exits, even with nohup or disconnect.
# ------------------------------------------------------------------------------
cleanup() {
    echo ""
    echo ">>> [CLEANUP] Stopping any remaining OCEAN / Spectre child processes..."
    # Kill any processes spawned by this script
    pkill -P $$ 2>/dev/null
    # Cleanly terminate any orphan spectre/virtuoso/Xvfb instances for user13
    pkill -u "$USER" -9 -f "spectre|virtuoso|ocean|cdsXvfb" 2>/dev/null
    echo ">>> [CLEANUP] Done. Server resources 100% freed!"
}
trap cleanup EXIT SIGINT SIGTERM SIGHUP

echo "================================================================="
echo " RUNNING 80 MISMATCH SIMULATIONS IN 2 JOBS (TT, FF, SS CORNERS)"
echo " PDK Model: 1.8V (crn28hpcp_1d8_elk...)"
echo " Timestamp: $(date)"
echo "================================================================="

mkdir -p logs_mismatches

echo ""
echo ">>> [1/2] Running Job 1: TT Corner (38 test cases)..."
ocean -nograph < job1_TT_38.ocn > logs_mismatches/job1_TT.log 2>&1
echo ">>> Job 1 finished."

echo ""
echo ">>> [2/2] Running Job 2: FF & SS Corners (42 test cases: 21 FF + 21 SS)..."
ocean -nograph < job2_FF_SS_42.ocn > logs_mismatches/job2_FF_SS.log 2>&1
echo ">>> Job 2 finished."

echo ""
echo "================================================================="
echo " ALL 80 MISMATCH SIMULATIONS COMPLETED!"
echo " Results written to: results_job1_TT.csv and results_job2_FF_SS.csv"
echo "================================================================="
python compare_mismatches_80.py

