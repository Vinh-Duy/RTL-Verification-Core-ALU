# Formal verification

## Specification checked

`formal/alu_spec.sv` is a separately written combinational specification. It
models unsigned 8-bit operands, a 3-bit opcode and the complete 16-bit output:

- ADD is a zero-extended 16-bit sum, retaining the carry.
- SUB is unsigned subtraction modulo 65,536.
- MUL retains the full product of the two operands.
- DIV truncates toward zero for these unsigned operands and returns zero when
  the divisor is zero.
- AND, OR and XOR are zero-extended bitwise operations.
- SHL shifts the zero-extended operand by `b[2:0]`; the upper five bits of `b`
  do not affect the shift amount.
- All eight 3-bit opcode encodings are defined. The default branch returns zero,
  but is unreachable for a fully known 3-bit opcode.

The SAT model is two-state. Its complete input space is 2^19 binary combinations.
X/Z values are outside this proof domain; their simulator behavior remains covered
only by the existing targeted four-state tests. There are no assumptions, clock,
state, reset, or environmental constraints. The miter compares all 16 output
bits using a mismatch signal.

## Proof method and negative control

`make formal` invokes Yosys to elaborate and flatten the miter, map arithmetic
cells to Boolean logic, then solve `mismatch == 0` with the built-in SAT engine.
This is a complete combinational proof over the finite input domain, not bounded
model checking and not a temporal proof. A passing reference case means the SAT
solver found no binary input with unequal outputs.

The second invocation substitutes `formal/alu_faulty.sv` for the DUT. It truncates
the ADD result to eight bits before zero extension, dropping carry. The Yosys
`-falsify` mode requires this equivalence claim to fail and the runner checks for a
counterexample VCD. A missing counterexample or a proof that unexpectedly succeeds
fails the target. These formal artifacts are written to `results/formal/` and are
not folded into simulation coverage or its 142 custom bins.

## Running and current status

Run `make formal` with Yosys installed. The runner writes the actual Yosys version,
individual solver logs, the negative-control VCD and a machine-readable summary to
`results/formal/`. If Yosys is unavailable, the target exits nonzero with
**NOT RUN**; it does not substitute simulation results.

The repository's current local environment has Python 3.10.11 and Icarus Verilog
13.0, but no Yosys executable. The existing regression passed before and after
these changes (16 Python tests and the portable suite, including 1,333 closed-suite
transactions on each run). Formal proof remains **NOT RUN locally**.

GitHub Actions [run #4](https://github.com/Vinh-Duy/RTL-Verification-Core-ALU/actions/runs/40522416479)
passed for commit `68a0f9ffde37e0e6964a4922e9d7a1c3e77fe214` on Ubuntu 24.04.
The `formal` job installed Yosys, ran `make formal`, and uploaded `formal-evidence`.
The runner exits successfully only when the SAT miter proves output equality and
the faulty ADD control produces the expected counterexample. The CI run therefore
verified both outcomes over all 2^19 known-binary inputs. Run/job metadata is saved
in [github-actions-formal.json](evidence/github-actions-formal.json); the artifact
was uploaded, but its detailed logs and exact Yosys version were not downloaded
for this review. The existing simulation regression and mutation commands are
unchanged.
