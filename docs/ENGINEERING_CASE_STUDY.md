# Engineering Case Study: Verifying a Small ALU

## 1. Engineering problem

An eight-bit combinational ALU is small enough to understand completely, but it
still exposes the failure modes that make verification nontrivial: arithmetic
width, division-by-zero behavior, masked shift amounts, transaction ordering,
unknown values, and error propagation into automation. A few hand-written
examples can pass while a carry, wraparound, or checker failure path remains
untested.

This project therefore treats the verification infrastructure as an engineering
subject. The goal is not to claim industrial sign-off. The goal is to make each
layer measurable, independent where practical, and explicit about what it does
and does not establish.

## 2. Architecture and ownership

The production DUT is [rtl/alu_8bit.sv](../rtl/alu_8bit.sv). Its contract is
also written as [formal/alu_spec.sv](../formal/alu_spec.sv), while the Python
model in [verification/model.py](../verification/model.py) provides a separate
integer oracle. The portable bridge passes vectors into SystemVerilog, captures
results, validates IDs and knownness, and returns failures through simulator
status and Python exit status.

The formal miter compares the DUT and specification independently of the
portable vector bridge. The advanced bench uses classes and mailboxes to test
generator, driver, monitor, scoreboard, and coverage behavior. The mutation
campaign creates isolated DUT copies rather than modifying production RTL.

## 3. Portable verification

The portable layer combines:

- Literal directed answers for boundaries, wraparound, division, products, and
  shifts.
- Seeded random traffic with a documented boundary/interior weighting.
- Metamorphic checks for algebraic relationships.
- Exhaustive simulation of all `2^8 * 2^8 * 2^3 = 524,288` known inputs.
- A Python functional coverage plan with 142 reachable bins.
- Isolated faulty-DUT tests that must fail, followed by a clean-DUT pass.

Coverage is sampled only after a transaction is returned, stable, known, and
equal to the independent expected value. This prevents a failed transaction
from inflating coverage. The closed local run reached 142/142 bins; that is a
statement about the defined scenario plan, not code coverage or universal
hardware correctness.

## 4. Advanced SystemVerilog environment

The advanced environment in [tb/alu_oop_env.svh](../tb/alu_oop_env.svh) is
deliberately small and educational. It is not UVM. Its generator randomizes
transactions with `dist` constraints, the driver owns interface writes, the
monitor takes immutable snapshots, and the scoreboard checks ordered IDs and
expected results. Parameterized mailboxes, an end sentinel, acknowledgments,
and a watchdog prevent the old independent-delay pattern from silently losing
or reordering work.

The native coverage wrapper defines a separate covergroup plan for opcode and
operand categories. The runner first probes native constraint and covergroup
support, then executes 4,096 transactions twice with the same seed, checks the
weighted distribution, requires all scoreboard checks to pass, and runs a
deliberately faulty ADD control. GitHub Actions validated Verilator 5.052,
native coverage at 80/80 bins, same-seed reproducibility, and rejection of the
faulty control.

## 5. Formal verification

The formal model is a two-state combinational problem with 19 input bits and a
16-bit result. Yosys elaborates the DUT, specification, and miter, then solves
the mismatch property. A correct baseline must prove UNSAT: there is no
known-binary input for which the complete result differs.

The formal negative control truncates ADD before zero extension. It must produce
SAT and a counterexample. This is not a timing proof, an X/Z proof, a synthesis
check, or a proof that the specification itself is correct.

## 6. Formal-derived semantic mutation audit

The audit in [formal/mutation_audit.py](../formal/mutation_audit.py) evaluates
seven selected single-fault transformations:

| Mutant | Fault model | Expected outcome |
|---|---|---|
| `ADD_DROP_CARRY` | Truncate ADD to eight bits | KILLED |
| `SUB_TRUNCATE_TO_8` | Truncate SUB to eight bits | KILLED |
| `MUL_TRUNCATE_TO_8` | Truncate MUL to eight bits | KILLED |
| `DIV_ZERO_GUARD_ERROR` | Return `ffff` for zero divisor | KILLED |
| `DIV_ROUND_UP` | Round division upward | KILLED |
| `AND_SIGN_EXTENSION` | Sign-extend AND | KILLED |
| `SHL_USE_FULL_B` | Use all of B as shift amount | KILLED |

