module adder_8bit (
    input  logic [7:0] a,   // Đầu vào A (8-bit: từ 0 đến 255)
    input  logic [7:0] b,   // Đầu vào B (8-bit)
    output logic [8:0] sum  // Đầu ra Kết quả (9-bit để giữ bit tràn)
);

    // Mạch tổ hợp: sum bằng a cộng b
    assign sum = a + b;

endmodule