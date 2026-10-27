#!/usr/bin/env python3
"""Run an unbounded combinational Yosys SAT equivalence check and its negative control."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FORMAL = ROOT / "formal"
OUT = ROOT / "results" / "formal"


def run_case(yosys: str, name: str, dut: Path, expect_counterexample: bool) -> dict:
    log_path = OUT / f"{name}.log"
    vcd_path = OUT / f"{name}-counterexample.vcd"
    proof_option = "-falsify" if expect_counterexample else "-verify"
    sat_command = (
        "sat "
        f"{proof_option} -prove mismatch 0 -timeout 300 "
        "-show a -show b -show opcode -show dut_result -show spec_result "
        f"-dump_vcd {vcd_path}"
    )
    script = "; ".join(
        [
            f"read_verilog -sv {dut} {FORMAL / 'alu_spec.sv'} {FORMAL / 'alu_miter.sv'}",
            "prep -top alu_formal_miter -flatten",
            "techmap",
            "opt",
            "check",
            sat_command,
        ]
    )
    command = [yosys, "-Q", "-p", script]
    try:
        proc = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=330,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        output = exc.stdout or ""
        if isinstance(output, bytes):
            output = output.decode(errors="replace")
        log_path.write_text(output + "\nERROR: Yosys invocation timed out.\n")
        raise RuntimeError(f"{name} timed out; see {log_path}") from exc

    log_path.write_text(proc.stdout)
    if proc.returncode != 0:
        raise RuntimeError(
            f"{name} Yosys command exited {proc.returncode}; see {log_path}"
        )

    if expect_counterexample:
        if "model found: FAIL!" not in proc.stdout or not vcd_path.is_file():
            raise RuntimeError(
                f"Negative control did not produce a SAT counterexample; see {log_path}"
            )
        outcome = "EXPECTED_COUNTEREXAMPLE"
    else:
        if "no model found: SUCCESS!" not in proc.stdout:
            raise RuntimeError(
                f"Reference equivalence was not proven; see {log_path}"
            )
        outcome = "PROVED"

    return {
        "case": name,
        "outcome": outcome,
        "yosys_exit_code": proc.returncode,
        "proof_mode": "combinational SAT; exhaustive over all binary inputs",
        "assumptions": [],
        "log": str(log_path.relative_to(ROOT)),
        "counterexample_vcd": str(vcd_path.relative_to(ROOT)) if expect_counterexample else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--yosys", default=shutil.which("yosys"))
    args = parser.parse_args()
    if not args.yosys:
        OUT.mkdir(parents=True, exist_ok=True)
        not_run = {
            "status": "NOT_RUN",
            "proof_mode": "combinational SAT, no time bound or input assumptions",
            "reason": "Yosys executable not found",
            "results": [],
        }
        (OUT / "summary.json").write_text(json.dumps(not_run, indent=2) + "\n")
        print("FORMAL NOT RUN: Yosys executable not found (install Yosys and retry).", file=sys.stderr)
        return 2

    OUT.mkdir(parents=True, exist_ok=True)
    version = subprocess.run(
        [args.yosys, "-V"], cwd=ROOT, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False,
    )
    (OUT / "yosys-version.txt").write_text(version.stdout)
    if version.returncode:
        print(version.stdout, file=sys.stderr)
        return version.returncode

    started = datetime.now(timezone.utc).isoformat()
    try:
        results = [
            run_case(args.yosys, "reference", ROOT / "rtl" / "alu_8bit.sv", False),
            run_case(args.yosys, "negative-control", FORMAL / "alu_faulty.sv", True),
        ]
    except RuntimeError as exc:
        report = {
            "status": "FAIL",
            "yosys_version": version.stdout.strip(),
            "started_at_utc": started,
            "proof_mode": "combinational SAT, no time bound or input assumptions",
            "results": [],
            "error": str(exc),
        }
        (OUT / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
        print(f"FORMAL FAIL: {exc}", file=sys.stderr)
        return 1

    report = {
        "status": "PASS",
        "yosys_version": version.stdout.strip(),
        "started_at_utc": started,
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "proof_mode": "combinational SAT, no time bound or input assumptions",
        "property": "all 16 result bits equal for every 8-bit a, 8-bit b, and 3-bit opcode",
        "domain": "all 2^19 known binary inputs; X/Z behavior is outside this two-state model",
        "results": results,
    }
    (OUT / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
