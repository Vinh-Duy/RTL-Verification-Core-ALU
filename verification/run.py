"""Reproducible Icarus/Python verification. Run from any cwd with -m or Make."""
import argparse
import csv
import hashlib
import json
import platform
import re
import shlex
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from .coverage import Coverage
from . import stimuli
from .model import OPS

ROOT = Path(__file__).resolve().parents[1]


def save(path, data):
    path.write_text(json.dumps(data, indent=2) + '\n')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(args, log, timeout=120):
    with log.open('w') as out:
        out.write('$ ' + shlex.join(list(map(str, args))) + '\n')
        out.flush()
        process = subprocess.run(list(map(str, args)), cwd=ROOT, stdout=out,
                                 stderr=subprocess.STDOUT, timeout=timeout)
    return process.returncode


def require(tool):
    if not shutil.which(tool):
        raise RuntimeError(f'Missing {tool}; install Icarus Verilog (brew install icarus-verilog)')


def metadata():
    require('iverilog')
    require('vvp')
    version = subprocess.run(['iverilog', '-V'], capture_output=True, text=True,
                             timeout=10).stdout.splitlines()[0]
    return {'simulator': version, 'os': platform.platform(), 'python': platform.python_version(),
            'recorded_at_utc': datetime.now(timezone.utc).isoformat(),
            'source_sha256': {str(p.relative_to(ROOT)): digest(p) for p in sorted(ROOT.rglob('*'))
                              if p.is_file() and p.suffix in ('.py', '.sv', '.svh', '.csv')
                              and p.parts[len(ROOT.parts)] in ('rtl', 'tb', 'verification', 'tests')}}


def simulate(rows, output, seed, rtl=None, wave=False, timeout=120):
    output.mkdir(parents=True, exist_ok=True)
    rows = list(rows)
    if not rows:
        raise ValueError('No transactions requested')
    save(output / 'regression_summary.json', {'status': 'RUNNING'})
    start = time.perf_counter()
    stimulus = output / 'vectors.txt'
    with stimulus.open('w') as f:
        for i, (_, a, b, op, expected) in enumerate(rows):
            f.write(f'{i} {a:02x} {b:02x} {op:x} {expected:04x}\n')
    executable = output / 'simulation.vvp'
    rc = command(['iverilog', '-g2012', '-Wall', '-s', 'tb_alu_vectors', '-o', executable,
                  rtl or ROOT / 'rtl/alu_8bit.sv', ROOT / 'tb/tb_alu_vectors.sv'],
                 output / 'compile.log', timeout)
    if rc:
        raise RuntimeError(f'Compile failed ({rc}): {output / "compile.log"}')
    args = ['vvp', executable, f'+VECTORS={stimulus}', f'+OUTPUT={output / "test_results.csv"}',
            f'+COUNT={len(rows)}', f'+SEED={seed}']
    if wave:
        args.append(f'+WAVE={output / "waveform.vcd"}')
    rc = command(args, output / 'simulator.log', timeout)
    coverage = Coverage()
    actuals, failures = [], []
    with (output / 'test_results.csv').open() as f:
        for i, row in enumerate(csv.DictReader(f)):
            if i >= len(rows):
                raise RuntimeError('Simulator returned extra transactions')
            name, a, b, op, expected = rows[i]
            if [int(row[k]) for k in ('id', 'a', 'b', 'opcode', 'expected')] != [i, a, b, op, expected]:
                raise RuntimeError(f'Transaction ordering/data corrupted at id {i}')
            try:
                actual = int(row['actual'], 16)
            except ValueError:
                actual = None
            actuals.append(actual)
            good = actual == expected and row['status'] == 'PASS' and row['stable'] == '1'
            if good:
                coverage.sample(a, b, op)
            else:
                failures.append({'id': i, 'name': name, 'opcode': OPS[op], 'a': a, 'b': b,
                                 'expected': expected, 'actual': row['actual'], 'seed': seed})
    complete = len(actuals) == len(rows)
    simulator_text = (output / 'simulator.log').read_text()
    status = 'PASS' if rc == 0 and not failures and complete and 'Status: PASS' in simulator_text else 'FAIL'
    report = {'status': status, 'requested': len(rows), 'checked': len(actuals),
              'passed': len(actuals) - len(failures), 'failed': len(failures),
              'completed': complete, 'simulator_exit_code': rc, 'seed': seed,
              'elapsed_seconds': round(time.perf_counter() - start, 6),
              'stimulus_sha256': digest(stimulus), 'results_sha256': digest(output / 'test_results.csv'),
              'rtl_sha256': digest(rtl or ROOT / 'rtl/alu_8bit.sv'),
              'coverage': coverage.report(), 'first_failures': failures[:10],
              'command': list(map(str, args)), 'missing': len(rows) - len(actuals)}
    save(output / 'regression_summary.json', report)
    save(output / 'coverage_summary.json', report['coverage'])
    (output / 'uncovered_bins.txt').write_text('\n'.join(report['coverage']['uncovered']) + '\n')
    print(f'{output.name}: {status}; checked={len(actuals)} failed={len(failures)} '
          f'coverage={report["coverage"]["hit"]}/{report["coverage"]["eligible"]} seed={seed}')
    for fail in failures[:3]:
        print('  MISMATCH', fail)
    return report, actuals


