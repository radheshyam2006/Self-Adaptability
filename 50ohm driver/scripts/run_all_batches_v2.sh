#!/bin/bash
# run_all_batches_v2.sh
# Runs Ocean batch scripts, MAX_PARALLEL at a time
# Usage: bash run_all_batches_v2.sh [MAX_PARALLEL]

MAX_PARALLEL=${1:-3}
LOG_DIR="ocean_batch_logs"
mkdir -p ocean_batch_results $LOG_DIR

count=0
TOTAL=67
echo "Total scripts: $TOTAL, Max parallel: $MAX_PARALLEL"

for script in ocean_batch/run_*.ocn; do
    name=$(basename "$script" .ocn)
    corner_batch=$(echo "$name" | sed 's/run_//')
    mkdir -p "ocean_batch_results/$corner_batch"
    count=$((count + 1))
    echo "[$count/$TOTAL] Starting $name..."
    ocean -nograph -restore "$script" > "$LOG_DIR/${name}.log" 2>&1 &

    if [ $((count % MAX_PARALLEL)) -eq 0 ]; then
        echo "  Waiting for batch of $MAX_PARALLEL to finish..."
        wait
        echo "  Batch done. Completed so far: $count/$TOTAL"
    fi
done

echo "Waiting for final jobs..."
wait
echo "ALL $TOTAL BATCHES COMPLETE!"

FIRST=$(ls results_*_batch*.csv 2>/dev/null | head -1)
if [ -n "$FIRST" ]; then
    head -1 "$FIRST" > calibrated_results_all.csv
    for f in results_*_batch*.csv; do
        tail -n +2 "$f" >> calibrated_results_all.csv
    done
    echo "Final: calibrated_results_all.csv"
    wc -l calibrated_results_all.csv
fi
