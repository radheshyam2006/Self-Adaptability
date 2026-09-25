# ==========================================
# Genus Synthesis Script for DT Predictor
# ==========================================

# 1. Set your TSMC 28nm standard cell library here!
# Replace <PATH_TO_LIB> with the path you find using the search command
set_db library /home/cadence-2023/GENUS201/share/synth/tutorials/tech/tutorial.lib

# 2. Read RTL files (Assuming they are in the 'rtl' folder)
read_hdl rtl/tree_traversal_fsm.v
read_hdl rtl/dt_trim_predictor.v

# 3. Elaborate the top module
elaborate dt_trim_predictor

# SRAM memory is now externalized to top-level ports, so Genus will synthesize logic perfectly without optimizing it away!

# ==========================================

# 4. Set basic timing constraints (e.g., 500MHz clock)
create_clock -name clk -period 2.0 [get_ports clk]
set_input_delay 0.5 -clock clk [all_inputs -no_clocks]
set_output_delay 0.5 -clock clk [all_outputs]

# 5. Synthesize
syn_generic
syn_map
syn_opt

# 6. Report Area, Power, and Gates
report_area > area_report.txt
report_power > power_report.txt
report_gates > gates_report.txt
report_qor   > qor_report.txt

puts "Synthesis Complete! Check the *_report.txt files."
exit
