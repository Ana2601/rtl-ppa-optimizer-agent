// Self-checking testbench with an independent reference model.
module tb;
    localparam int W = 16, ACC_W = 40;
    logic clk = 0, rst_n = 0, in_valid = 0, clr = 0, sel = 0;
    logic [W-1:0] a = 0, b = 0, c = 0, d = 0;
    logic [ACC_W-1:0] acc;
    logic out_valid;

    dual_mac #(.W(W), .ACC_W(ACC_W)) dut (.*);

    always #5 clk = ~clk;

    logic [ACC_W-1:0] m_acc = 0;
    logic m_valid = 0;
    int errors = 0, checks = 0;

    function automatic logic [W-1:0] pick();
        case ($urandom_range(0, 5))
            0: return '0;
            1: return '1;
            2: return W'(1) << $urandom_range(0, W-1);
            default: return W'($urandom);
        endcase
    endfunction

    initial begin
        repeat (3) @(posedge clk);
        rst_n = 1;
        for (int i = 0; i < 20000; i++) begin
            @(negedge clk);
            // compare the registered outputs against the model
            checks++;
            if (acc !== m_acc || out_valid !== m_valid) begin
                errors++;
                if (errors < 10) $display("MISMATCH cycle %0d: acc=%h exp=%h valid=%b exp=%b",
                                          i, acc, m_acc, out_valid, m_valid);
            end
            in_valid = ($urandom_range(0, 9) != 0);
            clr      = ($urandom_range(0, 199) == 0);
            sel      = 1'($urandom_range(0, 1));
            a = pick(); b = pick(); c = pick(); d = pick();
            // model update for the coming edge
            m_valid = in_valid;
            if (clr) m_acc = '0;
            else if (in_valid) m_acc = m_acc + ACC_W'(sel ? (2*W)'(a) * (2*W)'(b) : (2*W)'(c) * (2*W)'(d));
        end
        if (errors == 0) $display("PASS dual_mac: %0d cycles checked", checks);
        else $display("FAIL dual_mac: %0d mismatches", errors);
        $finish;
    end
endmodule
