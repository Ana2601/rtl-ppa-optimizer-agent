// Self-checking testbench: random lanes with forced ties and extremes.
module tb;
    localparam int W = 16;
    logic clk = 0, rst_n = 0, in_valid = 0;
    logic [8*W-1:0] lanes = '0;
    logic [W-1:0] max_val;
    logic [2:0] max_idx;
    logic out_valid;

    argmax8 #(.W(W)) dut (.*);

    always #5 clk = ~clk;

    logic [W-1:0] m_val = 0;
    logic [2:0] m_idx = 0;
    logic m_valid = 0;
    int errors = 0, checks = 0, ties = 0;

    initial begin
        repeat (3) @(posedge clk);
        rst_n = 1;
        for (int n = 0; n < 30000; n++) begin
            @(negedge clk);
            checks++;
            if (max_val !== m_val || max_idx !== m_idx || out_valid !== m_valid) begin
                errors++;
                if (errors < 10) $display("MISMATCH %0d: val=%h/%h idx=%0d/%0d", n, max_val, m_val, max_idx, m_idx);
            end
            in_valid = ($urandom_range(0, 7) != 0);
            for (int i = 0; i < 8; i++) begin
                case ($urandom_range(0, 9))
                    0: lanes[i*W +: W] = '0;
                    1: lanes[i*W +: W] = '1;
                    2: lanes[i*W +: W] = W'($urandom_range(0, 3));   // dense ties
                    default: lanes[i*W +: W] = W'($urandom);
                endcase
            end
            if ($urandom_range(0, 3) == 0) begin                      // force an exact tie
                int s, t;
                s = $urandom_range(0, 7); t = $urandom_range(0, 7);
                lanes[t*W +: W] = lanes[s*W +: W];
            end
            m_valid = in_valid;
            if (in_valid) begin
                logic [W-1:0] bv;
                int nb;
                bv = lanes[0 +: W]; m_idx = 0; nb = 0;
                for (int i = 1; i < 8; i++)
                    if (lanes[i*W +: W] > bv) begin bv = lanes[i*W +: W]; m_idx = 3'(i); end
                for (int i = 0; i < 8; i++) if (lanes[i*W +: W] == bv) nb++;
                if (nb > 1) ties++;
                m_val = bv;
            end
        end
        if (errors == 0) $display("PASS argmax8: %0d cycles, %0d with tied maxima", checks, ties);
        else $display("FAIL argmax8: %0d mismatches", errors);
        $finish;
    end
endmodule
