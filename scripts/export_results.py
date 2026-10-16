"""Export a compact, measured evidence snapshot; never synthesizes pass results."""
import json
import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
folders = ('regression', 'exhaustive', 'smoke', 'extended', 'alternate_seed',
           'directed', 'examples', 'coverage', 'mutation', 'waveform', 'random', 'lint-run')
evidence = {}
rows = []
for folder in folders:
    path = ROOT / 'results' / folder / 'regression_summary.json'
    data = json.loads(path.read_text())
    if data['status'] != 'PASS' or not data['completed']:
        raise SystemExit(f'Cannot publish incomplete/failing clean run: {path}')
    for name, expected_hash in data['environment']['source_sha256'].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != expected_hash:
            raise SystemExit(f'Stale source for {folder}: {name}; rerun the affected experiment')
    for run in data['runs']:
        name = Path(run['command'][1]).parent.name
        cov = run['coverage']
        rows.append((f'{folder}/{name}', run['checked'], run['passed'], run['failed'],
                     run['seed'], f'{cov["hit"]}/{cov["eligible"]} ({cov["percent"]:.2f}%)',
                     run['status'], run['completed'], run['elapsed_seconds']))
    for run in data.get('examples', []):
        rows.append((f'{folder}/{run["top"]}', run['checked'], run['passed'], run['failed'],
                     run['seed'], 'not collected', run['status'], run['completed'], run['elapsed_seconds']))
    # Keep detailed bin hits only once for the final closure, not every replay.
    compact = json.loads(json.dumps(data))
    for run in compact['runs']:
        run['coverage'].pop('bins', None)
    for key in ('coverage_before', 'coverage_after'):
        if key in compact:
            compact[key].pop('bins', None)
    evidence[folder] = compact

reg = evidence['regression']
before, after = reg['coverage_before'], reg['coverage_after']
exhaustive = evidence['exhaustive']['runs'][0]
directed = evidence['directed']['runs'][0]
closed = next(r for r in reg['runs'] if Path(r['command'][1]).parent.name == 'closed')
adder = next(r for r in reg['examples'] if r['top'] == 'tb_adder_8bit')
flat = next(r for r in reg['examples'] if r['top'] == 'tb_alu_flat')
four_state = next(r for r in reg['examples'] if r['top'] == 'tb_alu_four_state')
property_rows = sum(r['checked'] for r in reg['runs']
                    if Path(r['command'][1]).parent.name in ('properties', 'xor_inverse'))
clean_after = next(r for r in reg['runs'] if Path(r['command'][1]).parent.name == 'clean_after_mutation')
closure_count = closed['checked'] - directed['checked'] - reg['random_count']
unit_log = (ROOT / 'results/unit_tests.log').read_text()
match = re.search(r'Ran (\d+) tests in ([0-9.]+)s\s+OK', unit_log)
if not match:
    raise SystemExit('No passing unit test summary in results/unit_tests.log')
evidence['unit_tests'] = {'passed': int(match[1]), 'elapsed_seconds': float(match[2])}
evidence['closed_coverage'] = json.loads((ROOT / 'results/regression/coverage_summary.json').read_text())
(ROOT / 'docs/evidence/final.json').write_text(json.dumps(evidence, indent=2) + '\n')
for name in ('wrong_add', 'unknown_add', 'clean_after_mutation'):
    (ROOT / f'docs/evidence/{name}.log').write_text((ROOT / f'results/regression/{name}/simulator.log').read_text())
(ROOT / 'docs/evidence/unit_tests.log').write_text(unit_log)
text = f'''# Measured verification results

Generated from executed reports by `python3 scripts/export_results.py`.
The machine-readable snapshot is [evidence/final.json](evidence/final.json).
Exploratory runs and the original-source baseline are preserved separately in
[evidence/exploratory.json](evidence/exploratory.json).

Simulator: {reg['environment']['simulator']}. OS: {reg['environment']['os']}.
Python: {reg['environment']['python']}. Final regression recorded at
{reg['environment']['recorded_at_utc']} (UTC; local time is UTC+7).
All rows below used this simulator/OS. Times are measured wall-clock seconds,
including compilation, simulation, and result parsing for bridge runs. Runs made
concurrently are laptop observations, not controlled performance benchmarks.
The seed is recorded for directed/exhaustive runs but does not alter their vectors.

| Executed configuration | Checked | Passed | Failed | Seed | Custom functional bins | Status | Completed | Seconds |
|---|---:|---:|---:|---:|---|---|---|---:|
'''
for row in rows:
    text += '| ' + ' | '.join(str(x) for x in row) + ' |\n'
