module alu32 (
    input  logic [2:0]  op,
    input  logic [31:0] a,
    input  logic [31:0] b,
    output logic [31:0] y
);
    localparam logic [2:0] ADD = 3'd0, SUB = 3'd1, SLT = 3'd2, SLTU = 3'd3,
                           AND = 3'd4, OR  = 3'd5, XOR = 3'd6, SEQ  = 3'd7;

    // a == b is ~|(a ^ b); reuse the XOR that op XOR already needs
    logic [31:0] axb;
    assign axb = a ^ b;

    always_comb begin
        case (op)
            ADD:     y = a + b;
            SUB:     y = a - b;
            SLT:     y = {31'b0, $signed(a) < $signed(b)};
            SLTU:    y = {31'b0, a < b};
            AND:     y = a & b;
            OR:      y = a | b;
            XOR:     y = axb;
            SEQ:     y = {31'b0, ~|axb};
        endcase
    end
endmodule
