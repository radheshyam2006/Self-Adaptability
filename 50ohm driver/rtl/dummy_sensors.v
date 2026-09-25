module dummy_sensors (
    output wire [28:0] pmon_out,
    output wire [4:0]  vreg_out,
    output wire [9:0]  temp_out,
    // We can even generate the control signals here!
    output reg         clk,
    output reg         rst_n,
    output reg         start
);
    // Set your test conditions here! For example:
    // ---- PVT CORNER: vreg=0.99V, temp=10C ----
    // vreg encoding: round((V - 0.80) * 100) = round((0.99-0.80)*100) = 19
    // temp encoding: round((C + 40) * 4)     = round((10+40)*4)       = 200
    assign vreg_out = 5'd19;
    assign temp_out = 10'd200;
    assign pmon_out = 29'd300000000; // PMON ring-osc count (typical TT)

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
