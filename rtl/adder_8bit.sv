`timescale 1ns/1ps
module adder_8bit (
    input  logic [7:0] a,
    input  logic [7:0] b,
    output logic [8:0] sum
);
    assign sum = {1'b0, a} + {1'b0, b};
endmodule
