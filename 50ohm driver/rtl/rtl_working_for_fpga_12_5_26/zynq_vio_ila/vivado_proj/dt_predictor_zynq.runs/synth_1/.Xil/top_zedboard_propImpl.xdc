set_property SRC_FILE_INFO {cfile:c:/fpga/dt_pred/rtl/zynq_vio_ila/vivado_proj/dt_predictor_zynq.gen/sources_1/ip/ila_0_1/ila_v6_2/constraints/ila.xdc rfile:../../../dt_predictor_zynq.gen/sources_1/ip/ila_0_1/ila_v6_2/constraints/ila.xdc id:1 order:EARLY scoped_inst:u_ila/inst} [current_design]
set_property SRC_FILE_INFO {cfile:c:/fpga/dt_pred/rtl/zynq_vio_ila/vivado_proj/dt_predictor_zynq.gen/sources_1/ip/vio_0_1/vio_0.xdc rfile:../../../dt_predictor_zynq.gen/sources_1/ip/vio_0_1/vio_0.xdc id:2 order:EARLY scoped_inst:u_vio} [current_design]
set_property SRC_FILE_INFO {cfile:C:/fpga/dt_pred/rtl/zynq_vio_ila/zedboard.xdc rfile:../../../../zedboard.xdc id:3} [current_design]
current_instance u_ila/inst
set_property src_info {type:SCOPED_XDC file:1 line:108 export:INPUT save:INPUT read:READ} [current_design]
create_waiver -internal -type CDC -id {CDC-10} -user ila -tags "1191969" -description "CDC-10 waiver for DDR Calibration logic" -scope -from [get_pins -quiet -filter {REF_PIN_NAME=~*CLK} -of_objects [get_cells -hierarchical -filter {NAME =~*u_trig/N_DDR_TC.N_DDR_TC_INST[*].U_TC/allx_typeA_match_detection.ltlib_v1_0_3_allx_typeA_inst/DUT/u_srl_drive}]] -to [get_pins -quiet -filter {REF_PIN_NAME=~*D} -of_objects [get_cells -hierarchical -filter {NAME =~*u_trig/N_DDR_TC.N_DDR_TC_INST[*].U_TC/allx_typeA_match_detection.ltlib_v1_0_3_allx_typeA_inst/DUT/I_IS_TERMINATION_SLICE_W_OUTPUT_REG.DOUT_O_reg}]]
current_instance
current_instance u_vio
set_property src_info {type:SCOPED_XDC file:2 line:55 export:INPUT save:INPUT read:READ} [current_design]
create_waiver -type CDC -id CDC-4 -from [get_pins -filter {REF_PIN_NAME=~C} -of_objects [get_cells -hierarchical -filter {SCOPED_NAME =~ "*probe_in_reg_reg*"}]]  -to [get_pins -filter {REF_PIN_NAME=~D} -of_objects [get_cells -hierarchical -filter {SCOPED_NAME =~ "*data_int_sync1_reg*"}]]  -user "vio" -description {The path has combinational circuit. But from hardware prospective the design works perfectly and the signals crossing happen after a very long time from the source has the value.} -tags "1050886" -scope -internal
set_property src_info {type:SCOPED_XDC file:2 line:56 export:INPUT save:INPUT read:READ} [current_design]
create_waiver -type CDC -id CDC-1 -from [get_pins -filter {REF_PIN_NAME=~C} -of_objects [get_cells -hierarchical -filter { SCOPED_NAME =~  "*Hold_probe_in*" &&  IS_SEQUENTIAL } ]]  -to [get_pins -filter {REF_PIN_NAME=~CE} -of_objects [get_cells -hierarchical -filter { SCOPED_NAME =~  "*PROBE_IN_INST/probe_in_reg*" && IS_SEQUENTIAL} ]]  -user "vio" -description {The path has combinational circuit. But from hardware prospective the design works perfectly and the signals crossing happen after a very long time from the source has the value.} -tags "1050886" -scope -internal
current_instance
set_property src_info {type:XDC file:3 line:17 export:INPUT save:INPUT read:READ} [current_design]
set_property -dict {PACKAGE_PIN Y9  IOSTANDARD LVDS_25} [get_ports sys_clk_p]
set_property src_info {type:XDC file:3 line:18 export:INPUT save:INPUT read:READ} [current_design]
set_property -dict {PACKAGE_PIN W9  IOSTANDARD LVDS_25} [get_ports sys_clk_n]
set_property src_info {type:XDC file:3 line:33 export:INPUT save:INPUT read:READ} [current_design]
set_property -dict {PACKAGE_PIN T22  IOSTANDARD LVCMOS33} [get_ports {led[0]}]
set_property src_info {type:XDC file:3 line:34 export:INPUT save:INPUT read:READ} [current_design]
set_property -dict {PACKAGE_PIN T21  IOSTANDARD LVCMOS33} [get_ports {led[1]}]
set_property src_info {type:XDC file:3 line:35 export:INPUT save:INPUT read:READ} [current_design]
set_property -dict {PACKAGE_PIN U22  IOSTANDARD LVCMOS33} [get_ports {led[2]}]
set_property src_info {type:XDC file:3 line:36 export:INPUT save:INPUT read:READ} [current_design]
set_property -dict {PACKAGE_PIN U21  IOSTANDARD LVCMOS33} [get_ports {led[3]}]
set_property src_info {type:XDC file:3 line:37 export:INPUT save:INPUT read:READ} [current_design]
set_property -dict {PACKAGE_PIN V22  IOSTANDARD LVCMOS33} [get_ports {led[4]}]
set_property src_info {type:XDC file:3 line:38 export:INPUT save:INPUT read:READ} [current_design]
set_property -dict {PACKAGE_PIN W22  IOSTANDARD LVCMOS33} [get_ports {led[5]}]
set_property src_info {type:XDC file:3 line:39 export:INPUT save:INPUT read:READ} [current_design]
set_property -dict {PACKAGE_PIN U19  IOSTANDARD LVCMOS33} [get_ports {led[6]}]
set_property src_info {type:XDC file:3 line:40 export:INPUT save:INPUT read:READ} [current_design]
set_property -dict {PACKAGE_PIN U14  IOSTANDARD LVCMOS33} [get_ports {led[7]}]
