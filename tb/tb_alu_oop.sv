// 1. KHOI TAO INTERFACE
interface alu_if;
    logic [7:0] a, b;
    logic [2:0] opcode;
    logic [15:0] result;
endinterface

// 2. CLASS TRANSACTION
class transaction;
    rand logic [7:0] a;
    rand logic [7:0] b;
    rand logic [2:0] opcode;
    logic [15:0] result;

    constraint c_div_by_zero {
        if (opcode == 3'b011) b != 0;
    }
endclass

// 3. CLASS GENERATOR
class generator;
    mailbox #(transaction) gen2drv;
    int num_transactions;

    function new(mailbox #(transaction) gen2drv, int num_transactions);
        this.gen2drv = gen2drv;
        this.num_transactions = num_transactions;
    endfunction

    task run();
        transaction tx;
        for (int i = 0; i < num_transactions; i++) begin
            tx = new();
            void'(tx.randomize()); // Fix warning "result is ignored"
            gen2drv.put(tx);
        end
    endtask
endclass

// 4. CLASS DRIVER
class driver;
    virtual alu_if vif;
    mailbox #(transaction) gen2drv; // Fix warning mailbox

    function new(virtual alu_if vif, mailbox #(transaction) gen2drv);
        this.vif = vif;
        this.gen2drv = gen2drv;
    endfunction

    task run();
        transaction tx;
        forever begin
            gen2drv.get(tx);
            vif.a = tx.a;
            vif.b = tx.b;
            vif.opcode = tx.opcode;
            #5; 
        end
    endtask
endclass

// 5. CLASS SCOREBOARD
class scoreboard;
    virtual alu_if vif;
    int num_transactions;

    function new(virtual alu_if vif, int num_transactions);
        this.vif = vif;
        this.num_transactions = num_transactions;
    endfunction

    task run();
        logic [15:0] expected_result;
        string op_name;

        for (int i = 0; i < num_transactions; i++) begin
            #5; 
            case (vif.opcode)
                3'b000: begin expected_result = vif.a + vif.b; op_name = "ADD"; end
                3'b001: begin expected_result = vif.a - vif.b; op_name = "SUB"; end
                3'b010: begin expected_result = vif.a * vif.b; op_name = "MUL"; end
                3'b011: begin expected_result = vif.a / vif.b; op_name = "DIV"; end
                3'b100: begin expected_result = vif.a & vif.b; op_name = "AND"; end
                3'b101: begin expected_result = vif.a | vif.b; op_name = "OR "; end
                3'b110: begin expected_result = vif.a ^ vif.b; op_name = "XOR"; end
                3'b111: begin expected_result = vif.a << vif.b[2:0]; op_name = "SHL"; end
            endcase

            if (vif.result === expected_result)
                $display("[PASS] %s | a=%3d, b=%3d | Result=%5d", op_name, vif.a, vif.b, vif.result);
            else
                $display("[FAIL] %s | Loi! Mach=%5d, Dung=%5d", op_name, vif.result, expected_result);
        end
    endtask
endclass

// 6. CLASS ENVIRONMENT
class environment;
    generator gen;
    driver    drv;
    scoreboard scb;
    mailbox #(transaction) gen2drv;
    virtual alu_if vif;
    int num_transactions = 20;

    function new(virtual alu_if vif);
        this.vif = vif;
        gen2drv = new();
        gen = new(gen2drv, num_transactions);
        drv = new(vif, gen2drv);
        scb = new(vif, num_transactions);
    endfunction

    task run();
        fork
            drv.run();
        join_none
        
        fork
            gen.run();
            scb.run();
        join
    endtask
endclass

// 7. TOP MODULE
module tb_alu_oop;
    alu_if vif(); 
    
    alu_8bit dut (
        .a(vif.a),
        .b(vif.b),
        .opcode(vif.opcode),
        .result(vif.result)
    );

    environment env;

    initial begin
        $dumpfile("dump.vcd");
        $dumpvars;

        $display("");
        $display("[START]");
        $display("");
        
        env = new(vif);
        env.run(); 
        
        $display("");
        $display("[SUCCESS]");
        $display("");
        $finish;
    end
endmodule