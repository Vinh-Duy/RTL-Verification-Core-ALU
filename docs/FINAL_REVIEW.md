# Final engineering review

## Scope and repository state

Reviewed base commit `1621da9b2d9d395698cc23a3dfc3ecf2e66e905d` on 2026-10-17 (UTC+7).
Initial working tree: **clean**. No commit or push was performed during that review. The changes are
limited to the three GitHub action majors, documentation and new evidence records.
RTL, testbench architecture, Python oracle, coverage model and verification tests
are unchanged. All 16 historical source hashes match
the current implementation and were checked again before execution.

**VERIFIED:** no significant RTL or verification correctness problem was found in
this review. The portable project is suitable for presentation as an independent
undergraduate engineering portfolio project within its documented scope.

## Findings and disposition

- **VERIFIED — correctness:** ADD preserves carry; SUB wraps at 16 bits; MUL retains
  the full product; DIV guards zero and truncates; SHL uses B[2:0] on a 16-bit value.
  The integer oracle is independent of DUT outputs. Literal answers and metamorphic
  tests provide checks beyond duplicating the DUT's expressions.
- **VERIFIED — checker reliability:** transaction IDs and final counts reject missing,
  duplicate or reordered work. Knownness and stability checks prevent X/Z from
  masquerading as a pass. Python validates returned inputs/expected values before
  sampling coverage, and requires simulator success plus complete checked results.
  Mutants, malformed input, unknown values and missing dependencies are negative
  tests, not evidence that the production DUT fails.
- **VERIFIED — reproducibility:** seeded stimulus regeneration and replay fingerprints
  match. Every one of the 142 eligible bins has a reachable witness. Coverage samples
  only returned, stable, matching transactions; it is not code or assertion coverage.
- **FIXED — CI maintenance:** both historical workflows reported deprecated Node.js 20
  action metadata. The new workflow selects supported stable v7 majors using Node.js 24.
  Test commands, Ubuntu 24.04, Python 3.12, permissions and artifact inputs are unchanged.
  Mandatory test steps have no failure suppression or `continue-on-error` setting.
- **FIXED — documentation:** both successful CI runs are identified by commit; the
  original local measurements are preserved; fresh results have separate provenance;
  the README introduction states purpose, implementation, evidence and limits; and
  the application summary has four highlights, a 100–130 word summary, methodology,
  two CV lines and five technical explanations.
- **REMAINING LIMITATION — OOP:** inspection found no obvious new implementation defect
  in generator ownership, bounded mailboxes, stable monitor snapshots, checked-ID
  acknowledgments, null-sentinel completion or watchdog termination. Native coverage
  samples only passed snapshots. This inspection is not a simulation result.
  **NOT RUN — Requires a compatible SystemVerilog simulator.**
- **Optional future work:** synthesis/timing and additional four-state scenarios are
  separate experiments, not requirements completed by this review. No UVM migration
  or hardware feature expansion was introduced.

## Fresh local execution

These are newly executed results, not a rewrite of `docs/evidence/final.json`.
The environment was macOS-13.7.8-x86_64-i386-64bit, Python 3.10.11,
Icarus Verilog version 13.0 (stable) (v13_0) and
Icarus Verilog runtime version 13.0 (stable) (v13_0).
Version output, exact exit codes, source hashes, timestamps and actual console logs
are under [evidence/review-1621da9/](evidence/review-1621da9/execution.json).

| Executed command | Exit code | Wall time (s) |
|---|---:|---:|
| `make clean` | 0 | 0.236 |
| `make lint` | 0 | 0.640 |
| `make test` | 0 | 3.583 |
| `make regression SEED=2026 COUNT=1000` | 0 | 4.130 |
| `make exhaustive` | 0 | 21.698 |
| `make mutation` | 0 | 0.636 |
| `make waveform` | 0 | 0.380 |

All seven commands completed. `make lint` passed Icarus warning-enabled RTL
elaboration; Verilator was unavailable and is **NOT RUN locally**. No compiler
warnings were emitted by the fresh portable builds. This is not a claim that Icarus
elaboration is equivalent to Verilator lint.

- Unit/integration suite: 16 tests passed in both `make test` and regression.
- Directed ALU: 116 passed.
- Standard closed suite: 1,333 passed, including 1,000 random vectors at seed 2026.
- Main regression: 69,387 clean checked transactions including examples
  and replay (3,687 bridge transactions); zero clean failures.
- Adder: 65,558 passed, including all 65,536 pairs. Flat ALU: 132 passed.
  Targeted four-state bench: 10 passed. These are included in the regression total.
- Metamorphic properties: 60 checks over 90 DUT transactions.
- Custom functional coverage: 138/142
  (97.1831%) before closure, then
  142/142 (100.00%).
  Uncovered core bins after closure: [].