def assert_pass(report):
    if report['status'] != 'PASS':
        raise RuntimeError('Verification failed; inspect simulator.log and regression_summary.json')


def metamorphic(output, seed, timeout):
    rows, checks = stimuli.properties()
    report, actuals = simulate(rows, output / 'properties', seed, timeout=timeout)
    assert_pass(report)
    inverse_rows = []
    for kind, index, operand in checks:
        if kind == 'equal':
            if actuals[index] != actuals[operand]:
                raise RuntimeError(f'Commutativity property failed at {index}')
        elif kind == 'constant':
            if actuals[index] != operand:
                raise RuntimeError(f'Identity property failed at {index}')
        else:
            a, b = operand
            # Expected is the original a, independent of the model.
            inverse_rows.append(('xor_self_inverse', actuals[index], b, 6, a))
    inverse, _ = simulate(inverse_rows, output / 'xor_inverse', seed, timeout=timeout)
    assert_pass(inverse)
    return [report, inverse], {'status': 'PASS', 'checks': len(checks),
                               'stable_output_checks': len(rows) + len(inverse_rows)}


def mutations(output, seed, timeout):
    source = (ROOT / 'rtl/alu_8bit.sv').read_text()
    results = []
    for name, wrong in (('wrong_add', 'a_extended + b_extended + 16\'d1'),
                        ('unknown_add', "16'hxxxx")):
        folder = output / name
        folder.mkdir(parents=True, exist_ok=True)
        fixture = folder / 'alu_8bit.sv'
        target = 'result = a_extended + b_extended;'
        if source.count(target) != 1:
            raise RuntimeError('Mutation anchor changed; update fixture generation')
        fixture.write_text(source.replace(target, f'result = {wrong};'))
        report, _ = simulate(stimuli.known_answers(), folder, seed, rtl=fixture, timeout=timeout)
        text = (folder / 'simulator.log').read_text()
        rejected = (report['status'] == 'FAIL' and report['failed'] > 0 and
                    report['simulator_exit_code'] != 0 and report['completed'] and
                    'MISMATCH' in text and 'Status: PASS' not in text)
        results.append({'mutation': name, 'verifier_rejected': rejected,
                        'checked': report['checked'], 'failed': report['failed'],
                        'simulator_exit_code': report['simulator_exit_code']})
        if not rejected:
            raise RuntimeError(f'Verifier did not reject {name}')
    report, _ = simulate(stimuli.known_answers(), output / 'clean_after_mutation', seed, timeout=timeout)
    assert_pass(report)
    save(output / 'mutation_summary.json', {'status': 'PASS', 'mutations': results,
                                           'clean_after': report})
    return results, report


