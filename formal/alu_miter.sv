// Combinational miter. No state or assumptions: all 19 binary input bits are free.
module alu_formal_miter (
    input  wire [7:0] a,
    input  wire [7:0] b,
    input  wire [2:0] opcode,
    output wire [15:0] dut_result,
    output wire [15:0] spec_result,
    output wire mismatch
);
    alu_8bit dut (
        .a(a), .b(b), .opcode(opcode), .result(dut_result)
    );
    alu_spec spec (
        .a(a), .b(b), .opcode(opcode), .result(spec_result)
    );

    assign mismatch = (dut_result != spec_result);
endmodule
