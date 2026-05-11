module dummy_sensors (
    output wire [28:0] pmon_out,
    output wire [4:0]  vreg_out,
    output wire [9:0]  temp_out,
    output reg         clk,
    output reg         rst_n,
    output reg         start
);
    // ---- PVT CORNER: tt_vdd_temp_2662 ----
    // vreg = 0.97V  => round((0.97 - 0.80) * 100) = 17
    // temp = -29.0C  => round((-29.0 + 40) * 4)      = 44
    // pmon = 369419010.0   => (raw integer)                  = 369419010
    assign vreg_out = 5'd17;
    assign temp_out = 10'd44;
    assign pmon_out = 29'd369419010;

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
