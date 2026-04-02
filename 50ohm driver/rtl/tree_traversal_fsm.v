//============================================================================
// tree_traversal_fsm.v — Reusable FSM engine for Decision Tree traversal
//============================================================================
// Walks a decision tree stored in SRAM node-by-node.
// Uses 1 comparator, reused each cycle.
// Latency: (depth * 2) + 2 cycles worst-case (FETCH+COMPARE per level).
//
// SRAM entry format (60 bits per node):
//   [59]    is_leaf
//   [58:57] feature_id  (0=pmon, 1=vreg, 2=temp)
//   [56:28] threshold   (29-bit, encoded to match input format)
//   [27:18] left_child  (10-bit node address)
//   [17:8]  right_child (10-bit node address)
//   [7:0]   leaf_value  (8-bit trim code output)
//============================================================================

module tree_traversal_fsm #(
    parameter NODE_COUNT  = 789,
    parameter ADDR_WIDTH  = 10,
    parameter TREE_DEPTH  = 14,
    parameter INIT_FILE   = ""     // Hex file for default SRAM init
  )(
    input  wire                    clk,
    input  wire                    rst_n,

    // Prediction interface
    input  wire                    start,
    input  wire [28:0]             pmon_in,
    input  wire [4:0]              vreg_in,
    input  wire [9:0]              temp_in,
    output reg  [7:0]              trim_out,
    output reg                     done,

    // SRAM configuration port (for reprogramming)
    input  wire                    cfg_wr_en,
    input  wire [ADDR_WIDTH-1:0]   cfg_wr_addr,
    input  wire [59:0]             cfg_wr_data
  );

  // ----------------------------------------------------------------
  // FSM states
  // ----------------------------------------------------------------
  localparam S_IDLE    = 2'd0;
  localparam S_FETCH   = 2'd1;
  localparam S_COMPARE = 2'd2;

  reg [1:0] state;

  // ----------------------------------------------------------------
  // SRAM array
  // ----------------------------------------------------------------
  reg [59:0] sram [0:NODE_COUNT-1];

  // Initialize from hex file if provided
  initial
  begin
    if (INIT_FILE != "")
      $readmemh(INIT_FILE, sram);
  end

  // Registered read data
  reg [59:0] node_data;
  reg [ADDR_WIDTH-1:0] node_addr;

  // Synchronous read
  always @(posedge clk)
  begin
    node_data <= sram[node_addr];
  end

  // Synchronous write (configuration port)
  always @(posedge clk)
  begin
    if (cfg_wr_en)
      sram[cfg_wr_addr] <= cfg_wr_data;
  end

  // ----------------------------------------------------------------
  // Unpack current node fields
  // ----------------------------------------------------------------
  wire        node_is_leaf   = node_data[59];
  wire [1:0]  node_feat_id   = node_data[58:57];
  wire [28:0] node_threshold = node_data[56:28];
  wire [ADDR_WIDTH-1:0] node_left  = node_data[27:18];
  wire [ADDR_WIDTH-1:0] node_right = node_data[17:8];
  wire [7:0]  node_leaf_val  = node_data[7:0];

  // ----------------------------------------------------------------
  // Latched inputs (stable during entire traversal)
  // ----------------------------------------------------------------
  reg [28:0] pmon_lat;
  reg [4:0]  vreg_lat;
  reg [9:0]  temp_lat;

  // ----------------------------------------------------------------
  // Input MUX: select latched input based on current node's feature_id
  // ----------------------------------------------------------------
  reg [28:0] selected_input;

  always @(*)
  begin
    case (node_feat_id)
      2'd0:
        selected_input = pmon_lat;
      2'd1:
        selected_input = {24'd0, vreg_lat};
      2'd2:
        selected_input = {19'd0, temp_lat};
      default:
        selected_input = 29'd0;
    endcase
  end

  // ----------------------------------------------------------------
  // Single comparator: input <= threshold  =>  go left
  // ----------------------------------------------------------------
  wire go_left = (selected_input <= node_threshold);

  // ----------------------------------------------------------------
  // Depth counter (safety: prevent infinite loops)
  // ----------------------------------------------------------------
  reg [4:0] depth_cnt;

  // ----------------------------------------------------------------
  // FSM
  // ----------------------------------------------------------------
  always @(posedge clk or negedge rst_n)
  begin
    if (!rst_n)
    begin
      state     <= S_IDLE;
      node_addr <= {ADDR_WIDTH{1'b0}};
      trim_out  <= 8'd0;
      done      <= 1'b0;
      depth_cnt <= 5'd0;
      pmon_lat  <= 29'd0;
      vreg_lat  <= 5'd0;
      temp_lat  <= 10'd0;
    end
    else
    begin
      done <= 1'b0;  // Default: done is a 1-cycle pulse

      case (state)

        // Wait for start pulse
        S_IDLE:
        begin
          if (start)
          begin
            // Latch inputs for stable comparison
            pmon_lat  <= pmon_in;
            vreg_lat  <= vreg_in;
            temp_lat  <= temp_in;
            // Begin at root node (address 0)
            node_addr <= {ADDR_WIDTH{1'b0}};
            depth_cnt <= 5'd0;
            state     <= S_FETCH;
          end
        end

        // Wait 1 cycle for SRAM read latency
        S_FETCH:
        begin
          state <= S_COMPARE;
        end

        // Evaluate current node
        S_COMPARE:
        begin
          if (node_is_leaf || depth_cnt >= TREE_DEPTH)
          begin
            // Reached a leaf: output result
            trim_out <= node_leaf_val;
            done     <= 1'b1;
            state    <= S_IDLE;
          end
          else
          begin
            // Internal node: branch left or right
            node_addr <= go_left ? node_left : node_right;
            depth_cnt <= depth_cnt + 1'b1;
            state     <= S_FETCH;
          end
        end

        default:
          state <= S_IDLE;

      endcase
    end
  end

endmodule
