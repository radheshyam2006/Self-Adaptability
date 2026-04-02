//============================================================================
// tb_dt_trim_predictor.v — Testbench for Decision Tree Trim Predictor
//============================================================================
// Reads 200 test vectors from test_vectors.hex (held-out test data)
// Applies each input set, waits for done, compares with expected output
// Reports PASS/FAIL per vector and overall accuracy
// Dumps VCD waveform for GTKWave viewing
//============================================================================

`timescale 1ns / 1ps

module tb_dt_trim_predictor;

  // ----------------------------------------------------------------
  // Parameters
  // ----------------------------------------------------------------
  parameter CLK_PERIOD = 10;     // 100 MHz clock
  parameter NUM_VECTORS = 200;

  // ----------------------------------------------------------------
  // DUT signals
  // ----------------------------------------------------------------
  reg         clk;
  reg         rst_n;
  reg  [28:0] pmon_in;
  reg  [4:0]  vreg_in;
  reg  [9:0]  temp_in;
  reg         start;
  wire [7:0]  pvtp_out;
  wire [7:0]  pvtn_out;
  wire        done;



  // ----------------------------------------------------------------
  // DUT instantiation
  // ----------------------------------------------------------------
  dt_trim_predictor #(
                      .PVTP_NODES (789),
                      .PVTN_NODES (653),
                      .ADDR_WIDTH (10),
                      .TREE_DEPTH (14),
                      .PVTP_INIT  ("pvtp_tree.hex"),
                      .PVTN_INIT  ("pvtn_tree.hex")
                    ) dut (
                      .clk          (clk),
                      .rst_n        (rst_n),
                      .pmon_in      (pmon_in),
                      .vreg_in      (vreg_in),
                      .temp_in      (temp_in),
                      .start        (start),
                      .pvtp_out     (pvtp_out),
                      .pvtn_out     (pvtn_out),
                      .done         (done)
                    );

  // ----------------------------------------------------------------
  // Clock generation
  // ----------------------------------------------------------------
  initial
    clk = 0;
  always #(CLK_PERIOD/2) clk = ~clk;

  // ----------------------------------------------------------------
  // Test vector storage
  // ----------------------------------------------------------------
  // Format: [59:31] pmon(29b), [30:26] vreg(5b), [25:16] temp(10b),
  //         [15:8] pvtp(8b), [7:0] pvtn(8b)
  reg [59:0] test_mem [0:NUM_VECTORS-1];

  initial
  begin
    $readmemh("test_vectors.hex", test_mem);
  end

  // ----------------------------------------------------------------
  // Test variables
  // ----------------------------------------------------------------
  integer i;
  integer pass_pvtp, fail_pvtp;
  integer pass_pvtn, fail_pvtn;
  integer pass_both;
  integer timeout_cnt;
  integer cycle_count;
  integer total_cycles;

  reg [28:0] exp_pmon;
  reg [4:0]  exp_vreg;
  reg [9:0]  exp_temp;
  reg [7:0]  exp_pvtp;
  reg [7:0]  exp_pvtn;

  // ----------------------------------------------------------------
  // VCD dump for GTKWave
  // ----------------------------------------------------------------
  initial
  begin
    $dumpfile("waveform.vcd");
    $dumpvars(0, tb_dt_trim_predictor);
  end

  // ----------------------------------------------------------------
  // Main test sequence
  // ----------------------------------------------------------------
  initial
  begin
    // Initialize
    rst_n        = 0;
    start        = 0;
    pmon_in      = 0;
    vreg_in      = 0;
    temp_in      = 0;

    pass_pvtp    = 0;
    fail_pvtp    = 0;
    pass_pvtn    = 0;
    fail_pvtn    = 0;
    pass_both    = 0;
    total_cycles = 0;

    // Reset
    #(CLK_PERIOD * 5);
    rst_n = 1;
    #(CLK_PERIOD * 2);

    $display("============================================================");
    $display("  Decision Tree Trim Predictor — Testbench");
    $display("  %0d test vectors from held-out test set", NUM_VECTORS);
    $display("============================================================");

    // Run all test vectors
    for (i = 0; i < NUM_VECTORS; i = i + 1)
    begin
      // Unpack test vector
      exp_pmon = test_mem[i][59:31];
      exp_vreg = test_mem[i][30:26];
      exp_temp = test_mem[i][25:16];
      exp_pvtp = test_mem[i][15:8];
      exp_pvtn = test_mem[i][7:0];

      // Apply inputs
      pmon_in = exp_pmon;
      vreg_in = exp_vreg;
      temp_in = exp_temp;

      // Pulse start
      @(posedge clk);
      start = 1;
      @(posedge clk);
      start = 0;

      // Wait for done (with timeout)
      cycle_count = 0;
      timeout_cnt = 0;
      while (!done && timeout_cnt < 100)
      begin
        @(posedge clk);
        timeout_cnt = timeout_cnt + 1;
        cycle_count = cycle_count + 1;
      end

      total_cycles = total_cycles + cycle_count;

      if (timeout_cnt >= 100)
      begin
        $display("  [%3d] TIMEOUT! pmon=%0d vreg=%0d temp=%0d",
                 i, exp_pmon, exp_vreg, exp_temp);
      end
      else
      begin
        // Check results
        if (pvtp_out == exp_pvtp && pvtn_out == exp_pvtn)
        begin
          pass_both = pass_both + 1;
        end

        if (pvtp_out == exp_pvtp)
        begin
          pass_pvtp = pass_pvtp + 1;
        end
        else
        begin
          fail_pvtp = fail_pvtp + 1;
          if (fail_pvtp <= 10)
          begin  // Print first 10 failures
            $display("  [%3d] pvtp MISMATCH: got=%0d exp=%0d (pmon=%0d vreg=%0d temp=%0d)",
                     i, pvtp_out, exp_pvtp, exp_pmon, exp_vreg, exp_temp);
          end
        end

        if (pvtn_out == exp_pvtn)
        begin
          pass_pvtn = pass_pvtn + 1;
        end
        else
        begin
          fail_pvtn = fail_pvtn + 1;
          if (fail_pvtn <= 10)
          begin
            $display("  [%3d] pvtn MISMATCH: got=%0d exp=%0d (pmon=%0d vreg=%0d temp=%0d)",
                     i, pvtn_out, exp_pvtn, exp_pmon, exp_vreg, exp_temp);
          end
        end
      end

      // Small gap between vectors
      @(posedge clk);
    end

    // ---- Summary ----
    $display("");
    $display("============================================================");
    $display("  RESULTS SUMMARY");
    $display("============================================================");
    $display("  pvtp: %0d/%0d PASS (%0d FAIL) — Accuracy: %0d%%",
             pass_pvtp, NUM_VECTORS, fail_pvtp,
             (pass_pvtp * 100) / NUM_VECTORS);
    $display("  pvtn: %0d/%0d PASS (%0d FAIL) — Accuracy: %0d%%",
             pass_pvtn, NUM_VECTORS, fail_pvtn,
             (pass_pvtn * 100) / NUM_VECTORS);
    $display("  Both correct: %0d/%0d — Combined: %0d%%",
             pass_both, NUM_VECTORS,
             (pass_both * 100) / NUM_VECTORS);
    $display("  Avg cycles per prediction: %0d",
             total_cycles / NUM_VECTORS);
    $display("============================================================");

    if (fail_pvtp == 0 && fail_pvtn == 0)
      $display("  *** ALL TESTS PASSED — RTL matches Python model ***");
    else
      $display("  *** SOME TESTS FAILED — Check mismatches above ***");

    $display("============================================================");
    $display("");

    #(CLK_PERIOD * 10);
    $finish;
  end

endmodule
