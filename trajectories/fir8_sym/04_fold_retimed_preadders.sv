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
    // Linear phase: h[k] == h[7-k], so only 4 products are needed:
    //   y = 3*(t0+t7) - 11*(t1+t6) + 25*(t2+t5) + 47*(t3+t4)
    // The pre-adders are retimed across the delay-line registers: the next value of
    // every mirrored pair is already known one cycle early (x + t6, t0 + t5,
    // t1 + t4, t2 + t3), so the sums are registered and the critical path starts
    // at the multipliers. tap[7] is then never read and disappears.
    logic signed [XW-1:0] tap [7];
    logic signed [XW:0]   s0, s1, s2, s3;
    logic [3:0]           seen;
    logic                 in_valid_q;
    logic signed [YW-1:0] acc;

    assign acc = YW'(s0) * YW'(3) + YW'(s1) * YW'(-11) + YW'(s2) * YW'(25) + YW'(s3) * YW'(47);

    // data path: no reset - y is only sampled when out_valid is high, and
    // out_valid needs 8 fresh samples, which overwrite every tap and every sum
    always_ff @(posedge clk) begin
        if (in_valid) begin
            tap[0] <= x;
            for (int k = 1; k < 7; k++) tap[k] <= tap[k-1];
            s0 <= (XW+1)'(x)      + (XW+1)'(tap[6]);
            s1 <= (XW+1)'(tap[0]) + (XW+1)'(tap[5]);
            s2 <= (XW+1)'(tap[1]) + (XW+1)'(tap[4]);
            s3 <= (XW+1)'(tap[2]) + (XW+1)'(tap[3]);
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
