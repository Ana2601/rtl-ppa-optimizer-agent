module alu32 (
    input  logic [2:0]  op,
    input  logic [31:0] a,
    input  logic [31:0] b,
    output logic [31:0] y
);
    // Shared adder/subtractor as a 4 x 8-bit carry-select adder: each upper block
    // precomputes both carry-in cases; the block carries then ripple through three
    // muxes instead of 24 more full-adder stages.
    logic        sub;
    logic [31:0] bx;
    logic [8:0]  blk0;
    logic [8:0]  s0 [1:3], s1 [1:3];   // block sums (+carry) for carry-in 0 / 1
    logic [3:0]  c;                    // carry into block k (c[0] = sub); carry-out below
    logic        cout;
    logic [31:0] sum;
    logic        lt_u, lt_s;

    assign sub  = (op != 3'd0);
    assign bx   = b ^ {32{sub}};
    assign blk0 = {1'b0, a[7:0]} + {1'b0, bx[7:0]} + 9'(sub);

    always_comb
        for (int k = 1; k < 4; k++) begin
            s0[k] = {1'b0, a[8*k +: 8]} + {1'b0, bx[8*k +: 8]};
            s1[k] = {1'b0, a[8*k +: 8]} + {1'b0, bx[8*k +: 8]} + 9'd1;
        end

    // block carries: written out so each one is a plain mux of the previous one
    assign c[0] = sub;
    assign c[1] = blk0[8];
    assign c[2] = c[1] ? s1[1][8] : s0[1][8];
    assign c[3] = c[2] ? s1[2][8] : s0[2][8];
    assign cout = c[3] ? s1[3][8] : s0[3][8];
    assign sum  = {c[3] ? s1[3][7:0] : s0[3][7:0],
                   c[2] ? s1[2][7:0] : s0[2][7:0],
                   c[1] ? s1[1][7:0] : s0[1][7:0],
                   blk0[7:0]};

    assign lt_u = ~cout;                                     // no carry out = borrow
    assign lt_s = (a[31] != b[31]) ? a[31] : sum[31];

    always_comb begin
        case (op)
            3'd0, 3'd1: y = sum;
            3'd2:       y = {31'b0, lt_s};
            3'd3:       y = {31'b0, lt_u};
            3'd4:       y = a & b;
            3'd5:       y = a | b;
            3'd6:       y = a ^ b;
            default:    y = {31'b0, a == b};
        endcase
    end
endmodule
