# Formal-derived semantic mutation audit

## Purpose and scope

`make formal-mutation` evaluates whether the existing two-state Yosys SAT miter,
independent SystemVerilog specification, Python reference model, and Icarus
simulation checker can detect seven selected single-fault semantic mutations.
It supplements, and does not replace, `make formal` or the portable
`make mutation` suite.

The campaign reuses `formal/alu_miter.sv` and `formal/alu_spec.sv` unchanged.
For each mutation it generates an isolated copy of the production ALU and
changes exactly one operation assignment. It records both source hashes, compiles
the production baseline and each generated DUT separately, and queries whether
the mutant's complete 16-bit result differs from the specification over all
2^19 known-binary input combinations. There are no assumptions. X/Z behavior is
outside this two-state experiment.
The audited production RTL, formal spec, and miter are fingerprint-pinned.
Intentional source changes require review and an explicit update to those
fingerprints; otherwise the campaign stops before running mutants.

The selected faults are ADD carry truncation, SUB truncation to eight bits, MUL
truncation to eight bits, a wrong DIV zero result, ceiling instead of floor DIV,
AND sign extension, and using all of B as the SHL shift amount. Each model
preserves the other operation assignments.

## Classification and validation

The production baseline must first prove equivalent. Mutant SAT results are
classified from the solver result, not just its process exit code. An UNSAT
mismatch query is reported as `EQUIVALENT`; solver indeterminacy, timeout, and
tool failures remain distinct outcomes. The campaign expects these seven
deliberate faults to be non-equivalent and exits unsuccessfully if any result
remains unresolved or is not killed.

For each SAT counterexample, the campaign reads A, B, opcode, and both full
16-bit outputs from the generated VCD. It checks the specification output against
`verification.model.reference`, then replays that exact vector through the
existing `tb_alu_vectors.sv` checker using the generated mutant source. A kill
counts only when the replayed output matches the formal mutant output and the
independent checker rejects it.

Each invocation uses a new timestamp-and-commit-named directory under
`results/formal_mutation/`, so reports do not overwrite earlier campaign runs.
It contains `summary.json`, `mutants.csv`, baseline logs, generated mutant RTL,
per-mutant compile and SAT logs, VCD counterexamples, Python validation logs,
and Icarus replay outputs. The report records tools, source hashes, campaign
metadata, per-mutant classification, and aggregate counts.
It captures Python, Yosys, Icarus compiler, and Icarus runtime versions, with
the tool version command output retained in separate logs.
CI runs the campaign twice under the same tool installation and compares source
and generated-mutant hashes, tool versions, classifications, and validated
counterexamples. SAT assignments may differ between runs; equality of the
specific counterexample inputs is recorded but not required.

## Reproduction and evidence

With Yosys and Icarus Verilog installed:

```sh
make formal
make formal-mutation
```

The GitHub Actions formal job installs both tools, runs the existing formal
baseline first, then runs two mutation campaigns and uploads the separate
`formal-mutation-evidence` artifact. Missing evidence is an upload error. The
existing portable functional coverage
(142 custom bins) and advanced native SystemVerilog covergroup coverage remain
separate metrics.

Campaign execution has not yet been claimed as complete until its actual
`summary.json`, per-mutant logs, counterexample validation, and uploaded CI
artifact have been inspected. This seven-mutant sample evaluates these selected
fault models only; it does not establish complete specification or verification
coverage and is not a novel formal algorithm.
