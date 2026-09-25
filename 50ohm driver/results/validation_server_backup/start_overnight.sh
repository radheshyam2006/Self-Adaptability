#!/bin/bash
# ==============================================================================
# start_overnight.sh
# ==============================================================================
# Single launcher command to start Phase 0 + Phase 1 safely in background.
# Survives SSH disconnects completely.
# ==============================================================================

chmod +x *.sh

echo "Launching Phase 0 and Phase 1 in background with nohup..."
nohup ./run_overnight.sh > overnight.out 2>&1 &
RUN_PID=$!

echo ""
echo "================================================================="
echo "   OVERNIGHT RUNNER LAUNCHED SUCCESSFULLY!"
echo "   Process ID (PID): $RUN_PID"
echo "================================================================="
echo "It is now safely running completely detached in the background."
echo "You can close this SSH terminal window and go to sleep."
echo ""
echo "To monitor live logs before you sleep (optional):"
echo "   tail -f overnight_logs/master_overnight.log"
echo "================================================================="
