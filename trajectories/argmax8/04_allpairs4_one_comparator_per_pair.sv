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
    // Level 1: 4 pairwise compares (as in the tree).
    // Level 2: the 4 survivors are resolved with all-pairs compares, one comparator
    // per pair (6 in total), instead of two more tree levels.
    logic [W-1:0] v1 [4];
    logic [2:0]   i1 [4];
    logic [3:0]   win;
    logic [3:0]   gt [4];
    logic [W-1:0] best;
    logic [2:0]   best_i;

    always_comb begin
        for (int j = 0; j < 4; j++) begin
            if (lanes[(2*j+1)*W +: W] > lanes[(2*j)*W +: W]) begin
                v1[j] = lanes[(2*j+1)*W +: W]; i1[j] = 3'(2*j+1);
            end else begin
                v1[j] = lanes[(2*j)*W +: W];   i1[j] = 3'(2*j);
            end
        end
        // one comparator per pair: gt[j][k] = (v1[k] > v1[j]) for j < k.
        // survivor j beats a higher survivor k iff !gt[j][k] (ties stay with j),
        // and beats a lower survivor k iff gt[k][j].
        for (int j = 0; j < 4; j++)
            for (int k = 0; k < 4; k++)
                gt[j][k] = (k > j) ? (v1[k] > v1[j]) : 1'b0;
        for (int j = 0; j < 4; j++) begin
            win[j] = 1'b1;
            for (int k = 0; k < 4; k++) begin
                if (k > j &&  gt[j][k]) win[j] = 1'b0;
                if (k < j && !gt[k][j]) win[j] = 1'b0;
            end
        end
        best   = '0;
        best_i = '0;
        for (int j = 0; j < 4; j++) begin
            best   = best   | (v1[j] & {W{win[j]}});
            best_i = best_i | (i1[j] & {3{win[j]}});
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
