#!/bin/bash
# ==============================================================================
# run_all_good.sh
# Runs GOOD test suites sequentially with 1.8V PDK model.
# ==============================================================================

echo "================================================================="
echo " STARTING TEST: GOOD SIMULATIONS"
echo " PDK Model: TSMC 28nm 1.8V Model (crn28hpcp_1d8_elk...)"
echo " Timestamp: $(date)"
echo "================================================================="

mkdir -p good_logs

for suite in TT FF SS FS_ffres FS_ssres SF_ssres SF_ffres; do
    echo ""
    echo ">>> Running Suite $suite (good)..."
    ocean -nograph < run_good_$suite.ocn > good_logs/$suite.log 2>&1
    echo ">>> Suite $suite finished."
done

echo ""
echo "================================================================="
echo " ALL GOOD SIMULATIONS FINISHED!"
echo " Results written to: results_good_*.csv"
echo "================================================================="
python compare_good.py
