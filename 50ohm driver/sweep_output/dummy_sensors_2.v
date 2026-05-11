module dummy_sensors (
    output wire [28:0] pmon_out,
    output wire [4:0]  vreg_out,
    output wire [9:0]  temp_out,
    output reg         clk,
    output reg         rst_n,
    output reg         start
);
    // ---- PVT CORNER: tt_vdd_temp_1 ----
    // vreg = 0.81V  => round((0.81 - 0.80) * 100) = 1
    // temp = -39.5C  => round((-39.5 + 40) * 4)      = 2
    // pmon = 248491330.0   => (raw integer)                  = 248491330
    assign vreg_out = 5'd1;
    assign temp_out = 10'd2;
    assign pmon_out = 29'd248491330;

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
