`timescale 1ns/1ps
module tb_alu_flat;
    logic [7:0] a, b;
    logic [2:0] opcode;
    logic [15:0] result;
    integer total = 0, passed = 0, failed = 0, seed = 2026, rng_seed, count = 100;
    integer unused;
    string wave;
    alu_8bit dut(.*);
    `include "alu_reference.svh"

    task automatic check(input logic [7:0] aa, bb, input logic [2:0] op);
        logic [15:0] expected;
        a = aa; b = bb; opcode = op;
        expected = alu_expected(aa, bb, op);
        #1;
        total++;
        if ((^result === 1'bx) || result !== expected) begin
            failed++;
            $display("MISMATCH id=%0d seed=%0d op=%0d a=%0d b=%0d expected=%h actual=%h",
                     total-1, seed, op, aa, bb, expected, result);
        end else passed++;
    endtask

    initial begin
        unused = $value$plusargs("SEED=%d", seed);
        unused = $value$plusargs("COUNT=%d", count);
        if (count < 8) $fatal(1, "COUNT must be >=8");
        rng_seed = seed;
        unused = $urandom(rng_seed);
        if (!$value$plusargs("WAVE=%s", wave)) wave = "alu_flat_waveform.vcd";
        $dumpfile(wave); $dumpvars(0, tb_alu_flat);
        for (int op = 0; op < 8; op++) begin
            check(0, 0, 3'(op));
            check(255, 255, 3'(op));
            check(0, 1, 3'(op));
            check(255, 0, 3'(op));
        end
        for (int i = 0; i < count; i++)
            check(8'($urandom_range(0, 255)), 8'($urandom_range(0, 255)), 3'(i % 8));
        $display("VERIFICATION SUMMARY total=%0d passed=%0d failed=%0d seed=%0d", total, passed, failed, seed);
        if (failed || total != count + 32) $fatal(1, "Status: FAIL");
        $display("Status: PASS"); $finish;
    end
    initial begin #10000000; $fatal(1, "Watchdog expired"); end
endmodule
