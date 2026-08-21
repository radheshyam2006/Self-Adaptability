# =================================================================
# Genus Synthesis Script for DT Trim Predictor
# =================================================================
# Usage (on server):
#   csh
#   source /home/cadence-2023/cadence2.csh
#   cd ~/synthesis
#   genus -files genus_synth.tcl -log genus_run.log
#
# BEFORE RUNNING: Update LIB_PATH below with the correct path.
# Find it with: find /data/cad/pdk_all/pdk_tsmc/pdk_tsmc_28 -name "*.lib" -path "*/Front_End/*" | head
# =================================================================

# ---- CONFIGURATION (UPDATE THESE) ----
set LIB_PATH "/data/cad/pdk_all/pdk_tsmc/pdk_tsmc_28/PDK/TSMC_new_iPDK/digital/Front_End/timing_power_noise/NLDM/tcbn28hpcplusbwp30p140_110a/tcbn28hpcplusbwp30p140tt0p9v25c.lib"
# If the above path doesn't exist, find it:
# find /data/cad/pdk_all/pdk_tsmc/pdk_tsmc_28 -name "*.lib" | grep -i "tt.*0p9" | head

set TOP_MODULE "dt_trim_predictor"
set CLK_PERIOD 10.0  ;# 100 MHz = 10ns period
set RTL_DIR "rtl"

# ---- SETUP ----
set_db / .information_level 7
set_db / .hdl_error_on_latch true

# Create output directories
file mkdir reports
file mkdir outputs

# ---- READ LIBRARY ----
puts "Reading standard cell library..."
read_libs $LIB_PATH

# ---- READ RTL ----
puts "Reading RTL files..."
read_hdl -v2001 [glob ${RTL_DIR}/*.v]

# ---- ELABORATE ----
puts "Elaborating design..."
elaborate $TOP_MODULE
check_design -unresolved

# ---- CONSTRAINTS ----
puts "Setting constraints..."
# Clock definition
create_clock -name clk -period $CLK_PERIOD [get_ports clk]
set_clock_uncertainty 0.5 [get_clocks clk]

# Reset
set_false_path -from [get_ports rst_n]

# Input/Output delays
set_input_delay -clock clk [expr $CLK_PERIOD * 0.3] [all_inputs]
set_output_delay -clock clk [expr $CLK_PERIOD * 0.3] [all_outputs]

# Don't touch clock and reset
set_dont_touch_network [get_ports clk]

# ---- SYNTHESIZE ----
puts "Running synthesis..."
set_db / .syn_generic_effort high
syn_generic
syn_map
syn_opt

# ---- REPORTS ----
puts "Generating reports..."

# Area report
report_area > reports/area.rpt
report_area -detail > reports/area_detail.rpt

# Power report
report_power > reports/power.rpt
report_power -detail > reports/power_detail.rpt

# Timing report
report_timing > reports/timing.rpt
report_timing -max_paths 10 > reports/timing_detail.rpt

# Gate count
report_gates > reports/gates.rpt

# QoR summary
report_qor > reports/qor.rpt

# ---- EXPORT ----
puts "Exporting netlist..."
write_hdl > outputs/dt_trim_predictor_synth.v
write_sdc > outputs/dt_trim_predictor.sdc
write_sdf > outputs/dt_trim_predictor.sdf

# ---- SUMMARY ----
puts "============================================"
puts "SYNTHESIS COMPLETE"
puts "============================================"
puts "Reports in: reports/"
puts "  area.rpt     - Total area"
puts "  power.rpt    - Total power"
puts "  timing.rpt   - Critical path"
puts "  gates.rpt    - Gate count"
puts "Netlist: outputs/dt_trim_predictor_synth.v"
puts "============================================"

exit
