module argmax8 #(
    parameter int W = 16
) (
    input  logic           clk,
    input  logic           rst_n,
    input  logic           in_valid,
    input  logic [8*W-1:0] lanes,
    output logic [W-1:0]   max_val,
    output logic [2:0]     max_idx,
    output logic           out_valid
);
    // tournament tree: 3 comparator levels instead of a 7-deep chain.
    // The right-hand (higher index) contender only wins when strictly greater,
    // which keeps "ties go to the lowest index".
    logic [W-1:0] v1 [4], v2 [2], best;
    logic [0:0]   i1 [4];
    logic [1:0]   i2 [2];
    logic [2:0]   best_i;

    always_comb begin
        for (int j = 0; j < 4; j++) begin
            if (lanes[(2*j+1)*W +: W] > lanes[(2*j)*W +: W]) begin
                v1[j] = lanes[(2*j+1)*W +: W]; i1[j] = 1'b1;
            end else begin
                v1[j] = lanes[(2*j)*W +: W];   i1[j] = 1'b0;
            end
        end
        for (int j = 0; j < 2; j++) begin
            if (v1[2*j+1] > v1[2*j]) begin
                v2[j] = v1[2*j+1]; i2[j] = {1'b1, i1[2*j+1]};
            end else begin
                v2[j] = v1[2*j];   i2[j] = {1'b0, i1[2*j]};
            end
        end
        if (v2[1] > v2[0]) begin
            best = v2[1]; best_i = {1'b1, i2[1]};
        end else begin
            best = v2[0]; best_i = {1'b0, i2[0]};
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
