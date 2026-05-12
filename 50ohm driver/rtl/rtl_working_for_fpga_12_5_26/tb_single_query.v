`timescale 1ns / 1ps
module tb_single_query;
  reg clk, rst_n, start;
  reg [28:0] pmon_in;
  reg [4:0]  vreg_in;
  reg [9:0]  temp_in;
  wire [7:0] pvtp_out, pvtn_out;
  wire done;

  dt_trim_predictor #(
                      .PVTP_INIT("pvtp_tree.hex"),
                      .PVTN_INIT("pvtn_tree.hex")
                    ) dut (
                      .clk(clk), .rst_n(rst_n), .start(start),
                      .pmon_in(pmon_in), .vreg_in(vreg_in), .temp_in(temp_in),
                      .pvtp_out(pvtp_out), .pvtn_out(pvtn_out), .done(done),
                      .cfg_wr_en(1'b0), .cfg_tree_sel(1'b0),
                      .cfg_wr_addr(10'd0), .cfg_wr_data(60'd0)
                    );

  initial
    clk = 0;
  always #5 clk = ~clk;

  integer cyc;
  initial
  begin
    rst_n = 0;
    start = 0;
    pmon_in = 29'd369419010;   // 248,568,380 Hz
    vreg_in = 5'd17;            // 0.81V -> (0.81-0.80)*100 = 1
    temp_in = 10'd44;           // -40C -> (-40+40)*4 = 0

    #50 rst_n = 1;
    #20;

    $display("");
    $display("========================================");
    $display("  Single Query Test");
    $display("========================================");
    $display("  Inputs:");
    $display("    pmon_cmos_res = 248568380 Hz");
    $display("    voltage       = 0.81 V  (encoded: %0d)", vreg_in);
    $display("    temperature   = -40 C   (encoded: %0d)", temp_in);
    $display("========================================");

    @(posedge clk);
    start = 1;
    @(posedge clk);
    start = 0;

    cyc = 0;
    while (!done && cyc < 100)
    begin
      @(posedge clk);
      cyc = cyc + 1;
    end

    $display("  Results (after %0d cycles):", cyc);
    $display("    pvtp = %0d (binary: %b)", pvtp_out, pvtp_out);
    $display("    pvtn = %0d (binary: %b)", pvtn_out, pvtn_out);
    $display("========================================");
    $display("");

    #50 $finish;
  end
endmodule
