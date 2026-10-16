# Implementation delivery and final quality gate

This snapshot records implementation and verification before the changes were
grouped into commits. Work used the original opened directory; no push, reset,
history deletion, or separate EDA-repository change was performed. The initial
tracked tree was clean. Existing ignored root simulation files were preserved.

## Files modified (8)

- [.gitignore](../.gitignore)
- [README.md](../README.md)
- [rtl/adder_8bit.sv](../rtl/adder_8bit.sv)
- [rtl/alu_8bit.sv](../rtl/alu_8bit.sv)
- [tb/tb_adder_8bit.sv](../tb/tb_adder_8bit.sv)
- [tb/tb_alu_coverage.sv](../tb/tb_alu_coverage.sv)
- [tb/tb_alu_flat.sv](../tb/tb_alu_flat.sv)
- [tb/tb_alu_oop.sv](../tb/tb_alu_oop.sv)

## Files created (30)

- [.github/workflows/verification.yml](../.github/workflows/verification.yml)
- [Makefile](../Makefile)
- [docs/ADVANCED_SUITE.md](../docs/ADVANCED_SUITE.md)
- [docs/ALU_SPECIFICATION.md](../docs/ALU_SPECIFICATION.md)
- [docs/AUDIT.md](../docs/AUDIT.md)
- [docs/COVERAGE_PLAN.md](../docs/COVERAGE_PLAN.md)
- [docs/DELIVERY.md](../docs/DELIVERY.md)
- [docs/PROJECT_SUMMARY.md](../docs/PROJECT_SUMMARY.md)
- [docs/RESULTS.md](../docs/RESULTS.md)
- [docs/VERIFICATION_REPORT.md](../docs/VERIFICATION_REPORT.md)
- [docs/evidence/clean_after_mutation.log](../docs/evidence/clean_after_mutation.log)
- [docs/evidence/exploratory.json](../docs/evidence/exploratory.json)
- [docs/evidence/final.json](../docs/evidence/final.json)
- [docs/evidence/original_exhaustive.log](../docs/evidence/original_exhaustive.log)
- [docs/evidence/original_oop_compile.log](../docs/evidence/original_oop_compile.log)
- [docs/evidence/unit_tests.log](../docs/evidence/unit_tests.log)
- [docs/evidence/unknown_add.log](../docs/evidence/unknown_add.log)
- [docs/evidence/wrong_add.log](../docs/evidence/wrong_add.log)
- [requirements.txt](../requirements.txt)
- [scripts/export_results.py](../scripts/export_results.py)
- [tb/alu_oop_env.svh](../tb/alu_oop_env.svh)
- [tb/alu_reference.svh](../tb/alu_reference.svh)
- [tb/tb_alu_four_state.sv](../tb/tb_alu_four_state.sv)
- [tb/tb_alu_vectors.sv](../tb/tb_alu_vectors.sv)
- [tests/test_verification.py](../tests/test_verification.py)
- [verification/coverage.py](../verification/coverage.py)
- [verification/known_answers.csv](../verification/known_answers.csv)
- [verification/model.py](../verification/model.py)
- [verification/run.py](../verification/run.py)
- [verification/stimuli.py](../verification/stimuli.py)

## Commands actually executed

The actual Icarus compile/runtime invocations are in each run's logs. The following
commands were executed during the final gate; repeated runs superseded earlier
measurements after the checker input-knownness correction.

```sh
make clean
make regression
make lint
make test-random SEED=2026 COUNT=1000
make test
make coverage
make mutation
make exhaustive
make waveform
python3 -m verification.run --mode random --count 100 --seed 2026 --output results/smoke
python3 -m verification.run --mode random --count 10000 --seed 2026 --output results/extended
python3 -m verification.run --mode random --count 1000 --seed 2027 --output results/alternate_seed
python3 scripts/export_results.py
git diff --check
```

The original-source exhaustive experiment ran before clean-up:

```sh
cp rtl/alu_8bit.sv build/original_alu.sv  # performed before editing the original RTL
python3 -m verification.run --mode exhaustive --rtl build/original_alu.sv --output results/original_exhaustive
```

