`timescale 1ns/1ps

module tb_adder_8bit;

    // 1. Khai báo các tín hiệu để kết nối với DUT
    logic [7:0] t_a;
    logic [7:0] t_b;
    logic [8:0] t_sum;

    // 2. Gọi khối DUT vào trong Testbench
    adder_8bit dut (
        .a(t_a),
        .b(t_b),
        .sum(t_sum)
    );

    // 3. Khối khởi tạo quy trình ném dữ liệu test
    initial begin
        // Để xuất file dạng sóng (.vcd) xem bằng GTKWave
        $dumpfile("adder_waveform.vcd");
        $dumpvars(0, tb_adder_8bit);

        $display("");
        $display("[START]");
        $display("");

        // TESTCASE 1: Kiểm thử giá trị cơ bản ---
        t_a = 8'd15; t_b = 8'd25;
        #10; // Đợi 10ns để mạch phản hồi
        if (t_sum == 9'd40) begin
            $display("[PASS] TC1: 15 + 25 = %d", t_sum);
        end else begin
            $error("[FAIL] TC1: Tinh sai! Ket qua ra: %d, Mong doi: 40", t_sum);
        end

        // TESTCASE 2: Kiểm thử giá trị biên (Max value / Overflow) ---
        t_a = 8'd255; t_b = 8'd1;
        #10;
        if (t_sum == 9'd256) begin
            $display("[PASS] TC2: 255 + 1 = %d (Giu duoc bit tran ok!)", t_sum);
        end else begin
            $error("[FAIL] TC2: Loi tran bit! Ket qua ra: %d", t_sum);
        end

        // TESTCASE 3: Constrained Random Verification (CRV) nhẹ ---
        // Sinh ngẫu nhiên liên tục 20 cặp số để test tự động
        $display("Chay nguyen nhien 20 cap so tu dong");
        for (int i = 0; i < 20; i++) begin
            t_a = $urandom_range(0, 255);
            t_b = $urandom_range(0, 255);
            #10;
            
            if (t_sum == (t_a + t_b)) begin
                $display("[PASS] Cap %0d: %d + %d = %d", i, t_a, t_b, t_sum);
            end else begin
                $error("[FAIL] Cap %0d: %d + %d bi SAI! Ra: %d", i, t_a, t_b, t_sum);
            end
        end

        $display("");
        $display("[SUCCESS]");
        $display("");
        $finish;
    end

endmodule
