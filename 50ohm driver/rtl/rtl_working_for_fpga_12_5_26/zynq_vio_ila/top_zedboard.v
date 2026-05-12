//==============================================================================
// top_zedboard.v  —  ZedBoard Top-level Wrapper
//==============================================================================
// This is the ONLY new Verilog file you write for the FPGA.
// It does THREE things:
//   1. Takes the 100 MHz ZedBoard clock and routes it to your DT predictor
//   2. Instantiates a VIO core so Vivado's Hardware Manager can drive inputs
//      and read outputs — like a software oscilloscope + signal generator
//   3. Instantiates an ILA core so you can see waveforms of every internal
//      signal in real-time, even after programming the chip
//
// Your actual compute (dt_trim_predictor) runs on the FPGA fabric (PL side).
// Nothing runs on the ARM CPU (PS side) — we're not using it at all.
//==============================================================================

module top_zedboard (
    // ZedBoard has a 100 MHz GCLK on pin Y9
    input wire sys_clk_p,   // 200 MHz differential clock (GCLK_P)
    input wire sys_clk_n,   // 200 MHz differential clock (GCLK_N)

    // Onboard LEDs (LD0..LD7) — we'll show the lower 8 bits of trim outputs
    // so you can see something blinking/changing physically!
    output wire [7:0] led
);

  //----------------------------------------------------------------------------
  // Step 1: Clock Buffer
  // The ZedBoard 200 MHz differential clock must be converted to single-ended
  // before we can use it. IBUFDS does this conversion.
  // We'll then divide by 2 using BUFR to get 100 MHz for our logic.
  //----------------------------------------------------------------------------
  wire clk_200mhz;
  wire clk_100mhz;

  // Differential input buffer
  IBUFDS #(
    .DIFF_TERM    ("FALSE"),
    .IBUF_LOW_PWR ("TRUE"),
    .IOSTANDARD   ("LVDS_25")
  ) u_ibufds (
    .O  (clk_200mhz),
    .I  (sys_clk_p),
    .IB (sys_clk_n)
  );

  // Divide 200 MHz by 2 → 100 MHz using BUFR
  BUFR #(
    .BUFR_DIVIDE ("2"),
    .SIM_DEVICE  ("7SERIES")
  ) u_bufr (
    .O   (clk_100mhz),
    .CE  (1'b1),
    .CLR (1'b0),
    .I   (clk_200mhz)
  );

  //----------------------------------------------------------------------------
  // Step 2: Reset Synchronizer
  // We create a simple power-on reset that holds rst_n LOW for 16 cycles,
  // then goes HIGH. This ensures all flip-flops start clean.
  //----------------------------------------------------------------------------
  reg [3:0] rst_shift = 4'b0000;   // initial value in simulation/FPGA init
  wire      rst_n;

  always @(posedge clk_100mhz) begin
    rst_shift <= {rst_shift[2:0], 1'b1};
  end
  assign rst_n = rst_shift[3];  // Goes HIGH after 4 clock cycles

  //----------------------------------------------------------------------------
  // Step 3: VIO (Virtual I/O) Input Wires
  // These will be driven by Vivado's Hardware Manager dashboard.
  // You type values into a GUI table — no physical pins, no dip switches needed.
  //----------------------------------------------------------------------------
  wire [28:0] vio_pmon_in;    // Ring-osc count. Range: 0 to ~200,000,000
  wire [4:0]  vio_vreg_in;    // Encoded voltage: round((V - 0.80)*100). Range 0..31
  wire [9:0]  vio_temp_in;    // Encoded temperature: round((C + 40)*4). Range 0..679
  wire        vio_start;      // Pulse this to 1 then back to 0 to trigger prediction

  //----------------------------------------------------------------------------
  // Step 4: DUT Output Wires
  // These are the outputs of your Decision Tree predictor.
  // We'll probe them with ILA to see waveforms.
  //----------------------------------------------------------------------------
  wire [13:0] pvtp_out;       // Predicted PVTP trim code (14-bit, upper 6 are 0)
  wire [13:0] pvtn_out;       // Predicted PVTN trim code (14-bit, upper 6 are 0)
  wire        done;           // 1-cycle pulse when prediction is complete

  //----------------------------------------------------------------------------
  // Step 5: Instantiate your actual Decision Tree Predictor
  // THIS IS WHERE THE REAL COMPUTE HAPPENS — on the FPGA fabric (PL side).
  // The SRAM arrays (pvtp_tree.hex and pvtn_tree.hex) are loaded into BRAM blocks
  // on the FPGA during programming. The FSMs run at 100 MHz.
  //
  // NOTE: We override the INIT_FILE paths here to use relative paths
  //       that Vivado will resolve from the project directory.
  //----------------------------------------------------------------------------
  dt_trim_predictor #(
    .PVTP_NODES (789),
    .PVTN_NODES (653),
    .ADDR_WIDTH (10),
    .TREE_DEPTH (14),
    // These paths are relative to the Vivado project's sim/synth working directory
    // After you set up the project, Vivado will find them via the fileset
    .PVTP_INIT  ("pvtp_tree.hex"),
    .PVTN_INIT  ("pvtn_tree.hex")
  ) u_dt_predictor (
    .clk      (clk_100mhz),
    .rst_n    (rst_n),
    .pmon_in  (vio_pmon_in),
    .vreg_in  (vio_vreg_in),
    .temp_in  (vio_temp_in),
    .start    (vio_start),
    .pvtp_out (pvtp_out),
    .pvtn_out (pvtn_out),
    .done     (done)
  );

  //----------------------------------------------------------------------------
  // Step 6: Drive LEDs with lower 8 bits of pvtp trim output
  // This gives you physical feedback — LEDs will change pattern when
  // you change inputs and trigger a new prediction!
  //----------------------------------------------------------------------------
  assign led = pvtp_out[7:0];

  //----------------------------------------------------------------------------
  // Step 7: VIO Core Instantiation
  // "vio_0" is the name you will give the VIO IP when you add it in Vivado.
  //
  // VIO Port map (configured in Vivado IP Customizer):
  //   probe_out0[28:0] → pmon_in   (you type this value in Hardware Manager)
  //   probe_out1[4:0]  → vreg_in
  //   probe_out2[9:0]  → temp_in
  //   probe_out3[0:0]  → start     (toggle this to trigger)
  //   probe_in0[13:0]  ← pvtp_out  (you READ this in Hardware Manager)
  //   probe_in1[13:0]  ← pvtn_out
  //   probe_in2[0:0]   ← done
  //----------------------------------------------------------------------------
  vio_0 u_vio (
    .clk        (clk_100mhz),
    // Inputs TO Hardware Manager (things you want to READ)
    .probe_in0  (pvtp_out),   // 14-bit: read trim result P
    .probe_in1  (pvtn_out),   // 14-bit: read trim result N
    .probe_in2  (done),       //  1-bit: prediction complete flag
    // Outputs FROM Hardware Manager (things you DRIVE from PC)
    .probe_out0 (vio_pmon_in),  // 29-bit: type pmon value
    .probe_out1 (vio_vreg_in),  //  5-bit: type vreg value
    .probe_out2 (vio_temp_in),  // 10-bit: type temp value
    .probe_out3 (vio_start)     //  1-bit: toggle to start prediction
  );

  //----------------------------------------------------------------------------
  // Step 8: ILA Core Instantiation
  // "ila_0" is the name for the ILA IP in Vivado.
  //
  // ILA Port map (configured in Vivado IP Customizer):
  //   All signals are probed — you see full waveforms in Hardware Manager.
  //
  // ILA Configuration:
  //   - Number of probes: 8
  //   - Sample data depth: 1024 (captures 1024 consecutive clock cycles)
  //   - Trigger on: done == 1 (auto-capture the prediction result moment)
  //----------------------------------------------------------------------------
  ila_0 u_ila (
    .clk    (clk_100mhz),
    // Probe 0: the pmon input (so you can verify VIO drove it correctly)
    .probe0 (vio_pmon_in),    // [28:0]
    // Probe 1: vreg input
    .probe1 ({24'b0, vio_vreg_in}),   // [28:0] zero-padded
    // Probe 2: temp input
    .probe2 ({19'b0, vio_temp_in}),   // [28:0] zero-padded
    // Probe 3: start pulse
    .probe3 ({28'b0, vio_start}),     // [28:0] zero-padded
    // Probe 4: pvtp result
    .probe4 ({15'b0, pvtp_out}),      // [28:0] zero-padded
    // Probe 5: pvtn result
    .probe5 ({15'b0, pvtn_out}),      // [28:0] zero-padded
    // Probe 6: done signal
    .probe6 ({28'b0, done}),          // [28:0] zero-padded
    // Probe 7: combined rst_n for debug
    .probe7 ({28'b0, rst_n})          // [28:0] zero-padded
  );

endmodule
