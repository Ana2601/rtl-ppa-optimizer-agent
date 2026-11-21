module fir8_sym #(
    parameter int XW = 12,
    parameter int YW = 24
) (
    input  logic                 clk,
    input  logic                 rst_n,
    input  logic                 in_valid,
    input  logic signed [XW-1:0] x,
    output logic signed [YW-1:0] y,
    output logic                 out_valid
);
    logic signed [XW-1:0] tap [8];
    logic [3:0]           seen;
    logic                 in_valid_q;

    // linear phase: h[k] == h[7-k], so add the mirrored samples first and
    // multiply 4 sums instead of 8 samples
    logic signed [XW:0]   s0, s1, s2, s3;
    logic signed [YW-1:0] acc;
    assign s0 = tap[0] + tap[7];
    assign s1 = tap[1] + tap[6];
    assign s2 = tap[2] + tap[5];
    assign s3 = tap[3] + tap[4];
    assign acc = YW'(s0) * YW'(3) + YW'(s1) * YW'(-11) + YW'(s2) * YW'(25) + YW'(s3) * YW'(47);

    // data path: no reset needed - y is only sampled when out_valid is high,
    // and out_valid needs 8 fresh samples, which overwrite the whole delay line
    always_ff @(posedge clk) begin
        if (in_valid) begin
            tap[0] <= x;
            for (int k = 1; k < 8; k++) tap[k] <= tap[k-1];
        end
        if (in_valid_q) y <= acc;
    end

    // control path keeps its reset
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            seen       <= '0;
            in_valid_q <= 1'b0;
            out_valid  <= 1'b0;
        end else begin
            in_valid_q <= in_valid;
            if (in_valid && seen != 4'd8) seen <= seen + 4'd1;
            out_valid <= in_valid_q && (seen == 4'd8);
        end
    end
endmodule
