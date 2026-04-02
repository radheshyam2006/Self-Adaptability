// Minimal debug testbench
`timescale 1ns / 1ps

module tb_debug;

  reg         clk;
  reg         rst_n;
  reg         start;
  reg  [28:0] pmon;
  reg  [4:0]  vdd;
  reg  [8:0]  temp;
  wire        done;
  wire [5:0]  result;

  initial
    clk = 0;
  always #5 clk = ~clk;

  tree_traversal_fsm #(
                       .NUM_NODES(256),
                       .INIT_FILE("pctrl_tree.hex")
                     ) dut (
                       .clk(clk), .rst_n(rst_n), .start(start),
                       .in_pmon(pmon), .in_vdd(vdd), .in_temp(temp),
                       .result(result), .done(done),
                       .cfg_wr_en(1'b0), .cfg_wr_addr(10'd0), .cfg_wr_data(58'd0)
                     );

  initial
  begin
    $dumpfile("debug.vcd");
    $dumpvars(0, tb_debug);

    rst_n = 0;
    start = 0;
    pmon = 0;
    vdd = 0;
    temp = 0;
    #50;
    rst_n = 1;
    #20;

    // Test vector: pmon=299797680, vdd_enc=6, temp_enc=70
    // Expected pctrl=7
    pmon = 29'd299797680;
    vdd  = 5'd6;
    temp = 9'd70;

    @(posedge clk);
    start = 1;
    @(posedge clk);
    start = 0;

    // Monitor FSM
    repeat(30)
    begin
      @(posedge clk);
      $display("t=%0t state=%0d addr=%0d node=%h is_leaf=%b feat=%0d thr=%0d L=%0d R=%0d leaf=%0d sel_in=%0d cmp=%b done=%b result=%0d",
               $time,
               dut.state, dut.node_addr,
               dut.node_data,
               dut.nd_is_leaf, dut.nd_feat_id, dut.nd_threshold,
               dut.nd_left, dut.nd_right, dut.nd_leaf_val,
               dut.selected_input, dut.compare_le,
               done, result);
      if (done)
      begin
        $display("DONE! result=%0d (expected 7)", result);
        #20;
        $finish;
      end
    end

    $display("TIMEOUT!");
    $finish;
  end
endmodule