def lint(output):
    output.mkdir(parents=True, exist_ok=True)
    checks = []
    for top in ('alu_8bit', 'adder_8bit'):
        args = ['iverilog', '-g2012', '-Wall', '-s', top, '-t', 'null', ROOT / f'rtl/{top}.sv']
        rc = command(args, output / f'icarus_{top}.log')
        checks.append({'tool': 'Icarus warning-enabled elaboration', 'top': top, 'exit_code': rc})
        if rc:
            raise RuntimeError(f'Icarus elaboration failed for {top}')
        if shutil.which('verilator'):
            rc = command(['verilator', '--lint-only', '-Wall', '--top-module', top,
                          ROOT / f'rtl/{top}.sv'], output / f'verilator_{top}.log')
            checks.append({'tool': 'Verilator lint', 'top': top, 'exit_code': rc})
            if rc:
                raise RuntimeError(f'Verilator lint failed for {top}')
    report = {'status': 'PASS', 'checks': checks,
              'verilator': 'EXECUTED' if shutil.which('verilator') else 'NOT RUN: executable unavailable'}
    save(output / 'lint_summary.json', report)
    print('RTL checks passed;', report['verilator'])
    return report


def examples(output, seed, timeout):
    results = []
    for top, rtl in (('tb_adder_8bit', 'adder_8bit'), ('tb_alu_flat', 'alu_8bit'),
                     ('tb_alu_four_state', 'alu_8bit')):
        start = time.perf_counter()
        folder = output / top
        folder.mkdir(parents=True, exist_ok=True)
        exe = folder / 'sim.vvp'
        rc = command(['iverilog', '-g2012', '-Wall', '-I', ROOT / 'tb', '-s', top,
                      '-o', exe, ROOT / f'rtl/{rtl}.sv', ROOT / f'tb/{top}.sv'], folder / 'compile.log')
        if rc:
            raise RuntimeError(f'{top}: compilation failed')
        rc = command(['vvp', exe, f'+SEED={seed}', f'+WAVE={folder / "waveform.vcd"}'],
                     folder / 'simulator.log', timeout)
        text = (folder / 'simulator.log').read_text()
        if rc or 'Status: PASS' not in text:
            raise RuntimeError(f'{top}: simulation failed')
        match = re.search(r'VERIFICATION SUMMARY total=(\d+) passed=(\d+) failed=(\d+)', text)
        if not match:
            raise RuntimeError(f'{top}: missing counters')
        total, passed, failed = map(int, match.groups())
        if total != passed or failed:
            raise RuntimeError(f'{top}: inconsistent success summary')
        results.append({'top': top, 'status': 'PASS', 'exit_code': rc, 'checked': total,
                        'passed': passed, 'failed': failed, 'completed': True, 'seed': seed,
                        'elapsed_seconds': round(time.perf_counter() - start, 6),
                        'log': str(folder / 'simulator.log')})
        print(f'{top}: PASS')
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=['directed', 'random', 'coverage', 'regression',
                                          'exhaustive', 'mutation', 'lint', 'examples'], default='regression')
    parser.add_argument('--seed', type=int, default=2026)
    parser.add_argument('--count', type=int, default=1000)
    parser.add_argument('--output', type=Path, default=ROOT / 'results')
    parser.add_argument('--rtl', type=Path, help='Alternate ALU source, for isolated comparison only')
    parser.add_argument('--wave', action='store_true')
    parser.add_argument('--timeout', type=int, default=120, help='Wall-clock timeout per subprocess (seconds)')
    args = parser.parse_args()
    if not 0 <= args.seed <= 2147483647 or args.timeout <= 0:
        parser.error('seed must be 0..2147483647 and timeout must be positive')
    if args.mode in ('random', 'coverage', 'regression') and args.count < 8:
        parser.error('count must be at least 8')
    if args.rtl and args.mode not in ('directed', 'random', 'exhaustive'):
        parser.error('--rtl is supported only for directed, random, or exhaustive modes')
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    summary_path = output / 'regression_summary.json'
    summary = {'status': 'RUNNING', 'command': [sys.executable, '-m', 'verification.run', *sys.argv[1:]],
               'mode': args.mode, 'seed': args.seed, 'random_count': args.count, 'runs': []}
    save(summary_path, summary)
    start = time.perf_counter()
    try:
        summary['environment'] = metadata()
        runs = summary['runs']
        if args.mode == 'lint':
            summary['lint'] = lint(output / 'lint')
        elif args.mode == 'examples':
            summary['examples'] = examples(output, args.seed, args.timeout)
        elif args.mode == 'mutation':
            summary['mutations'], clean = mutations(output, args.seed, args.timeout)
            runs.append(clean)
        elif args.mode in ('directed', 'random', 'exhaustive'):
            rows = (stimuli.directed() if args.mode == 'directed' else
                    stimuli.randomized(args.count, args.seed) if args.mode == 'random' else stimuli.exhaustive())
            report, _ = simulate(rows, output / args.mode, args.seed,
                                 rtl=args.rtl.resolve() if args.rtl else None,
                                 wave=args.wave, timeout=args.timeout)
            runs.append(report)
            assert_pass(report)
        else:
            if args.mode == 'regression':
                summary['lint'] = lint(output / 'lint')
                summary['examples'] = examples(output, args.seed, args.timeout)
            initial_rows = stimuli.directed() + stimuli.randomized(args.count, args.seed)
            initial, _ = simulate(initial_rows, output / 'initial', args.seed, timeout=args.timeout)
            runs.append(initial)
            assert_pass(initial)
            closed, _ = simulate(initial_rows + stimuli.closure(), output / 'closed', args.seed,
                                 wave=args.wave, timeout=args.timeout)
            runs.append(closed)
            assert_pass(closed)
            summary['coverage_before'] = initial['coverage']
            summary['coverage_after'] = closed['coverage']
            save(output / 'coverage_summary.json', closed['coverage'])
            if closed['coverage']['uncovered']:
                raise RuntimeError('Coverage closure left reachable core bins uncovered')
            if args.mode == 'regression':
                props, summary['properties'] = metamorphic(output, args.seed, args.timeout)
                runs.extend(props)
                summary['mutations'], clean = mutations(output, args.seed, args.timeout)
                runs.append(clean)
                repeat, _ = simulate(initial_rows, output / 'reproducibility', args.seed, timeout=args.timeout)
                runs.append(repeat)
                assert_pass(repeat)
                if repeat['results_sha256'] != initial['results_sha256'] or repeat['stimulus_sha256'] != initial['stimulus_sha256']:
                    raise RuntimeError('Same-seed reproducibility comparison failed')
                # Regenerate independently as well as replaying the same vector list.
                if stimuli.randomized(args.count, args.seed) != stimuli.randomized(args.count, args.seed):
                    raise RuntimeError('Random generator not reproducible')
                summary['reproducibility'] = 'PASS: independently regenerated vectors and exact CSV replay'
        summary['status'] = 'PASS'
    except (RuntimeError, ValueError, OSError, KeyError, csv.Error, subprocess.TimeoutExpired) as exc:
        summary['status'] = 'FAIL'
        summary['error'] = str(exc)
        print(f'ERROR: {exc}', file=sys.stderr)
    summary['elapsed_seconds'] = round(time.perf_counter() - start, 6)
    summary['bridge_checked'] = sum(r['checked'] for r in summary['runs'])
    clean_runs = summary['runs'] + summary.get('examples', [])
    summary['checked'] = sum(r['checked'] for r in clean_runs)
    summary['passed'] = sum(r['passed'] for r in clean_runs)
    summary['failed'] = sum(r['failed'] for r in clean_runs)
    summary['count_scope'] = 'Clean bridge and example transactions including replay; isolated mutations excluded'
    summary['completed'] = summary['status'] == 'PASS' and all(r['completed'] for r in summary['runs'])
    save(summary_path, summary)
    print(f'REGRESSION {summary["status"]}: {summary_path}')
    return 0 if summary['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
