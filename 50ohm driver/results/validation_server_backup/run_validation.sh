#!/bin/bash
# ==============================================================================
# run_validation.sh
# ==============================================================================
# Master server-side runner for Cadence Spectre validation.
#
# Usage:
#   ./run_validation.sh [PHASE] [ALERT_EMAIL]
# Examples:
#   ./run_validation.sh 1                   # Run Phase 1 (Sanity)
#   ./run_validation.sh 2 user13@iiit.ac.in # Run Phase 2 (Full) with email alert
# ==============================================================================

PHASE=${1:-1}
ALERT_EMAIL=${2:-""}

JOBS_CONF="jobs.conf"
PAUSE_FLAG="pause.flag"
QUARANTINE_FILE="quarantined_corners.txt"
PROGRESS_FILE="validation_progress.json"

LOG_DIR="validation_logs"
RESULTS_DIR="ocean_results"
mkdir -p "$LOG_DIR" "$RESULTS_DIR"

# Initialize control files if not existing
[ ! -f "$JOBS_CONF" ] && echo "5" > "$JOBS_CONF"
[ ! -f "$QUARANTINE_FILE" ] && touch "$QUARANTINE_FILE"
[ ! -f "$PROGRESS_FILE" ] && echo '{"completed":[],"quarantined":[]}' > "$PROGRESS_FILE"

echo "================================================================="
echo " STARTING CADENCE SPECTRE VALIDATION: PHASE $PHASE"
echo "================================================================="
echo "Dynamic parallelism enabled via $JOBS_CONF (Default: $(cat $JOBS_CONF))"
echo "Manual control interface: ./control_jobs.sh {status|set|pause|resume|stop}"
echo ""

SCRIPTS_DIR="validation_generated/phase${PHASE}"
if [ ! -d "$SCRIPTS_DIR" ]; then
    echo "Directory $SCRIPTS_DIR not found! Please generate scripts first."
    exit 1
fi

running=0

for script in "$SCRIPTS_DIR"/run_*.ocn; do
    [ -f "$script" ] || continue

    script_name=$(basename "$script")
    corner=$(echo "$script_name" | sed -E 's/.*_([A-Z]{2})(_.*)?\.ocn/\1/')

    # 1. Check if Corner is Quarantined
    if grep -q "^$corner$" "$QUARANTINE_FILE" 2>/dev/null; then
        echo "[QUARANTINED SKIP] Skipping $script_name because corner $corner is quarantined."
        continue
    fi

    # 2. Check if already completed
    expected_csv=$(echo "$script_name" | sed 's/\.ocn/\.csv/' | sed 's/run_/results_/')
    if [ -f "$expected_csv" ] && [ -s "$expected_csv" ]; then
        echo "[RESUME SKIP] $expected_csv already completed. Skipping."
        continue
    fi

    # 3. Handle PAUSE state
    while [ -f "$PAUSE_FLAG" ]; do
        echo "[PAUSED] Runner paused via $PAUSE_FLAG. Sleeping 10s... (Run './control_jobs.sh resume' to continue)"
        sleep 10
    done

    # 4. Check dynamic parallelism limit from jobs.conf
    max_jobs=$(cat "$JOBS_CONF" 2>/dev/null || echo 5)
    while [ "$running" -ge "$max_jobs" ]; do
        # Wait for any background process to finish
        wait -n 2>/dev/null || sleep 3
        
        # Count actual running ocean processes
        running=$(pgrep -f "ocean -nograph" | wc -l)
        max_jobs=$(cat "$JOBS_CONF" 2>/dev/null || echo 5)
    done

    # 5. Launch batch job
    echo ">>> Starting $script_name with Spectre (Corner: $corner, Active Jobs: $((running + 1))/$max_jobs)..."
    ocean -nograph -restore "$script" > "$LOG_DIR/${script_name}.log" 2>&1 &
    running=$((running + 1))

    # Brief delay to avoid simultaneous file I/O contention
    sleep 2
done

# Wait for all remaining jobs
echo ""
echo "Waiting for all active validation jobs to finish..."
wait
echo "All spawned jobs completed!"

# Post-run health checks and quarantine evaluation
echo ""
echo "================================================================="
echo " EVALUATING BATCH HEALTH & SPEC COMPLIANCE"
echo "================================================================="
for csv in results_phase${PHASE}_*.csv; do
    [ -f "$csv" ] || continue
    corner=$(echo "$csv" | sed -E 's/.*_([A-Z]{2})(_.*)?\.csv/\1/')

    if ! python check_batch.py "$csv"; then
        echo "[ALERT] Corner $corner exceeded error threshold! Adding to quarantine..."
        echo "$corner" >> "$QUARANTINE_FILE"
        sort -u "$QUARANTINE_FILE" -o "$QUARANTINE_FILE"

        if [ -n "$ALERT_EMAIL" ]; then
            echo "Corner $corner failed validation in $csv. Check logs." | mail -s "[CADENCE ALERT] High Error in Corner $corner" "$ALERT_EMAIL" 2>/dev/null || true
        fi
    fi
done

echo ""
echo "Validation Phase $PHASE execution finished."
echo "Check status with: ./control_jobs.sh status"
