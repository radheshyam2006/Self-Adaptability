//============================================================================
// dt_trim_predictor.v — Top-level Decision Tree Trim Bit Predictor
//============================================================================
// Predicts 8-bit pvtp and pvtn trim codes for impedance matching.
// Two parallel FSM engines traverse pvtp and pvtn trees simultaneously.
//
// Latency: max 30 clock cycles (14 levels * 2 cycles/level + 2)
// Hardware: 2 comparators (29-bit), 2 SRAMs, 2 FSMs
//============================================================================

module dt_trim_predictor #(
    parameter PVTP_NODES  = 789,
    parameter PVTN_NODES  = 653,
    parameter ADDR_WIDTH  = 10,
    parameter TREE_DEPTH  = 14,
    parameter PVTP_INIT   = "/data/proj/Low_power_design/tech_tsmc128nm/work/users/user13/rtl_import/pvtp_tree.hex",
    parameter PVTN_INIT   = "/data/proj/Low_power_design/tech_tsmc128nm/work/users/user13/rtl_import/pvtn_tree.hex"
  )(
    input  wire        clk,
    input  wire        rst_n,

    // ---- Sensor inputs ----
    input  wire [28:0] pmon_in,     // Ring oscillator count (29-bit unsigned)
    input  wire [4:0]  vreg_in,     // Vreg: round((V - 0.80) * 100)
    input  wire [9:0]  temp_in,     // Temp: round((C + 40) * 4)

    // ---- Prediction interface ----
    input  wire        start,       // Pulse to begin prediction
    output wire [13:0] pvtp_out,    // Predicted pvtp trim code
    output wire [13:0] pvtn_out,    // Predicted pvtn trim code
    output wire        done,        // 1-cycle pulse when BOTH results ready

    // ---- External SRAM Interface (For Synthesis) ----
    output wire [ADDR_WIDTH-1:0] pvtp_sram_addr,
    input  wire [59:0]           pvtp_sram_data,
    
    output wire [ADDR_WIDTH-1:0] pvtn_sram_addr,
    input  wire [59:0]           pvtn_sram_data
  );

  // ----------------------------------------------------------------
  // Per-tree done signals
  // ----------------------------------------------------------------
  wire done_pvtp, done_pvtn;

  // ----------------------------------------------------------------
  // Internal 8-bit wires from the FSM
  // ----------------------------------------------------------------
  wire [7:0] pvtp_8bit;
  wire [7:0] pvtn_8bit;

  // Tie the upper 6 bits to 0 (Matching the Maestro pvt8-13 variables)
  assign pvtp_out = {6'b000000, pvtp_8bit};
  assign pvtn_out = {6'b000000, pvtn_8bit};

  // ----------------------------------------------------------------
  // pvtp tree FSM instance
  // ----------------------------------------------------------------
  tree_traversal_fsm #(
                       .NODE_COUNT (PVTP_NODES),
                       .ADDR_WIDTH (ADDR_WIDTH),
                       .TREE_DEPTH (TREE_DEPTH)
                     ) u_pvtp_tree (
                       .clk         (clk),
                       .rst_n       (rst_n),
                       .start       (start),
                       .pmon_in     (pmon_in),
                       .vreg_in     (vreg_in),
                       .temp_in     (temp_in),
                       .trim_out    (pvtp_8bit),
                       .done        (done_pvtp),
                       .node_addr   (pvtp_sram_addr),
                       .node_data_in(pvtp_sram_data)
                     );

  // ----------------------------------------------------------------
  // pvtn tree FSM instance
  // ----------------------------------------------------------------
  tree_traversal_fsm #(
                       .NODE_COUNT (PVTN_NODES),
                       .ADDR_WIDTH (ADDR_WIDTH),
                       .TREE_DEPTH (TREE_DEPTH)
                     ) u_pvtn_tree (
                       .clk         (clk),
                       .rst_n       (rst_n),
                       .start       (start),
                       .pmon_in     (pmon_in),
                       .vreg_in     (vreg_in),
                       .temp_in     (temp_in),
                       .trim_out    (pvtn_8bit),
                       .done        (done_pvtn),
                       .node_addr   (pvtn_sram_addr),
                       .node_data_in(pvtn_sram_data)
                     );

  // ----------------------------------------------------------------
  // Done synchronization: assert done when BOTH trees have finished
  // ----------------------------------------------------------------
  reg pvtp_result_ready, pvtn_result_ready;

  always @(posedge clk or negedge rst_n)
  begin
    if (!rst_n)
    begin
      pvtp_result_ready <= 1'b0;
      pvtn_result_ready <= 1'b0;
    end
    else
    begin
      if (start)
      begin
        // Clear ready flags on new prediction
        pvtp_result_ready <= 1'b0;
        pvtn_result_ready <= 1'b0;
      end
      else
      begin
        if (done_pvtp)
          pvtp_result_ready <= 1'b1;
        if (done_pvtn)
          pvtn_result_ready <= 1'b1;
      end
    end
  end

  // Done when both trees produce results (same cycle or staggered)
  assign done = (done_pvtp & done_pvtn)           |  // Both finish together
         (done_pvtp & pvtn_result_ready)    |  // pvtp finishes second
         (done_pvtn & pvtp_result_ready);      // pvtn finishes second

endmodule
