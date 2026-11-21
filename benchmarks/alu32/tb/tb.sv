// Self-checking testbench: every op against corner-heavy random operands.
module tb;
    logic [2:0] op;
    logic [31:0] a, b, y;

    alu32 dut (.*);

    function automatic logic [31:0] corner();
        case ($urandom_range(0, 7))
            0: return 32'h0;
            1: return 32'hFFFF_FFFF;
            2: return 32'h8000_0000;
            3: return 32'h7FFF_FFFF;
            4: return 32'h1 << $urandom_range(0, 31);
            default: return $urandom;
        endcase
    endfunction

    function automatic logic [31:0] model(logic [2:0] o, logic [31:0] x, logic [31:0] z);
        case (o)
            0: return x + z;
            1: return x - z;
            2: return {31'b0, $signed(x) < $signed(z)};
            3: return {31'b0, x < z};
            4: return x & z;
            5: return x | z;
            6: return x ^ z;
            default: return {31'b0, x == z};
        endcase
    endfunction

    int errors = 0, checks = 0;
    initial begin
        for (int n = 0; n < 200000; n++) begin
            op = 3'(n % 8);
            a = corner();
            b = ($urandom_range(0, 9) == 0) ? a : corner();     // equal operands
            #1;
            checks++;
            if (y !== model(op, a, b)) begin
                errors++;
                if (errors < 10) $display("MISMATCH op=%0d a=%h b=%h y=%h exp=%h", op, a, b, y, model(op, a, b));
            end
        end
        if (errors == 0) $display("PASS alu32: %0d vectors", checks);
        else $display("FAIL alu32: %0d mismatches", errors);
        $finish;
    end
endmodule
