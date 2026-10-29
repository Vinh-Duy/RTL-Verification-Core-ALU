# RTL Design and Verification of an 8-bit ALU

**Independent Digital Hardware Engineering Project**

## 1. Overview

An unsigned combinational 8-bit ALU with eight operations and a 16-bit result,
developed to study arithmetic width, simulation scheduling and reliable checking.
The implementation includes the RTL, an independent Python reference model,
portable SystemVerilog tests, reproducible random stimulus and a custom functional
coverage collector. Icarus Verilog and Python's standard library run the baseline.

Recorded local evidence includes 116 directed transactions, all 524,288 known
binary ALU input combinations, mutation rejection and 142/142 bins in the defined
functional coverage plan. [Measured results](docs/RESULTS.md) distinguish the
original experiments, successful GitHub runs and the fresh
[final review](docs/FINAL_REVIEW.md). The adder and flat/OOP examples preserve the
project's educational progression.

The advanced OOP/CRV/native-covergroup suite now has a dedicated `make advanced`
target and CI job pinned to Verilator 5.052. The local machine lacks Verilator and
Z3, so this revision's advanced result remains **NOT RUN locally** until the
workflow executes. See [advanced suite status and evidence](docs/ADVANCED_SUITE.md).

## 2. Motivation

The project explores arithmetic widths, simulation scheduling, trustworthy
scoreboards and measurable testing. It is an independent undergraduate engineering
project, not a tapeout verification platform. The separate
[EDA routing project](https://github.com/Vinh-Duy/EDA_Routing_Algorithm) explores
algorithms and experimental validation; the two repositories remain independent.

## 3. ALU Specification

Inputs are unsigned 8-bit A/B and a 3-bit opcode; result is 16 bits. There is no
clock or state. Full details, including X/Z behavior, are in the
[specification](docs/ALU_SPECIFICATION.md). Explicit-width RTL preserves the original
known-input behavior. The original and revised ALUs each passed an exhaustive
known-input simulation against the documented model.

## 4. Supported Operations

| Opcode | Name | Result |
|---|---|---|
| 000 | ADD | A+B; carry retained |
| 001 | SUB | (A−B) mod 65536 |
| 010 | MUL | Full 8×8 product |
| 011 | DIV | Floor(A/B), or zero when B=0 |
| 100 | AND | Zero-extended bitwise AND |
| 101 | OR | Zero-extended bitwise OR |
| 110 | XOR | Zero-extended bitwise XOR |
| 111 | SHL | A shifted left by B[2:0], with a 16-bit result |

## 5. Verification Architecture

Python model and stimulus → vector file → sequential SV driver/checker → result
CSV → Python result validation and custom coverage → JSON summaries.

The bridge checks transaction IDs/counts, rejects unknown outputs, checks stable
results, and returns failure through `$fatal` and the runner exit code. Simulation
and subprocess watchdogs bound execution. A 1 ns settling interval permits
zero-delay RTL evaluation; it does not represent measured hardware latency.

The flat bench makes sequential self-checking easy to inspect. The OOP examples
teach separation of generator, driver, monitor, scoreboard and coverage. Their
bounded mailbox completion/acknowledgment path replaces independent `#4/#5` loops.
See [advanced suite status and commands](docs/ADVANCED_SUITE.md).

## 6. Directed and Random Testing

Thirty-two literal known answers underpin a 116-transaction directed suite.
It covers boundaries, division zero/remainder, subtraction wrap, full products,
ignored shift bits, repeated inputs and changing opcodes. Random operands use a
35% boundary-pool / 65% uniform mixture; opcodes cycle evenly through all eight.
Seeds and counts are configurable and logged. Sixty metamorphic checks exercise
DUT algebraic relationships. A separate bench checks ten selected X/Z cases.

## 7. Functional Coverage

The [142-bin plan](docs/COVERAGE_PLAN.md) measures opcodes, operand categories,
relationships, arithmetic edges and useful crosses. Coverage samples only returned,
checked, matching transactions. Reports list every uncovered bin. A dedicated
closure phase exercises missing scenarios without changing the denominator.
This is **custom functional coverage**, not code coverage or native covergroup
coverage. The transaction pass rate and exhaustive input count are separate metrics.

## 8. Verification Results

### Formal equivalence status

An independent Yosys SAT miter is available through `make formal`. It is set up to
compare all 16 result bits for every known binary input combination and to require
a counterexample for a carry-truncating ADD fault. Formal results remain separate
from simulation coverage. Yosys is unavailable locally, so the proof is **NOT RUN**
on this machine. GitHub Actions run #4 passed for commit `68a0f9f`, including the
formal job. See the
[formal verification notes](docs/FORMAL_VERIFICATION.md) for exact scope and limits.

The table preserves the original local measurements. Fresh checks and their source
hashes are recorded separately in the [final review](docs/FINAL_REVIEW.md).

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

GitHub Actions [run #1](https://github.com/Vinh-Duy/RTL-Verification-Core-ALU/actions/runs/38939887081) passed for `cdc8e24`, and
[run #2](https://github.com/Vinh-Duy/RTL-Verification-Core-ALU/actions/runs/38943467205) passed for `1621da9`. Both cover the portable regression,
exhaustive simulation, waveform and artifact-upload steps. They do not execute the
advanced OOP/native-covergroup suite. The pending action-version upgrade has **NOT
RUN** on GitHub. See the [CI evidence scope](docs/RESULTS.md#github-actions-verification-separate-from-local-experiments).

See [full measured results](docs/RESULTS.md), [technical report](docs/VERIFICATION_REPORT.md)
and [machine-readable evidence](docs/evidence/final.json) for environments, runtimes,
counts, negative tests, source hashes and limitations. Exhaustive simulation checks
all 524,288 known-input combinations; it is not formal or physical verification.

## 9. Repository Structure

```text
rtl/                 ALU and original educational adder
tb/                 flat, vector, X/Z and shared OOP benches
verification/       Python model, stimuli, coverage, runner and literal answers
tests/              oracle, coverage and failure-propagation tests
scripts/            measured-result exporter
docs/               audit, specification, coverage plan and reports
docs/evidence/      compact executed evidence snapshots
.github/workflows/  portable CI configuration
results/            generated logs, CSV, JSON, waveforms and isolated mutants (ignored)
```

## 10. Installation

Use Python >=3.10,<3.15 and Icarus Verilog (locally tested with 13.0; CI targets the
Ubuntu-packaged version). There are no pip dependencies; `requirements.txt` records
this intentionally. Verilator is optional locally and installed in CI for lint.

```sh
# macOS, with Homebrew already installed
brew install icarus-verilog verilator python@3.12

# Ubuntu / Debian
sudo apt-get update
sudo apt-get install -y iverilog verilator python3 make
```

For the versioned Homebrew Python, use `make PYTHON=python3.12 regression`, or
activate a virtual environment created with `python3.12 -m venv .venv`.
The [Homebrew Python 3.12 formula](https://formulae.brew.sh/formula/python@3.12)
provides the versioned executable. An existing supported Python also works.

GTKWave is optional. Install a distribution compatible with your OS using the
[GTKWave project](https://gtkwave.github.io/gtkwave/). Its executable is present on
the development machine; interactive viewing was not validated here. cocotb was
considered but is not required for this small file-vector flow. A missing Icarus
executable produces an explicit error and nonzero status.

## 11. Quick Start

```sh
make test             # Python checks, directed ALU, adder, flat and X/Z examples
make regression       # lint/elaboration, random, coverage, properties, mutations, replay
make advanced SEED=2026 COUNT=4096  # native OOP/CRV/covergroups and fault control
```

## 12. Running Regression Tests

```sh
make lint
make test-random SEED=2026 COUNT=100       # smoke random
make test-random SEED=2026 COUNT=1000      # standard random
make test-random SEED=2026 COUNT=10000     # extended random
make coverage SEED=2026 COUNT=1000
make mutation
make exhaustive                          # all 524,288 known-input ALU combinations
make regression SEED=2027 COUNT=1000 TIMEOUT=300
make clean                               # removes only generated build/ and results/
```

Make targets call `python3 -m verification.run`; `PYTHON` can override the interpreter.
Reports are under `results/<target>/`, with per-simulation `test_results.csv`,
`simulator.log`, `coverage_summary.json`, `uncovered_bins.txt` and
`regression_summary.json`. The regression reports real counts and verifies identical
stimulus/results for a repeated seed. Mutation logs intentionally show failed DUT
runs; the mutation test passes only when those faulty DUTs are rejected.

`make lint` uses Icarus warning-enabled elaboration and also runs Verilator when
available. It clearly reports unavailable Verilator; Icarus elaboration is not
represented as an equivalent lint tool. CI fails on either tool's failure and
uploads evidence even if a later test fails. Runs #1 (`cdc8e24`) and #2 (`1621da9`)
succeeded with the previous action versions; the v7 action update still requires
its own GitHub run. See [measured results](docs/RESULTS.md) for exact
commands to regenerate the evidence snapshot and tables.

## 13. Waveform Visualization

```sh
make waveform
gtkwave results/waveform/directed/waveform.vcd
```

This real simulation includes operand/opcode changes, carry, subtraction wrap,
full-width multiplication and shift boundaries. Add A, B, opcode and result, set
hexadecimal/unsigned radix and zoom to the first 64 ns for literal known answers.
Capture an image manually from GTKWave if needed; no screenshot is fabricated.
VCD files and simulation executables are ignored. Exhaustive runs omit VCD by default.

The standalone flat example is also available:

```sh
mkdir -p build results/manual
iverilog -g2012 -Wall -Itb -s tb_alu_flat -o build/alu_flat rtl/alu_8bit.sv tb/tb_alu_flat.sv
vvp build/alu_flat +SEED=2026 +COUNT=100 +WAVE=results/manual/alu.vcd
```

## 14. Technical Documentation

- [Initial audit and corrections](docs/AUDIT.md)
- [ALU specification](docs/ALU_SPECIFICATION.md)
- [Coverage plan](docs/COVERAGE_PLAN.md)
- [Verification report](docs/VERIFICATION_REPORT.md)
- [Measured results](docs/RESULTS.md)
- [Advanced suite](docs/ADVANCED_SUITE.md)
- [Application summary and interview preparation](docs/PROJECT_SUMMARY.md)
- [Final engineering review and fresh execution](docs/FINAL_REVIEW.md)
- [Formal verification notes](docs/FORMAL_VERIFICATION.md)

Tool references: [Icarus command-line options](https://steveicarus.github.io/iverilog/usage/command_line_flags.html)
and [Verilator lint options](https://verilator.org/guide/latest/exe_verilator.html).

## 15. Limitations

The advanced suite and its new CI job have not yet run on this revision; no native
covergroup result is claimed. The portable GitHub Actions run passed with Verilator
installed for lint, but that was not an OOP simulation. No synthesis, physical
timing or code coverage is claimed. The formal miter passed in CI run #4; it
remains **NOT RUN** on this machine because Yosys is unavailable. X/Z tests cover
selected semantics, not all four-state combinations.
Measured evidence applies to the recorded sources and input contract only.

## 16. Future Work

Run the advanced job on GitHub and review its uploaded simulator/coverage
artifacts; validate the pending action-runtime upgrade, and consider a separately
scoped synthesis/timing experiment. Keep the design small and understandable;
UVM migration and extra hardware blocks are outside this revision's scope.
