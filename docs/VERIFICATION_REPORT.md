# Verification report

## 1. Project Overview

This independent educational project develops an unsigned combinational 8-bit ALU
and a reproducible verification environment. The repository preserves its earlier
9-bit-output adder and flat, object-oriented, and coverage-oriented testbench stages.
The work is a hardware engineering exercise, not a tapeout platform or research paper.

## 2. Engineering Motivation

A useful verification result must establish that inputs were driven, outputs were
sampled correctly, comparisons were performed, and errors reached automation.
This project emphasizes those mechanisms alongside arithmetic correctness. It
complements algorithm experiments in the separate EDA routing project without
claiming a complete semiconductor design flow.

## 3. ALU Functional Specification

[ALU_SPECIFICATION.md](ALU_SPECIFICATION.md) defines every opcode. ADD retains
carry, SUB wraps modulo 65536, MUL preserves the full 8×8 product, DIV truncates
and returns zero for a zero denominator, bitwise results are zero extended, and
SHL uses only B[2:0]. Known binary inputs define the finite exhaustive domain.

## 4. RTL Architecture

The ALU contains a complete `always_comb` case with explicit unsigned 16-bit
operand extensions. It has no clock, storage, flags, or modeled propagation delay.
The original default result for an X/Z opcode is retained. The adder explicitly
extends both operands to nine bits. No intentional DUT functionality changed.

## 5. Verification Objectives

Check every operation and relevant arithmetic boundary; reject unknown results for
known inputs; verify error propagation; measure selected functional scenarios;
make failures reproducible; and preserve the educational progression. Exhaustive
finite-input simulation strengthens known-input evidence but does not replace
physical implementation validation or formal verification.

## 6. Verification Environment

Python writes named vectors and independent expected values. A portable SV bridge
drives one transaction at a time, waits 1 ns for combinational settling, captures
the result, then checks stability after another 1 ns. It writes IDs and inputs
with results to CSV, rejects X/Z, counts outcomes, verifies the expected transaction
count and exits through `$fatal` on any failure. Python validates every returned
row, rechecks its result, collects coverage and generates JSON reports. A simulated
watchdog and configurable subprocess timeout bound execution.

The flat SV example remains directly runnable. The shared advanced environment
now separates generator, driver, monitor, scoreboard and coverage sampling using
bounded mailboxes and acknowledgments. Its source is inspected but **NOT RUN** in
a capable simulator; details and commands are in [ADVANCED_SUITE.md](ADVANCED_SUITE.md).
No results from Python are attributed to native covergroups.

## 7. Reference Model

`verification/model.py` uses Python unsigned integers, explicit modulo for SUB,
integer floor division and multiplication by a power of two for SHL. It does not
read DUT outputs. Thirty-two manually derived values live separately in CSV and
are checked against both the model and DUT. Unit tests add subtraction round-trip
and quotient-bound checks. Independent implementations reduce shared coding errors,
but agreement alone cannot prove the specification itself is correct.

## 8. Directed Testing Strategy

The 116-vector suite contains literal known answers, boundaries for all opcodes,
complementary patterns, equal/unequal inputs, repeated identical transactions,
rapid opcode changes and alternating extremes. All vectors execute back to back
through the sequential bridge. Separate ten-case X/Z testing covers selected
four-state semantics outside the core functional coverage domain. The adder retains
its original two directed and twenty random checks and adds all 65,536 input pairs.

## 9. Random Verification Strategy

The Python `random.Random(seed)` stream is local to the run. Opcodes cycle through
0…7 to guarantee all operations and balanced counts; operand values are random.
Each operand independently chooses the boundary pool {0,1,2,127,128,254,255} with
35% probability, otherwise a uniform value 0…255. Thus boundaries can also occur
in the uniform branch. DIV zero is allowed. Count must be at least eight and seed
must fit 0…2^31−1. Default 1,000, smoke 100 and extended 10,000 counts refer only
to random vectors, not extra directed/closure checks. Python/version metadata and
stimulus SHA-256 fingerprints make reproduction inspectable. No cross-version
promise about Python random helper algorithms is required.

