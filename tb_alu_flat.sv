module tb_alu_flat;

    logic [7:0] t_a, t_b;
    logic [2:0] t_opcode;
    logic [15:0] t_result;
    logic [15:0] expected_result;
    string op_name;

    // Ket noi voi mach ALU (DUT)
    alu_8bit dut (
        .a(t_a),
        .b(t_b),
        .opcode(t_opcode),
        .result(t_result)
    );

    initial begin
        $dumpfile("alu_flat_waveform.vcd");
        $dumpvars(0, tb_alu_flat);

        $display("");
        $display("[START]");
        $display("");

        for (int i = 0; i < 8; i++) begin
            t_opcode = i;
            // Random a va b, dam bao b != 0 neu la phep chia
            t_a = $urandom_range(10, 50);
            t_b = (i == 3) ? $urandom_range(1, 10) : $urandom_range(0, 20);
            
            #5;

            case (t_opcode)
                3'b000: begin expected_result = t_a + t_b; op_name = "ADD"; end
                3'b001: begin expected_result = t_a - t_b; op_name = "SUB"; end
                3'b010: begin expected_result = t_a * t_b; op_name = "MUL"; end
                3'b011: begin expected_result = t_a / t_b; op_name = "DIV"; end
                3'b100: begin expected_result = t_a & t_b; op_name = "AND"; end
                3'b101: begin expected_result = t_a | t_b; op_name = "OR "; end
                3'b110: begin expected_result = t_a ^ t_b; op_name = "XOR"; end
                3'b111: begin expected_result = t_a << t_b[2:0]; op_name = "SHL"; end
            endcase

            if (t_result === expected_result)
                $display("[PASS] %s | %3d op %3d = %5d", op_name, t_a, t_b, t_result);
            else
                $display("[FAIL] %s | Loi roi! Mach ra %5d nhung dung ra phai la %5d", op_name, t_result, expected_result);
        end

        $display("");
        $display("[SUCCESS]");
        $display("");
        $finish;
    end

endmodule