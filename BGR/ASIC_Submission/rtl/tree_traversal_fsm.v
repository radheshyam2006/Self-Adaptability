// ============================================================================
// tree_traversal_fsm.v — Reusable FSM Engine for Decision Tree Traversal
// ============================================================================
// Unified 58-bit node format for both pctrl and nctrl trees.
//
// Node format (58 bits, MSB first):
//   Bit [57]    : is_leaf      (1 bit)
//   Bit [56:55] : feature_id   (2 bits: 0=pmon, 1=vdd, 2=temp)
//   Bit [54:26] : threshold    (29 bits)
//   Bit [25:16] : left_child   (10 bits — node address)
//   Bit [15:6]  : right_child  (10 bits — node address)
//   Bit [5:0]   : leaf_value   (6 bits — trim code output)
//
// FSM: IDLE -> FETCH -> COMPARE -> (loop or output)
// ============================================================================

module tree_traversal_fsm #(
    parameter NUM_NODES = 512,
    parameter INIT_FILE = ""
  )(
    input  wire        clk,
    input  wire        rst_n,
    input  wire        start,
    input  wire [28:0] in_pmon,
    input  wire [4:0]  in_vdd,
    input  wire [8:0]  in_temp,
    output reg  [5:0]  result,
    output reg         done
  );

  // FSM states
  localparam S_IDLE    = 2'd0;
  localparam S_FETCH   = 2'd1;
  localparam S_COMPARE = 2'd2;

  reg [1:0]   state;
  reg [9:0]   node_addr;
  reg [28:0]  latched_pmon;
  reg [4:0]   latched_vdd;
  reg [8:0]   latched_temp;

  // SRAM
  reg [57:0] sram [0:NUM_NODES-1];
  reg [57:0] node_data;

  // Initialize from HEX
  initial
  begin
    if (INIT_FILE != "")
    begin
      $readmemh(INIT_FILE, sram);
    end
  end

  // Node field extraction — MUST match Python encode_node_58bit()
  wire        nd_is_leaf   = node_data[57];
  wire [1:0]  nd_feat_id   = node_data[56:55];
  wire [28:0] nd_threshold = node_data[54:26];
  wire [9:0]  nd_left      = node_data[25:16];
  wire [9:0]  nd_right     = node_data[15:6];
  wire [5:0]  nd_leaf_val  = node_data[5:0];

  // Feature MUX
  reg [28:0] selected_input;
  always @(*)
  begin
    case (nd_feat_id)
      2'd0:
        selected_input = latched_pmon;
      2'd1:
        selected_input = {24'd0, latched_vdd};
      2'd2:
        selected_input = {20'd0, latched_temp};
      default:
        selected_input = 29'd0;
    endcase
  end

  // Comparator
  wire compare_le = (selected_input <= nd_threshold);



  // SRAM read (1-cycle latency)
  always @(posedge clk)
  begin
    node_data <= sram[node_addr];
  end

  // FSM
  always @(posedge clk or negedge rst_n)
  begin
    if (!rst_n)
    begin
      state        <= S_IDLE;
      node_addr    <= 10'd0;
      result       <= 6'd0;
      done         <= 1'b0;
      latched_pmon <= 29'd0;
      latched_vdd  <= 5'd0;
      latched_temp <= 9'd0;
    end
    else
    begin
      case (state)
        S_IDLE:
        begin
          done <= 1'b0;
          if (start)
          begin
            latched_pmon <= in_pmon;
            latched_vdd  <= in_vdd;
            latched_temp <= in_temp;
            node_addr    <= 10'd0;  // Start at root
            state        <= S_FETCH;
          end
        end

        S_FETCH:
        begin
          // Wait 1 cycle for SRAM read
          state <= S_COMPARE;
        end

        S_COMPARE:
        begin
          if (nd_is_leaf)
          begin
            result <= nd_leaf_val;
            done   <= 1'b1;
            state  <= S_IDLE;
          end
          else
          begin
            node_addr <= compare_le ? nd_left : nd_right;
            state     <= S_FETCH;
          end
        end

        default:
          state <= S_IDLE;
      endcase
    end
  end

endmodule
