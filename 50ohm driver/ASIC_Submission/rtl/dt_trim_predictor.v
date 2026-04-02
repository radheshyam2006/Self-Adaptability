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
    parameter PVTP_INIT   = "pvtp_tree.hex",
    parameter PVTN_INIT   = "pvtn_tree.hex"
  )(
    input  wire        clk,
    input  wire        rst_n,

    // ---- Sensor inputs ----
    input  wire [28:0] pmon_in,     // Ring oscillator count (29-bit unsigned)
    input  wire [4:0]  vreg_in,     // Vreg: round((V - 0.80) * 100)
    input  wire [9:0]  temp_in,     // Temp: round((C + 40) * 4)

    // ---- Prediction interface ----
    input  wire        start,       // Pulse to begin prediction
    output wire [7:0]  pvtp_out,    // Predicted pvtp trim code
    output wire [7:0]  pvtn_out,    // Predicted pvtn trim code
    output wire        done         // 1-cycle pulse when BOTH results ready
  );



  // ----------------------------------------------------------------
  // Per-tree done signals
  // ----------------------------------------------------------------
  wire done_pvtp, done_pvtn;

  // ----------------------------------------------------------------
  // pvtp tree FSM instance
  // ----------------------------------------------------------------
  tree_traversal_fsm #(
                       .NODE_COUNT (PVTP_NODES),
                       .ADDR_WIDTH (ADDR_WIDTH),
                       .TREE_DEPTH (TREE_DEPTH),
                       .INIT_FILE  (PVTP_INIT)
                     ) u_pvtp_tree (
                       .clk         (clk),
                       .rst_n       (rst_n),
                       .start       (start),
                       .pmon_in     (pmon_in),
                       .vreg_in     (vreg_in),
                       .temp_in     (temp_in),
                       .trim_out    (pvtp_out),
                       .done        (done_pvtp)
                     );

  // ----------------------------------------------------------------
  // pvtn tree FSM instance
  // ----------------------------------------------------------------
  tree_traversal_fsm #(
                       .NODE_COUNT (PVTN_NODES),
                       .ADDR_WIDTH (ADDR_WIDTH),
                       .TREE_DEPTH (TREE_DEPTH),
                       .INIT_FILE  (PVTN_INIT)
                     ) u_pvtn_tree (
                       .clk         (clk),
                       .rst_n       (rst_n),
                       .start       (start),
                       .pmon_in     (pmon_in),
                       .vreg_in     (vreg_in),
                       .temp_in     (temp_in),
                       .trim_out    (pvtn_out),
                       .done        (done_pvtn)
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
