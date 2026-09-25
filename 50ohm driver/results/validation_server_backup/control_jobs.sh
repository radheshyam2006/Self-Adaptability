#!/bin/bash
# ==============================================================================
# control_jobs.sh
# ==============================================================================
# Manual runtime control interface for Cadence Spectre validation runs.
# Allows adjusting parallelism, pausing, resuming, and checking live status.
#
# Commands:
#   ./control_jobs.sh status          - Show active jobs, progress, and settings
#   ./control_jobs.sh set <N>         - Change max parallel jobs on the fly
#   ./control_jobs.sh pause           - Pause launching new jobs
#   ./control_jobs.sh resume          - Resume launching jobs
#   ./control_jobs.sh stop            - Gracefully terminate running jobs
#   ./control_jobs.sh quarantine <C>  - Manually quarantine a corner (e.g. FS)
#   ./control_jobs.sh unquarantine <C>- Remove a corner from quarantine
# ==============================================================================

JOBS_CONF="jobs.conf"
PAUSE_FLAG="pause.flag"
STOP_FLAG="stop.flag"
QUARANTINE_FILE="quarantined_corners.txt"

# Default jobs if conf missing
[ ! -f "$JOBS_CONF" ] && echo "5" > "$JOBS_CONF"
[ ! -f "$QUARANTINE_FILE" ] && touch "$QUARANTINE_FILE"

cmd=$1
arg=$2

case "$cmd" in
    status|"")
        echo "=========================================================="
        echo "          CADENCE VALIDATION RUNNER STATUS"
        echo "=========================================================="
        max_jobs=$(cat "$JOBS_CONF" 2>/dev/null || echo "5")
        echo "  Configured Max Jobs: $max_jobs"
        
        if [ -f "$PAUSE_FLAG" ]; then
            echo "  Execution State:     PAUSED (pause.flag exists)"
        elif [ -f "$STOP_FLAG" ]; then
            echo "  Execution State:     STOPPING (stop.flag exists)"
        else
            echo "  Execution State:     RUNNING (Active)"
        fi
        
        # Count running ocean and spectre processes
        n_ocean=$(pgrep -f "ocean -nograph" | wc -l)
        n_spectre=$(pgrep -f "spectre" | wc -l)
        echo "  Active Ocean Procs:  $n_ocean"
        echo "  Active Spectre Procs:$n_spectre"
        
        # Quarantined corners
        echo -n "  Quarantined Corners: "
        if [ -s "$QUARANTINE_FILE" ]; then
            cat "$QUARANTINE_FILE" | tr '\n' ' '
            echo ""
        else
            echo "None"
        fi
        
        # Completed batches
        n_completed=$(ls results_*_batch*.csv 2>/dev/null | wc -l)
        echo "  Completed Batches:   $n_completed"
        echo "=========================================================="
        ;;

    set)
        if [ -z "$arg" ] || ! [[ "$arg" =~ ^[0-9]+$ ]]; then
            echo "Usage: ./control_jobs.sh set <number_of_jobs>"
            exit 1
        fi
        echo "$arg" > "$JOBS_CONF"
        echo "[SUCCESS] Max parallel jobs updated to $arg (takes effect immediately)."
        ;;

    pause)
        touch "$PAUSE_FLAG"
        echo "[PAUSED] Runner will finish currently running jobs and pause."
        echo "Use './control_jobs.sh resume' to continue."
        ;;

    resume)
        rm -f "$PAUSE_FLAG"
        echo "[RESUMED] Runner resumed active execution."
        ;;

    stop)
        echo "Stopping all active Cadence/Ocean processes..."
        touch "$STOP_FLAG"
        pkill -f "ocean -nograph"
        pkill -f "spectre"
        echo "[STOPPED] Active jobs terminated. You can resume later."
        rm -f "$STOP_FLAG"
        ;;

    quarantine)
        if [ -z "$arg" ]; then
            echo "Usage: ./control_jobs.sh quarantine <CORNER> (e.g. FS)"
            exit 1
        fi
        echo "$arg" >> "$QUARANTINE_FILE"
        sort -u "$QUARANTINE_FILE" -o "$QUARANTINE_FILE"
        echo "[QUARANTINED] Corner $arg added to quarantine list."
        ;;

    unquarantine)
        if [ -z "$arg" ]; then
            echo "Usage: ./control_jobs.sh unquarantine <CORNER>"
            exit 1
        fi
        sed -i "/^$arg$/d" "$QUARANTINE_FILE"
        echo "[UNQUARANTINED] Corner $arg removed from quarantine."
        ;;

    *)
        echo "Usage: ./control_jobs.sh {status|set <N>|pause|resume|stop|quarantine <CORNER>|unquarantine <CORNER>}"
        exit 1
        ;;
esac
