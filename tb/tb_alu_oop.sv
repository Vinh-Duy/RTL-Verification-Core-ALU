`timescale 1ns/1ps
`include "alu_oop_env.svh"
module tb_alu_oop;
    alu_if vif();
    alu_8bit dut(.a(vif.a), .b(vif.b), .opcode(vif.opcode), .result(vif.result));
    environment env;
    int count = 20, seed = 2026, unused;
    string wave;
    initial begin
        unused = $value$plusargs("COUNT=%d", count);
        unused = $value$plusargs("SEED=%d", seed);
        if (count < 8) $fatal(1, "COUNT must be >=8");
        if (!$value$plusargs("WAVE=%s", wave)) wave = "tb_alu_oop_waveform.vcd";
        $dumpfile(wave); $dumpvars(0, tb_alu_oop);
        env = new(vif, count, seed);
        env.run();
        $finish;
    end
    initial begin #10000000ns; $fatal(1, "OOP watchdog expired"); end
endmodule
