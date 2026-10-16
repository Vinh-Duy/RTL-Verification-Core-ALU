`timescale 1ns/1ps
// File bridge: Python writes independent expected values; SV checks four states.
module tb_alu_vectors;
    logic [7:0] a, b;
    logic [2:0] opcode;
    logic [15:0] result, expected, first_result;
    integer input_fd, output_fd, scanned, id, total = 0, passed = 0, failed = 0;
    integer expected_count, seed;
    string vectors_path, output_path, wave_path;
    alu_8bit dut(.a(a), .b(b), .opcode(opcode), .result(result));

    initial begin
        if (!$value$plusargs("VECTORS=%s", vectors_path) ||
            !$value$plusargs("OUTPUT=%s", output_path) ||
            !$value$plusargs("COUNT=%d", expected_count) ||
            !$value$plusargs("SEED=%d", seed)) $fatal(1, "Missing bridge arguments");
        if ($value$plusargs("WAVE=%s", wave_path)) begin
            $dumpfile(wave_path);
            $dumpvars(0, tb_alu_vectors);
        end
        input_fd = $fopen(vectors_path, "r");
        output_fd = $fopen(output_path, "w");
        if (!input_fd || !output_fd) $fatal(1, "Cannot open bridge files");
        $fdisplay(output_fd, "id,a,b,opcode,expected,actual,stable,status");
        scanned = $fscanf(input_fd, "%d %h %h %h %h\n", id, a, b, opcode, expected);
        while (scanned == 5) begin
            if (id != total) $fatal(1, "Unexpected transaction id %0d", id);
            #1; // Allow zero-delay combinational evaluation; not a handshake.
            first_result = result;
            #1; // Inputs stay stable; also check output determinism.
            total++;
            if ((^{a, b, opcode} === 1'bx) ||
                (^result === 1'bx) || (^expected === 1'bx) ||
                result !== expected || result !== first_result) begin
                failed++;
                if (failed <= 10)
                    $display("MISMATCH id=%0d seed=%0d op=%0d a=%0d b=%0d expected=%h actual=%h",
                             id, seed, opcode, a, b, expected, result);
                $fdisplay(output_fd, "%0d,%0d,%0d,%0d,%0d,%h,%0d,FAIL",
                          id, a, b, opcode, expected, result, result === first_result);
            end else begin
                passed++;
                $fdisplay(output_fd, "%0d,%0d,%0d,%0d,%0d,%h,1,PASS",
                          id, a, b, opcode, expected, result);
            end
            scanned = $fscanf(input_fd, "%d %h %h %h %h\n", id, a, b, opcode, expected);
        end
        if (!$feof(input_fd) || (scanned != -1 && scanned != 0))
            $fatal(1, "Malformed stimulus after transaction %0d", total);
        $fclose(input_fd);
        $fclose(output_fd);
        $display("VERIFICATION SUMMARY total=%0d passed=%0d failed=%0d seed=%0d",
                 total, passed, failed, seed);
        if (failed || total != expected_count || total == 0)
            $fatal(1, "Status: FAIL (expected %0d transactions)", expected_count);
        $display("Status: PASS");
        $finish;
    end
    initial begin
        #10000000;
        $fatal(1, "Watchdog expired");
    end
endmodule
