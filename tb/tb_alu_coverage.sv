`timescale 1ns/1ps
`define ALU_NATIVE_COVERAGE
`include "alu_oop_env.svh"
`undef ALU_NATIVE_COVERAGE
module tb_alu_coverage;
    alu_if vif();
    alu_8bit dut(.a(vif.a), .b(vif.b), .opcode(vif.opcode), .result(vif.result));
    environment env;
    int count = 200, seed = 2026, unused;
    string wave;
    initial begin
        unused = $value$plusargs("COUNT=%d", count);
        unused = $value$plusargs("SEED=%d", seed);
        if (count < 8) $fatal(1, "COUNT must be >=8");
        if (!$value$plusargs("WAVE=%s", wave)) wave = "tb_alu_coverage_waveform.vcd";
        $dumpfile(wave); $dumpvars(0, tb_alu_coverage);
        env = new(vif, count, seed);
        env.run();
        $finish;
    end
    initial begin #10000000ns; $fatal(1, "OOP watchdog expired"); end
endmodule
