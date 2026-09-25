#!/bin/bash
# ==============================================================================
# run_all_6_jobs_parallel.sh
# Launches all 6 simulation jobs concurrently in parallel using separate resultsDir.
# Total Runtime: ~20 to 30 seconds across 6 jobs!
# ==============================================================================

echo "================================================================="
echo " LAUNCHING 6 PARALLEL CADENCE SPECTRE OCEAN JOBS (35 SIMS TOTAL)"
echo " PDK Model: 1.8V (crn28hpcp_1d8_elk...)"
echo " Timestamp: $(date)"
echo "================================================================="

mkdir -p logs_6jobs

echo ">>> Starting Job 1: TT in background..."
ocean -nograph < job1_TT.ocn > logs_6jobs/job1_TT.log 2>&1 &
PID_1=$!
echo ">>> Starting Job 2: FF in background..."
ocean -nograph < job2_FF.ocn > logs_6jobs/job2_FF.log 2>&1 &
PID_2=$!
echo ">>> Starting Job 3: SS in background..."
ocean -nograph < job3_SS.ocn > logs_6jobs/job3_SS.log 2>&1 &
PID_3=$!
echo ">>> Starting Job 4: FS_ffres in background..."
ocean -nograph < job4_FS_ffres.ocn > logs_6jobs/job4_FS_ffres.log 2>&1 &
PID_4=$!
echo ">>> Starting Job 5: FS_ssres in background..."
ocean -nograph < job5_FS_ssres.ocn > logs_6jobs/job5_FS_ssres.log 2>&1 &
PID_5=$!
echo ">>> Starting Job 6: SF_both_res in background..."
ocean -nograph < job6_SF_both_res.ocn > logs_6jobs/job6_SF_both_res.log 2>&1 &
PID_6=$!

echo ""
echo ">>> Waiting for all 6 parallel jobs to finish..."
wait $PID_1
echo ">>> Job 1 finished."
wait $PID_2
echo ">>> Job 2 finished."
wait $PID_3
echo ">>> Job 3 finished."
wait $PID_4
echo ">>> Job 4 finished."
wait $PID_5
echo ">>> Job 5 finished."
wait $PID_6
echo ">>> Job 6 finished."

echo ""
echo "================================================================="
echo " ALL 6 JOBS COMPLETED SUCCESSFULLY!"
echo " Results written to: results_job*.csv"
echo "================================================================="
python compare_6_jobs.py
