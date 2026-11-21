module fir8_sym #(
    parameter int XW = 12,             // input sample width (signed)
    parameter int YW = 24              // output width (signed)
) (
    input  logic                 clk,
    input  logic                 rst_n,
    input  logic                 in_valid,
    input  logic signed [XW-1:0] x,
    output logic signed [YW-1:0] y,
    output logic                 out_valid
);
    // h = [3, -11, 25, 47, 47, 25, -11, 3]
    function automatic logic signed [7:0] H(input int k);
        case (k)
            0, 7:    H =  8'sd3;
            1, 6:    H = -8'sd11;
            2, 5:    H =  8'sd25;
            default: H =  8'sd47;
        endcase
    endfunction

    logic signed [XW-1:0] tap [8];     // tap[0] is the newest sample
    logic [3:0]           seen;        // samples received since reset, saturates at 8
    logic                 in_valid_q;  // a sample entered the delay line last cycle
    logic signed [YW-1:0] acc;

    always_comb begin
        acc = '0;
        for (int k = 0; k < 8; k++)
            acc = acc + YW'(tap[k] * H(k));
    end

    // data path: no reset - y is only sampled while out_valid is high, and
    // out_valid needs 8 fresh samples, which overwrite the whole delay line
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
