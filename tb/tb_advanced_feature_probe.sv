`timescale 1ns/1ps
// A small tool-capability gate for native class constraints and covergroups.
class constrained_probe_item;
    rand bit [7:0] value;
    constraint legal_values {
        value inside {8'h5a, 8'ha5};
        value dist {8'h5a := 1, 8'ha5 := 1};
    }
endclass

module tb_advanced_feature_probe;
    bit [7:0] sampled_value;
    int sample_count = 0;
    constrained_probe_item item;

    covergroup probe_cg;
        cp_value: coverpoint sampled_value {
            bins lower = {8'h5a};
            bins upper = {8'ha5};
        }
    endgroup

    probe_cg cg;
    initial begin
        item = new();
        item.srandom(2026);
        cg = new();
        repeat (32) begin
            if (!item.randomize()) $fatal(1, "PROBE randomize() failed");
            if (item.value != 8'h5a && item.value != 8'ha5)
                $fatal(1, "PROBE constraint was not honored: value=%02h", item.value);
            sampled_value = item.value;
            cg.sample();
            sample_count++;
        end
        if (cg.get_inst_coverage() != 100.0)
            $fatal(1, "PROBE covergroup bins incomplete: coverage=%0.2f%%", cg.get_inst_coverage());
        $display("FEATURE_PROBE PASS randomize=%0d native_covergroup=%0.2f%%",
                 sample_count, cg.get_inst_coverage());
        $finish;
    end
endmodule
