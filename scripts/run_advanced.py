#!/usr/bin/env python3
"""Build and audit the native SystemVerilog OOP/CRV/coverage suite."""

from __future__ import annotations

import argparse
import collections
from pathlib import Path
import re
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "advanced"
EXPECTED_VERILATOR = "5.052"
EXPECTED_Z3 = "4.8.12"
BLOCKING_DIAGNOSTICS = re.compile(r"CONSTRAINTIGN|COVERAGEIGN|UNSUPPORTED|UNSATCONSTR")


class AdvancedRunError(RuntimeError):
    pass


def record_run(name: str, argv: list[str], *, timeout: int = 300,
               expected_success: bool = True, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    OUT.mkdir(parents=True, exist_ok=True)
    try:
        result = subprocess.run(
            argv, cwd=ROOT, env=env, text=True, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, timeout=timeout, check=False,
        )
    except subprocess.TimeoutExpired as exc:
        output = exc.stdout or ""
        if isinstance(output, bytes):
            output = output.decode("utf-8", errors="replace")
        (OUT / f"{name}.log").write_text(
            f"{output}\nADVANCED COMMAND TIMEOUT after {timeout}s: {argv}\n", encoding="utf-8"
        )
        raise AdvancedRunError(f"{name}: timed out after {timeout}s; see results/advanced/{name}.log") from exc
    (OUT / f"{name}.log").write_text(result.stdout, encoding="utf-8")
    if BLOCKING_DIAGNOSTICS.search(result.stdout):
        raise AdvancedRunError(f"{name}: blocking simulator diagnostic found; see results/advanced/{name}.log")
    succeeded = result.returncode == 0
    if succeeded != expected_success:
        expectation = "success" if expected_success else "failure"
        raise AdvancedRunError(
            f"{name}: expected {expectation}, exit={result.returncode}; see results/advanced/{name}.log"
        )
    return result


def build(name: str, top: str, sources: list[str], *, negative: bool = False) -> Path:
    obj_dir = OUT / f"obj_{name}"
    cmd = ["verilator", "--binary", "--timing", "--coverage", "--trace", "-Wno-fatal",
           "-j", "2", "--Mdir", str(obj_dir), "--top-module", top,
           "-Itb"]
    if negative:
        cmd.append("-DALU_NEGATIVE_CONTROL")
    cmd.extend(sources)
    record_run(f"build_{name}", cmd)
    binary = obj_dir / f"V{top}"
    if not binary.is_file():
        raise AdvancedRunError(f"{name}: simulator did not create {binary}")
    return binary


def simulate(name: str, binary: Path, *, count: int, seed: int,
             coverage_file: Path | None = None, expected_success: bool = True) -> str:
    cmd = [str(binary), f"+COUNT={count}", f"+SEED={seed}",
           f"+WAVE={OUT / (name + '.vcd')}"]
    if coverage_file is not None:
        coverage_file.parent.mkdir(parents=True, exist_ok=True)
        cmd.append(f"+verilator+coverage+file+{coverage_file}")
    return record_run(name, cmd, expected_success=expected_success).stdout


def stimulus_lines(log: str) -> list[str]:
    return re.findall(r"^ADVANCED_STIMULUS .*?$", log, flags=re.MULTILINE)


def check_weighted_distribution(log: str, count: int) -> dict[str, dict[str, int]]:
    rows = re.findall(
        r"^ADVANCED_STIMULUS id=\d+ seed=\d+ opcode=\d+ a=(\d+) b=(\d+)$",
        log, flags=re.MULTILINE,
    )
    if len(rows) != count:
        raise AdvancedRunError(f"expected {count} recorded native transactions, found {len(rows)}")
    summary: dict[str, dict[str, int]] = {}
    for column, label in enumerate(("a", "b")):
        counts = collections.Counter(int(row[column]) for row in rows)
        if any(not 0 <= int(row[column]) <= 255 for row in rows):
            raise AdvancedRunError(f"operand {label} escaped its 8-bit domain")
        fractions = {str(value): counts[value] / count for value in (0, 1, 255)}
        inner_fraction = sum(counts[value] for value in range(2, 255)) / count
        # The dist statement weights each boundary value to 10% and the
        # interior range to 70%; tolerances catch an ignored/uniform constraint
        # while allowing deterministic solver variation.
        if any(not 0.075 <= fraction <= 0.125 for fraction in fractions.values()):
            raise AdvancedRunError(f"operand {label} boundary dist is outside tolerance: {fractions}")
        if not 0.64 <= inner_fraction <= 0.76:
            raise AdvancedRunError(f"operand {label} interior dist is outside tolerance: {inner_fraction:.3f}")
        summary[label] = {**{key: counts[int(key)] for key in fractions},
                          "interior_2_to_254": sum(counts[value] for value in range(2, 255))}
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--count", type=int, default=4096)
    args = parser.parse_args()
    if args.count < 8:
        parser.error("--count must be at least 8")
    for tool in ("verilator", "verilator_coverage", "z3"):
        if shutil.which(tool) is None:
            print(f"ADVANCED NOT RUN: required executable '{tool}' is unavailable", file=sys.stderr)
            return 2

    OUT.mkdir(parents=True, exist_ok=True)
    version = record_run("verilator_version", ["verilator", "--version"]).stdout.strip()
    coverage_version = record_run("coverage_tool_version", ["verilator_coverage", "--version"]).stdout.strip()
    z3_version = record_run("z3_version", ["z3", "--version"]).stdout.strip()
    (OUT / "tool-versions.txt").write_text(
        f"{version}\n{coverage_version}\n{z3_version}\n", encoding="utf-8"
    )
    if not re.search(rf"\b{re.escape(EXPECTED_VERILATOR)}\b", version):
        raise AdvancedRunError(f"requires Verilator {EXPECTED_VERILATOR}; found: {version}")
    if not re.search(rf"\b{re.escape(EXPECTED_Z3)}\b", z3_version):
        raise AdvancedRunError(f"requires Z3 {EXPECTED_Z3}; found: {z3_version}")

    probe = build("feature_probe", "tb_advanced_feature_probe", ["tb/tb_advanced_feature_probe.sv"])
    probe_log = simulate("feature_probe", probe, count=1, seed=args.seed)
    if "FEATURE_PROBE PASS randomize=32 native_covergroup=100.00%" not in probe_log:
        raise AdvancedRunError("native constraint/covergroup capability probe did not report full success")

    sources = ["rtl/alu_8bit.sv", "tb/tb_alu_oop.sv"]
    oop = build("oop", "tb_alu_oop", sources)
    first = simulate("oop_seed_a", oop, count=args.count, seed=args.seed)
    second = simulate("oop_seed_b", oop, count=args.count, seed=args.seed)
    lines_a, lines_b = stimulus_lines(first), stimulus_lines(second)
    if len(lines_a) != args.count or lines_a != lines_b:
        raise AdvancedRunError("same-seed stimulus did not reproduce exactly")
    expected_summary = f"VERIFICATION SUMMARY total={args.count} passed={args.count} failed=0 seed={args.seed}"
    if expected_summary not in first or "Status: PASS" not in first:
        raise AdvancedRunError("OOP run did not complete every scoreboard check")
    distribution = check_weighted_distribution(first, args.count)

    coverage = build("coverage", "tb_alu_coverage", ["rtl/alu_8bit.sv", "tb/tb_alu_coverage.sv"])
    cov_path = OUT / "native-coverage.dat"
    coverage_log = simulate("coverage", coverage, count=args.count, seed=args.seed,
                            coverage_file=cov_path)
    match = re.search(r"Native covergroup coverage \(separate metric\): ([0-9.]+)%", coverage_log)
    if not match or float(match.group(1)) < 100.0:
        raise AdvancedRunError("required native opcode/operand cross bins did not all reach 100%")
    if expected_summary not in coverage_log or "Status: PASS" not in coverage_log:
        raise AdvancedRunError("coverage wrapper did not complete every checked transaction")
    coverage_report = record_run(
        "native_coverage_report", ["verilator_coverage", "--report", "summary", str(cov_path)]
    ).stdout
    (OUT / "native-coverage-summary.txt").write_text(coverage_report, encoding="utf-8")
    if not re.search(r"covergroup", coverage_report, flags=re.IGNORECASE):
        raise AdvancedRunError("verilator_coverage report contains no native covergroup rows")

    faulty = build("negative_control", "tb_alu_oop",
                   ["rtl/alu_8bit.sv", "tb/alu_8bit_faulty.sv", "tb/tb_alu_oop.sv"],
                   negative=True)
    fault_log = simulate("negative_control", faulty, count=8, seed=args.seed,
                         expected_success=False)
    if "MISMATCH" not in fault_log or "Status: FAIL" not in fault_log:
        raise AdvancedRunError("faulty ALU did not reach and fail the independent scoreboard")

    summary = (
        f"ADVANCED SUITE PASS\nVerilator: {version}\nSeed: {args.seed}\nTransactions: {args.count}\n"
        f"Same-seed reproducibility: PASS ({len(lines_a)} stimuli compared)\n"
        f"Native CRV distribution counts: {distribution}\n"
        f"Native covergroup API: {float(match.group(1)):.2f}%\n"
        "Coverage report: results/advanced/native-coverage-summary.txt\n"
        "Negative control: PASS (faulty ADD rejected by scoreboard)\n"
    )
    (OUT / "summary.txt").write_text(summary, encoding="utf-8")
    print(summary, end="")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AdvancedRunError, subprocess.TimeoutExpired, OSError) as exc:
        print(f"ADVANCED FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
