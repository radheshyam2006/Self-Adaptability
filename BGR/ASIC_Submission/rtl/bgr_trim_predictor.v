// ============================================================================
// bgr_trim_predictor.v — Top-Level BGR Trim Bit Predictor
// ============================================================================
// Two parallel tree_traversal_fsm engines.
// Latches individual done signals until BOTH trees complete.
// ============================================================================

module bgr_trim_predictor (
    input  wire        clk,
    input  wire        rst_n,
    input  wire [28:0] pmon_count,
    input  wire [4:0]  vdd_code,
    input  wire [8:0]  temp_code,
    input  wire        start,
    output wire        done,
    output wire [3:0]  pctrl_out,
    output wire [5:0]  nctrl_out
  );

  wire done_p_raw, done_n_raw;
  wire [5:0] pctrl_raw, nctrl_raw;

  // Latch done signals until BOTH are done
  reg done_p_latched, done_n_latched;

  assign done = done_p_latched & done_n_latched;
  assign pctrl_out = pctrl_raw[3:0];
  assign nctrl_out = nctrl_raw;

  always @(posedge clk or negedge rst_n)
  begin
    if (!rst_n)
    begin
      done_p_latched <= 1'b0;
      done_n_latched <= 1'b0;
    end
    else
    begin
      if (start)
      begin
        // Clear latches on new prediction
        done_p_latched <= 1'b0;
        done_n_latched <= 1'b0;
      end
      else
      begin
        if (done_p_raw)
          done_p_latched <= 1'b1;
        if (done_n_raw)
          done_n_latched <= 1'b1;
      end
    end
  end

  tree_traversal_fsm #(
                       .NUM_NODES(256),
                       .INIT_FILE("pctrl_tree.hex")
                     ) u_pctrl (
                       .clk(clk), .rst_n(rst_n), .start(start),
                       .in_pmon(pmon_count), .in_vdd(vdd_code), .in_temp(temp_code),
                       .result(pctrl_raw), .done(done_p_raw)
                     );

  tree_traversal_fsm #(
                       .NUM_NODES(512),
                       .INIT_FILE("nctrl_tree.hex")
                     ) u_nctrl (
                       .clk(clk), .rst_n(rst_n), .start(start),
                       .in_pmon(pmon_count), .in_vdd(vdd_code), .in_temp(temp_code),
                       .result(nctrl_raw), .done(done_n_raw)
                     );

endmodule
