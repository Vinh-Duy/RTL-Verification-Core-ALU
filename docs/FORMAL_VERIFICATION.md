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
transactions on each run). The formal proof and negative control are **NOT RUN
locally**. A separate Ubuntu 24.04 GitHub
Actions job installs the distribution Yosys package, invokes this same target and
uploads its evidence. That job must complete successfully before reporting the
proof as passed. Its Yosys version is recorded in the artifact because the Ubuntu
package can change over time. The existing simulation regression and mutation
commands are unchanged.
