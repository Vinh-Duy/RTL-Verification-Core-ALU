// Independently coded two-state specification for alu_8bit.
// The input domain is every binary value of a, b, and opcode.
module alu_spec (
    input  wire [7:0]  a,
    input  wire [7:0]  b,
    input  wire [2:0]  opcode,
    output reg  [15:0] result
);
    wire [15:0] a16 = {8'h00, a};
    wire [15:0] b16 = {8'h00, b};

    always @* begin
        case (opcode)
            3'b000: result = a16 + b16;
            3'b001: result = a16 - b16; // Unsigned modulo 2^16.
            3'b010: result = a16 * b16;
            3'b011: result = (b == 8'h00) ? 16'h0000 : a16 / b16;
            3'b100: result = a16 & b16;
            3'b101: result = a16 | b16;
            3'b110: result = a16 ^ b16;
            3'b111: result = a16 << b[2:0];
            default: result = 16'h0000;
        endcase
    end
endmodule
