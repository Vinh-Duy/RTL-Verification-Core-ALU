// Negative control: ADD is incorrectly truncated to 8 bits before zero extension.
// All other operations intentionally match the DUT so the miter can expose the fault.
module alu_8bit (
    input  wire [7:0]  a,
    input  wire [7:0]  b,
    input  wire [2:0]  opcode,
    output reg  [15:0] result
);
    wire [15:0] a16 = {8'h00, a};
    wire [15:0] b16 = {8'h00, b};

    always @* begin
        case (opcode)
            3'b000: result = {8'h00, (a + b)}; // Fault: drops the carry bit.
            3'b001: result = a16 - b16;
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
