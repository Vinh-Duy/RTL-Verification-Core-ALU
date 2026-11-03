#!/usr/bin/env python3
"""Run a reproducible formal-derived semantic mutation audit for the 8-bit ALU."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import re
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
SOURCE_FINGERPRINTS = {
    "production_rtl": "1d9aef598f1ff52c5f10bca44d207e30e2dbe79b5e9ffe169735114ff9a1ce03",
    "formal_spec": "5df84d06df042cd4b5eb904d22908a65ccd1beadc6b07f57466f92fd116b3bff",
    "formal_miter": "7b049f6d949ac1166267b8efab689c5308a0784eaa0cc2270d10e3d1519feaf8",
}
SAT_TIMEOUT = 60
PROCESS_TIMEOUT = SAT_TIMEOUT + 15
VCD_WIDTHS = {"a": 8, "b": 8, "opcode": 3, "dut_result": 16, "spec_result": 16}


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


def source_fingerprints() -> dict[str, str]:
    return {
        "production_rtl": sha256(RTL),
        "formal_spec": sha256(SPEC),
        "formal_miter": sha256(MITER),
    }


def module_header(source: str) -> str:
    match = re.search(r"\bmodule\s+alu_8bit\s*\(.*?\);", source, re.DOTALL)
    if match is None:
        raise ValueError("Source must declare the alu_8bit module with its expected interface")
    return match.group(0)


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
    except subprocess.TimeoutExpired as exc:
        log_path.write_text(f"Version command timed out: {exc}\n", encoding="utf-8")
        raise TimeoutError(f"Version command timed out for {executable}") from exc
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
    source_hash = hashlib.sha256(source.encode("utf-8")).hexdigest()
    if source_hash != SOURCE_FINGERPRINTS["production_rtl"]:
        raise ValueError(
            "Production RTL fingerprint changed unexpectedly; review and update the audit baseline"
        )
    expected_header_hash = hashlib.sha256(
        module_header(RTL.read_text(encoding="utf-8")).encode("utf-8")
    ).hexdigest()
    if hashlib.sha256(module_header(source).encode("utf-8")).hexdigest() != expected_header_hash:
        raise ValueError("Mutation must preserve the alu_8bit module name and interface")
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
    if hashlib.sha256(module_header(mutated).encode("utf-8")).hexdigest() != expected_header_hash:
        raise ValueError(f"{mutation.identifier}: transformation changed the module interface")
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
    except KeyboardInterrupt:
        log_path.write_text(
            f"$ {' '.join(command)}\nINTERRUPTED by user\n",
            encoding="utf-8",
        )
        raise
    except OSError as exc:
        log_path.write_text(f"$ {' '.join(command)}\nTOOL_ERROR: {exc}\n", encoding="utf-8")
        return -1, str(exc)
    log_path.write_text(f"$ {' '.join(command)}\n{process.stdout}", encoding="utf-8")
    return process.returncode, process.stdout


def solver_result(log: str, return_code: int | None) -> str:
    lowered = log.lower()
    results = []
    if re.search(r"sat (?:solving|proof) finished\s*-\s*model found:\s*fail!", lowered):
        results.append("SAT")
    if re.search(
        r"sat (?:solving|proof) finished\s*-\s*no model found:\s*success!",
        lowered,
    ):
        results.append("UNSAT")
    if is_solver_timeout(lowered):
        results.append("TIMEOUT")
    if re.search(r"sat (?:solving|proof) finished\s*-\s*unknown\b", lowered):
        results.append("UNKNOWN")
    if return_code is None:
        return "TIMEOUT"
    if len(results) != 1:
        return "TOOL_ERROR"
    if return_code != 0:
        return results[0] if results[0] == "TIMEOUT" else "TOOL_ERROR"
    return results[0]


def is_solver_timeout(log: str) -> bool:
    return any(
        marker in log
        for marker in (
            "sat solving finished - timeout",
            "sat proof finished - timeout",
            "solver timeout",
            "timeout during sat solving",
            "timed out",
            "timeout after ",
        )
    )


def parse_counterexample_vcd(path: Path) -> dict[str, int]:
    declarations: dict[str, list[tuple[tuple[str, ...], str, int]]] = {}
    scopes: list[str] = []
    values: dict[str, str] = {}
    in_header = True
    saw_timestamp = False
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        fields = line.strip().split()
        if not fields:
            continue
        if in_header:
            if fields[0] == "$scope" and len(fields) >= 3:
                if fields[-1] != "$end":
                    raise ValueError("Malformed VCD scope declaration")
                scopes.append(fields[2].lstrip("\\"))
            elif fields[0] == "$upscope" and fields == ["$upscope", "$end"] and scopes:
                scopes.pop()
            elif fields[0] == "$upscope":
                raise ValueError("Malformed VCD scope nesting")
            elif fields[0] == "$var" and len(fields) >= 5:
                try:
                    width = int(fields[2])
                except ValueError:
                    raise ValueError("Malformed VCD signal width") from None
                if width < 1 or fields[-1] != "$end":
                    raise ValueError("Malformed VCD signal declaration")
                symbol = fields[3]
                name = fields[4].lstrip("\\")
                leaf = name.rsplit(".", 1)[-1].split("[", 1)[0]
                declarations.setdefault(leaf, []).append((tuple(scopes), symbol, width))
            elif fields[0] == "$enddefinitions":
                if fields != ["$enddefinitions", "$end"] or scopes:
                    raise ValueError("Malformed or incomplete VCD header")
                in_header = False
            continue

        if line.startswith("#"):
            try:
                int(line[1:].strip())
            except ValueError:
                raise ValueError("Malformed VCD timestamp") from None
            saw_timestamp = True
        elif line.startswith(("b", "B")):
            parts = line[1:].split()
            if len(parts) != 2 or not parts[0]:
                raise ValueError("Malformed VCD vector value")
            if any(bit not in "01xXzZ" for bit in parts[0]):
                raise ValueError("Malformed binary value in VCD")
            values[parts[1]] = parts[0]
        elif line[0] in "01xXzZ":
            symbol = line[1:].strip()
            if not symbol:
                raise ValueError("Malformed VCD scalar value")
            values[symbol] = line[0]
        elif not line.startswith("$"):
            raise ValueError("Malformed VCD value change")

    if in_header:
        raise ValueError("Incomplete VCD header")
    if not saw_timestamp:
        raise ValueError("Incomplete VCD value section")

    result: dict[str, int] = {}
    for name in ("a", "b", "opcode", "dut_result", "spec_result"):
        candidates = declarations.get(name, [])
        if len(candidates) != 1 or candidates[0][0] != ("alu_formal_miter",):
            raise ValueError(f"VCD has no unique signal named {name} in alu_formal_miter")
        _, symbol, width = candidates[0]
        if width != VCD_WIDTHS[name]:
            raise ValueError(
                f"VCD signal {name} has width {width}, expected {VCD_WIDTHS[name]}"
            )
        bits = values.get(symbol)
        if bits is None:
            raise ValueError(f"VCD signal {name} has no value")
        if any(bit not in "01" for bit in bits):
            raise ValueError(f"VCD signal {name} has no fully known binary value")
        if len(bits) > width:
            raise ValueError(f"VCD signal {name} value exceeds declared width {width}")
        if len(bits) != width:
            raise ValueError(
                f"VCD signal {name} value has width {len(bits)}, expected {width}"
            )
        result[name] = int(bits, 2)
    if result["dut_result"] == result["spec_result"]:
        raise ValueError("VCD counterexample does not distinguish DUT and specification")
    return result


def counterexample_matches_summary(
    model: dict[str, int],
    result: dict[str, Any],
    expected_output: int | None = None,
) -> None:
    if expected_output is None:
        expected_output = model["spec_result"]
    counterexample = result.get("counterexample")
    expected = {
        "a": model["a"],
        "b": model["b"],
        "opcode": model["opcode"],
        "expected_output": expected_output,
        "specification_output": model["spec_result"],
        "mutant_output": model["dut_result"],
    }
    if counterexample != expected:
        raise ValueError("VCD counterexample does not match the summary")
    top_level = {
        "a": model["a"],
        "b": model["b"],
        "opcode": model["opcode"],
        "expected_output": f"0x{expected_output:04x}",
        "mutant_output": f"0x{model['dut_result']:04x}",
    }
    if any(result.get(key) != value for key, value in top_level.items()):
        raise ValueError("VCD counterexample does not match the summary")

def read_sat_status(log: str, return_code: int | None) -> str:
    return solver_result(log, return_code)


def run_compile(yosys: str, dut: Path, folder: Path) -> tuple[str, int | None]:
    netlist = folder / "compiled.json"
    netlist.unlink(missing_ok=True)
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
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in CSV_FIELDS})
    os.replace(temporary, path)


def save_report(summary_path: Path, csv_path: Path, report: dict[str, Any]) -> None:
    write_csv(csv_path, report["mutants"])
    temporary = summary_path.with_name(summary_path.name + ".tmp")
    temporary.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, summary_path)


def save_json(path: Path, report: dict[str, Any]) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


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
        "production_source_sha256": SOURCE_FINGERPRINTS["production_rtl"],
        "source_sha256": source_hash,
        "mutant_source_path": report_path(mutant_path),
        "transformation": {
            "anchor": mutation.anchor,
            "replacement": mutation.replacement,
        },
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
    vcd_path.unlink(missing_ok=True)
    solver_code, solver_log = run_yosys(
        yosys,
        yosys_script(mutant_path, expect_mismatch=True, counterexample=vcd_path),
        folder / "solver.log",
        PROCESS_TIMEOUT,
    )
    result["sat_exit_code"] = solver_code
    result["sat_result"] = read_sat_status(solver_log, solver_code)
    if result["sat_result"] == "UNSAT":
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
            from verification.model import OPS, reference

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
            counterexample_matches_summary(model, result, expected)
            result["python_validation"] = "PASS" if python_valid else "FAIL"
            if not python_valid:
                result["classification"] = "FAIL"
                result["validation_error"] = "SAT model conflicts with an independent semantic validator"
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
                sim_report_path = replay_folder / "regression_summary.json"
                if not isinstance(replay_report, dict):
                    raise ValueError("Icarus replay result is not a JSON object")
                disk_report = json.loads(sim_report_path.read_text(encoding="utf-8"))
                if not isinstance(disk_report, dict):
                    raise ValueError("Icarus replay summary is not a JSON object")
                failures = disk_report.get("first_failures")
                first_failure = (
                    failures[0]
                    if isinstance(failures, list)
                    and failures
                    and isinstance(failures[0], dict)
                    else {}
                )
                simulation_valid = (
                    len(actuals) == 1
                    and actuals[0] == model["dut_result"]
                    and replay_report["checked"] == 1
                    and replay_report["failed"] == 1
                    and replay_report["simulator_exit_code"] != 0
                    and disk_report.get("status") == "FAIL"
                    and disk_report.get("requested") == 1
                    and disk_report.get("checked") == 1
                    and disk_report.get("failed") == 1
                    and disk_report.get("completed") is True
                    and disk_report.get("simulator_exit_code") == replay_report["simulator_exit_code"]
                    and first_failure.get("id") == 0
                    and first_failure.get("opcode") == OPS[model["opcode"]]
                    and first_failure.get("a") == model["a"]
                    and first_failure.get("b") == model["b"]
                    and first_failure.get("expected") == expected
                    and first_failure.get("actual") == f"{model['dut_result']:04x}"
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
                    result["classification"] = "FAIL"
                    result["validation_error"] = "Icarus replay did not confirm the SAT mutant result"
        except subprocess.TimeoutExpired as exc:
            result["classification"] = "TIMEOUT"
            result["simulation_replay"] = "TIMEOUT"
            result["validation_error"] = str(exc)
        except (
            OSError,
            ValueError,
            ImportError,
            KeyError,
            RuntimeError,
            TypeError,
            IndexError,
        ) as exc:
            result["classification"] = "TOOL_ERROR"
            result["validation_error"] = str(exc)
            (folder / "validation.log").write_text(
                f"VALIDATION TOOL_ERROR: {exc}\n", encoding="utf-8"
            )

    result["elapsed_seconds"] = round(time.perf_counter() - started, 6)
    return result


def metrics(results: list[dict[str, Any]]) -> dict[str, int]:
    classes = ("KILLED", "EQUIVALENT", "FAIL", "UNKNOWN", "TIMEOUT", "TOOL_ERROR", "NOT_RUN")
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


def not_run_mutants(reason: str) -> list[dict[str, str]]:
    return [
        {
            "mutant_id": mutation.identifier,
            "classification": "NOT_RUN",
            "reason": reason,
        }
        for mutation in MUTATIONS
    ]


def evidence_file(path: str) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else ROOT / candidate


def validate_campaign_evidence(report: dict[str, Any], out: Path) -> None:
    if report.get("source_sha256") != SOURCE_FINGERPRINTS:
        raise ValueError("Source fingerprints in the report do not match the reviewed baseline")
    current_commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()
    if report.get("git_commit") != current_commit:
        raise ValueError("Campaign summary is not tied to the current commit")
    if report["baseline"].get("status") != "PROVED":
        raise ValueError("Baseline proof evidence is incomplete")
    baseline = out / "baseline"
    for path in (baseline / "compiled.json", baseline / "compile.log", baseline / "solver.log"):
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError(f"Missing baseline evidence: {path}")
    baseline_log = (baseline / "solver.log").read_text(encoding="utf-8", errors="replace")
    if read_sat_status(baseline_log, report["baseline"].get("solver_exit_code")) != "UNSAT":
        raise ValueError("Baseline solver log does not confirm the reported proof")
    for version_log in report["tool_version_logs"].values():
        path = evidence_file(version_log)
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError(f"Missing tool-version evidence: {path}")

    csv_path = out / "mutants.csv"
    with csv_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != len(MUTATIONS):
        raise ValueError("Mutation CSV does not contain every planned mutant")
    rows_by_id = {row["mutant_id"]: row for row in rows}

    for item in report["mutants"]:
        if item.get("classification") != "KILLED":
            raise ValueError(f"Mutant {item.get('mutant_id')} is not classified as killed")
        mutant_path = evidence_file(item["mutant_source_path"])
        if not mutant_path.is_file() or sha256(mutant_path) != item.get("source_sha256"):
            raise ValueError(f"Generated mutant source is missing or has changed: {mutant_path}")
        folder = mutant_path.parent
        compile_log = folder / "compile.log"
        solver_log = folder / "solver.log"
        validation_log = folder / "validation.log"
        simulation_log = folder / "simulation" / "simulator.log"
        simulation_report_path = folder / "simulation" / "regression_summary.json"
        required_logs = (compile_log, solver_log, validation_log, simulation_log)
        if any(not path.is_file() or path.stat().st_size == 0 for path in required_logs):
            raise ValueError(f"Mutant {item['mutant_id']} is missing required evidence logs")
        if read_sat_status(
            solver_log.read_text(encoding="utf-8", errors="replace"),
            item.get("sat_exit_code"),
        ) != "SAT":
            raise ValueError(f"Mutant {item['mutant_id']} solver log does not confirm SAT")
        vcd_path = evidence_file(item.get("counterexample_vcd", ""))
        if not vcd_path.is_file():
            raise ValueError(f"Mutant {item['mutant_id']} counterexample VCD is missing")
        model = parse_counterexample_vcd(vcd_path)
        from verification.model import OPS, reference

        python_expected = reference(model["a"], model["b"], model["opcode"])
        counterexample_matches_summary(model, item, python_expected)
        if python_expected != model["spec_result"]:
            raise ValueError(f"Mutant {item['mutant_id']} counterexample fails Python validation")
        if "python_validation=PASS" not in validation_log.read_text(encoding="utf-8"):
            raise ValueError(f"Mutant {item['mutant_id']} validation log is incomplete")
        replay_log = simulation_log.read_text(encoding="utf-8", errors="replace")
        if "MISMATCH" not in replay_log or "REPLAY_MATCHES_FORMAL_MUTANT=PASS" not in replay_log:
            raise ValueError(f"Mutant {item['mutant_id']} replay log does not confirm rejection")
        replay_report = json.loads(simulation_report_path.read_text(encoding="utf-8"))
        if not isinstance(replay_report, dict):
            raise ValueError(f"Mutant {item['mutant_id']} replay report is not a JSON object")
        failures = replay_report.get("first_failures")
        first_failure = (
            failures[0]
            if isinstance(failures, list)
            and failures
            and isinstance(failures[0], dict)
            else {}
        )
        replay_summary = item.get("simulation")
        if not isinstance(replay_summary, dict):
            raise ValueError(f"Mutant {item['mutant_id']} replay summary is missing")
        if not (
            replay_report.get("status") == "FAIL"
            and replay_report.get("requested") == 1
            and replay_report.get("checked") == 1
            and replay_report.get("failed") == 1
            and replay_report.get("completed") is True
            and replay_report.get("simulator_exit_code") != 0
            and first_failure.get("id") == 0
            and first_failure.get("opcode") == OPS[model["opcode"]]
            and first_failure.get("a") == model["a"]
            and first_failure.get("b") == model["b"]
            and first_failure.get("expected") == python_expected
            and first_failure.get("actual") == f"{model['dut_result']:04x}"
            and replay_summary.get("actual_output") == model["dut_result"]
            and replay_summary.get("simulator_exit_code")
            == replay_report.get("simulator_exit_code")
            and replay_summary.get("reference_checker_rejected") is True
        ):
            raise ValueError(f"Mutant {item['mutant_id']} replay report is incomplete")
        row = rows_by_id.get(item["mutant_id"])
        if row is None or row.get("classification") != "KILLED":
            raise ValueError(f"Mutation CSV disagrees with summary for {item['mutant_id']}")
        if row.get("source_sha256") != item.get("source_sha256"):
            raise ValueError(f"Mutation CSV source hash disagrees for {item['mutant_id']}")
        if any(
            row.get(key) != str(value)
            for key, value in {
                "a": model["a"],
                "b": model["b"],
                "opcode": model["opcode"],
                "expected_output": f"0x{python_expected:04x}",
                "mutant_output": f"0x{model['dut_result']:04x}",
                "python_validation": "PASS",
                "simulation_replay": "PASS",
                "sat_result": "SAT",
                "compile_result": "PASS",
            }.items()
        ):
            raise ValueError(f"Mutation CSV counterexample disagrees for {item['mutant_id']}")


def campaign_status(report: dict[str, Any]) -> str:
    results = report.get("mutants", [])
    classifications = [item.get("classification") for item in results]
    if any(value == "FAIL" or value == "EQUIVALENT" for value in classifications):
        return "FAIL"

    baseline = report["baseline"].get("status")
    if baseline == "NOT_RUN":
        return "NOT_RUN" if all(value == "NOT_RUN" for value in classifications) else "FAIL"
    if baseline in ("TIMEOUT", "UNKNOWN", "TOOL_ERROR"):
        return baseline
    if baseline != "PROVED":
        return "FAIL"

    for status in ("TOOL_ERROR", "TIMEOUT", "UNKNOWN", "NOT_RUN"):
        if status in classifications:
            return status
    if len(results) != len(MUTATIONS) or any(value != "KILLED" for value in classifications):
        return "NOT_RUN"
    return "PASS"


def campaign(yosys: str, output_root: Path, solver_timeout: int) -> int:
    global SAT_TIMEOUT, PROCESS_TIMEOUT
    SAT_TIMEOUT = solver_timeout
    PROCESS_TIMEOUT = solver_timeout + 15

    started_at = datetime.now(timezone.utc)
    run_id = f"{started_at.strftime('%Y%m%dT%H%M%S.%fZ')}-{subprocess.run(['git', 'rev-parse', '--short=12', 'HEAD'], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()}"
    out = output_root / run_id
    out.mkdir(parents=True, exist_ok=False)

    source = RTL.read_text(encoding="utf-8")
    fingerprints = source_fingerprints()
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
        "source_sha256": fingerprints,
        "expected_source_sha256": SOURCE_FINGERPRINTS,
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
        save_report(summary_path, out / "mutants.csv", report)

    save()
    if fingerprints != SOURCE_FINGERPRINTS:
        report["mutants"] = not_run_mutants("Source fingerprint preflight failed")
        report["metrics"] = metrics(report["mutants"])
        report.update(
            status="TOOL_ERROR",
            stage="source_preflight",
            exit_code=1,
            error="Production RTL or formal source fingerprints changed unexpectedly",
            elapsed_seconds=round(
                (datetime.now(timezone.utc) - started_at).total_seconds(), 6
            ),
        )
        save()
        return 1

    version_log = out / "yosys-version.log"
    try:
        report["tool_versions"]["yosys"] = capture_version(yosys, version_log)
        missing_simulators = [
            tool for tool in ("iverilog", "vvp") if shutil.which(tool) is None
        ]
        if missing_simulators:
            reason = f"Missing required replay tool(s): {', '.join(missing_simulators)}"
            report["mutants"] = not_run_mutants(reason)
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
    except TimeoutError as exc:
        report["mutants"] = not_run_mutants("Tool version preflight timed out")
        report["metrics"] = metrics(report["mutants"])
        report.update(
            status="TIMEOUT",
            stage="preflight",
            exit_code=1,
            error=str(exc),
            elapsed_seconds=round(
                (datetime.now(timezone.utc) - started_at).total_seconds(), 6
            ),
        )
        save()
        return 1
    except RuntimeError as exc:
        report["mutants"] = not_run_mutants("Tool version preflight failed")
        report["metrics"] = metrics(report["mutants"])
        report.update(
            status="TOOL_ERROR",
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
        report["mutants"] = not_run_mutants("Baseline compilation did not pass")
        report["metrics"] = metrics(report["mutants"])
        top_status = compile_result if compile_result in ("TIMEOUT", "TOOL_ERROR") else "FAIL"
        report.update(
            status=top_status,
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
        report["mutants"] = not_run_mutants("Baseline equivalence was not proved")
        report["metrics"] = metrics(report["mutants"])
        top_status = (
            baseline_sat
            if baseline_sat in ("TIMEOUT", "UNKNOWN", "TOOL_ERROR")
            else "FAIL"
        )
        report.update(
            status=top_status,
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
        except subprocess.TimeoutExpired as exc:
            item = {
                "mutant_id": mutation.identifier,
                "fault_category": mutation.category,
                "description": mutation.description,
                "generated": folder.joinpath("alu_8bit.sv").is_file(),
                "compile_result": "NOT_RUN",
                "sat_result": "NOT_RUN",
                "classification": "TIMEOUT",
                "error": str(exc),
                "elapsed_seconds": round(time.perf_counter() - mutation_started, 6),
            }
        except subprocess.SubprocessError as exc:
            item = {
                "mutant_id": mutation.identifier,
                "fault_category": mutation.category,
                "description": mutation.description,
                "generated": folder.joinpath("alu_8bit.sv").is_file(),
                "compile_result": "NOT_RUN",
                "sat_result": "NOT_RUN",
                "classification": "TOOL_ERROR",
                "error": str(exc),
                "elapsed_seconds": round(time.perf_counter() - mutation_started, 6),
            }
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
    status = campaign_status(report)
    if status == "PASS":
        try:
            validate_campaign_evidence(report, out)
        except (OSError, ValueError, KeyError, csv.Error, json.JSONDecodeError) as exc:
            status = "TOOL_ERROR"
            report["evidence_error"] = str(exc)
    exit_code = 0 if status == "PASS" else 2 if status == "NOT_RUN" else 1
    report.update(status=status, exit_code=exit_code)
    save()
    return exit_code


def compare_campaigns(first: dict[str, Any], second: dict[str, Any]) -> dict[str, Any]:
    same_sources = (
        first.get("source_sha256") == second.get("source_sha256") == SOURCE_FINGERPRINTS
    )
    same_tools = first.get("tool_versions") == second.get("tool_versions")
    same_commit = first.get("git_commit") == second.get("git_commit")
    baselines_proved = (
        first.get("baseline", {}).get("status") == "PROVED"
        and second.get("baseline", {}).get("status") == "PROVED"
    )
    first_mutants = {item["mutant_id"]: item for item in first.get("mutants", [])}
    second_mutants = {item["mutant_id"]: item for item in second.get("mutants", [])}
    same_mutant_sources = (
        first_mutants.keys() == second_mutants.keys()
        and all(
            first_mutants[key].get("source_sha256")
            == second_mutants[key].get("source_sha256")
            for key in first_mutants.keys() & second_mutants.keys()
        )
    )
    from verification.model import reference

    def valid_witness(item: dict[str, Any]) -> bool:
        witness = item.get("counterexample", {})
        try:
            values = tuple(
                witness[name] for name in ("a", "b", "opcode", "expected_output", "mutant_output")
            )
            a, b, opcode, expected, actual = values
            return (
                all(type(value) is int for value in values)
                and reference(a, b, opcode) == expected
                and expected != actual
            )
        except (KeyError, TypeError, ValueError):
            return False

    semantic_results_valid = (
        len(first_mutants) == len(MUTATIONS)
        and len(second_mutants) == len(MUTATIONS)
        and first_mutants.keys() == second_mutants.keys()
        and baselines_proved
        and all(
            left.get("classification") == right.get("classification") == "KILLED"
            and left.get("python_validation") == right.get("python_validation") == "PASS"
            and left.get("simulation_replay") == right.get("simulation_replay") == "PASS"
            and left.get("counterexample", {}).get("expected_output")
            == left.get("counterexample", {}).get("specification_output")
            and right.get("counterexample", {}).get("expected_output")
            == right.get("counterexample", {}).get("specification_output")
            and valid_witness(left)
            and valid_witness(right)
            for key in first_mutants.keys() & second_mutants.keys()
            for left, right in ((first_mutants[key], second_mutants[key]),)
        )
    )
    exact_counterexamples = (
        first_mutants.keys() == second_mutants.keys()
        and all(
            first_mutants[key].get("counterexample")
            == second_mutants[key].get("counterexample")
            for key in first_mutants
        )
    )
    return {
        "status": (
            "PASS"
            if same_sources
            and same_tools
            and same_commit
            and same_mutant_sources
            and semantic_results_valid
            else "FAIL"
        ),
        "source_reproducibility": same_sources and same_mutant_sources,
        "tool_version_reproducibility": same_tools,
        "commit_reproducibility": same_commit,
        "semantic_reproducibility": semantic_results_valid,
        "exact_counterexample_reproducibility": exact_counterexamples,
        "counterexample_assignments_required_to_match": False,
    }


def run_reproducibility(
    yosys: str, output_root: Path, solver_timeout: int
) -> int:
    output_root.mkdir(parents=True, exist_ok=True)
    commit = subprocess.run(
        ["git", "rev-parse", "--short=12", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    group = output_root / (
        f"repro-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')}-{commit}"
    )
    group.mkdir(parents=False, exist_ok=False)
    runs = []
    exit_codes = []
    for index in (1, 2):
        run_root = group / f"run-{index}"
        run_root.mkdir()
        exit_codes.append(campaign(yosys, run_root, solver_timeout))
        summaries = list(run_root.glob("*/summary.json"))
        if len(summaries) != 1:
            runs.append(None)
        else:
            runs.append(json.loads(summaries[0].read_text(encoding="utf-8")))

    comparison = (
        compare_campaigns(runs[0], runs[1])
        if runs[0] is not None and runs[1] is not None
        else {"status": "TOOL_ERROR", "reason": "A campaign summary is missing"}
    )
    report = {
        "status": (
            comparison["status"]
            if all(code == 0 for code in exit_codes)
            else next(
                (run.get("status") for run in runs if run and run.get("status") != "PASS"),
                "TOOL_ERROR",
            )
        ),
        "git_commit": subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip(),
        "run_directories": [report_path(run_root) for run_root in (group / "run-1", group / "run-2")],
        "exit_codes": exit_codes,
        "comparison": comparison,
    }
    save_json(group / "reproducibility.json", report)
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "PASS" else 1


def write_not_run(output_root: Path, reason: str) -> int:
    output_root.mkdir(parents=True, exist_ok=True)
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    run_id = f"not-run-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')}-{commit[:12]}"
    out = output_root / run_id
    out.mkdir(exist_ok=False)
    report = {
        "campaign_id": run_id,
        "git_commit": commit,
        "status": "NOT_RUN",
        "stage": "preflight",
        "exit_code": 2,
        "reason": reason,
        "planned_mutants": len(MUTATIONS),
        "tool_versions": {"python": platform.python_version()},
        "source_sha256": source_fingerprints(),
        "metrics": metrics(not_run_mutants(reason)),
        "baseline": {"status": "NOT_RUN"},
        "mutants": not_run_mutants(reason),
    }
    save_report(out / "summary.json", out / "mutants.csv", report)
    print(f"FORMAL MUTATION NOT RUN: {reason}", file=sys.stderr)
    return 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--yosys", default=shutil.which("yosys"))
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--timeout", type=int, default=SAT_TIMEOUT)
    parser.add_argument("--repeat", type=int, choices=(1, 2), default=1)
    args = parser.parse_args()
    if args.timeout < 1:
        parser.error("--timeout must be positive")

    if not args.yosys or (
        not Path(args.yosys).is_file() and shutil.which(args.yosys) is None
    ):
        return write_not_run(
            args.output_root,
            f"Yosys executable not found: {args.yosys or 'not configured'}",
        )

    try:
        if args.repeat == 2:
            return run_reproducibility(args.yosys, args.output_root, args.timeout)
        return campaign(args.yosys, args.output_root, args.timeout)
    except KeyboardInterrupt:
        print("FORMAL MUTATION UNKNOWN: interrupted before campaign completion", file=sys.stderr)
        return 130
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"FORMAL MUTATION TOOL_ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    raise SystemExit(main())
