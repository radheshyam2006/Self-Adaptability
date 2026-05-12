## =============================================================================
## create_project.tcl  —  Run this in Vivado's Tcl Console to build the project
## =============================================================================
## HOW TO USE:
##   1. Open Vivado 2022.x (or later)
##   2. In the Tcl Console at the bottom, type:
##        source {C:/path/to/your/rtl/zynq_vio_ila/create_project.tcl}
##   3. The project will be created automatically with all files added.
## =============================================================================

## ---- EDIT THIS PATH to match where your files are ----
set root_dir {C:/Users/dell/FPGA_Implementation/50-ohm-driver-fpga/Self-Adaptability/50ohm driver}
set rtl_dir  "$root_dir/rtl"
set zynq_dir "$rtl_dir/zynq_vio_ila"

## Create the Vivado project inside the zynq_vio_ila folder
## Part: XC7Z020CLG484-1 = Zynq-7020 on ZedBoard (484-pin BGA, speed grade -1)
create_project dt_predictor_zynq "$zynq_dir/vivado_proj" \
    -part xc7z020clg484-1 \
    -force

## Set the target language to Verilog
set_property target_language Verilog [current_project]

## ---- Add all Verilog source files ----
add_files -norecurse [list \
    "$zynq_dir/top_zedboard.v"       \
    "$rtl_dir/dt_trim_predictor.v"   \
    "$rtl_dir/tree_traversal_fsm.v"  \
]

## Add the hex memory init files (these get loaded into BRAM at programming time)
add_files -norecurse [list \
    "$rtl_dir/pvtp_tree.hex" \
    "$rtl_dir/pvtn_tree.hex" \
]

## Mark hex files as "Memory Initialization Files" so Vivado handles them correctly
set_property file_type {Memory Initialization Files} [get_files pvtp_tree.hex]
set_property file_type {Memory Initialization Files} [get_files pvtn_tree.hex]

## Add the constraints (pin assignments)
add_files -fileset constrs_1 -norecurse "$zynq_dir/zedboard.xdc"

## Set the top-level module
set_property top top_zedboard [current_fileset]

## Update compile order so Vivado knows the hierarchy
update_compile_order -fileset sources_1

puts ""
puts "============================================================"
puts "  Project created successfully!"
puts "  Next step: Add VIO and ILA IPs — see README_VIVADO_STEPS.md"
puts "============================================================"
