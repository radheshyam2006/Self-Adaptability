#!/bin/bash
prev=""
for arg in "$@"; do
    if [ "$prev" = "-f" ] && [ -f "$arg" ]; then
        sed -i '/-spectre_args +logstatus/d' "$arg"
    fi
    prev="$arg"
done
exec /home/cadence-2023/INCISIVE152/tools/bin/irun "$@"