`make regression` invokes the 16 Python unit/integration tests. Final unit output
was captured to `/tmp/alu-final-regression.log`, then copied to
`results/unit_tests.log` for evidence export. The original OOP compile was attempted
and rejected; its real diagnostic is saved in `docs/evidence/original_oop_compile.log`.

## Final measurements

- Revised ALU exhaustive: 524,288 checked, 524,288 passed, zero failures;
  24.183 s for vector writing, compilation, simulation and parsing.
- Main regression: 69,387 clean checks, including replay and examples;
  3,687 belong to the Python/SV bridge. No clean failures.
- Directed: 116 passed. Closed standard suite: 1,333 passed (seed 2026).
- Random-only runs: 100, 1,000 and 10,000 vectors at seed 2026; 1,000 at seed 2027.
- Adder: 65,558 passed, including all 65,536 operand pairs.
- Flat ALU: 132 passed. Targeted four-state bench: 10 passed.
- Unit/integration checks: 16 passed.
- Custom functional coverage: 138/142 = 97.1831% before closure;
  142/142 = 100% afterward. No uncovered core bins remain in the closed run.
- Random-only extended coverage: 141/142; `shift.cross.5.clear` remained uncovered.
- Each isolated ADD mutant: 32 checked, three mismatches, simulator exit 1.
  The clean known-answer run then passed all 32 checks. A separate faulty XOR
  integration test required outer runner exit 1.

The 100% figure describes only the explicitly defined functional bins. It is not
code coverage, assertion coverage or complete physical hardware verification.

## Corrections and limitations

No functional RTL arithmetic bug was established: the original ALU also passed
the full known-input space. RTL width intent is now explicit. Verification defects
corrected include unconditional success, missing counts/IDs, ignored randomization
failure, omitted zero-divisor oracle behavior and absent error propagation.
The OOP source now has monitor snapshots, bounded mailboxes, acknowledgments and
explicit end-of-stream termination; these changes remain unexecuted on a capable
simulator. The portable baseline independently supplies actual pass evidence.

Icarus warning-enabled RTL elaboration passed with no revised-RTL warnings.
Verilator lint is NOT RUN locally because the executable is absent. Advanced OOP,
native covergroups, GitHub Actions execution and manual GTKWave viewing are NOT RUN.
No synthesis, physical timing, native code coverage or formal proof is claimed.

## Final artifact checks

- Rebuilt after `make clean`; all portable required paths completed.
- Checked JSON counts, completion, coverage bin arithmetic and sample counts.
- Checked same-seed regenerated inputs and byte-identical replay CSV fingerprints.
- Checked source SHA-256 hashes before exporting evidence.
- Inspected the real VCD header, signal declarations and final timestamp.
- Checked relative documentation links and reviewed the final Git diff.
- Generated artifacts are ignored; compact evidence snapshots are intentional source additions.
- Source and reports preserve the adder → flat → OOP → coverage educational progression.

## Before committing

1. Review `git diff` and the newly created files listed above.
2. To complete local Verilator checks, install it (`brew install verilator`) and run
   `make lint`; retain the new log rather than treating this report as that result.
3. If a capable advanced simulator is available, follow ADVANCED_SUITE.md and
   validate its failure exit using an isolated faulty DUT. Otherwise retain NOT RUN.
4. Review the measured claims and your own contribution/understanding. If code
   changes, rerun the affected tests and regenerate evidence.
5. Commit and push only when you decide to do so. GitHub CI remains unverified until
   the workflow actually executes after a push.

## Three concepts to explain independently

1. **Width is part of the specification.** Explain why ADD retains a ninth bit,
   0−1 becomes 0xffff under 16-bit modular subtraction, and SHL retains bits above
   bit 7 while ignoring B[7:3].
2. **A reliable check needs ownership, ordering and a failure path.** A settling
   delay allows RTL evaluation; a completion token identifies a transaction.
   Immutable snapshots prevent checking later inputs by mistake. Counters and
   nonzero exits ensure a mismatch cannot become a successful regression.
3. **Coverage and proof are different.** A transaction pass rate measures checked
   outcomes; custom bins measure selected scenarios. Exhaustive simulation checks
   all known inputs for the current finite DUT but cannot establish physical timing
   or correctness of a wrong specification. Mutation tests validate the checker.
