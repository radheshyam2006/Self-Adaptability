#!/bin/bash
# ==============================================================================
# run_all_6_jobs_sequential.sh
# Runs all 6 simulation jobs sequentially one after another.
# ==============================================================================

echo "================================================================="
echo " RUNNING 6 JOBS SEQUENTIALLY (35 SIMS TOTAL)"
echo "================================================================="
mkdir -p logs_6jobs

echo ">>> Running Job 1: TT..."
ocean -nograph < job1_TT.ocn > logs_6jobs/job1_TT.log 2>&1
echo ">>> Job 1 completed."

echo ">>> Running Job 2: FF..."
ocean -nograph < job2_FF.ocn > logs_6jobs/job2_FF.log 2>&1
echo ">>> Job 2 completed."

echo ">>> Running Job 3: SS..."
ocean -nograph < job3_SS.ocn > logs_6jobs/job3_SS.log 2>&1
echo ">>> Job 3 completed."

echo ">>> Running Job 4: FS_ffres..."
ocean -nograph < job4_FS_ffres.ocn > logs_6jobs/job4_FS_ffres.log 2>&1
echo ">>> Job 4 completed."

echo ">>> Running Job 5: FS_ssres..."
ocean -nograph < job5_FS_ssres.ocn > logs_6jobs/job5_FS_ssres.log 2>&1
echo ">>> Job 5 completed."

echo ">>> Running Job 6: SF_both_res..."
ocean -nograph < job6_SF_both_res.ocn > logs_6jobs/job6_SF_both_res.log 2>&1
echo ">>> Job 6 completed."

echo "ALL JOBS FINISHED!"
python compare_6_jobs.py
