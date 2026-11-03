# Portfolio Description

## One-sentence summary

Built and independently verified an unsigned 8-bit ALU using portable
simulation, exhaustive checking, SAT equivalence, formal-derived mutation
testing, and an adversarial audit of the verification infrastructure.

## Technical summary (68 words)

This independent RTL project implements an eight-operation combinational 8-bit
ALU with a 16-bit result. A Python oracle, SystemVerilog vector bridge, seeded
random and exhaustive simulation, custom functional coverage, and negative tests
form the portable layer. Yosys SAT proves the known-binary contract and a
seven-mutant audit validates failure detection. A Verilator 5.052 OOP/CRV suite
adds native coverage, reproducibility, and a faulty-DUT control in CI.

## Detailed project description (178 words)

I developed a small RTL verification environment around an unsigned
combinational 8-bit ALU whose 16-bit output makes arithmetic width part of the
specification. The project separates production RTL, an independently written
Python reference model, a SystemVerilog vector bridge, a formal specification,
and an advanced class-based testbench. The portable flow checks directed
answers, seeded random traffic, metamorphic relationships, selected four-state
behavior, and all 524,288 known-binary input combinations. Its defined Python
functional coverage plan reached 142/142 bins.

To test the verification infrastructure rather than only the DUT, I generated
seven validated semantic mutants covering arithmetic truncation, division
semantics, sign extension, and shift behavior. Yosys SAT found counterexamples;
Python and Icarus independently validated all seven. A separate adversarial
audit exercised ambiguous transformations, malformed solver/VCD evidence,
timeouts, missing artifacts, and status propagation. The advanced Verilator
5.052 CI job completed 4,096 OOP/CRV transactions, reproduced same-seed
stimulus, reached 100% of its native covergroup bins, and rejected a faulty
ALU. Results are reported with explicit local/CI provenance and limitations.

## Five grounded highlights

1. Exhaustively simulated 524,288 known-binary ALU input combinations with zero
   clean failures.
2. Closed a 142-bin custom functional coverage plan without conflating it with
   native covergroup or code coverage.
3. Killed seven selected formal-derived semantic mutants and independently
   validated every counterexample through Python and Icarus replay.
4. Built a non-UVM OOP/CRV environment with mailbox synchronization, snapshots,
   acknowledgments, watchdog behavior, and native covergroups.
5. Found and fixed a real Yosys SAT-result marker compatibility issue while
   preserving fail-closed classification.

## Interview questions and defensible answers

### Why is exhaustive simulation not the same as formal proof?

Exhaustive simulation enumerates this finite DUT's known binary input space and
observes simulator results. The SAT miter reasons over that same two-state
domain symbolically and checks the equality property. Neither establishes
four-state behavior, physical timing, synthesis quality, or correctness of a
wrong shared specification.

### Why does the result have 16 bits?

ADD must retain the carry from 255 + 255, multiplication needs the full product,
and left shifts can move bits above bit 7. SUB is explicitly unsigned modulo
65536, so 0 - 1 is `16'hffff`. These are behavioral requirements, not merely
signal declarations.

### How was a false PASS risk tested?

The project used faulty DUTs, malformed rows, unknown values, missing tools,
invalid transformations, incomplete VCD evidence, solver ambiguity, stale
artifacts, and a real Yosys marker mismatch. The infrastructure must return a
failure or unresolved status rather than convert incomplete evidence into PASS.

### What does seven-mutant coverage prove?

It proves that seven selected, deliberate semantic faults were detected and
that their counterexamples passed independent validation. It does not prove
that every possible RTL fault or every specification error would be detected.

### Why is the advanced environment not UVM?

It uses SystemVerilog classes, mailboxes, a virtual interface, constraints, and
covergroups to demonstrate OOP verification concepts, but it has no UVM library,
factory, phases, or UVM components. Calling it UVM would be inaccurate.
