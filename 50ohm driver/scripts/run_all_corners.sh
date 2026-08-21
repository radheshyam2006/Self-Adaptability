#!/bin/bash
# =================================================================
# Run Spectre simulations for a given corner (parallel, 5 at a time)
# Usage: ./run_all_corners.sh FF
#        ./run_all_corners.sh SS
# =================================================================
CORNER=$1
if [ -z "$CORNER" ]; then
    echo "Usage: $0 <CORNER> (FF|SS|TT|FS|SF)"
    exit 1
fi

NETLIST_DIR="netlists"
RESULTS_DIR="results/${CORNER}"
OCEAN_SCRIPT="measure_resistance.ocn"
MAX_PARALLEL=5

mkdir -p "$RESULTS_DIR"

# Count netlists for this corner
NETLISTS=$(ls ${NETLIST_DIR}/${CORNER}_row*.scs 2>/dev/null | wc -l)
echo "Found $NETLISTS netlists for corner $CORNER"
echo "Running $MAX_PARALLEL in parallel..."

run_one() {
    local scs_file=$1
    local basename=$(basename "$scs_file" .scs)
    local sim_dir="sim_${basename}"
    local result_file="${RESULTS_DIR}/${basename}.csv"
    
    # Skip if already done
    if [ -f "$result_file" ]; then
        return
    fi
    
    mkdir -p "$sim_dir"
    
    # Run Spectre
    spectre "$scs_file" \
        +aps +mt=2 \
        -format psfbin \
        -outdir "${sim_dir}" \
        +log "${sim_dir}/spectre.log" \
        2>&1 | tail -1
    
    # Extract resistance using Ocean
    if [ -f "${sim_dir}/psf/tran.tran" ]; then
        ocean -nograph -log "${sim_dir}/ocean.log" <<EOF
openResults("${sim_dir}")
selectResult('tran)

;; Measure pull-up resistance: R = (Vdd - Voutp) / I(outp)
;; Time window: 450ns to 490ns (steady state)
pup = average(clip((v("/vdd") - v("/outp")) / i("/xdrv_p/out") 4.5e-7 4.9e-7))
pdn = -1 * average(clip(v("/outn") / i("/xdrv_p/out") 4.5e-7 4.9e-7))

;; Write to CSV
port = outfile("${result_file}")
fprintf(port "%s,%.6f,%.6f\n" "${basename}" pup pdn)
close(port)
exit()
EOF
    else
        echo "${basename},FAIL,FAIL" > "$result_file"
    fi
    
    # Cleanup simulation data (save space)
    rm -rf "$sim_dir"
}

# Run in parallel batches
count=0
for scs_file in ${NETLIST_DIR}/${CORNER}_row*.scs; do
    run_one "$scs_file" &
    count=$((count + 1))
    
    if [ $((count % MAX_PARALLEL)) -eq 0 ]; then
        wait
        echo "  Completed $count / $NETLISTS"
    fi
done
wait

echo "All $NETLISTS simulations complete for $CORNER"
echo "Results in: $RESULTS_DIR/"

# Combine results
echo "row_name,pull_up_res,pull_dn_res" > "results/${CORNER}_combined.csv"
cat ${RESULTS_DIR}/*.csv >> "results/${CORNER}_combined.csv"
echo "Combined results: results/${CORNER}_combined.csv"
