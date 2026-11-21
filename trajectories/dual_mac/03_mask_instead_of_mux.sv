module dual_mac #(
    parameter int W = 16,
    parameter int ACC_W = 40
) (
    input  logic             clk,
    input  logic             rst_n,
    input  logic             in_valid,
    input  logic             clr,
    input  logic             sel,
    input  logic [W-1:0]     a,
    input  logic [W-1:0]     b,
    input  logic [W-1:0]     c,
    input  logic [W-1:0]     d,
    output logic [ACC_W-1:0] acc,
    output logic             out_valid
);
    // one shared multiplier: select the operands, not the products
    logic [W-1:0] x, y;
    assign x = sel ? a : c;
    assign y = sel ? b : d;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            acc       <= '0;
            out_valid <= 1'b0;
        end else begin
            out_valid <= in_valid;
            // clr: 0 + 0; idle: acc + 0; accumulate: acc + x*y - no muxes in front of the flops
            acc <= (acc & {ACC_W{~clr}}) + (ACC_W'(x * y) & {ACC_W{in_valid & ~clr}});
        end
    end
endmodule
