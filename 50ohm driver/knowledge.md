# Virtuoso Mixed-Signal Integration Notes

*Date: April 6, 2026*

## 1. Transferring RTL to Cadence
To get standard Verilog into the Cadence Virtuoso environment, we first need to transfer it via `scp`. We only transfer the raw Verilog source and the `.hex` SRAM files, **not** the testbenches.

```powershell
# In PowerShell:
scp "C:\Users\radhe\...\50ohm driver\rtl\*.v" user13@10.2.20.16:~/rtl_import/
scp "C:\Users\radhe\...\50ohm driver\rtl\*.hex" user13@10.2.20.16:~/rtl_import/
```

## 2. Generating the Symbol (Verilog In)
In the Virtuoso CIW (Main Window):
1. **File $\rightarrow$ Import $\rightarrow$ Verilog...**
2. **Target Library:** `tsmc28_tx_tb`
3. **Reference Libraries:** `analogLib basic`
4. **Verilog Files:** `/home/user13/rtl_import/dt_trim_predictor.v /home/user13/rtl_import/tree_traversal_fsm.v`
5. *Note:* You do not need to specify a "Top Cell" or import the `.hex` files here. The tool reads the `.v` to draw the pins. The `.hex` files will automatically be loaded during simulation playback!

## 3. Wiring Mismatched Buses in Schematic
The predictor outputs an 8-bit bus (`pvtp_out<7:0>`), but the analog driver requires a 14-bit bus (`pvtp<13:0>`). Since we only need 8 bits:
1. Delete the lowest 8 voltage sources (`pvtp<0>` to `<7>`).
2. Leave the upper 6 voltage sources (`pvtp<8>` to `<13>`).
3. Draw a wire from the predictor and explicitly name it `pvtp<7:0>`. 
Virtuoso will seamlessly map the bottom 8 bits to the predictor and take the top 6 from the DC sources!

## 4. Handling 44 PVT Sensor Inputs
Instead of drawing 44 individual `vsource` components for `pmon`, `vreg`, and `temp`:
1. Create a Verilog file `dummy_sensors.v` that hardcodes the digital 0s and 1s for a specific Test Corner.
2. Import it using **Verilog In**.
3. Place the `dummy_sensors` symbol next to the predictor and wire them together.
4. *Later:* We will automate this using a Python script that sweeps these values dynamically!