## 10. Functional Coverage Model

[COVERAGE_PLAN.md](COVERAGE_PLAN.md) defines 142 reachable bins: operations, A/B
categories, relationships, useful crosses, arithmetic edges and shift scenarios.
Only actually returned, matching, known, stable transactions sample this custom
collector. Coverage is hit bins divided by eligible bins, not a pass-rate measure.
Per-run JSON contains all bin counts; uncovered-bin text files expose gaps.

## 11. Coverage Closure

The first standard run missed four SHL amount × upper-bits-clear bins. Directed
closure adds category witnesses and every shift amount with upper bits both clear
and set. The same 142-bin definition is used before and after. Results are below
and in [RESULTS.md](RESULTS.md); no reachability exceptions were used to inflate
the percentage. Achieving these bins says nothing about unmodeled requirements.

## 12. Assertion and Invariant Checking

Executable DUT checks establish ADD/MUL/AND/OR/XOR commutativity, XOR-self zero,
AND-zero, OR-zero, MUL-zero, DIV-one and zero-shift identities across five boundary
pairs. XOR self-inverse tests use actual first-stage DUT outputs as second-stage
inputs, rather than an oracle-computed intermediate. These form 60 metamorphic
checks over 90 transactions. Every bridge transaction additionally checks knownness
and stable-output behavior. Portable procedural assertions are used instead of
unsupported temporal SVA; no assertion-coverage percentage is claimed.

## 13. Mutation Testing

The runner copies the DUT into ignored results directories and changes ADD to
sum+1, then separately to X. Both runs must complete their input streams, report
mismatches, return nonzero, and omit `Status: PASS`. The harness labels successful
rejection as a passing **mutation test**. A clean known-answer run follows. A unit
integration test independently replaces XOR with OR and verifies the outer Python
process returns 1. Production RTL never needs to be restored because it is never
changed. Missing dependencies, invalid counts, incomplete IDs, malformed inputs,
masked unknown inputs and unknown expected values are also tested failure paths.

## 14. Experimental Setup

