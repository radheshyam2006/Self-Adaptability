#!/bin/bash
# ==============================================================================
# run_test_10_correct.sh
# Runs 10 correct simulations across 5 corners sequentially (no collisions).
# Total runtime: ~60 to 90 seconds.
# ==============================================================================

echo "================================================================="
echo " STARTING TEST: 10 CORRECT SIMULATIONS ACROSS 5 CORNERS"
echo " Timestamp: $(date)"
echo "================================================================="

mkdir -p test_correct_logs

for corner in TT FF SS FS SF; do
    echo ""
    echo ">>> Running Corner $corner (correct)..."
    ocean -nograph < run_correct_$corner.ocn > test_correct_logs/$corner.log 2>&1
    echo ">>> Corner $corner finished."
done

echo ""
echo "================================================================="
echo " ALL 10 CORRECT SIMULATIONS FINISHED!"
echo " Results written to: results_correct_*.csv"
echo "================================================================="
python compare_10_correct.py
