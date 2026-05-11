module dummy_sensors (
    output wire [28:0] pmon_out,
    output wire [4:0]  vreg_out,
    output wire [9:0]  temp_out,
    output reg         clk,
    output reg         rst_n,
    output reg         start
);
    // ---- PVT CORNER: tt_vdd_temp_3295 ----
    // vreg = 0.99V  => round((0.99 - 0.80) * 100) = 19
    // temp = 123.0C  => round((123.0 + 40) * 4)      = 652
    // pmon = 326279260.0   => (raw integer)                  = 326279260
    assign vreg_out = 5'd19;
    assign temp_out = 10'd652;
    assign pmon_out = 29'd326279260;

    initial begin
        clk = 0;
        rst_n = 0;
        start = 0;
        #100 rst_n = 1;
        #50  start = 1;
        #20  start = 0;
    end
    always #5 clk = ~clk; // 100MHz clock
endmodule