The actual environment, timestamps, source hashes, commands and per-run runtimes
are exported to [evidence/final.json](evidence/final.json). The final local toolchain
is Icarus 13.0 and Python 3.10.11 on macOS 13.7.8, x86-64. No external Python
packages are required. Icarus warning-enabled elaboration executes locally;
Verilator was absent and remains NOT RUN for that local experiment. Separately,
[GitHub Actions run #1](https://github.com/Vinh-Duy/RTL-Verification-Core-ALU/actions/runs/38939887081) succeeded for `cdc8e24`, and
[run #2](https://github.com/Vinh-Duy/RTL-Verification-Core-ALU/actions/runs/38943467205) succeeded for `1621da9`, each on an Ubuntu 24.04 job
configured for Python 3.12. GitHub API metadata confirms successful simulator
installation, regression, exhaustive simulation, waveform generation and artifact
upload. The workflow installs Icarus and Verilator; the regression includes RTL
lint. This establishes the configured portable CI result, not advanced-suite
execution. Exact CI tool versions and numerical reports were not independently
inspected; see the [CI evidence scope](RESULTS.md#github-actions-verification-separate-from-local-experiments).

## 15. Results

The table below preserves the original macOS experiment. The fresh review at base
commit `1621da9` has separate execution evidence in [FINAL_REVIEW.md](FINAL_REVIEW.md);
its results do not overwrite these historical measurements.

<!-- measured-results:start -->
| Local executed check | Local measured result |
|---|---|
| Directed ALU suite | 116 checked, 116 passed |
| Standard closed suite | 1,333 checked, 1,333 passed; seed 2026 |
| Custom functional coverage | 138/142 (97.18%) before → 142/142 (100.00%) after closure |
| Exhaustive ALU | 524,288 checked, all passed; 24.183 s |
| Adder example | 65,558 passed, including all 65,536 input pairs |
| Verifier tests | 16 unit/integration tests passed; ADD and X-output mutants rejected |
| Advanced OOP / native covergroups | NOT RUN |
<!-- measured-results:end -->

[RESULTS.md](RESULTS.md) lists every retained local configuration with simulator,
OS, seed, checked/pass/fail counts, coverage, completion and measured runtime.
Raw CSV, simulator logs and coverage JSON are under ignored `results/`; compact
measured snapshots and selected logs remain under `docs/evidence/`. Early
exploratory measurements are separately retained in `exploratory.json`. The new
`github-actions-1.json` and `github-actions-2.json` records contain GitHub run/job/step
metadata only. No local
counts, runtimes or coverage results have been replaced with CI values.

The original ALU at Git revision `32430ca` also passed all 524,288 known-input
combinations against this specification. Its actual log and report are archived
in `docs/evidence/`. This provides evidence that explicit sizing preserved behavior;
it does not justify describing implicit sizing as a corrected functional defect.
Exhaustive simulation covers the finite combinational truth table, not timing,
power, synthesis equivalence, analog behavior or future source revisions.

## 16. Bugs Identified and Corrected

[AUDIT.md](AUDIT.md) records initial evidence and severity. Verification corrections
include unconditional success, discarded randomization status, missing counts and
IDs, no monitor/snapshot path, fragile delay synchronization, lack of explicit
termination, missing zero-divisor reference behavior, and unsubstantiated README
claims. The OOP structural corrections remain unvalidated by simulation. RTL
changes clarify widths and signedness; no functional arithmetic bug was established.

## 17. Limitations

Advanced OOP and native covergroups remain unexecuted on a capable simulator.
Verilator lint remains unexecuted in the original local experiment, although the
portable CI run passed with Verilator installed. Manual GTKWave viewing remains
unexecuted, and detailed CI logs and artifact contents were not independently
inspected in this review. The workflow now selects Node.js 24 action majors, but
that edited workflow has **NOT RUN** on GitHub; both verified runs predate the upgrade.
No synthesis, gate-level, physical timing,
code coverage or formal proof has been performed. Four-state testing is targeted,
not exhaustive. Delay-based settling assumes the current zero-delay combinational
DUT. Functional bin selection is intentionally limited, not a universal completeness
claim. The preserved default unknown-opcode result can mask invalid inputs unless
the testbench enforces its known-input contract.

## 18. Future Work

Execute and negatively validate the advanced suite on a capable simulator; run
Verilator locally when available, retain CI checks for subsequent commits, and
validate the pending action-version upgrade on GitHub;
consider synthesis and timing experiments with a
specified target technology; and extend four-state tests if the input contract
changes. Keep each addition tied to a measurable question. UVM migration and new
hardware blocks are outside the current scope.

## 19. Reproduction Instructions

Install Python 3.10–3.14, Icarus Verilog and optionally Verilator/GTKWave. See the
README for platform commands. Run `make clean`, `make regression`, `make exhaustive`
and `make waveform`. `make test-random SEED=2026 COUNT=10000` selects a larger run.
The full experiment/export command list is in RESULTS.md. `TIMEOUT=300` raises
the per-process wall-clock limit on a slow machine. Each negative fixture and
clean follow-up has its own output directory and status.

To reproduce the original baseline without changing the checkout:

```sh
mkdir -p build
git show 32430ca:rtl/alu_8bit.sv > build/original_alu.sv
python3 -m verification.run --mode exhaustive --rtl build/original_alu.sv --output results/original_exhaustive
```

Inspect `git diff` before committing. Re-export
measured tables after changing verification or DUT sources. Do not treat a saved
snapshot as proof for a later modified design.

The central lessons are that bit widths are part of the hardware specification,
a comparison is useful only if its failure reaches the process exit status, and
transaction synchronization and coverage require explicit evidence rather than
plausible delays or large random counts.
