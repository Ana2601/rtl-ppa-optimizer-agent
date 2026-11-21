// Registered arg-max over 8 unsigned lanes (baseline: a linear scan).
// Ties resolve to the lowest lane index.
module argmax8 #(
    parameter int W = 16
) (
    input  logic           clk,
    input  logic           rst_n,
    input  logic           in_valid,
    input  logic [8*W-1:0] lanes,      // lane i = lanes[i*W +: W]
    output logic [W-1:0]   max_val,
    output logic [2:0]     max_idx,
    output logic           out_valid
);
    logic [W-1:0] best;
    logic [2:0]   best_i;

    always_comb begin
        best   = lanes[0 +: W];
        best_i = 3'd0;
        for (int i = 1; i < 8; i++) begin
            if (lanes[i*W +: W] > best) begin
                best   = lanes[i*W +: W];
                best_i = 3'(i);
            end
        end
    end

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            max_val   <= '0;
            max_idx   <= '0;
            out_valid <= 1'b0;
        end else begin
            out_valid <= in_valid;
            if (in_valid) begin
                max_val <= best;
                max_idx <= best_i;
            end
        end
    end
endmodule
