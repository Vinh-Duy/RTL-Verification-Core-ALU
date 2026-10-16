`timescale 1ns/1ps
module alu_8bit (
    input  logic [7:0] a, b,
    input  logic [2:0] opcode,
    output logic [15:0] result
);
    localparam logic [2:0] ADD = 3'd0, SUB = 3'd1, MUL = 3'd2,
                           DIV = 3'd3, AND_OP = 3'd4, OR_OP = 3'd5,
                           XOR_OP = 3'd6, SHL = 3'd7;
    wire [15:0] a_extended = {8'b0, a};
    wire [15:0] b_extended = {8'b0, b};
    wire [2:0] shift_amount = b[2:0];

    always_comb begin
        case (opcode)
            ADD:    result = a_extended + b_extended;
            SUB:    result = a_extended - b_extended; // Modulo 65536.
            MUL:    result = a_extended * b_extended;
            DIV:    result = (b != 8'd0) ? a_extended / b_extended : 16'd0;
            AND_OP: result = a_extended & b_extended;
            OR_OP:  result = a_extended | b_extended;
            XOR_OP: result = a_extended ^ b_extended;
            SHL:    result = a_extended << shift_amount;
            default: result = 16'd0; // Preserve unknown-opcode simulation fallback.
        endcase
    end
endmodule
