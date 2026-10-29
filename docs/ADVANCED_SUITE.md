# Advanced SystemVerilog OOP, CRV and native coverage

## Current status

The advanced suite now has a dedicated `make advanced` runner and Linux CI job.
The runner is pinned to Verilator 5.052, checks the CRV/covergroup feature probe,
executes the real OOP bench twice with the same seed, runs the native coverage
wrapper, and requires a controlled faulty-ALU run to fail its scoreboard.

This change has **not yet been executed with Verilator 5.052**. The local machine
has Icarus Verilog but no Verilator or Z3, and this request explicitly does not
authorize a commit or push. Therefore no advanced simulator pass, native coverage
total, or negative-control result is claimed yet. A GitHub Actions run on this
revision is needed to complete the evidence. `make advanced` exits nonzero and
prints `ADVANCED NOT RUN` when a required executable is absent.

## Source audit

The actual suite is in `tb/alu_oop_env.svh`, included separately by
`tb/tb_alu_oop.sv` and `tb/tb_alu_coverage.sv`:

- `transaction`, `generator`, `driver`, `monitor`, `scoreboard`, and `environment`
  are SystemVerilog classes. There is no class inheritance (`extends`).
- The transaction has `rand logic` operands and opcode, with `dist` constraints
  weighting each operand's 0, 1 and 255 values at 10 each and the 2–254 range at
  70 total. `randomize()` is checked for every generated transaction.
- Objects are seeded with `srandom(seed + id)`. The first eight opcodes are then
  set to 0–7 so each operation is exercised at least once.
- Synchronization uses parameterized mailboxes for generated transactions,
  driver/monitor completion, monitor/scoreboard snapshots, and checked-ID
  acknowledgments. There are no named events in the current bench.
- A SystemVerilog interface and virtual interface connect the classes to the
  combinational DUT. The testbench uses `fork...join`, `#1ns` settling, an end
  sentinel, and a 10 ms watchdog. A scoreboard mismatch is fatal after the
  outstanding transactions drain.
- Only `tb/tb_alu_coverage.sv` defines `ALU_NATIVE_COVERAGE`. Its covergroup has
  opcode bins, four operand-category bins for each input, and opcode-by-operand
  crosses. It samples only after the independent expected result matches the DUT.
  It is a native simulator metric and is not the Python 142-bin plan.

Targets that execute the suite: before this change, none of the Make targets or
CI jobs compiled these wrappers. The portable targets use flat benches and do
not exercise these OOP classes. `make advanced` is the new explicit target.

## Simulator and acceptance checks

Verilator 5.050 introduced covergroup/coverpoint/bin support; the job selects
release v5.052, which also supports the suite's `dist` randomization and coverage
runtime. Official references:
[Verilator 5.052 change log](https://verilator.org/guide/latest/changes.html),
[coverage collection guide](https://verilator.org/guide/latest/simulating.html#coverage-analysis),
[warning reference](https://verilator.org/guide/latest/warnings.html), and
[constraint solver setup](https://verilator.org/guide/latest/install.html#install-z3).
The release notes and documented feature availability establish the candidate
version; they do not substitute for a successful run of this repository's bench.

The runner enforces the following checks and retains logs in ignored
`results/advanced/`:

1. A small feature probe requires native `randomize()` to honor a nontrivial
   `inside`/`dist` constraint and requires both covergroup bins to reach 100%.
2. The OOP bench must complete all transactions, report zero checker failures,
   and produce byte-identical stimulus records on repeated runs with the same
   seed. It checks that recorded CRV outcomes are consistent with the configured
   distribution; warning IDs `CONSTRAINTIGN`, `COVERAGEIGN`, `UNSUPPORTED` and
   `UNSATCONSTR` fail the job.
3. The native coverage wrapper must finish the same number of checked
   transactions, reach 100% of its defined opcode/operand-category covergroup
   bins through `get_inst_coverage()`, and produce a `verilator_coverage` report
   containing native covergroup results.
4. The negative control wraps the real ALU and adds one to every ADD result. The
   advanced scoreboard must report a mismatch and exit unsuccessfully.

The distribution check is a finite seeded statistical check of the documented
`dist` weighting, not a proof of a solver's probability distribution. Seed
reproduction is scoped to the pinned Verilator 5.052/Z3 4.8.12 environment. No coverage
denominator from the native covergroup is merged with the Python custom bins.

## Reproduction

On a machine with Verilator 5.052, Z3 4.8.12, and a C++ compiler:

```sh
make advanced SEED=2026 COUNT=4096
```

The dedicated `advanced` GitHub Actions job builds the official Verilator v5.052
tag on Ubuntu 24.04 and installs Z3 4.8.12 from its pinned Ubuntu package. It
records simulator/solver versions, uses seed 2026 and 4096 transactions, has a
35-minute timeout, and uploads logs, waveform, and native
coverage data even on failure. The existing portable Icarus regression and
formal job remain separate. Exact advanced outcome and coverage counts are only
reported after that job has actually run.
