module alu32 (
    input  logic [2:0]  op,
    input  logic [31:0] a,
    input  logic [31:0] b,
    output logic [31:0] y
);
    // ADD keeps a dedicated adder. SUB, SLT and SLTU share one 33-bit subtractor:
    // the unsigned borrow is bit 32, the signed flag is the sign of a-b corrected
    // for overflow (when the operand signs differ, a < b iff a is negative).
    logic [32:0] diff;
    logic        lt_u, lt_s;
    assign diff = {1'b0, a} - {1'b0, b};
    assign lt_u = diff[32];
    assign lt_s = (a[31] != b[31]) ? a[31] : diff[31];

    always_comb begin
        case (op)
            3'd0:    y = a + b;
            3'd1:    y = diff[31:0];
            3'd2:    y = {31'b0, lt_s};
            3'd3:    y = {31'b0, lt_u};
            3'd4:    y = a & b;
            3'd5:    y = a | b;
            3'd6:    y = a ^ b;
            default: y = {31'b0, a == b};
        endcase
    end
endmodule
