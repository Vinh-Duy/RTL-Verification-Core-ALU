# Educational OOP suite — NOT RUN locally

The repaired files have been inspected but not compiled or simulated with a
capable class/constraint/covergroup simulator. Icarus 13.0 rejected the original
class bench and aborted in its parser. Its success on the flat suite is not
advanced-suite evidence. Verilator is absent; no assumptions about its class or
covergroup support are required by the portable flow.

## Ownership and synchronization

Generator → bounded gen2drv mailbox → driver → drv2mon completion mailbox →
monitor → mon2scb snapshot mailbox → scoreboard → checked-ID mailbox → driver.
All mailboxes have capacity one. There is at most one driven transaction awaiting
verification. Each stimulus object is allocated once and no longer modified after
the generator enqueues it. The monitor allocates a separate snapshot containing
the sampled inputs, result and ID. The scoreboard never reads the live interface.
The monitor also checks that the live driven inputs match the completion token.

The driver waits 1 ns for combinational settling, then sends completion and waits
for the checked ID. This is explicit transaction synchronization; changing the
settling interval does not change mailbox ordering. The scoreboard rejects
unknown values, checks sequential IDs, counts passes/failures, and samples native
coverage only after a successful comparison. A null sentinel passes through all
three transaction channels. Each component returns, and the environment joins all
four tasks. A 10 ms simulation-time watchdog catches a broken completion chain.
No clock has been added to the DUT.

Both examples share `alu_oop_env.svh`; the coverage wrapper enables a compile-time
covergroup. Compile wrappers separately because they intentionally use the same
educational class/interface names. The top names are now distinct. The original
20-transaction OOP and 200-transaction coverage defaults are preserved, configurable
with `+COUNT`. Every opcode is selected in the first eight transactions. Constrained
randomization then uses 10% weight each for 0,1,255 and 70% for 2…254 for each
operand; zero denominators are allowed. Every randomization result is checked.
Objects receive `srandom(seed + id)`; reproducibility is scoped to the same simulator
and version, not bit-identical across different proprietary solvers.

## Example Questa commands (unexecuted here)

A license supporting these SystemVerilog features is required. From the repository
root, use separate compilation libraries for the two alternatives:

```sh
mkdir -p results/advanced
vlib results/advanced/oop_work
vlog -work results/advanced/oop_work -sv +incdir+tb rtl/alu_8bit.sv tb/tb_alu_oop.sv
vsim -c -onfinish stop -lib results/advanced/oop_work tb_alu_oop +COUNT=1000 +SEED=2026 +WAVE=results/advanced/oop.vcd -do 'onerror {quit -code 1}; onbreak {quit -code 1}; run -all; quit -code 0'

vlib results/advanced/coverage_work
vlog -work results/advanced/coverage_work -sv +incdir+tb rtl/alu_8bit.sv tb/tb_alu_coverage.sv
vsim -c -onfinish stop -lib results/advanced/coverage_work tb_alu_coverage +COUNT=1000 +SEED=2026 +WAVE=results/advanced/coverage.vcd -do 'onerror {quit -code 1}; onbreak {quit -code 1}; run -all; quit -code 0'
```

Simulator release/license differences may require command adaptation. Before
trusting this flow, execute it, verify the summary count, and repeat using an
isolated wrong-result DUT to confirm the batch exit code. Until then, repaired
OOP synchronization and native coverage remain inspected implementations, not
validated execution claims. The portable suite independently supplies the
mandatory correctness evidence.
