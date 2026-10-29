`timescale 1ns/1ps
// Negative control: preserve the real ALU and inject a deterministic ADD fault.
module alu_8bit_faulty (
    input  logic [7:0] a, b,
    input  logic [2:0] opcode,
    output logic [15:0] result
);
    logic [15:0] correct_result;
    alu_8bit correct(.a(a), .b(b), .opcode(opcode), .result(correct_result));

    always_comb begin
        result = correct_result;
        if (opcode == 3'd0) result = correct_result + 16'd1;
    end
endmodule
