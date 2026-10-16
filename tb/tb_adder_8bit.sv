`timescale 1ns/1ps
module tb_adder_8bit;
    logic [7:0] a, b;
    logic [8:0] sum;
    integer total = 0, passed = 0, failed = 0, seed = 2026, rng_seed, unused;
    string wave;
    adder_8bit dut(.*);
    task automatic check(input logic [7:0] aa, bb);
        integer expected;
        a = aa; b = bb;
        expected = int'(aa) + int'(bb);
        #1;
        total++;
        if ((^sum === 1'bx) || sum !== expected[8:0]) begin
            failed++;
            $display("MISMATCH id=%0d seed=%0d a=%0d b=%0d expected=%0d actual=%h",
                     total-1, seed, a, b, expected, sum);
        end else passed++;
    endtask
    initial begin
        unused = $value$plusargs("SEED=%d", seed);
        rng_seed = seed; unused = $urandom(rng_seed);
        if (!$value$plusargs("WAVE=%s", wave)) wave = "adder_waveform.vcd";
        $dumpfile(wave); $dumpvars(0, tb_adder_8bit);
        check(15, 25); check(255, 1);
        for (int i = 0; i < 20; i++)
            check(8'($urandom_range(0, 255)), 8'($urandom_range(0, 255)));
        for (int aa = 0; aa < 256; aa++)
            for (int bb = 0; bb < 256; bb++) check(8'(aa), 8'(bb));
        $display("VERIFICATION SUMMARY total=%0d passed=%0d failed=%0d seed=%0d", total, passed, failed, seed);
        if (failed || total != 65558) $fatal(1, "Status: FAIL");
        $display("Status: PASS"); $finish;
    end
    initial begin #1000000; $fatal(1, "Watchdog expired"); end
endmodule
