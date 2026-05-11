## ZedBoard XDC Constraints — top_zedboard.v
## ============================================================
## This file tells Vivado:
##   1. WHERE the clock pins are on the ZedBoard PCB
##   2. HOW FAST the clock runs (so timing analysis works)
##   3. WHERE the LED pins are connected
##
## The ZedBoard schematic reference: UG865 (Avnet ZedBoard HW User Guide)
## ============================================================

##--------------------------------------------------------------
## 200 MHz System Clock (Differential — LVDS pair)
## ZedBoard schematic net: GCLK_P / GCLK_N
## FPGA pin: Y9 (P side), W9 (N side)
## This is the main oscillator soldered on the board.
##--------------------------------------------------------------
set_property -dict {PACKAGE_PIN Y9  IOSTANDARD LVDS_25} [get_ports sys_clk_p]
set_property -dict {PACKAGE_PIN W9  IOSTANDARD LVDS_25} [get_ports sys_clk_n]

## Tell Vivado: "this clock input runs at 200 MHz"
## Vivado will then check if ALL your logic can meet 200 MHz timing.
## Our BUFR divides it to 100 MHz, so actual logic runs at 100 MHz.
create_clock -period 5.000 -name sys_clk [get_ports sys_clk_p]

##--------------------------------------------------------------
## User LEDs (LD0 to LD7)
## ZedBoard has 8 green LEDs on the board.
## We use them to display pvtp_out[7:0] — physical proof it's working!
##
## Schematic reference: LED0=T22, LED1=T21, LED2=U22, LED3=U21
##                      LED4=V22, LED5=W22, LED6=U19, LED7=U14
##--------------------------------------------------------------
set_property -dict {PACKAGE_PIN T22  IOSTANDARD LVCMOS33} [get_ports {led[0]}]
set_property -dict {PACKAGE_PIN T21  IOSTANDARD LVCMOS33} [get_ports {led[1]}]
set_property -dict {PACKAGE_PIN U22  IOSTANDARD LVCMOS33} [get_ports {led[2]}]
set_property -dict {PACKAGE_PIN U21  IOSTANDARD LVCMOS33} [get_ports {led[3]}]
set_property -dict {PACKAGE_PIN V22  IOSTANDARD LVCMOS33} [get_ports {led[4]}]
set_property -dict {PACKAGE_PIN W22  IOSTANDARD LVCMOS33} [get_ports {led[5]}]
set_property -dict {PACKAGE_PIN U19  IOSTANDARD LVCMOS33} [get_ports {led[6]}]
set_property -dict {PACKAGE_PIN U14  IOSTANDARD LVCMOS33} [get_ports {led[7]}]

##--------------------------------------------------------------
## Bitstream Configuration Settings
## These tell the Zynq how to load the bitstream properly.
## CFGBVS = VCCO: voltage standard for config pins
## CONFIG_VOLTAGE = 3.3: our I/O bank runs at 3.3V
##--------------------------------------------------------------
set_property CFGBVS VCCO               [current_design]
set_property CONFIG_VOLTAGE 3.3        [current_design]

## Optional: compress bitstream (makes download faster via USB)
set_property BITSTREAM.GENERAL.COMPRESS TRUE [current_design]
