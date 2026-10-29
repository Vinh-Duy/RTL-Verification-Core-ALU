`timescale 1ns/1ps
// Compile either wrapper separately. Requires classes, constraints and mailboxes.
interface alu_if;
    logic [7:0] a, b;
    logic [2:0] opcode;
    logic [15:0] result;
endinterface

class transaction;
    rand logic [7:0] a, b;
    rand logic [2:0] opcode;
    logic [15:0] result;
    int id;
    constraint boundaries {
        a dist {0 := 10, 1 := 10, 255 := 10, [2:254] :/ 70};
        b dist {0 := 10, 1 := 10, 255 := 10, [2:254] :/ 70};
    }
endclass

class generator;
    mailbox #(transaction) gen2drv;
    int count, seed;
    function new(mailbox #(transaction) channel, int count, int seed);
        gen2drv = channel; this.count = count; this.seed = seed;
    endfunction
    task run();
        transaction tx;
        for (int i = 0; i < count; i++) begin
            tx = new();
            tx.srandom(seed + i);
            if (!tx.randomize()) $fatal(1, "Randomization failed id=%0d seed=%0d", i, seed);
            tx.id = i;
            // Every opcode appears in the first eight transactions.
            if (i < 8) tx.opcode = 3'(i);
            $display("ADVANCED_STIMULUS id=%0d seed=%0d opcode=%0d a=%0d b=%0d",
                     tx.id, seed, tx.opcode, tx.a, tx.b);
            gen2drv.put(tx); // Ownership transfers; generator never reuses tx.
        end
        gen2drv.put(null); // Explicit end of stream.
    endtask
endclass

class driver;
    virtual alu_if vif;
    mailbox #(transaction) gen2drv, drv2mon;
    mailbox #(int) checked;
    function new(virtual alu_if vif, mailbox #(transaction) gen2drv,
                 mailbox #(transaction) drv2mon, mailbox #(int) checked);
        this.vif = vif; this.gen2drv = gen2drv;
        this.drv2mon = drv2mon; this.checked = checked;
    endfunction
    task run();
        transaction tx;
        int acknowledged_id;
        forever begin
            gen2drv.get(tx);
            if (tx == null) begin drv2mon.put(null); break; end
            vif.a = tx.a; vif.b = tx.b; vif.opcode = tx.opcode;
            #1ns; // Only combinational settling; completion uses mailboxes.
            drv2mon.put(tx);
            checked.get(acknowledged_id);
            if (acknowledged_id != tx.id) $fatal(1, "Wrong driver acknowledgment");
        end
    endtask
endclass

class monitor;
    virtual alu_if vif;
    mailbox #(transaction) drv2mon, mon2scb;
    function new(virtual alu_if vif, mailbox #(transaction) drv2mon,
                 mailbox #(transaction) mon2scb);
        this.vif = vif; this.drv2mon = drv2mon; this.mon2scb = mon2scb;
    endfunction
    task run();
        transaction sent, snapshot;
        forever begin
            drv2mon.get(sent);
            if (sent == null) begin mon2scb.put(null); break; end
            if ({vif.a, vif.b, vif.opcode} !== {sent.a, sent.b, sent.opcode})
                $fatal(1, "Driver/monitor stimulus disagreement id=%0d", sent.id);
            snapshot = new();
            snapshot.id = sent.id;
            snapshot.a = vif.a; snapshot.b = vif.b; snapshot.opcode = vif.opcode;
            snapshot.result = vif.result;
            mon2scb.put(snapshot); // No subsequent mutations of this object.
        end
    endtask
endclass

class scoreboard;
    mailbox #(transaction) mon2scb;
    mailbox #(int) checked;
    int count, seed, total = 0, passed = 0, failed = 0;
    `include "alu_reference.svh"
`ifdef ALU_NATIVE_COVERAGE
    logic [7:0] sampled_a, sampled_b;
    logic [2:0] sampled_opcode;
    covergroup alu_cg;
        option.per_instance = 1;
        cp_opcode: coverpoint sampled_opcode { bins operations[] = {[0:7]}; }
        cp_a: coverpoint sampled_a {
            bins zero = {0}; bins one = {1}; bins max = {255}; bins other = {[2:254]};
        }
        cp_b: coverpoint sampled_b {
            bins zero = {0}; bins one = {1}; bins max = {255}; bins other = {[2:254]};
        }
        op_a: cross cp_opcode, cp_a;
        op_b: cross cp_opcode, cp_b;
    endgroup
`endif
    function new(mailbox #(transaction) mon2scb, mailbox #(int) checked, int count, int seed);
        this.mon2scb = mon2scb; this.checked = checked;
        this.count = count; this.seed = seed;
`ifdef ALU_NATIVE_COVERAGE
        alu_cg = new();
`endif
    endfunction
    task run();
        transaction tx;
        logic [15:0] expected;
        forever begin
            mon2scb.get(tx);
            if (tx == null) break;
            if (tx.id != total) $fatal(1, "Missing/duplicate/out-of-order transaction id=%0d", tx.id);
            expected = alu_expected(tx.a, tx.b, tx.opcode);
            total++;
            if ($isunknown({tx.a, tx.b, tx.opcode, tx.result, expected}) || tx.result !== expected) begin
                failed++;
                $display("MISMATCH id=%0d seed=%0d op=%0d a=%0d b=%0d expected=%h actual=%h",
                         tx.id, seed, tx.opcode, tx.a, tx.b, expected, tx.result);
            end else begin
                passed++;
`ifdef ALU_NATIVE_COVERAGE
                sampled_a = tx.a; sampled_b = tx.b; sampled_opcode = tx.opcode;
                alu_cg.sample();
`endif
            end
            checked.put(tx.id); // Driver may advance only after this check.
        end
        $display("VERIFICATION SUMMARY total=%0d passed=%0d failed=%0d seed=%0d", total, passed, failed, seed);
`ifdef ALU_NATIVE_COVERAGE
        $display("Native covergroup coverage (separate metric): %0.2f%%", alu_cg.get_inst_coverage());
        if (alu_cg.get_inst_coverage() < 100.0)
            $fatal(1, "Native covergroup bins incomplete: %0.2f%%", alu_cg.get_inst_coverage());
`endif
        if (failed || total != count) $fatal(1, "Status: FAIL");
        $display("Status: PASS");
    endtask
endclass

class environment;
    generator gen;
    driver drv;
    monitor mon;
    scoreboard scb;
    mailbox #(transaction) gen2drv, drv2mon, mon2scb;
    mailbox #(int) checked;
    function new(virtual alu_if vif, int count, int seed);
        gen2drv = new(1); drv2mon = new(1); mon2scb = new(1); checked = new(1);
        gen = new(gen2drv, count, seed);
        drv = new(vif, gen2drv, drv2mon, checked);
        mon = new(vif, drv2mon, mon2scb);
        scb = new(mon2scb, checked, count, seed);
    endfunction
    task run();
        fork
            gen.run(); drv.run(); mon.run(); scb.run();
        join // All four terminate by propagating the end sentinel.
    endtask
endclass
