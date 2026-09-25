#!/bin/bash
# ==============================================================================
# run_test_10_bad.sh
# Runs 10 bad simulations across 5 corners sequentially (no collisions).
# Total runtime: ~60 to 90 seconds.
# ==============================================================================

echo "================================================================="
echo " STARTING TEST: 10 BAD SIMULATIONS ACROSS 5 CORNERS"
echo " Timestamp: $(date)"
echo "================================================================="

mkdir -p test_bad_logs

for corner in TT FF SS FS SF; do
    echo ""
    echo ">>> Running Corner $corner (bad)..."
    ocean -nograph < run_bad_$corner.ocn > test_bad_logs/$corner.log 2>&1
    echo ">>> Corner $corner finished."
done

echo ""
echo "================================================================="
echo " ALL 10 BAD SIMULATIONS FINISHED!"
echo " Results written to: results_bad_*.csv"
echo "================================================================="
python compare_10_bad.py
