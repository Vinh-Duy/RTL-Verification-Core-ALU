# Project summary for application preparation

## A. Short English summary (130 words)

This independent digital hardware project develops and verifies an unsigned
8-bit arithmetic logic unit with eight operations and a 16-bit output. It retains
an earlier adder and compares simple sequential testing with an educational
object-oriented SystemVerilog environment. The executable baseline combines Icarus
Verilog with a Python integer reference model, manually derived corner cases,
reproducible random inputs, and a defined functional coverage plan. Verification
includes explicit failure counters, unknown-value rejection, transaction-count
checks, metamorphic properties, and isolated faulty designs that test the checker
itself. Exhaustive simulation checked all 524,288 known-input ALU combinations
successfully. The work illustrates how arithmetic width, simulator scheduling,
and trustworthy failure reporting affect engineering conclusions. Advanced
object-oriented simulation, physical timing, and synthesis remain outside the
measured results. Documentation records commands, actual evidence, and limitations
to make the experiments reproducible.

## B. Demonstrable technical work

- Defined unsigned arithmetic semantics, including 16-bit subtraction wrap,
  zero-divisor behavior and low-three-bit shift amounts; clarified RTL widths.
- Built and executed a portable SV/Python checker with transaction IDs, counters,
  watchdogs, unknown rejection and nonzero failure exits.
- Executed literal directed cases, deterministic random traffic and DUT algebraic
  checks, with reproducible seeds and machine-readable results.
- Measured 142 defined functional bins and closed observed gaps using directed
  inputs, while retaining the original coverage denominator.
- Executed isolated ADD/X-output mutations and a faulty-XOR integration test;
  checked all known-input ALU combinations and all adder operand pairs.

## C. Engineering challenges

The main challenge was making a reported pass trustworthy. The original class
bench used independent delays and live interface reads; it lacked transaction
identity and could report success after a mismatch. The portable suite now makes
each executed comparison visible and checks that no transaction was lost. Arithmetic
width was another challenge: a 16-bit subtraction result differs from an 8-bit
wrapped result, and an 8-bit operand does not imply an 8-bit expression in every
SystemVerilog context. Random traffic also left reachable shift bins untested,
which required deliberate coverage-driven stimulus.

## D. Actual evidence

In the original local macOS experiment, Icarus 13.0 executed 116 directed ALU transactions, a closed standard run of 1,333
transactions, the complete 524,288 known-input ALU space, and the adder's 65,536
pairs plus 22 original-style examples. All clean checks passed. Custom functional
coverage increased from 138/142 bins to 142/142. Both ADD mutations produced three
mismatches and simulator exit code 1; clean RTL passed afterward. Sixteen Python
unit/integration tests passed. Exact logs, runtimes and provenance are linked in
[RESULTS.md](RESULTS.md). Counts describe distinct experiments and must not be
added together as a unique-input claim.

Separately, [GitHub Actions run #1](https://github.com/Vinh-Duy/RTL-Verification-Core-ALU/actions/runs/38939887081) succeeded for `cdc8e24`. GitHub metadata
confirms successful portable regression, exhaustive simulation, waveform and
artifact-upload steps on the Ubuntu job. This is CI execution evidence; the local
counts and custom functional coverage measurements above remain unchanged.
Detailed CI logs and artifact measurements were not independently inspected.

## E. Limitations

This is a finite combinational simulation study. It does not establish physical
timing, fabrication readiness, formal proof or a complete ASIC verification flow.
Native covergroups and the repaired OOP environment have not executed in a capable
simulator; the successful GitHub run covers only the portable suite. No synthesis,
code coverage or exhaustive X/Z verification is claimed. No faculty supervision,
publication, industry employment or award is implied.

## F. Suggested resume description

Developed an educational 8-bit ALU verification project using SystemVerilog,
Icarus Verilog and Python; validated all 524,288 known-input combinations, measured
a 142-bin functional coverage plan, and tested failure detection with isolated
faulty RTL.

## G. Five interview questions and explanations

1. **Why does 0−1 produce 65535 instead of 255?**
   The specification uses unsigned 16-bit modular subtraction. Zero minus one is
   −1 mathematically; modulo 65536 it is 65535 (0xffff). An eight-bit operation
   would instead yield 255. Explain the chosen width before discussing overflow.

2. **Why is a one-nanosecond delay different from transaction synchronization?**
   The delay lets zero-delay combinational logic settle in simulation. It says
   nothing about which transaction a separate concurrent process observes. In the
   repaired OOP design, completion tokens, snapshot objects and checked IDs provide
   ordering, and the driver cannot overwrite inputs until acknowledgment. That
   architecture still needs execution on a capable simulator before claiming it works.

3. **How do you know the scoreboard can fail?**
   Isolated source copies deliberately produce ADD+1, X on ADD, and OR instead of
   XOR. The tests observe mismatches and require nonzero process returns. The clean
   source then passes again. A log message alone would not be enough for automation.

4. **What does 100% coverage mean in this repository?**
   It means every one of 142 explicitly defined reachable custom functional bins
   received a successfully checked sample. It does not mean 100% code coverage,
   complete X/Z testing or proof of all hardware behavior. The 10,000-vector random
   run missed one bin, illustrating why a large count is not coverage evidence.

5. **How independent is the oracle, and what does exhaustive simulation prove?**
   The Python oracle computes from integer formulas without reading DUT output.
   Literal answers and metamorphic properties reduce dependence on one implementation.
   Exhaustive simulation checks every known binary input tuple for this particular
   combinational module and specification. A wrong specification could still make
   DUT and oracle agree; timing, synthesis and future revisions require other checks.
