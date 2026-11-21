module alu32 (
    input  logic [2:0]  op,
    input  logic [31:0] a,
    input  logic [31:0] b,
    output logic [31:0] y
);
    // One shared adder/subtractor (a + b' + sub), built as a carry-select adder:
    // the upper half is computed for both carry-ins in parallel with the lower
    // half, so the ripple path is 16 bits plus a mux instead of 32 bits.
    logic        sub;
    logic [31:0] bx;
    logic [16:0] lo;                // lower 16 bits + carry
    logic [16:0] hi0, hi1;          // upper 16 bits + carry, for carry-in 0 / 1
    logic [32:0] sum;
    logic        lt_u, lt_s;

    assign sub = (op != 3'd0);
    assign bx  = b ^ {32{sub}};
    assign lo  = {1'b0, a[15:0]}  + {1'b0, bx[15:0]} + 17'(sub);
    assign hi0 = {1'b0, a[31:16]} + {1'b0, bx[31:16]};
    assign hi1 = {1'b0, a[31:16]} + {1'b0, bx[31:16]} + 17'd1;
    assign sum = lo[16] ? {hi1, lo[15:0]} : {hi0, lo[15:0]};

    assign lt_u = ~sum[32];                                  // no carry out = borrow
    assign lt_s = (a[31] != b[31]) ? a[31] : sum[31];

    always_comb begin
        case (op)
            3'd0, 3'd1: y = sum[31:0];
            3'd2:       y = {31'b0, lt_s};
            3'd3:       y = {31'b0, lt_u};
            3'd4:       y = a & b;
            3'd5:       y = a | b;
            3'd6:       y = a ^ b;
            default:    y = {31'b0, a == b};
        endcase
    end
endmodule
