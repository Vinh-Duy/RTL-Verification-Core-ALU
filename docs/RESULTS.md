# Measured verification results

Local measurements generated from executed reports by `python3 scripts/export_results.py`.
GitHub Actions status is maintained separately below; it does not replace these local measurements.
The machine-readable snapshot is [evidence/final.json](evidence/final.json).
Exploratory runs and the original-source baseline are preserved separately in
[evidence/exploratory.json](evidence/exploratory.json).

Simulator: Icarus Verilog version 13.0 (stable) (v13_0). OS: macOS-13.7.8-x86_64-i386-64bit.
Python: 3.10.11. Final regression recorded at
2026-10-16T17:15:05.712659+00:00 (UTC; local time is UTC+7).
All rows below used this simulator/OS. Times are measured wall-clock seconds,
including compilation, simulation, and result parsing for bridge runs. Runs made
concurrently are laptop observations, not controlled performance benchmarks.
The seed is recorded for directed/exhaustive runs but does not alter their vectors.

| Executed configuration | Checked | Passed | Failed | Seed | Custom functional bins | Status | Completed | Seconds |
|---|---:|---:|---:|---:|---|---|---|---:|
| regression/initial | 1116 | 1116 | 0 | 2026 | 138/142 (97.18%) | PASS | True | 0.163224 |
| regression/closed | 1333 | 1333 | 0 | 2026 | 142/142 (100.00%) | PASS | True | 0.161243 |
| regression/properties | 85 | 85 | 0 | 2026 | 96/142 (67.61%) | PASS | True | 0.10723 |
| regression/xor_inverse | 5 | 5 | 0 | 2026 | 15/142 (10.56%) | PASS | True | 0.124815 |
| regression/clean_after_mutation | 32 | 32 | 0 | 2026 | 102/142 (71.83%) | PASS | True | 0.077578 |
| regression/reproducibility | 1116 | 1116 | 0 | 2026 | 138/142 (97.18%) | PASS | True | 0.157879 |
| regression/tb_adder_8bit | 65558 | 65558 | 0 | 2026 | not collected | PASS | True | 1.660991 |
| regression/tb_alu_flat | 132 | 132 | 0 | 2026 | not collected | PASS | True | 0.143456 |
| regression/tb_alu_four_state | 10 | 10 | 0 | 2026 | not collected | PASS | True | 0.105752 |
| exhaustive/exhaustive | 524288 | 524288 | 0 | 2026 | 142/142 (100.00%) | PASS | True | 24.182922 |
| smoke/random | 100 | 100 | 0 | 2026 | 94/142 (66.20%) | PASS | True | 0.0779 |
| extended/random | 10000 | 10000 | 0 | 2026 | 141/142 (99.30%) | PASS | True | 0.772509 |
| alternate_seed/random | 1000 | 1000 | 0 | 2027 | 137/142 (96.48%) | PASS | True | 0.25218 |
| directed/directed | 116 | 116 | 0 | 2026 | 130/142 (91.55%) | PASS | True | 0.088855 |
| examples/tb_adder_8bit | 65558 | 65558 | 0 | 2026 | not collected | PASS | True | 0.972948 |
| examples/tb_alu_flat | 132 | 132 | 0 | 2026 | not collected | PASS | True | 0.087187 |
| examples/tb_alu_four_state | 10 | 10 | 0 | 2026 | not collected | PASS | True | 0.07391 |
| coverage/initial | 1116 | 1116 | 0 | 2026 | 138/142 (97.18%) | PASS | True | 0.18343 |
| coverage/closed | 1333 | 1333 | 0 | 2026 | 142/142 (100.00%) | PASS | True | 0.148442 |
| mutation/clean_after_mutation | 32 | 32 | 0 | 2026 | 102/142 (71.83%) | PASS | True | 0.125593 |
| waveform/directed | 116 | 116 | 0 | 2026 | 130/142 (91.55%) | PASS | True | 0.166837 |
| random/random | 1000 | 1000 | 0 | 2026 | 138/142 (97.18%) | PASS | True | 0.095886 |

## Coverage closure

Standard initial: 138/142 (97.1831%).
After directed closure: 142/142 (100.0000%).
Initial missing bins: shift.cross.3.clear, shift.cross.4.clear, shift.cross.5.clear, shift.cross.6.clear.
Final uncovered bins: [].
The denominator is the 142 reachable bins defined in COVERAGE_PLAN.md; this is
not code coverage. The closed run contains 116 directed, 1,000 biased random,
and 217 closure transactions, each actually checked. Replay counts are not unique
input-space counts. Exhaustive simulation separately checked 524,288
distinct known-input combinations and completed in 24.183 seconds.

