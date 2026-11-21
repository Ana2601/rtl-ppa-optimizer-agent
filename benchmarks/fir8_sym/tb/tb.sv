// Self-checking testbench: bursty random samples, mid-run resets, a numeric
// model of the filter, and `y` checked only when `out_valid` is high (as the spec says).
module tb;
    localparam int XW = 12, YW = 24;
    localparam int H [8] = '{3, -11, 25, 47, 47, 25, -11, 3};
    logic clk = 0, rst_n = 0, in_valid = 0;
    logic signed [XW-1:0] x = 0;
    logic signed [YW-1:0] y;
    logic out_valid;

    fir8_sym #(.XW(XW), .YW(YW)) dut (.*);

    always #5 clk = ~clk;

    int hist [$];                     // samples since the last reset, newest first
    // expected outputs, indexed by the cycle they must appear in
    int exp_y [int];
    int errors = 0, outputs = 0, cyc = 0;

    task automatic do_reset();
        rst_n = 0; in_valid = 0;
        repeat (2) @(negedge clk);
        hist.delete(); exp_y.delete();
        rst_n = 1;
    endtask

    initial begin
        do_reset();
        for (int n = 0; n < 40000; n++) begin
            @(negedge clk);
            cyc++;
            // check this cycle's outputs
            if (exp_y.exists(cyc)) begin
                outputs++;
                if (!out_valid || y !== YW'(exp_y[cyc])) begin
                    errors++;
                    if (errors < 10) $display("MISMATCH cyc %0d: valid=%b y=%0d exp=%0d", cyc, out_valid, y, exp_y[cyc]);
                end
                exp_y.delete(cyc);
            end else if (out_valid) begin
                errors++;
                if (errors < 10) $display("SPURIOUS out_valid at cyc %0d", cyc);
            end
            if ($urandom_range(0, 2999) == 0) begin do_reset(); continue; end
            // drive the next sample
            in_valid = ($urandom_range(0, 3) != 0);
            case ($urandom_range(0, 5))
                0: x = -(2**(XW-1));
                1: x = 2**(XW-1) - 1;
                default: x = XW'($urandom);
            endcase
            if (in_valid) begin
                hist.push_front(int'(x));
                if (hist.size() > 8) void'(hist.pop_back());
                if (hist.size() == 8) begin
                    int s;
                    s = 0;
                    for (int k = 0; k < 8; k++) s += H[k] * hist[k];
                    exp_y[cyc + 2] = s;
                end
            end
        end
        if (errors == 0 && outputs > 1000) $display("PASS fir8_sym: %0d outputs checked", outputs);
        else $display("FAIL fir8_sym: %0d errors, %0d outputs", errors, outputs);
        $finish;
    end
endmodule
