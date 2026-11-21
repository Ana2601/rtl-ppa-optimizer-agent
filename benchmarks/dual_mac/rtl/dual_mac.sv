// Dual-source multiply-accumulate (baseline, written for clarity, not PPA).
// Each valid cycle accumulates either a*b or c*d, chosen by sel.
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
    logic [2*W-1:0] p_ab, p_cd, p;

    assign p_ab = a * b;
    assign p_cd = c * d;
    assign p    = sel ? p_ab : p_cd;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            acc       <= '0;
            out_valid <= 1'b0;
        end else begin
            out_valid <= in_valid;
            if (clr)
                acc <= '0;
            else if (in_valid)
                acc <= acc + ACC_W'(p);
        end
    end
endmodule
