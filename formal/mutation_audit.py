#!/usr/bin/env python3
"""Run a reproducible formal-derived semantic mutation audit for the 8-bit ALU."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RTL = ROOT / "rtl" / "alu_8bit.sv"
FORMAL = ROOT / "formal"
SPEC = FORMAL / "alu_spec.sv"
MITER = FORMAL / "alu_miter.sv"
OUTPUT_ROOT = ROOT / "results" / "formal_mutation"
SAT_TIMEOUT = 60
PROCESS_TIMEOUT = SAT_TIMEOUT + 15


@dataclass(frozen=True)
class Mutation:
    identifier: str
    category: str
    description: str
    anchor: str
    replacement: str


MUTATIONS = (
    Mutation(
        "ADD_DROP_CARRY",
        "ADD width truncation",
        "Truncate the addition to eight bits before zero extension.",
        "            ADD:    result = a_extended + b_extended;",
        "            ADD:    result = {8'b0, (a + b)};",
    ),
    Mutation(
        "SUB_TRUNCATE_TO_8",
        "SUB width truncation",
        "Truncate subtraction to eight bits before zero extension.",
        "            SUB:    result = a_extended - b_extended; // Modulo 65536.",
        "            SUB:    result = {8'b0, (a - b)};",
    ),
    Mutation(
        "MUL_TRUNCATE_TO_8",
        "MUL width truncation",
        "Truncate multiplication to eight bits before zero extension.",
        "            MUL:    result = a_extended * b_extended;",
        "            MUL:    result = {8'b0, (a * b)};",
    ),
    Mutation(
        "DIV_ZERO_GUARD_ERROR",
        "DIV zero-divisor semantics",
        "Return 16'hffff for a zero divisor instead of the defined zero result.",
        "            DIV:    result = (b != 8'd0) ? a_extended / b_extended : 16'd0;",
        "            DIV:    result = (b == 8'd0) ? 16'hffff : a_extended / b_extended;",
    ),
    Mutation(
        "DIV_ROUND_UP",
        "DIV quotient rounding",
        "Use ceiling division for nonzero divisors while preserving the zero guard.",
        "            DIV:    result = (b != 8'd0) ? a_extended / b_extended : 16'd0;",
        "            DIV:    result = (b != 8'd0) ? ((a_extended + b_extended - 16'd1) / b_extended) : 16'd0;",
    ),
    Mutation(
        "AND_SIGN_EXTENSION",
        "AND result extension",
        "Sign-extend an AND result with bit 7 set instead of zero-extending it.",
        "            AND_OP: result = a_extended & b_extended;",
        "            AND_OP: result = {((a[7] & b[7]) ? 8'hff : 8'h00), (a & b)};",
    ),
    Mutation(
        "SHL_USE_FULL_B",
        "SHL shift-amount semantics",
        "Use all eight bits of B as the shift amount instead of B[2:0].",
        "            SHL:    result = a_extended << shift_amount;",
        "            SHL:    result = a_extended << b;",
    ),
)

CSV_FIELDS = (
    "mutant_id",
    "fault_category",
    "source_sha256",
    "compile_result",
    "sat_result",
    "classification",
    "a",
    "b",
    "opcode",
    "expected_output",
    "mutant_output",
    "python_validation",
    "simulation_replay",
    "counterexample_vcd",
    "elapsed_seconds",
    "compile_log",
    "solver_log",
    "validation_log",
    "simulation_log",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def capture_version(executable: str, log_path: Path) -> str:
    try:
        process = subprocess.run(
            [executable, "-V"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        log_path.write_text(f"Version command failed: {exc}\n", encoding="utf-8")
        raise RuntimeError(f"Version command failed for {executable}: {exc}") from exc

    log_path.write_text(process.stdout, encoding="utf-8")
    if process.returncode != 0:
        raise RuntimeError(
            f"Version command for {executable} exited {process.returncode}"
        )
    version = next((line.strip() for line in process.stdout.splitlines() if line.strip()), "")
    if not version:
        raise RuntimeError(f"Version command for {executable} returned no output")
    return version


def report_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def generate_mutant(source: str, mutation: Mutation) -> str:
    if source.count(mutation.anchor) != 1:
        raise ValueError(
            f"{mutation.identifier}: source anchor must match exactly once; "
            f"found {source.count(mutation.anchor)}"
        )
    mutated = source.replace(mutation.anchor, mutation.replacement, 1)
    if mutated == source:
        raise ValueError(f"{mutation.identifier}: transformation made no source change")

    before = source.splitlines()
    after = mutated.splitlines()
    changed = [
        (left, right)
        for left, right in zip(before, after)
        if left != right
    ]
    if len(before) != len(after) or changed != [(mutation.anchor, mutation.replacement)]:
        raise ValueError(f"{mutation.identifier}: transformation changed more than one RTL line")
    return mutated


def yosys_script(dut: Path, *, compile_json: Path | None = None,
                 expect_mismatch: bool = False, counterexample: Path | None = None) -> str:
    commands = [
        f"read_verilog -sv {dut} {SPEC} {MITER}",
        "prep -top alu_formal_miter -flatten",
        "techmap",
        "opt",
        "check",
    ]
    if compile_json is not None:
        commands.append(f"write_json {compile_json}")
    else:
        mode = "-falsify" if expect_mismatch else "-verify"
        sat = (
            f"sat {mode} -prove mismatch 0 -timeout {SAT_TIMEOUT} "
            "-show a -show b -show opcode -show dut_result -show spec_result"
        )
        if counterexample is not None:
            sat += f" -dump_vcd {counterexample}"
        commands.append(sat)
    return "; ".join(commands)


def run_yosys(yosys: str, script: str, log_path: Path, timeout: int) -> tuple[int | None, str]:
    command = [yosys, "-Q", "-p", script]
    log_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        process = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        output = exc.stdout or ""
        if isinstance(output, bytes):
            output = output.decode("utf-8", errors="replace")
        log_path.write_text(
            f"$ {' '.join(command)}\n{output}\nTIMEOUT after {timeout} seconds\n",
            encoding="utf-8",
        )
        return None, output
    except OSError as exc:
        log_path.write_text(f"$ {' '.join(command)}\nTOOL_ERROR: {exc}\n", encoding="utf-8")
        return -1, str(exc)
    log_path.write_text(f"$ {' '.join(command)}\n{process.stdout}", encoding="utf-8")
    return process.returncode, process.stdout


def solver_result(log: str, return_code: int | None) -> str:
    lowered = log.lower()
    if "model found: fail!" in lowered or "sat solving finished - model found" in lowered:
        return "SAT"
    if "no model found: success!" in lowered or "sat solving finished - no model found" in lowered:
        return "UNSAT"
    if return_code is None or is_solver_timeout(lowered):
        return "TIMEOUT"
    if "unknown" in lowered:
        return "UNKNOWN"
    return "TOOL_ERROR"


def is_solver_timeout(log: str) -> bool:
    return any(
        marker in log
        for marker in (
            "sat solving finished - timeout",
            "solver timeout",
            "timeout during sat solving",
            "timed out",
            "timeout after ",
        )
    )


def parse_counterexample_vcd(path: Path) -> dict[str, int]:
    declarations: dict[str, list[tuple[int, str, int]]] = {}
    scopes: list[str] = []
    values: dict[str, str] = {}
    in_header = True
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        fields = line.strip().split()
        if not fields:
            continue
        if in_header:
            if fields[0] == "$scope" and len(fields) >= 3:
                scopes.append(fields[2])
            elif fields[0] == "$upscope" and scopes:
                scopes.pop()
            elif fields[0] == "$var" and len(fields) >= 5:
                try:
                    width = int(fields[2])
                except ValueError:
                    continue
                symbol = fields[3]
                name = fields[4].lstrip("\\")
                leaf = name.rsplit(".", 1)[-1].split("[", 1)[0]
                declarations.setdefault(leaf, []).append((len(scopes), symbol, width))
            elif fields[0] == "$enddefinitions":
                in_header = False
            continue

        if line.startswith("b") or line.startswith("B"):
            parts = line[1:].split()
            if len(parts) == 2:
                values[parts[1]] = parts[0]
        elif line[0] in "01xXzZ":
            symbol = line[1:].strip()
            if symbol:
                values[symbol] = line[0]

    result: dict[str, int] = {}
    for name in ("a", "b", "opcode", "dut_result", "spec_result"):
        candidates = declarations.get(name, [])
        if not candidates:
            raise ValueError(f"VCD has no signal named {name}")
        shallowest = min(item[0] for item in candidates)
        _, symbol, _ = next(item for item in candidates if item[0] == shallowest)
        bits = values.get(symbol)
        if bits is None or any(bit not in "01" for bit in bits):
            raise ValueError(f"VCD signal {name} has no fully known binary value")
        result[name] = int(bits, 2)
    return result


def read_sat_status(log: str, return_code: int | None) -> str:
    if return_code is None:
        return "TIMEOUT"
    if return_code != 0:
        return "TIMEOUT" if is_solver_timeout(log.lower()) else "TOOL_ERROR"
    return solver_result(log, return_code)


def run_compile(yosys: str, dut: Path, folder: Path) -> tuple[str, int | None]:
    netlist = folder / "compiled.json"
    code, _ = run_yosys(
        yosys,
        yosys_script(dut, compile_json=netlist),
        folder / "compile.log",
        PROCESS_TIMEOUT,
    )
    if code is None:
        return "TIMEOUT", code
    if code != 0 or not netlist.is_file():
        return "TOOL_ERROR", code
    try:
        design = json.loads(netlist.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "TOOL_ERROR", code
    if "alu_formal_miter" not in design.get("modules", {}):
        return "TOOL_ERROR", code
    return "PASS", code


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in CSV_FIELDS})


def evaluate_mutant(yosys: str, source: str, mutation: Mutation, folder: Path) -> dict[str, Any]:
    started = time.perf_counter()
    folder.mkdir(parents=True, exist_ok=False)
    mutant_source = generate_mutant(source, mutation)
    mutant_path = folder / "alu_8bit.sv"
    mutant_path.write_text(mutant_source, encoding="utf-8")
    source_hash = sha256(mutant_path)
    result: dict[str, Any] = {
        "mutant_id": mutation.identifier,
        "fault_category": mutation.category,
        "description": mutation.description,
        "source_sha256": source_hash,
        "generated": True,
        "compile_result": "NOT_RUN",
        "compile_exit_code": None,
        "sat_result": "NOT_RUN",
        "sat_exit_code": None,
        "classification": "TOOL_ERROR",
        "counterexample": None,
        "counterexample_vcd": None,
        "python_validation": "NOT_RUN",
        "simulation_replay": "NOT_RUN",
        "elapsed_seconds": None,
        "logs": {
            "compile": report_path(folder / "compile.log"),
            "solver": report_path(folder / "solver.log"),
            "validation": report_path(folder / "validation.log"),
            "simulation": report_path(folder / "simulation" / "simulator.log"),
        },
    }

    compile_result, compile_code = run_compile(yosys, mutant_path, folder)
    result["compile_result"] = compile_result
    result["compile_exit_code"] = compile_code
    if compile_result != "PASS":
        result["classification"] = compile_result
        result["elapsed_seconds"] = round(time.perf_counter() - started, 6)
        return result

    vcd_path = folder / "counterexample.vcd"
    solver_code, solver_log = run_yosys(
        yosys,
        yosys_script(mutant_path, expect_mismatch=True, counterexample=vcd_path),
        folder / "solver.log",
        PROCESS_TIMEOUT,
    )
    result["sat_exit_code"] = solver_code
    result["sat_result"] = read_sat_status(solver_log, solver_code)
    if solver_code != 0:
        result["classification"] = (
            "TIMEOUT" if solver_code is None else "TOOL_ERROR"
        )
        result["solver_error"] = (
            "Yosys SAT command returned a nonzero exit status"
        )
    elif result["sat_result"] == "UNSAT":
        result["classification"] = "EQUIVALENT"
    elif result["sat_result"] in ("UNKNOWN", "TIMEOUT", "TOOL_ERROR"):
        result["classification"] = result["sat_result"]
    elif not vcd_path.is_file():
        result["classification"] = "TOOL_ERROR"
        result["validation_error"] = "SAT outcome had no counterexample VCD"
    else:
        result["counterexample_vcd"] = report_path(vcd_path)
        try:
            model = parse_counterexample_vcd(vcd_path)
            from verification.model import reference

            expected = reference(model["a"], model["b"], model["opcode"])
            python_valid = expected == model["spec_result"] and expected != model["dut_result"]
            validation_log = (
                f"inputs: a=0x{model['a']:02x} b=0x{model['b']:02x} "
                f"opcode=0b{model['opcode']:03b}\n"
                f"spec_result=0x{model['spec_result']:04x}\n"
                f"python_reference=0x{expected:04x}\n"
                f"mutant_result=0x{model['dut_result']:04x}\n"
                f"python_validation={'PASS' if python_valid else 'FAIL'}\n"
            )
            (folder / "validation.log").write_text(validation_log, encoding="utf-8")
            result["counterexample"] = {
                "a": model["a"],
                "b": model["b"],
                "opcode": model["opcode"],
                "expected_output": expected,
                "specification_output": model["spec_result"],
                "mutant_output": model["dut_result"],
            }
            result.update(
                a=model["a"],
                b=model["b"],
                opcode=model["opcode"],
                expected_output=f"0x{expected:04x}",
                mutant_output=f"0x{model['dut_result']:04x}",
            )
            result["python_validation"] = "PASS" if python_valid else "FAIL"
            if not python_valid:
                result["classification"] = "TOOL_ERROR"
                result["validation_error"] = "SAT model conflicts with the Python semantic oracle"
            else:
                from verification.run import simulate

                replay_folder = folder / "simulation"
                replay_folder.mkdir()
                row = (
                    mutation.identifier,
                    model["a"],
                    model["b"],
                    model["opcode"],
                    expected,
                )
                replay_report, actuals = simulate(
                    [row],
                    replay_folder,
                    seed=2026,
                    rtl=mutant_path,
                    timeout=30,
                )
                sim_log = replay_folder / "simulator.log"
                simulation_valid = (
                    len(actuals) == 1
                    and actuals[0] == model["dut_result"]
                    and replay_report["checked"] == 1
                    and replay_report["failed"] == 1
                    and replay_report["simulator_exit_code"] != 0
                    and "MISMATCH" in sim_log.read_text(encoding="utf-8", errors="replace")
                )
                result["simulation_replay"] = "PASS" if simulation_valid else "FAIL"
                result["simulation"] = {
                    "report": report_path(replay_folder / "regression_summary.json"),
                    "actual_output": actuals[0] if actuals else None,
                    "simulator_exit_code": replay_report["simulator_exit_code"],
                    "reference_checker_rejected": replay_report["failed"] == 1,
                }
                with sim_log.open("a", encoding="utf-8") as handle:
                    handle.write(
                        f"\nREPLAY_MATCHES_FORMAL_MUTANT="
                        f"{'PASS' if simulation_valid else 'FAIL'}\n"
                    )
                if simulation_valid:
                    result["classification"] = "KILLED"
                else:
                    result["classification"] = "TOOL_ERROR"
                    result["validation_error"] = "Icarus replay did not confirm the SAT mutant result"
        except (OSError, ValueError, ImportError, KeyError, RuntimeError) as exc:
            result["classification"] = "TOOL_ERROR"
            result["validation_error"] = str(exc)
            (folder / "validation.log").write_text(
                f"VALIDATION TOOL_ERROR: {exc}\n", encoding="utf-8"
            )

    result["elapsed_seconds"] = round(time.perf_counter() - started, 6)
    return result


def metrics(results: list[dict[str, Any]]) -> dict[str, int]:
    classes = ("KILLED", "EQUIVALENT", "UNKNOWN", "TIMEOUT", "TOOL_ERROR", "NOT_RUN")
    output = {status.lower(): sum(item["classification"] == status for item in results)
              for status in classes}
    output["generated"] = sum(bool(item.get("generated")) for item in results)
    output["compiled"] = sum(item.get("compile_result") == "PASS" for item in results)
    output["counterexamples_validated"] = sum(
        item.get("classification") == "KILLED"
        and item.get("python_validation") == "PASS"
        for item in results
    )
    output["simulation_replays_passed"] = sum(
        item.get("simulation_replay") == "PASS" for item in results
    )
    return output


def campaign(yosys: str, output_root: Path, solver_timeout: int) -> int:
    global SAT_TIMEOUT, PROCESS_TIMEOUT
    SAT_TIMEOUT = solver_timeout
    PROCESS_TIMEOUT = solver_timeout + 15

    started_at = datetime.now(timezone.utc)
    run_id = f"{started_at.strftime('%Y%m%dT%H%M%S.%fZ')}-{subprocess.run(['git', 'rev-parse', '--short=12', 'HEAD'], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()}"
    out = output_root / run_id
    out.mkdir(parents=True, exist_ok=False)

    source = RTL.read_text(encoding="utf-8")
    report: dict[str, Any] = {
        "campaign_id": run_id,
        "status": "RUNNING",
        "stage": "preflight",
        "exit_code": None,
        "git_commit": subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip(),
        "started_at_utc": started_at.isoformat(),
        "tool_versions": {
            "python": platform.python_version(),
            "yosys": None,
            "iverilog": None,
            "vvp": None,
        },
        "source_sha256": {
            "production_rtl": sha256(RTL),
            "formal_spec": sha256(SPEC),
            "formal_miter": sha256(MITER),
        },
        "domain": "all 2^19 known-binary inputs; all 16 output bits compared; no assumptions; X/Z excluded",
        "output_directory": report_path(out),
        "tool_version_logs": {
            "yosys": report_path(out / "yosys-version.log"),
            "iverilog": report_path(out / "iverilog-version.log"),
            "vvp": report_path(out / "vvp-version.log"),
        },
        "fault_model_limitations": (
            "Seven selected single-fault semantic mutants; this does not establish "
            "complete specification or verification coverage."
        ),
        "planned_mutants": len(MUTATIONS),
        "metrics": {},
        "baseline": {"status": "NOT_RUN"},
        "mutants": [],
        "elapsed_seconds": None,
    }
    summary_path = out / "summary.json"

    def save() -> None:
        summary_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        write_csv(out / "mutants.csv", report["mutants"])

    save()
    version_log = out / "yosys-version.log"
    try:
        report["tool_versions"]["yosys"] = capture_version(yosys, version_log)
        missing_simulators = [
            tool for tool in ("iverilog", "vvp") if shutil.which(tool) is None
        ]
        if missing_simulators:
            reason = f"Missing required replay tool(s): {', '.join(missing_simulators)}"
            report["mutants"] = [
                {
                    "mutant_id": mutation.identifier,
                    "classification": "NOT_RUN",
                    "reason": reason,
                }
                for mutation in MUTATIONS
            ]
            report.update(
                status="NOT_RUN",
                stage="preflight",
                exit_code=2,
                reason=reason,
                metrics=metrics(report["mutants"]),
                elapsed_seconds=round(
                    (datetime.now(timezone.utc) - started_at).total_seconds(), 6
                ),
            )
            save()
            return 2
        report["tool_versions"]["iverilog"] = capture_version(
            shutil.which("iverilog") or "iverilog", out / "iverilog-version.log"
        )
        report["tool_versions"]["vvp"] = capture_version(
            shutil.which("vvp") or "vvp", out / "vvp-version.log"
        )
    except RuntimeError as exc:
        report.update(
            status="FAIL",
            stage="preflight",
            exit_code=1,
            error=str(exc),
            elapsed_seconds=round(
                (datetime.now(timezone.utc) - started_at).total_seconds(), 6
            ),
        )
        save()
        return 1
    save()

    baseline = out / "baseline"
    baseline.mkdir()
    report["stage"] = "baseline_compile"
    save()
    compile_result, compile_code = run_compile(yosys, RTL, baseline)
    report["baseline"] = {"compile_result": compile_result, "compile_exit_code": compile_code}
    if compile_result != "PASS":
        report["baseline"]["status"] = compile_result
        report.update(
            status="FAIL",
            stage="baseline_compile",
            exit_code=1,
            elapsed_seconds=round(
                (datetime.now(timezone.utc) - started_at).total_seconds(), 6
            ),
        )
        save()
        return 1

    report["stage"] = "baseline_proof"
    save()
    baseline_code, baseline_log = run_yosys(
        yosys,
        yosys_script(RTL),
        baseline / "solver.log",
        PROCESS_TIMEOUT,
    )
    baseline_sat = read_sat_status(baseline_log, baseline_code)
    report["baseline"].update(
        status="PROVED" if baseline_sat == "UNSAT" and baseline_code == 0 else baseline_sat,
        solver_result=baseline_sat,
        solver_exit_code=baseline_code,
        compile_log=report_path(baseline / "compile.log"),
        solver_log=report_path(baseline / "solver.log"),
    )
    if baseline_sat != "UNSAT" or baseline_code != 0:
        report.update(
            status="FAIL",
            stage="baseline_proof",
            exit_code=1,
            error="Correct production DUT did not prove equivalent to the formal specification",
            elapsed_seconds=round(
                (datetime.now(timezone.utc) - started_at).total_seconds(), 6
            ),
        )
        save()
        return 1

    report["completed_stages"] = ["preflight", "baseline_compile", "baseline_proof"]
    for mutation in MUTATIONS:
        stage = f"mutant_{mutation.identifier}"
        report["stage"] = stage
        save()
        folder = out / "mutants" / mutation.identifier
        mutation_started = time.perf_counter()
        try:
            item = evaluate_mutant(yosys, source, mutation, folder)
        except (OSError, ValueError) as exc:
            item = {
                "mutant_id": mutation.identifier,
                "fault_category": mutation.category,
                "description": mutation.description,
                "generated": False,
                "compile_result": "NOT_RUN",
                "sat_result": "NOT_RUN",
                "classification": "TOOL_ERROR",
                "error": str(exc),
                "elapsed_seconds": round(time.perf_counter() - mutation_started, 6),
            }
        report["mutants"].append(item)
        report["metrics"] = metrics(report["mutants"])
        if item["classification"] == "KILLED":
            report.setdefault("completed_stages", []).append(stage)
        save()

    report["stage"] = "complete"
    report["elapsed_seconds"] = round(
        (datetime.now(timezone.utc) - started_at).total_seconds(), 6
    )
    report["metrics"] = metrics(report["mutants"])
    successful = (
        len(report["mutants"]) == len(MUTATIONS)
        and report["baseline"]["status"] == "PROVED"
        and report["metrics"]["killed"] == len(MUTATIONS)
        and report["metrics"]["counterexamples_validated"] == len(MUTATIONS)
        and report["metrics"]["simulation_replays_passed"] == len(MUTATIONS)
    )
    report.update(
        status="PASS" if successful else "FAIL",
        exit_code=0 if successful else 1,
    )
    save()
    return 0 if successful else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--yosys", default=shutil.which("yosys"))
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--timeout", type=int, default=SAT_TIMEOUT)
    args = parser.parse_args()
    if args.timeout < 1:
        parser.error("--timeout must be positive")

    if not args.yosys:
        args.output_root.mkdir(parents=True, exist_ok=True)
        report = {
            "campaign_id": None,
            "status": "NOT_RUN",
            "stage": "preflight",
            "exit_code": 2,
            "reason": "Yosys executable not found",
            "planned_mutants": len(MUTATIONS),
            "metrics": {"not_run": len(MUTATIONS)},
            "mutants": [
                {
                    "mutant_id": mutation.identifier,
                    "classification": "NOT_RUN",
                    "reason": "Baseline formal tool unavailable",
                }
                for mutation in MUTATIONS
            ],
        }
        (args.output_root / "not-run-summary.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )
        write_csv(args.output_root / "not-run-mutants.csv", report["mutants"])
        print("FORMAL MUTATION NOT RUN: Yosys executable not found", file=sys.stderr)
        return 2
    if not Path(args.yosys).is_file() and shutil.which(args.yosys) is None:
        args.output_root.mkdir(parents=True, exist_ok=True)
        report = {
            "campaign_id": None,
            "status": "NOT_RUN",
            "stage": "preflight",
            "exit_code": 2,
            "reason": f"Yosys executable not found: {args.yosys}",
            "planned_mutants": len(MUTATIONS),
            "metrics": {"not_run": len(MUTATIONS)},
            "mutants": [
                {
                    "mutant_id": mutation.identifier,
                    "classification": "NOT_RUN",
                    "reason": "Baseline formal tool unavailable",
                }
                for mutation in MUTATIONS
            ],
        }
        (args.output_root / "not-run-summary.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )
        write_csv(args.output_root / "not-run-mutants.csv", report["mutants"])
        print(f"FORMAL MUTATION NOT RUN: {report['reason']}", file=sys.stderr)
        return 2

    try:
        return campaign(args.yosys, args.output_root, args.timeout)
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"FORMAL MUTATION TOOL_ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    raise SystemExit(main())
