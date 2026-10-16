# Initial audit and correction record

Inspected all eight originally tracked files before editing, at clean Git revision
`32430ca`. No local tracked changes existed. History and the separate EDA project
are untouched. The audit distinguishes source inspection from executed evidence.

## Existing architecture

The adder is a continuous combinational sum; the ALU is an eight-way combinational
case. The flat bench drives one random pair per operation, waits, and compares.
The OOP generator allocates randomized objects into an unbounded typed mailbox.
The driver takes each object, drives a virtual interface and waits five time units
forever. The scoreboard independently reads that live interface every five units.
There is no monitor, completion handshake, snapshot channel, or end sentinel.
The coverage variant samples the live interface after four units, then waits one.
It duplicates the class and top names of the OOP file, so the alternatives must be
compiled separately. Mailbox objects live with the environment; there is no
explicit teardown, and `$finish` ends the blocked driver.

## Findings

| Severity | Evidence / status | Impact | Correction |
|---|---|---|---|
| High | Confirmed by inspection: flat/OOP print FAIL but always print SUCCESS and `$finish` | A failing DUT can appear successful to automation | Counters, four-state checks, `$fatal`, checked process exit |
| High | Confirmed structural race: OOP drive and check wake at the same `#5` boundary | Ordering depends on scheduler; transaction identity is absent | Driver → monitor completion mailbox, immutable snapshot, scoreboard acknowledgment |
| High | Confirmed fragility: coverage's `#4/#1` is unrelated to driver completion | A timing change can duplicate/skip sampled transactions | Use the same handshake in both examples |
| High | Confirmed: `void'(randomize())` discards failure | Stale/default stimulus can masquerade as randomized tests | Fatal on randomization failure |
| Medium | Confirmed: no counters, expected-count checks, watchdog, explicit driver end | Missing work/deadlock cannot be reliably diagnosed | Bounded mailbox pipeline, null end sentinel, watchdog |
| Medium | Confirmed: DIV zero excluded; eight flat samples with narrow operands | Important valid boundary behavior never checked | Literal known answers, full-range biased random, coverage closure, exhaustive option |
| Medium | Confirmed: class DIV reference lacks zero guard | Enabling zero-denominator traffic would produce an invalid oracle | Align all models with documented zero result |
| Medium | Confirmed: `===` alone can accept equal X patterns | An unknown expected and actual value could pass | Reject unknown inputs/results before comparison |
| Medium | Confirmed: README claims production grade, no races and 100% opcode hits without saved measurements | Unsupported portfolio claims | Replace with measured, scoped evidence |
| Low | Width intent depends on context; **not a confirmed RTL bug** | Readers may wrongly assume 8-bit ADD/SUB/SHL | Explicit unsigned 16-bit operands and mathematical specification |
| Low | Flat and OOP lack explicit timescale | Delay units depend on compilation context | Explicit 1 ns / 1 ps testbench units |

## Simulation versus suspicion

The original flat bench was compiled and run with Icarus 13.0: eight displayed
passes, with no trustworthy aggregate failure counter. This does not establish
corner-case correctness. The original OOP compile was attempted: Icarus rejected
constraints/mailboxes and its parser aborted. No OOP simulation result is claimed.
Actual race occurrence in a capable simulator was **not measured**. No functional
RTL defect is asserted from implicit expression widths: assignment context widens
these expressions. A later exhaustive baseline comparison is recorded in the
verification report rather than retroactively called an initial finding.

## Tool compatibility and preservation

Use Icarus plus Python's standard library for the mandatory flow. Icarus `-g2012`
is not a promise of complete SystemVerilog class/covergroup support. Verilator was
not on PATH; Icarus warning-enabled elaboration is available but is weaker than
Verilator lint. cocotb is absent and unnecessary for a file-vector bridge. GTKWave
is on PATH; interactive waveform viewing remains a separate optional activity.
The advanced class/constraint/covergroup suite requires a capable simulator and
must be reported NOT RUN until actually executed there.

Preserve the adder progression, all eight opcodes, 16-bit SUB wrapping, zero DIV
result, low-three-bit shift amount, flat self-checking example, OOP classes,
functional coverage demonstration and real VCD generation. No UVM migration.
See ALU_SPECIFICATION.md for semantics and VERIFICATION_REPORT.md for measured
post-correction evidence and remaining limitations.
