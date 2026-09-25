#!/bin/bash
# ==============================================================================
# run_all_bad.sh
# Runs BAD test suites sequentially with 1.8V PDK model.
# ==============================================================================

echo "================================================================="
echo " STARTING TEST: BAD SIMULATIONS"
echo " PDK Model: TSMC 28nm 1.8V Model (crn28hpcp_1d8_elk...)"
echo " Timestamp: $(date)"
echo "================================================================="

mkdir -p bad_logs

for suite in TT FF SS FS_ffres FS_ssres SF_ssres SF_ffres; do
    echo ""
    echo ">>> Running Suite $suite (bad)..."
    ocean -nograph < run_bad_$suite.ocn > bad_logs/$suite.log 2>&1
    echo ">>> Suite $suite finished."
done

echo ""
echo "================================================================="
echo " ALL BAD SIMULATIONS FINISHED!"
echo " Results written to: results_bad_*.csv"
echo "================================================================="
python compare_bad.py
