#!/bin/bash
# ==============================================================================
# run_4_jobs_parallel.sh
# Runs 4 parallel OCEAN simulation jobs in isolated subdirectories (zero lock clashes).
# Total Runtime: ~25 to 30 seconds for all 80 simulations!
# ==============================================================================

echo "================================================================="
echo " LAUNCHING 4 PARALLEL JOBS FOR 80 MISMATCHES (TT, FF, SS)"
echo " PDK Model: 1.8V (crn28hpcp_1d8_elk...)"
echo " Timestamp: $(date)"
echo "================================================================="

# ------------------------------------------------------------------------------
# AUTOMATIC CLEANUP TRAP:
# Guarantees that all child Cadence, OCEAN, Virtuoso, and Spectre processes
# are cleanly terminated when the script exits, even with nohup or disconnect.
# ------------------------------------------------------------------------------
cleanup() {
    echo ""
    echo ">>> [CLEANUP] Stopping any remaining OCEAN / Spectre child processes..."
    for p in $PID_1 $PID_2 $PID_3 $PID_4; do
        if [ -n "$p" ] && kill -0 "$p" 2>/dev/null; then
            kill -9 "$p" 2>/dev/null
        fi
    done
    pkill -P $$ 2>/dev/null
    pkill -u "$USER" -9 -f "spectre|virtuoso|ocean|cdsXvfb" 2>/dev/null
    echo ">>> [CLEANUP] Done. Server resources 100% freed!"
}
trap cleanup EXIT SIGINT SIGTERM SIGHUP

SCRIPT_DIR=$(pwd)
mkdir -p logs_parallel

echo ">>> [1/4] Starting Job 1: TT (Part 1, 19 cases) in background..."
(cd job1_TT_pt1 && ocean -nograph < job1_TT_pt1.ocn > "$SCRIPT_DIR/logs_parallel/job1.log" 2>&1) &
PID_1=$!

echo ">>> [2/4] Starting Job 2: TT (Part 2, 19 cases) in background..."
(cd job2_TT_pt2 && ocean -nograph < job2_TT_pt2.ocn > "$SCRIPT_DIR/logs_parallel/job2.log" 2>&1) &
PID_2=$!

echo ">>> [3/4] Starting Job 3: FF (21 cases) in background..."
(cd job3_FF && ocean -nograph < job3_FF.ocn > "$SCRIPT_DIR/logs_parallel/job3.log" 2>&1) &
PID_3=$!

echo ">>> [4/4] Starting Job 4: SS (21 cases) in background..."
(cd job4_SS && ocean -nograph < job4_SS.ocn > "$SCRIPT_DIR/logs_parallel/job4.log" 2>&1) &
PID_4=$!

echo ""
echo ">>> All 4 parallel jobs spawned! Waiting for completion (~25 seconds)..."
wait $PID_1
echo ">>> Job 1 (TT part 1) finished."
wait $PID_2
echo ">>> Job 2 (TT part 2) finished."
wait $PID_3
echo ">>> Job 3 (FF) finished."
wait $PID_4
echo ">>> Job 4 (SS) finished."

echo ""
echo "================================================================="
echo " MERGING CSVs AND EVALUATING ALL 80 SIMULATION RESULTS..."
echo "================================================================="
cp job1_TT_pt1/results_job1_TT_pt1.csv .
cp job2_TT_pt2/results_job2_TT_pt2.csv .
cp job3_FF/results_job3_FF.csv .
cp job4_SS/results_job4_SS.csv .

python compare_80_fast.py