- Exhaustive simulation: 524,288/524,288 passed;
  20.790 s for vector writing, compilation, simulation and
  parsing. The command-level time above also includes startup and vector generation.
- Wrong-ADD and X-output fixtures: each completed 32 checks, found three mismatches
  and returned simulator exit 1. The mutation harness returned 0 only after correct
  rejection and a subsequent clean 32/32 known-answer run. The faulty-XOR integration
  test independently checks the outer runner's nonzero exit.
- Waveform generation: 116 checked transactions, with a real VCD at
  `results/waveform/directed/waveform.vcd`. Interactive GTKWave viewing is **NOT RUN**.

Per-configuration counters, runtime, coverage bins, seed, source hashes and failures
are retained in [local-results.json](evidence/review-1621da9/local-results.json).
No fresh clean run failed. Intentional fixture failures are clearly separate.
The 142/142 result is custom functional coverage within the defined plan; 524,288
is the complete known binary input space. Neither is formal proof or physical
implementation validation.

## Evidence preservation

Before `make clean`, all 210 generated files were inventoried,
archived and checked against SHA-256 hashes. The archive is outside directories
removed by `make clean`:

`/var/folders/jp/3k9m361d747f5kxw4svsdrbc0000gq/T/rtl-pre-review-backup-xxjgor1o/generated-before-clean.tar.gz`

Its archive digest and location are in `execution.json`, and a per-file manifest
is beside the archive. Existing tracked evidence was not regenerated or edited.
The original table runtimes remain historical, even where this fresh run is faster.

The [final safety checks](evidence/review-1621da9/final-safety.log) confirmed that
all nine previously tracked evidence files and all 16 recorded implementation
hashes are unchanged. Original numerical tables are identical, fresh snapshots
match generated reports, 24 compile/lint logs contain no compiler diagnostics,
and all 40 relative document links resolve. Local YAML parsing and comparison
confirmed that only the three action versions changed, with valid released inputs
and Node.js 24 runtimes. This static check does not replace a GitHub execution.

## GitHub Actions evidence and pending upgrade

**VERIFIED:** [run #1](https://github.com/Vinh-Duy/RTL-Verification-Core-ALU/actions/runs/38939887081)
succeeded at `cdc8e24`; [run #2](https://github.com/Vinh-Duy/RTL-Verification-Core-ALU/actions/runs/38943467205)
succeeded at `1621da9`. Both ran on October 16 UTC / October 17 UTC+7. Public pages
and API job/step outcomes confirm installation, regression, exhaustive simulation,
waveform generation and artifact upload. The configured regression includes
Icarus/Verilator RTL checks, random and directed testing, custom coverage, mutation
rejection and replay. OOP/native covergroups are not invoked by this workflow.
Detailed artifact contents and CI simulator logs were not independently inspected;
no CI transaction counts, exact simulator versions or coverage percentages are
invented from a green status.

The three v7 actions were selected after checking official stable releases:
[checkout v7.0.1](https://github.com/actions/checkout/releases/tag/v7.0.1),
[setup-python v7.0.0](https://github.com/actions/setup-python/releases/tag/v7.0.0),
and [upload-artifact v7.0.2](https://github.com/actions/upload-artifact/releases/tag/v7.0.2).
Their released manifests use `node24`. The documented Node 24 runner minimum is
2.327.1; this workflow uses GitHub-hosted Ubuntu 24.04, not an older self-hosted
runner. The previous warning also records that GitHub already forced the old
actions onto Node 24. Checkout's new restrictions concern `pull_request_target`
and `workflow_run`, neither of which is used here; removed setup inputs were not
used, and existing artifact inputs remain supported. Syntax and command scope
were checked locally. **NOT RUN:** the upgraded workflow itself awaits a new
GitHub run after a deliberate commit/push. Historical successes do not validate it.

## Final limitations and portfolio judgment

**REMAINING LIMITATION:** advanced OOP/native coverage execution, local Verilator,
updated remote workflow execution, interactive waveform viewing, synthesis,
gate-level/physical timing validation, code/native assertion coverage, formal proof
and exhaustive four-state verification are not completed. The existing targeted
X/Z checks do execute; that does not cover every four-state input combination.

The project is portfolio-ready as a small, reproducible educational RTL design and
verification exercise. Present its measured evidence and explain the width rules,
failure paths and coverage limits. Do not describe it as ASIC sign-off, a research
breakthrough or a physically verified implementation. Pending action-major changes
should receive a successful GitHub run before being described as validated CI.

## Reproduction

Preserve any needed generated evidence before cleaning, then execute sequentially:

```sh
make clean
make lint
make test
make regression SEED=2026 COUNT=1000
make exhaustive
make mutation
make waveform
```

The current review's command record is immutable evidence for this run. Future
executions should be recorded separately, with their actual source hashes and dates.
The review itself did not commit, push, force-push or rewrite history.
