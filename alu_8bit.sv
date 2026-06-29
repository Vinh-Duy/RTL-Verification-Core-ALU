module alu_8bit (
    input  logic [7:0] a, b,      // 2 toán hạng 8-bit
    input  logic [2:0] opcode,    // Mã lệnh điều khiển 3-bit (8 phép toán)
    output logic [15:0] result    // Kết quả 16-bit (để chứa đủ phép nhân)
);

    always_comb begin
        case (opcode)
            3'b000: result = a + b;
            3'b001: result = a - b;
            3'b010: result = a * b;
            3'b011: result = (b != 0) ? (a / b) : 0;
            3'b100: result = a & b;
            3'b101: result = a | b;
            3'b110: result = a ^ b;
            3'b111: result = a << b[2:0];
            default: result = 16'h0000;
        endcase
    end

endmodule