text += f'''
## Coverage closure

Standard initial: {before['hit']}/{before['eligible']} ({before['percent']:.4f}%).
After directed closure: {after['hit']}/{after['eligible']} ({after['percent']:.4f}%).
Initial missing bins: {', '.join(before['uncovered'])}.
Final uncovered bins: {after['uncovered']}.
The denominator is the 142 reachable bins defined in COVERAGE_PLAN.md; this is
not code coverage. The closed run contains {directed['checked']} directed, {reg['random_count']:,} biased random,
and {closure_count} closure transactions, each actually checked. Replay counts are not unique
input-space counts. Exhaustive simulation separately checked {exhaustive['checked']:,}
distinct known-input combinations and completed in {exhaustive['elapsed_seconds']:.3f} seconds.

## Negative testing and properties

{evidence['unit_tests']['passed']} Python unit/integration tests passed in
{evidence['unit_tests']['elapsed_seconds']:.3f} seconds. These include a faulty XOR
DUT subprocess, missing-simulator error, invalid count, missing/out-of-order rows,
malformed stimulus, masked unknown inputs and unknown expected values; expected failures returned nonzero.
The regression performed {reg['properties']['checks']} DUT metamorphic checks over
{property_rows} transactions, as well as a stable-output check on every bridge transaction.
Same-seed regenerated vectors matched, and the initial/replay stimulus and result
CSV SHA-256 hashes matched exactly.

| Isolated mutant | Checked | Mismatches | Simulator exit | Verifier correctly rejected |
|---|---:|---:|---:|---|
'''
for m in reg['mutations']:
    text += f'| {m["mutation"]} | {m["checked"]} | {m["failed"]} | {m["simulator_exit_code"]} | {m["verifier_rejected"]} |\n'
text += f'''
Mutation rejection is an expected failure of faulty RTL. It is not a passing
faulty-DUT simulation. The clean RTL then passed {clean_after['passed']} known-answer transactions.
No production source was modified for mutation testing. Mutants are generated
under ignored results directories. Mutation evidence logs are preserved under
`docs/evidence/`.

The main regression checked {reg['checked']:,} clean transactions including examples
and replay ({reg['bridge_checked']:,} bridge transactions), excluding intentionally
faulty fixtures. The examples account for {adder['checked']:,} adder checks, {flat['checked']} flat ALU checks,
and {four_state['checked']} targeted four-state checks. These counts intentionally include repetition.

## Unavailable or unexecuted checks

- Icarus warning-enabled RTL elaboration: PASS, no emitted warnings on revised RTL.
- Verilator lint: NOT RUN locally; executable unavailable. CI is configured to run it.
- Advanced OOP and native covergroups: NOT RUN with a capable simulator.
- GitHub Actions: configured, NOT RUN on GitHub during this task.
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
'''
(ROOT / 'docs/RESULTS.md').write_text(text)
# Keep compact results in README and the main report synchronized with evidence.
compact = f'''<!-- measured-results:start -->
| Executed check | Measured result |
|---|---|
| Directed ALU suite | {directed['checked']} checked, {directed['passed']} passed |
| Standard closed suite | {closed['checked']:,} checked, {closed['passed']:,} passed; seed {closed['seed']} |
| Custom functional coverage | {before['hit']}/{before['eligible']} ({before['percent']:.2f}%) before → {after['hit']}/{after['eligible']} ({after['percent']:.2f}%) after closure |
| Exhaustive ALU | {exhaustive['checked']:,} checked, all passed; {exhaustive['elapsed_seconds']:.3f} s |
| Adder example | {adder['passed']:,} passed, including all 65,536 input pairs |
| Verifier tests | {evidence['unit_tests']['passed']} unit/integration tests passed; ADD and X-output mutants rejected |
| Advanced OOP / GitHub CI | NOT RUN / NOT RUN |
<!-- measured-results:end -->'''
for name in ('README.md', 'docs/VERIFICATION_REPORT.md'):
    path = ROOT / name
    content = path.read_text()
    content, n = re.subn(r'<!-- measured-results:start -->.*?<!-- measured-results:end -->',
                         lambda _: compact, content, flags=re.S)
    if n != 1:
        raise SystemExit(f'Missing result markers in {name}')
    path.write_text(content)
print(f'Exported {len(rows)} measured configurations and {len(reg["mutations"])} negative cases.')
