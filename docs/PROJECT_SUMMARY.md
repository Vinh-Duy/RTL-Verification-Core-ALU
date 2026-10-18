# Project summary for application preparation

## A. Short English summary (115 words)

This independent project implements an unsigned 8-bit arithmetic logic unit with
eight operations and a 16-bit result. It was developed to understand digital
arithmetic and how verification can distinguish correct behavior from misleading
test output. The portable environment combines SystemVerilog, Icarus Verilog and
an independent Python reference model. Directed cases, reproducible random inputs,
metamorphic checks and isolated faulty designs test both the ALU and its checker.
Local experiments checked all 524,288 known binary input combinations and reached
all 142 bins in a defined custom functional coverage plan. Public CI runs provide
separate evidence of reproducibility. The project retains earlier adder and
object-oriented examples, while clearly identifying unexecuted advanced simulation
and the limits of functional testing.

## B. Four implementation highlights

- Specified unsigned arithmetic widths, modular subtraction, zero-divisor behavior
  and masked shift amounts, with explicit-width synthesizable RTL.
- Built a portable checker using an independent integer oracle, literal answers,
  transaction IDs, unknown-value rejection and nonzero failure exits.
- Implemented reproducible random stimulus, executable algebraic properties and
  a 142-bin custom functional coverage plan with directed closure.
- Validated the checker through isolated RTL mutations and negative tests, and
  executed every known binary ALU combination and every adder input pair.

## C. Verification methodology and challenges

Python generates inputs and expected values; the SV bridge drives the DUT, allows
combinational evaluation, checks knownness and stability, and returns identified
results. Python checks ordering and comparisons before collecting coverage.
Manual expected values and DUT properties provide checks beyond oracle agreement.
The main challenges were defining arithmetic widths precisely, ensuring that a
mismatch reaches the process exit status, and closing scenarios that random traffic
missed. Explicit completion and snapshots are used in the educational OOP design,
but that environment still requires execution on a capable simulator.

## D. Actual measured evidence

The original local record includes 116/116 directed checks, 1,333/1,333 checks in
the closed standard suite, 142/142 custom functional bins, 524,288/524,288 exhaustive
ALU combinations and 16 passing unit/integration tests. Those historical values
and runtimes remain unchanged in [RESULTS.md](RESULTS.md).

The [fresh final review](FINAL_REVIEW.md) independently reran the required commands
at base commit `1621da9`, confirmed the same source hashes and reproduced these
pass counts and bin hits. Both ADD mutants generated three mismatches with exit 1;
clean RTL passed afterward. Counts from separate runs must not be combined into
a unique-input claim. GitHub [run #1](https://github.com/Vinh-Duy/RTL-Verification-Core-ALU/actions/runs/38939887081)
at `cdc8e24` and [run #2](https://github.com/Vinh-Duy/RTL-Verification-Core-ALU/actions/runs/38943467205)
at `1621da9` succeeded for the portable workflow. CI status is distinct from the
local numerical measurements; detailed CI artifacts were not independently inspected.

## E. Limitations

OOP/native covergroups remain **NOT RUN — Requires a compatible SystemVerilog
simulator**. The new Node.js 24 action-major update has not yet run on GitHub.
Local Verilator and interactive GTKWave viewing remain unexecuted. There is no
synthesis, gate-level timing, physical implementation, code/native assertion
coverage, formal proof or exhaustive X/Z verification result. No faculty
supervision, publication or industry employment is implied.

## F. Two-line CV description

Independent RTL project: designed an 8-bit ALU and implemented reproducible SystemVerilog/Python verification.<br>
Checked 524,288 binary input combinations, measured 142 custom functional bins, and validated failure detection with isolated faulty RTL.

## G. Five interview questions and explanations

1. **Why does arithmetic width matter?**
   The output width defines the arithmetic representation. ADD needs nine bits to
   retain 255+255. Under the specified 16-bit subtraction, 0−1 wraps to 65535
   (0xffff), not the eight-bit value 255. MUL and SHL must retain bits above bit 7;
   SHL deliberately uses only the low three bits of B.

2. **How can a scoreboard produce a false pass?**
   It might compare the wrong transaction, use an equally wrong reference model,
   accept matching unknown values, or print an error without returning failure.
   This checker uses ordered IDs, expected counts, knownness checks, snapshots
   where needed, literal answers and nonzero failure exits. Settling time alone
   does not establish transaction identity between concurrent processes.

3. **How does mutation testing validate the checker?**
   Isolated DUT copies change ADD to ADD+1 or an unknown result. The tests must
   observe mismatches and fail; the mutation harness succeeds only when rejection
   is demonstrated. A separate XOR-to-OR mutation checks the Python exit status.
   Passing the clean DUT alone would not prove that the verifier can detect errors.

4. **What does 142/142 functional coverage mean?**
   Every reachable bin in the stated plan received a completed, successfully
   checked transaction. The bins include opcodes, operand categories, relationships,
   arithmetic edges and selected crosses. This is neither code coverage nor a
   universal completeness claim. A large random test count can still miss a bin.

5. **Why is exhaustive simulation not formal verification?**
   This run enumerates every known binary input tuple for one finite combinational
   implementation and compares observed results against a specification model.
   It does not construct a formal proof, test every X/Z combination, validate
   physical timing or establish that the chosen specification is correct.
   Literal examples and independent properties reduce shared-model mistakes,
   while synthesis and physical validation require separate experiments.
