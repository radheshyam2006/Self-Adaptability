// ============================================================================
// tb_bgr_trim_predictor.v — Testbench for BGR Trim Bit Predictor
// ============================================================================
// Loads 200 test vectors, applies each, compares results.
// Test vector HEX format (56 bits = 14 hex digits):
//   [55:27] pmon      (29 bits) -> extra 3 MSB padding bits at [55:53]
//   [26:22] vdd_enc   (5 bits)
//   [21:13] temp_enc  (9 bits)
//   [12:9]  pctrl_exp (4 bits)
//   [8:3]   nctrl_exp (6 bits)
//   [2:0]   padding   (3 bits)
// Actually: pmon(29)|vdd(5)|temp(9)|pctrl(4)|nctrl(6) = 53 bits, 14 hex = 56 bits
// $readmemh stores right-aligned, so bits [52:0] contain data, [55:53] = 0
// ============================================================================

`timescale 1ns / 1ps

module tb_bgr_trim_predictor;

  parameter NUM_VECTORS = 200;
  parameter CLK_PERIOD  = 10;

  reg         clk;
  reg         rst_n;
  reg         start;
  reg  [28:0] pmon_count;
  reg  [4:0]  vdd_code;
  reg  [8:0]  temp_code;
  wire        done;
  wire [3:0]  pctrl_out;
  wire [5:0]  nctrl_out;

  // 56-bit storage for 14 hex digits, data in lower 53 bits
  reg [55:0] test_vectors [0:NUM_VECTORS-1];

  integer i;
  integer pctrl_pass, pctrl_fail;
  integer nctrl_pass, nctrl_fail;
  integer both_pass;
  integer total_cycles;
  integer cycle_count;

  reg [3:0] expected_pctrl;
  reg [5:0] expected_nctrl;

  initial
    clk = 0;
  always #(CLK_PERIOD/2) clk = ~clk;

  bgr_trim_predictor dut (
                       .clk(clk), .rst_n(rst_n),
                       .pmon_count(pmon_count), .vdd_code(vdd_code), .temp_code(temp_code),
                       .start(start), .done(done),
                       .pctrl_out(pctrl_out), .nctrl_out(nctrl_out),
                       .cfg_wr_en(1'b0), .cfg_tree_sel(1'b0),
                       .cfg_wr_addr(10'd0), .cfg_wr_data(58'd0)
                     );

  initial
  begin
    $dumpfile("waveform.vcd");
    $dumpvars(0, tb_bgr_trim_predictor);
  end

  initial
  begin
    $readmemh("test_vectors.hex", test_vectors);

    rst_n = 0;
    start = 0;
    pmon_count = 0;
    vdd_code = 0;
    temp_code = 0;
    pctrl_pass = 0;
    pctrl_fail = 0;
    nctrl_pass = 0;
    nctrl_fail = 0;
    both_pass = 0;
    total_cycles = 0;

    repeat(5) @(posedge clk);
    rst_n = 1;
    repeat(2) @(posedge clk);

    $display("");
    $display("============================================================");
    $display("  BGR Decision Tree Trim Predictor - Testbench");
    $display("  %0d test vectors", NUM_VECTORS);
    $display("============================================================");

    for (i = 0; i < NUM_VECTORS; i = i + 1)
    begin
      // Extract fields from 53-bit packed vector (right-aligned in 56-bit reg)
      // Layout: pmon[52:24] | vdd[23:19] | temp[18:10] | pctrl[9:6] | nctrl[5:0]
      pmon_count     = test_vectors[i][52:24];
      vdd_code       = test_vectors[i][23:19];
      temp_code      = test_vectors[i][18:10];
      expected_pctrl = test_vectors[i][9:6];
      expected_nctrl = test_vectors[i][5:0];

      @(posedge clk);
      start = 1;
      cycle_count = 0;
      @(posedge clk);
      start = 0;

      while (!done)
      begin
        @(posedge clk);
        cycle_count = cycle_count + 1;
        if (cycle_count > 100)
        begin
          $display("ERROR: Timeout on vector %0d! pmon=%0d vdd=%0d temp=%0d",
                   i, pmon_count, vdd_code, temp_code);
          $finish;
        end
      end

      total_cycles = total_cycles + cycle_count;

      if (pctrl_out == expected_pctrl)
        pctrl_pass = pctrl_pass + 1;
      else
      begin
        pctrl_fail = pctrl_fail + 1;
        if (pctrl_fail <= 10)
          $display("  PCTRL MISMATCH [%0d]: exp=%0d got=%0d (pmon=%0d vdd=%0d temp=%0d)",
                   i, expected_pctrl, pctrl_out, pmon_count, vdd_code, temp_code);
      end

      if (nctrl_out == expected_nctrl)
        nctrl_pass = nctrl_pass + 1;
      else
      begin
        nctrl_fail = nctrl_fail + 1;
        if (nctrl_fail <= 10)
          $display("  NCTRL MISMATCH [%0d]: exp=%0d got=%0d (pmon=%0d vdd=%0d temp=%0d)",
                   i, expected_nctrl, nctrl_out, pmon_count, vdd_code, temp_code);
      end

      if (pctrl_out == expected_pctrl && nctrl_out == expected_nctrl)
        both_pass = both_pass + 1;

      @(posedge clk);
    end

    $display("");
    $display("============================================================");
    $display("  RESULTS");
    $display("============================================================");
    $display("  pctrl: %0d/%0d PASS (%0d FAIL) — Accuracy: %0d%%",
             pctrl_pass, NUM_VECTORS, pctrl_fail,
             (pctrl_pass * 100) / NUM_VECTORS);
    $display("  nctrl: %0d/%0d PASS (%0d FAIL) — Accuracy: %0d%%",
             nctrl_pass, NUM_VECTORS, nctrl_fail,
             (nctrl_pass * 100) / NUM_VECTORS);
    $display("  Both correct: %0d/%0d — Combined: %0d%%",
             both_pass, NUM_VECTORS,
             (both_pass * 100) / NUM_VECTORS);
    $display("  Avg cycles per prediction: %0d",
             total_cycles / NUM_VECTORS);

    if (pctrl_fail == 0 && nctrl_fail == 0)
      $display("  *** ALL TESTS PASSED ***");
    else
      $display("  *** SOME MISMATCHES ***");

    $display("============================================================");
    #100;
    $finish;
  end

endmodule
