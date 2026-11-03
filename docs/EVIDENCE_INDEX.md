# Verification Evidence Index

This index separates local measurements from remote CI evidence. Artifact links
are intentionally the run pages: GitHub artifact URLs are retained only for the
configured retention period and should be downloaded from the run's
**Artifacts** section.

## Phase validation runs

| Run | Commit | Purpose | Jobs | Artifacts | Establishes |
|---|---|---|---|---|---|
| [41421667512](https://github.com/Vinh-Duy/RTL-Verification-Core-ALU/actions/runs/41421667512) | `f3b9e4a61872c79d89a59b74ab08670e9370a13e` | Advanced CI recovery validation | `formal`, `portable`, `advanced` passed | `advanced-verification-evidence`, `formal-evidence`, `verification-evidence` | The recovered workflow completed all jobs and preserved evidence. |
| [41426335398](https://github.com/Vinh-Duy/RTL-Verification-Core-ALU/actions/runs/41426335398) | `d8e5be72cf996a2c7b0430dd92405076775b95cd` | Seven-mutant formal audit | `formal`, `portable`, `advanced` passed | `formal-evidence`, `formal-mutation-evidence`, `advanced-verification-evidence`, `verification-evidence` | Formal mutation evidence and the existing regression completed together. |
| [41591123907](https://github.com/Vinh-Duy/RTL-Verification-Core-ALU/actions/runs/41591123907) | `bced75a49048a547a625b06639c7408a246e7321` | Final adversarial infrastructure audit | `formal`, `portable`, `advanced` passed | `formal-evidence`, `formal-mutation-evidence`, `advanced-verification-evidence`, `verification-evidence` | The corrected SAT marker parser, seven-mutant audit, portable suite, and advanced suite passed in one workflow. |

The first two runs are phase milestones. Run 41591123907 is the strongest
single pre-portfolio validation because it includes the SAT marker compatibility
fix and both formal mutation campaigns.

## What to inspect

### Advanced artifact

Inspect `advanced-verification-evidence/` for:

- `summary.json` and `summary.txt`
- dependency installation and Verilator build logs
- preflight tool versions
- feature probe output
- two same-seed OOP logs
- native coverage data and `native-coverage-summary.txt`
- negative-control output

The expected evidence is Verilator 5.052, 4,096 completed transactions,
same-seed reproducibility, 100% native covergroup coverage, and an intentionally
failing faulty-DUT scoreboard run.

### Formal mutation artifact

Inspect `formal-mutation-evidence/` for:

- campaign `summary.json` files
- baseline compile and proof logs
- per-mutant generated RTL and hashes
- SAT solver logs and counterexample VCDs
- Python validation and Icarus replay logs
- CSV classifications

The expected result is seven `KILLED` classifications with independently
validated counterexamples. SAT assignment identity between repeated campaigns
is not required; semantic validity and classification are.

### Portable artifact

Inspect `verification-evidence/` for regression summaries, exhaustive results,
waveform output, mutation logs, and coverage reports. The local tracked
snapshots under [evidence/](evidence/) provide reproducible context for the
portable numbers.

## Local evidence

- [Local result export](evidence/final.json)
- [Measured results](RESULTS.md)
- [Fresh review evidence](evidence/review-1621da9/)
- [Formal CI metadata](evidence/github-actions-formal.json)

The local record reports 524,288 exhaustive known-binary checks, 142/142 custom
bins, and passing portable negative tests. Formal and advanced tool execution
was not available on that machine; their PASS claims come from the cited CI
artifacts.

## Reproduction

From the repository root:

```sh
make regression SEED=2026 COUNT=1000
make exhaustive
make formal
make formal-mutation FORMAL_REPEAT=2
make advanced SEED=2026 COUNT=4096
```

The first two commands are portable with Icarus and Python. The formal and
advanced commands require their documented external tools. A local command
that cannot run is a limitation, not a substitute for the corresponding CI
artifact.