Before the campaign, source fingerprints, module name, interface, and exact
anchor count are checked. Each transformation must change exactly one intended
source line and preserve the interface. A baseline compile and UNSAT proof are
mandatory before mutants run.

For each mutant, SAT evidence is read from the solver result and VCD, not
inferred from a process exit code. The candidate input and both full 16-bit
outputs are checked by Python and replayed through Icarus using the generated
mutant. Only an independently validated mismatch is classified as KILLED.
`UNKNOWN`, timeout, missing tools, malformed evidence, compile failure, and
tool error remain distinct non-success outcomes.

## 7. Adversarial infrastructure audit

Phase 3 tested false-PASS risks in generation, SAT parsing, VCD handling,
independent validators, status propagation, artifact integrity, stale outputs,
and reproducibility. The audit included 42 Python tests, 26 of them focused on
formal mutation behavior.

A real compatibility failure occurred when Yosys 0.33 emitted `SAT proof
finished` while the parser recognized only `SAT solving finished`. The campaign
correctly classified the mismatch as `TOOL_ERROR` instead of claiming a mutant
kill. The parser was extended to recognize the emitted marker, regression
coverage was added, and a subsequent CI run passed. This is the intended
fail-closed behavior: missing or ambiguous evidence cannot become PASS.

## 8. Measured results and provenance

### Fresh local execution

The portable local environment used Python 3.10.11 and Icarus Verilog 13.0.
It executed the regression, exhaustive simulation, mutation tests, waveform
generation, and unit tests. The local evidence records 524,288/524,288
exhaustive checks, 142/142 custom bins, and zero clean failures. Yosys,
Verilator, and Z3 were unavailable locally, so formal and advanced execution
are not local results.

### GitHub Actions evidence

The cited Ubuntu 24.04 runs passed all three jobs:

- Run [41421667512](https://github.com/Vinh-Duy/RTL-Verification-Core-ALU/actions/runs/41421667512)
  at `f3b9e4a` validated the recovered advanced CI path.
- Run [41426335398](https://github.com/Vinh-Duy/RTL-Verification-Core-ALU/actions/runs/41426335398)
  at `d8e5be7` exercised the seven-mutant audit and artifact preservation.
- Run [41591123907](https://github.com/Vinh-Duy/RTL-Verification-Core-ALU/actions/runs/41591123907)
  at `bced75a` is the final pre-portfolio validation, with formal, portable,
  and advanced jobs passing.

The [evidence index](EVIDENCE_INDEX.md) lists the artifacts for each run and
explains how to download them. Artifact availability is subject to GitHub
retention.

### Historical evidence

Older reports under `docs/evidence/` preserve earlier local measurements and
the progression from the adder example to the flat bench, OOP design, formal
checks, and advanced CI. They are historical snapshots, not fresh executions
of the current rewritten commit.

## 9. Threats to validity

- Seven mutants are selected fault models, so mutation adequacy is not
  exhaustive.
- The design is too small to demonstrate scalability to a large SoC.
- The Python oracle and formal specification can share an interpretation error;
  literal answers, properties, and cross-layer replay reduce but do not remove
  that risk.
- Formal proof is two-state; selected four-state tests do not cover every X/Z
  combination.
- Results depend on simulator, solver, operating system, and pinned tool
  versions.
- The adversarial suite exercises important scenarios but cannot enumerate every
  possible CI, filesystem, or tool failure.
- No PPA, timing, synthesis, physical, or silicon conclusion follows from this
  repository.

## 10. Engineering lessons

1. Width belongs in the behavioral contract: retaining ADD carry and defining
   16-bit subtraction prevents “obvious” but wrong eight-bit assumptions.
2. A settling delay is not transaction synchronization. Completion mailboxes,
   immutable snapshots, IDs, and acknowledgments provide ownership and order.
3. A green checker is not enough; deliberate faulty RTL is required to exercise
   the failure path.
4. SAT status must be interpreted together with solver output, exit code, and
   validated evidence.
5. Artifact preservation is part of verification: a failed setup must explain
   itself, not disappear before diagnosis.
