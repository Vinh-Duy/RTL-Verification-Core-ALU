`timescale 1ns/1ps
// These are targeted simulation semantics, outside the known-input core bins.
module tb_alu_four_state;
    logic [7:0] a, b;
    logic [2:0] opcode;
    logic [15:0] result;
    integer total = 0;
    alu_8bit dut(.*);
    task automatic known(input logic [15:0] expected);
        #1; total++;
        if ((^result === 1'bx) || result !== expected)
            $fatal(1, "Four-state known-result mismatch id=%0d expected=%h actual=%h", total-1, expected, result);
    endtask
    task automatic unknown_result;
        #1; total++;
        if (^result !== 1'bx) $fatal(1, "Expected an unknown result id=%0d actual=%h", total-1, result);
    endtask
    initial begin
        a = 8'hxx; b = 0; opcode = 4; known(0); // X AND zero.
        a = 8'hzz; b = 255; opcode = 5; known(255); // Z OR ones.
        a = 8'hxx; b = 0; opcode = 3; known(0); // Zero-divisor guard.
        a = 8'hxx; b = 1; opcode = 0; unknown_result();
        a = 8'hzz; b = 1; opcode = 2; unknown_result();
        a = 1; b = 8'bxxxxx001; opcode = 7; known(2); // Unused upper shift bits.
        a = 1; b = 8'b00000xxx; opcode = 7; unknown_result();
        a = 255; b = 8'hxx; opcode = 3; unknown_result();
        a = 255; b = 255; opcode = 3'bx00; known(0);
        opcode = 3'bz11; known(0);
        $display("VERIFICATION SUMMARY total=%0d passed=%0d failed=0", total, total);
        $display("Status: PASS"); $finish;
    end
    initial begin #1000; $fatal(1, "Watchdog expired"); end
endmodule