## Negative testing and properties

16 Python unit/integration tests passed in
3.421 seconds. These include a faulty XOR
DUT subprocess, missing-simulator error, invalid count, missing/out-of-order rows,
malformed stimulus, masked unknown inputs and unknown expected values; expected failures returned nonzero.
The regression performed 60 DUT metamorphic checks over
90 transactions, as well as a stable-output check on every bridge transaction.
Same-seed regenerated vectors matched, and the initial/replay stimulus and result
CSV SHA-256 hashes matched exactly.

| Isolated mutant | Checked | Mismatches | Simulator exit | Verifier correctly rejected |
|---|---:|---:|---:|---|
| wrong_add | 32 | 3 | 1 | True |
| unknown_add | 32 | 3 | 1 | True |

Mutation rejection is an expected failure of faulty RTL. It is not a passing
faulty-DUT simulation. The clean RTL then passed 32 known-answer transactions.
No production source was modified for mutation testing. Mutants are generated
under ignored results directories. Mutation evidence logs are preserved under
`docs/evidence/`.

The main regression checked 69,387 clean transactions including examples
and replay (3,687 bridge transactions), excluding intentionally
faulty fixtures. The examples account for 65,558 adder checks, 132 flat ALU checks,
and 10 targeted four-state checks. These counts intentionally include repetition.

<!-- github-actions:start -->
## GitHub Actions verification (separate from local experiments)

[RTL verification run #1](https://github.com/Vinh-Duy/RTL-Verification-Core-ALU/actions/runs/38939887081) completed successfully for commit
`cdc8e24494e5237448a241f4361e26cc58b4f33d` on `main`, triggered by a push.
GitHub's public run page and API agree on the successful conclusion. The `portable`
job ran on `ubuntu-24.04`; its API timestamps are 2026-10-16 17:28:08–17:28:35 UTC
(2026-10-17 00:28:08–00:28:35 UTC+7). The workflow selects Python 3.12.
The separately retrieved [CI metadata](evidence/github-actions-1.json) records
run identity, commit, job and step outcomes; it is not a simulation log.

GitHub reports success for simulator installation, the regression step
(`make regression SEED=2026 COUNT=1000`), exhaustive simulation (`make exhaustive`),
waveform generation (`make waveform`) and evidence upload. The committed workflow
installs Icarus and Verilator, and the regression invokes Verilator RTL lint when
available. Together, the successful install/regression steps and those commands
support Verilator lint passing in CI. Verilator remains NOT RUN in the original
local macOS experiment, where it was unavailable.

The public run page lists the `verification-evidence` artifact. Its contents and
the detailed CI logs were not downloaded or independently inspected in this audit.
Consequently, exact CI simulator versions, transaction counts, functional-bin hits
and per-test runtimes are not presented as newly measured values here. All numeric
experiment tables above and `evidence/final.json` remain the original local data.
The CI job duration is not an ALU simulation-performance measurement.

The workflow runs only the portable suite: advanced OOP and native covergroups
remain **NOT RUN**. The defined 142-bin metric is custom functional coverage, not
code coverage or native covergroup coverage; the local 142/142 result is not relabeled
as an independently inspected CI coverage measurement. This successful run applies
to the recorded commit, not automatically to later changes.

GitHub also reports a non-failing Node.js 20 deprecation annotation for the action
versions used; updating those action versions remains workflow maintenance work.
<!-- github-actions:end -->

## Remaining verification limits

- Icarus warning-enabled RTL elaboration: PASS, no emitted warnings on revised RTL.
- Verilator lint (original local experiment): NOT RUN: executable unavailable. See the separate CI result above.
- Advanced OOP and native covergroups: NOT RUN with a capable simulator.
- GTKWave interactive viewing/screenshot: NOT RUN; real VCD generated by Icarus.
- Synthesis, physical timing, code coverage, formal proof: not performed.

## Reproduction

```sh
make clean
make lint
make regression SEED=2026 COUNT=1000
make test-random SEED=2026 COUNT=1000
make exhaustive
make test
make coverage
make mutation
make waveform
python3 -m verification.run --mode random --count 100 --seed 2026 --output results/smoke
python3 -m verification.run --mode random --count 10000 --seed 2026 --output results/extended
python3 -m verification.run --mode random --count 1000 --seed 2027 --output results/alternate_seed
python3 -m unittest discover -s tests -v > results/unit_tests.log 2>&1
python3 scripts/export_results.py
```

Each report also records the actual invocation, environment and source SHA-256
hashes. Re-export refuses stale source hashes or unsuccessful runs. Runtime and
platform strings will differ on other computers. See VERIFICATION_REPORT.md for
interpretation and limitations.
