module alu32 (
    input  logic [2:0]  op,
    input  logic [31:0] a,
    input  logic [31:0] b,
    output logic [31:0] y
);
    // One adder serves ADD, SUB, SLT and SLTU: subtraction is a + ~b + 1,
    // and both "less than" flags fall out of the same difference.
    logic        sub;
    logic [32:0] sum;
    logic        lt_u, lt_s;

    assign sub  = (op != 3'd0);
    // carry-in folded into a 2-operand add: {a,1} + {b',sub} adds sub at bit 0,
    // so synthesis builds one 34-bit adder instead of an adder plus an incrementer
    logic [33:0] t;
    assign t    = {1'b0, a, 1'b1} + {1'b0, b ^ {32{sub}}, sub};
    assign sum  = t[33:1];
    logic  unused_t0;              // t[0] is the folded carry-in position, always 1
    assign unused_t0 = t[0];
    assign lt_u = ~sum[32];                                  // borrow out
    assign lt_s = (a[31] != b[31]) ? a[31] : sum[31];        // sign of a-b unless it overflowed

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
