#!/bin/bash
# ==============================================================================
# run_overnight.sh
# ==============================================================================
# Fully automated overnight execution for Phase 0 and Phase 1.
# - Runs Phase 0 (2d5 vs 1d8 model file benchmark)
# - Compares against Excel ground truth & identifies winner
# - Automatically switches Phase 1 scripts to the winning model
# - Runs Phase 1 across all 5 corners (25 simulations) with 5 parallel jobs
# - Flushes all CSVs and logs a final summary
# ==============================================================================

LOG_DIR="overnight_logs"
mkdir -p "$LOG_DIR" "ocean_results_phase0_2d5" "ocean_results_phase0_1d8"

OVERNIGHT_LOG="$LOG_DIR/master_overnight.log"
exec > >(tee -a "$OVERNIGHT_LOG") 2>&1

echo "================================================================="
echo " STARTING OVERNIGHT RUN: PHASE 0 + PHASE 1"
echo " Timestamp: $(date)"
echo "================================================================="

# ------------------------------------------------------------------------------
# STEP 1: RUN PHASE 0 BENCHMARK (10 sims: 5 with 2d5, 5 with 1d8)
# ------------------------------------------------------------------------------
echo ""
echo ">>> STEP 1: Running Phase 0 Benchmark (sequentially to prevent netlist collision)..."

echo "Running Phase 0 (crn28hpcp_2d5, ~1.5 min)..."
ocean -nograph -restore validation_generated/phase0/run_phase0_2d5.ocn > "$LOG_DIR/phase0_2d5.log" 2>&1
echo ">>> Phase 0 (2d5) finished."

echo "Running Phase 0 (crn28hpcp_1d8, ~1.5 min)..."
ocean -nograph -restore validation_generated/phase0/run_phase0_1d8.ocn > "$LOG_DIR/phase0_1d8.log" 2>&1
echo ">>> Phase 0 (1d8) finished."

# ------------------------------------------------------------------------------
# STEP 2: EVALUATE WINNING MODEL
# ------------------------------------------------------------------------------
echo ""
echo ">>> STEP 2: Evaluating Phase 0 Results against Excel Ground Truth..."
python compare_phase0.py

WINNER="2d5"
if [ -f "active_model.conf" ]; then
    WINNER=$(grep "MODEL_TAG=" active_model.conf | cut -d'=' -f2)
fi
echo ">>> Winning Model File for subsequent phases: crn28hpcp_$WINNER"

# Automatically update Phase 1 model file if 1d8 won
if [ "$WINNER" = "1d8" ]; then
    echo "Updating Phase 1 scripts to use crn28hpcp_1d8..."
    sed -i 's/crn28hpcp_2d5/crn28hpcp_1d8/g' validation_generated/phase1/run_phase1_*.ocn
fi

# ------------------------------------------------------------------------------
# STEP 3: RUN PHASE 1 SANITY CHECK (5 corners x 5 test cases = 25 sims)
# ------------------------------------------------------------------------------
echo ""
echo ">>> STEP 3: Running Phase 1 Sanity Check (all 5 corners, 5 parallel jobs)..."

JOBS_CONF="jobs.conf"
[ ! -f "$JOBS_CONF" ] && echo "5" > "$JOBS_CONF"

running_p1=0
for script in validation_generated/phase1/run_phase1_*.ocn; do
    [ -f "$script" ] || continue
    sname=$(basename "$script")
    cname=$(echo "$sname" | sed 's/run_phase1_//' | sed 's/\.ocn//')

    # Wait if max jobs reached
    max_j=$(cat "$JOBS_CONF" 2>/dev/null || echo 5)
    while [ "$running_p1" -ge "$max_j" ]; do
        wait -n 2>/dev/null || sleep 2
        running_p1=$(pgrep -f "ocean -nograph" | wc -l)
        max_j=$(cat "$JOBS_CONF" 2>/dev/null || echo 5)
    done

    echo "Launching Phase 1 for corner $cname..."
    ocean -nograph -restore "$script" > "$LOG_DIR/phase1_${cname}.log" 2>&1 &
    running_p1=$((running_p1 + 1))
    sleep 2
done

echo "Waiting for all Phase 1 simulations to complete..."
wait
echo ">>> Phase 1 completed!"

# ------------------------------------------------------------------------------
# STEP 4: FINAL EVALUATION & SUMMARY REPORT
# ------------------------------------------------------------------------------
echo ""
echo "================================================================="
echo " OVERNIGHT EXECUTION COMPLETE"
echo " Timestamp: $(date)"
echo "================================================================="

if [ -f "analyze_results.py" ]; then
    python analyze_results.py --phase 1
fi

echo "Summary report generated. All results ready for download!"
