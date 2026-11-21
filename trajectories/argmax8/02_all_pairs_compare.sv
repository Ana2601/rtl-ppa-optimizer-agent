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
    // All-pairs comparison: lane i wins if it is >= every lower lane and > every
    // higher lane. One comparator level, then an AND per lane and a one-hot mux.
    logic [7:0]   win;
    logic [W-1:0] best;
    logic [2:0]   best_i;

    always_comb begin
        for (int i = 0; i < 8; i++) begin
            win[i] = 1'b1;
            for (int j = 0; j < 8; j++) begin
                if (j < i && !(lanes[i*W +: W] >  lanes[j*W +: W])) win[i] = 1'b0;
                if (j > i && !(lanes[i*W +: W] >= lanes[j*W +: W])) win[i] = 1'b0;
            end
        end
        best   = '0;
        best_i = '0;
        for (int i = 0; i < 8; i++) begin
            best   = best   | (lanes[i*W +: W] & {W{win[i]}});
            best_i = best_i | (3'(i) & {3{win[i]}});
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
