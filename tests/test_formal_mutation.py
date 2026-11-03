import json
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from formal.mutation_audit import (
    MUTATIONS,
    capture_version,
    campaign,
    compare_campaigns,
    counterexample_matches_summary,
    evaluate_mutant,
    generate_mutant,
    main as mutation_main,
    parse_counterexample_vcd,
    read_sat_status,
    run_compile,
    run_yosys,
    save_report,
    SOURCE_FINGERPRINTS,
    validate_campaign_evidence,
)
from verification.model import reference
from verification.run import simulate


ROOT = Path(__file__).resolve().parents[1]
RTL = ROOT / "rtl" / "alu_8bit.sv"
def make_vcd(
    *,
    a=255,
    b=1,
    opcode=0,
    dut_result=0,
    spec_result=256,
    declarations=None,
    body=None,
    header_end=True,
):
    declarations = declarations or [
        "$var wire 8 v0 \\a $end",
        "$var wire 8 v1 \\b $end",
        "$var wire 16 v2 \\dut_result $end",
        "$var wire 3 v3 \\opcode $end",
        "$var wire 16 v4 \\spec_result $end",
    ]
    header = "\n".join(
        ["$scope module \\alu_formal_miter $end", *declarations, "$upscope $end"]
    )
    if header_end:
        header += "\n$enddefinitions $end"
    if body is None:
        body = (
            f"b{dut_result:016b} v2\nb{opcode:03b} v3\n"
            f"b{spec_result:016b} v4\nb{a:08b} v0\nb{b:08b} v1"
        )
    return f"{header}\n$dumpvars\n#-1\n{body}\n#0\n"


class FormalMutationTests(unittest.TestCase):
    def run_with_fake_sat(
        self, vcd, replay="match", reference_value=None, sat_log=None
    ):
        source = RTL.read_text(encoding="utf-8")
        mutation = MUTATIONS[0]
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary) / "mutant"

            def fake_yosys(_yosys, _script, log_path, _timeout):
                output = sat_log or "SAT solving finished - model found: FAIL!"
                log_path.write_text(output + "\n")
                if vcd is not None:
                    (folder / "counterexample.vcd").write_text(vcd, encoding="utf-8")
                return 0, output

            def fake_simulate(rows, output, **_kwargs):
                self.assertEqual(rows, [(mutation.identifier, 255, 1, 0, 256)])
                if replay == "ordering_error":
                    raise RuntimeError("Transaction ordering/data corrupted at id 0")
                if replay == "missing":
                    return {"checked": 0, "failed": 0, "simulator_exit_code": 0}, []
                actual = 1 if replay == "disagree" else 0
                first_failure = {
                    "id": 1 if replay == "wrong_order" else 0,
                    "opcode": "SUB" if replay == "wrong_order" else "ADD",
                    "a": 255,
                    "b": 1,
                    "expected": 256,
                    "actual": f"{actual:04x}",
                }
                report = {
                    "status": "FAIL",
                    "requested": 1,
                    "checked": 1,
                    "failed": 1,
                    "completed": True,
                    "simulator_exit_code": 1,
                    "first_failures": [first_failure],
                }
                (output / "simulator.log").write_text("MISMATCH\n", encoding="utf-8")
                if replay == "malformed":
                    (output / "regression_summary.json").write_text("{", encoding="utf-8")
                else:
                    (output / "regression_summary.json").write_text(
                        json.dumps(report), encoding="utf-8"
                    )
                return report, [actual]

            reference_patch = (
                patch("verification.model.reference", return_value=reference_value)
                if reference_value is not None
                else patch("verification.model.reference", wraps=reference)
            )
            with (
                patch("formal.mutation_audit.run_compile", return_value=("PASS", 0)),
                patch("formal.mutation_audit.run_yosys", side_effect=fake_yosys),
                patch("verification.run.simulate", side_effect=fake_simulate),
                reference_patch,
            ):
                return evaluate_mutant("yosys", source, mutation, folder)

    def test_each_transform_changes_exactly_one_rtl_line(self):
        source = RTL.read_text(encoding="utf-8")
        for mutation in MUTATIONS:
            with self.subTest(mutant=mutation.identifier):
                generated = generate_mutant(source, mutation)
                self.assertEqual(len(source.splitlines()), len(generated.splitlines()))
                differences = [
                    (before, after)
                    for before, after in zip(source.splitlines(), generated.splitlines())
                    if before != after
                ]
                self.assertEqual(differences, [(mutation.anchor, mutation.replacement)])

    def test_mutation_generator_fails_closed_for_ambiguous_or_drifted_sources(self):
        source = RTL.read_text(encoding="utf-8")
        mutation = MUTATIONS[0]
        cases = (
            (replace(mutation, anchor="missing anchor"), source, "match exactly once"),
            (replace(mutation, anchor="result ="), source, "match exactly once"),
            (mutation, source + "\n// unrelated source change\n", "fingerprint"),
            (replace(mutation, replacement=mutation.anchor), source, "no source change"),
            (
                replace(mutation, replacement=mutation.replacement + "\n            AND_OP: result = 0;"),
                source,
                "more than one RTL line",
            ),
            (
                replace(
                    mutation,
                    anchor="module alu_8bit (",
                    replacement="module alu_bad (",
                ),
                source,
                "declare the alu_8bit module",
            ),
            (
                replace(
                    mutation,
                    anchor="    input  logic [7:0] a, b,",
                    replacement="    input  logic [6:0] a, b,",
                ),
                source,
                "module interface",
            ),
        )
        for altered, candidate, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(ValueError, message):
                    generate_mutant(candidate, altered)

    def test_stale_mutant_directory_is_never_reused(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary) / "old-mutant"
            folder.mkdir()
            stale_source = folder / "alu_8bit.sv"
            stale_source.write_text("stale mutant", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                evaluate_mutant("yosys", RTL.read_text(encoding="utf-8"), MUTATIONS[0], folder)
            self.assertEqual(stale_source.read_text(encoding="utf-8"), "stale mutant")

    def test_all_seeded_fault_models_compile_and_replay_as_intended(self):
        examples = {
            "ADD_DROP_CARRY": (255, 1, 0, 256, 0),
            "SUB_TRUNCATE_TO_8": (0, 1, 1, 65535, 255),
            "MUL_TRUNCATE_TO_8": (16, 16, 2, 256, 0),
            "DIV_ZERO_GUARD_ERROR": (7, 0, 3, 0, 65535),
            "DIV_ROUND_UP": (5, 2, 3, 2, 3),
            "AND_SIGN_EXTENSION": (128, 128, 4, 128, 65408),
            "SHL_USE_FULL_B": (1, 8, 7, 1, 256),
        }
        source = RTL.read_text(encoding="utf-8")
        self.assertEqual(set(examples), {mutation.identifier for mutation in MUTATIONS})

        with tempfile.TemporaryDirectory() as temporary:
            temp_root = Path(temporary)
            for mutation in MUTATIONS:
                a, b, opcode, expected, faulty = examples[mutation.identifier]
                with self.subTest(mutant=mutation.identifier):
                    self.assertEqual(reference(a, b, opcode), expected)
                    mutant_rtl = temp_root / mutation.identifier / "alu_8bit.sv"
                    mutant_rtl.parent.mkdir()
                    mutant_rtl.write_text(generate_mutant(source, mutation), encoding="utf-8")
                    row = (mutation.identifier, a, b, opcode, expected)
                    report, actuals = simulate(
                        [row],
                        temp_root / mutation.identifier / "replay",
                        seed=2026,
                        rtl=mutant_rtl,
                        timeout=15,
                    )
                    self.assertEqual(report["status"], "FAIL")
                    self.assertEqual(report["checked"], 1)
                    self.assertEqual(report["failed"], 1)
                    self.assertEqual(actuals, [faulty])

    def test_vcd_counterexample_parser_reads_full_width_outputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "counterexample.vcd"
            path.write_text(make_vcd(), encoding="utf-8")
            model = parse_counterexample_vcd(path)
        self.assertEqual(model, {
            "a": 255,
            "b": 1,
            "opcode": 0,
            "dut_result": 0,
            "spec_result": 256,
        })

    def test_vcd_preserves_msb_and_full_output_bit_order(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "counterexample.vcd"
            path.write_text(
                make_vcd(a=129, b=3, dut_result=0x8001, spec_result=0x8123),
                encoding="utf-8",
            )
            model = parse_counterexample_vcd(path)
        self.assertEqual(model["a"], 129)
        self.assertEqual(model["b"], 3)
        self.assertEqual(model["dut_result"], 0x8001)
        self.assertEqual(model["spec_result"], 0x8123)

    def test_vcd_counterexample_parser_rejects_unknown_signals(self):
        vcd = make_vcd(body="bxxxxxxxx v0")
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "counterexample.vcd"
            path.write_text(vcd, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "fully known binary"):
                parse_counterexample_vcd(path)

    def test_vcd_parser_rejects_missing_ambiguous_malformed_and_wrong_width_evidence(self):
        declarations = [
            "$var wire 8 v0 \\a $end",
            "$var wire 8 v1 \\b $end",
            "$var wire 16 v2 \\dut_result $end",
            "$var wire 3 v3 \\opcode $end",
            "$var wire 16 v4 \\spec_result $end",
        ]
        cases = (
            ([item for item in declarations if "\\a " not in item], make_vcd(), "no unique signal named a"),
            ([item for item in declarations if "\\b " not in item], make_vcd(), "no unique signal named b"),
            ([item for item in declarations if "\\opcode " not in item], make_vcd(), "no unique signal named opcode"),
            ([item for item in declarations if "\\dut_result " not in item], make_vcd(), "no unique signal named dut_result"),
            ([item for item in declarations if "\\spec_result " not in item], make_vcd(), "no unique signal named spec_result"),
            (declarations + ["$var wire 8 v5 \\a $end"], make_vcd(), "no unique signal named a"),
            (
                [item.replace("wire 8 v0", "wire 7 v0") for item in declarations],
                make_vcd(),
                "width 7, expected 8",
            ),
            (declarations, make_vcd(body="b1 v0"), "width 1, expected 8"),
            (declarations, make_vcd(body="b100000000 v0"), "exceeds declared width"),
            (declarations, make_vcd(a=256), "exceeds declared width"),
            (declarations, make_vcd(opcode=8), "exceeds declared width"),
            (
                declarations,
                make_vcd(body="b0000000000000000 v2\nb000 v3\nb00000001 v4\nb11111111 v0\nb00000001 v1"),
                "width 8, expected 16",
            ),
            (
                declarations,
                make_vcd(body="b10000000000000000 v2\nb000 v3\nb0000000100000000 v4\nb11111111 v0\nb00000001 v1"),
                "exceeds declared width",
            ),
            (
                declarations,
                make_vcd(body="b0000000000000000 v2\nb000 v3\nb0000000100000000 v4\nb11111111 v0"),
                "VCD signal b has no value",
            ),
            (declarations, make_vcd(body="b10q v0"), "(?i)malformed binary value"),
            (declarations, make_vcd(header_end=False), "(?i)incomplete VCD header"),
            (declarations, make_vcd(dut_result=256, spec_result=256), "does not distinguish"),
        )
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "counterexample.vcd"
            for case_declarations, vcd, message in cases:
                with self.subTest(message=message):
                    # Preserve the signal declarations being tested while using the supplied body.
                    if case_declarations != declarations:
                        body = vcd.split("$dumpvars\n", 1)[-1]
                        vcd = make_vcd(declarations=case_declarations, body=body.split("#-1\n", 1)[-1].rsplit("\n#0", 1)[0])
                    path.write_text(vcd, encoding="utf-8")
                    with self.assertRaisesRegex(ValueError, message):
                        parse_counterexample_vcd(path)

    def test_counterexample_summary_mismatch_is_rejected(self):
        model = {
            "a": 255,
            "b": 1,
            "opcode": 0,
            "dut_result": 0,
            "spec_result": 256,
        }
        summary = {
            "counterexample": {
                "a": 255,
                "b": 1,
                "opcode": 0,
                "mutant_output": 1,
                "specification_output": 256,
            }
        }
        with self.assertRaisesRegex(ValueError, "does not match"):
            counterexample_matches_summary(model, summary)

    def test_inconsistent_python_or_formal_spec_validator_cannot_kill_mutant(self):
        cases = (
            (make_vcd(), 300, "FAIL"),
            (make_vcd(spec_result=255), None, "FAIL"),
        )
        for vcd, reference_value, classification in cases:
            with self.subTest(reference_value=reference_value, vcd=vcd[:40]):
                result = self.run_with_fake_sat(vcd, reference_value=reference_value)
                self.assertEqual(result["classification"], classification)
                self.assertEqual(result["simulation_replay"], "NOT_RUN")

    def test_inconsistent_or_missing_icarus_evidence_cannot_kill_mutant(self):
        for replay, expected_status in (
            ("disagree", "FAIL"),
            ("missing", "TOOL_ERROR"),
            ("malformed", "TOOL_ERROR"),
            ("wrong_order", "FAIL"),
            ("ordering_error", "TOOL_ERROR"),
        ):
            with self.subTest(replay=replay):
                result = self.run_with_fake_sat(make_vcd(), replay=replay)
                self.assertEqual(result["classification"], expected_status)
                self.assertNotEqual(result["classification"], "KILLED")

    def test_successful_kill_requires_python_and_icarus_agreement(self):
        result = self.run_with_fake_sat(make_vcd())
        self.assertEqual(result["classification"], "KILLED")
        self.assertEqual(result["python_validation"], "PASS")
        self.assertEqual(result["simulation_replay"], "PASS")

    def test_sat_without_a_fresh_valid_counterexample_is_not_killed(self):
        cases = (
            (None, "SAT solving finished - model found: FAIL!", "counterexample VCD"),
            (make_vcd(header_end=False), "SAT solving finished - model found: FAIL!", "TOOL_ERROR"),
            (make_vcd(), "malformed solver output", "TOOL_ERROR"),
        )
        for vcd, solver_log, message in cases:
            with self.subTest(message=message):
                result = self.run_with_fake_sat(vcd, sat_log=solver_log)
                self.assertEqual(result["classification"], "TOOL_ERROR")
                if message == "counterexample VCD":
                    self.assertIn("no counterexample VCD", result["validation_error"])

    def test_solver_status_requires_successful_process_exit(self):
        self.assertEqual(read_sat_status("SAT solving finished - model found: FAIL!", 0), "SAT")
        self.assertEqual(read_sat_status("SAT solving finished - model found: FAIL!", 1), "TOOL_ERROR")
        self.assertEqual(read_sat_status("SAT solving finished - timeout", 1), "TIMEOUT")
        self.assertEqual(read_sat_status("", None), "TIMEOUT")
        self.assertEqual(
            read_sat_status("$ yosys -timeout 60\nread error", 1),
            "TOOL_ERROR",
        )
        self.assertEqual(read_sat_status("SAT solving finished - timeout", 0), "TIMEOUT")
        self.assertEqual(read_sat_status("malformed solver output", 0), "TOOL_ERROR")
        self.assertEqual(read_sat_status("SAT solving finished - unknown", 0), "UNKNOWN")
        self.assertEqual(read_sat_status("SAT proof finished - model found: FAIL!", 0), "SAT")
        self.assertEqual(
            read_sat_status("SAT proof finished - no model found: SUCCESS!", 0),
            "UNSAT",
        )
        self.assertEqual(read_sat_status("SAT proof finished - timeout", 0), "TIMEOUT")
        self.assertEqual(read_sat_status("SAT proof finished - unknown", 0), "UNKNOWN")
        self.assertEqual(
            read_sat_status(
                "SAT solving finished - model found: FAIL!\n"
                "SAT solving finished - no model found: SUCCESS!",
                0,
            ),
            "TOOL_ERROR",
        )

    def test_missing_solver_timeout_and_stale_solver_log_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            missing_log = root / "missing.log"
            code, _ = run_yosys("missing-yosys-command", "sat", missing_log, 1)
            self.assertEqual(read_sat_status(missing_log.read_text(), code), "TOOL_ERROR")

            timeout_log = root / "timeout.log"
            timeout_log.write_text("SAT solving finished - no model found: SUCCESS!\n")
            with patch(
                "formal.mutation_audit.subprocess.run",
                side_effect=subprocess.TimeoutExpired(["yosys"], 1, output="partial"),
            ):
                code, text = run_yosys("yosys", "sat", timeout_log, 1)
            self.assertIsNone(code)
            self.assertEqual(read_sat_status(text, code), "TIMEOUT")
            self.assertIn("TIMEOUT after", timeout_log.read_text())

            stale_log = root / "stale.log"
            stale_log.write_text("SAT solving finished - no model found: SUCCESS!\n")
            with patch(
                "formal.mutation_audit.subprocess.run",
                return_value=subprocess.CompletedProcess(["yosys"], 0, "malformed output"),
            ):
                code, text = run_yosys("yosys", "sat", stale_log, 1)
            self.assertEqual(read_sat_status(text, code), "TOOL_ERROR")
            self.assertEqual(stale_log.read_text(), "$ yosys -Q -p sat\nmalformed output")

            interrupted_log = root / "interrupted.log"
            interrupted_log.write_text("SAT solving finished - no model found: SUCCESS!\n")
            with patch(
                "formal.mutation_audit.subprocess.run",
                side_effect=KeyboardInterrupt,
            ):
                with self.assertRaises(KeyboardInterrupt):
                    run_yosys("yosys", "sat", interrupted_log, 1)
            self.assertEqual(interrupted_log.read_text(), "$ yosys -Q -p sat\nINTERRUPTED by user\n")

    def test_compile_does_not_accept_a_stale_netlist(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            netlist = folder / "compiled.json"
            netlist.write_text(json.dumps({"modules": {"alu_formal_miter": {}}}))
            with patch("formal.mutation_audit.run_yosys", return_value=(0, "")):
                self.assertEqual(run_compile("yosys", RTL, folder), ("TOOL_ERROR", 0))
            self.assertFalse(netlist.exists())

    def test_report_does_not_publish_pass_if_csv_write_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            summary_path = root / "summary.json"
            csv_path = root / "mutants.csv"
            running = {"status": "RUNNING", "mutants": []}
            save_report(summary_path, csv_path, running)
            candidate = {"status": "PASS", "mutants": []}
            with patch("formal.mutation_audit.write_csv", side_effect=OSError("disk full")):
                with self.assertRaisesRegex(OSError, "disk full"):
                    save_report(summary_path, csv_path, candidate)
            self.assertEqual(json.loads(summary_path.read_text())["status"], "RUNNING")

    def test_baseline_failure_stops_mutant_campaign(self):
        with tempfile.TemporaryDirectory() as temporary:
            output_root = Path(temporary)
            with (
                patch("formal.mutation_audit.capture_version", return_value="test"),
                patch("formal.mutation_audit.run_compile", return_value=("TOOL_ERROR", 1)),
                patch("formal.mutation_audit.evaluate_mutant") as evaluate,
            ):
                result = campaign("yosys", output_root, 1)
            report_path = next(output_root.glob("*/summary.json"))
            report = json.loads(report_path.read_text())
            self.assertEqual(result, 1)
            self.assertEqual(report["status"], "TOOL_ERROR")
            self.assertEqual(report["baseline"]["status"], "TOOL_ERROR")
            self.assertEqual(len(report["mutants"]), len(MUTATIONS))
            self.assertTrue(all(item["classification"] == "NOT_RUN" for item in report["mutants"]))
            evaluate.assert_not_called()

    def test_baseline_proof_failure_is_fail_not_killed(self):
        with tempfile.TemporaryDirectory() as temporary:
            output_root = Path(temporary)
            with (
                patch("formal.mutation_audit.capture_version", return_value="test"),
                patch("formal.mutation_audit.run_compile", return_value=("PASS", 0)),
                patch(
                    "formal.mutation_audit.run_yosys",
                    return_value=(0, "SAT solving finished - model found: FAIL!"),
                ),
                patch("formal.mutation_audit.evaluate_mutant") as evaluate,
            ):
                result = campaign("yosys", output_root, 1)
            report = json.loads(next(output_root.glob("*/summary.json")).read_text())
            self.assertEqual(result, 1)
            self.assertEqual(report["status"], "FAIL")
            self.assertEqual(report["baseline"]["status"], "SAT")
            self.assertTrue(all(item["classification"] == "NOT_RUN" for item in report["mutants"]))
            evaluate.assert_not_called()

    def test_source_drift_stops_campaign_before_tools_or_mutants(self):
        with tempfile.TemporaryDirectory() as temporary:
            output_root = Path(temporary)
            with (
                patch(
                    "formal.mutation_audit.source_fingerprints",
                    return_value={"production_rtl": "changed"},
                ),
                patch("formal.mutation_audit.capture_version") as capture,
                patch("formal.mutation_audit.evaluate_mutant") as evaluate,
            ):
                result = campaign("yosys", output_root, 1)
            report = json.loads(next(output_root.glob("*/summary.json")).read_text())
            self.assertEqual(result, 1)
            self.assertEqual(report["status"], "TOOL_ERROR")
            self.assertEqual(report["stage"], "source_preflight")
            self.assertTrue(all(item["classification"] == "NOT_RUN" for item in report["mutants"]))
            capture.assert_not_called()
            evaluate.assert_not_called()

    def test_missing_yosys_writes_not_run_summary_and_csv(self):
        with tempfile.TemporaryDirectory() as temporary:
            output_root = Path(temporary)
            with (
                patch("formal.mutation_audit.shutil.which", return_value=None),
                patch.object(sys, "argv", ["mutation_audit.py", "--output-root", str(output_root)]),
            ):
                result = mutation_main()
            summary_path = next(output_root.glob("*/summary.json"))
            report = json.loads(summary_path.read_text())
            self.assertEqual(result, 2)
            self.assertEqual(report["status"], "NOT_RUN")
            self.assertEqual(report["exit_code"], 2)
            self.assertEqual(len(report["mutants"]), len(MUTATIONS))
            self.assertTrue((summary_path.parent / "mutants.csv").is_file())

    def test_missing_evidence_log_prevents_campaign_validation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "baseline").mkdir()
            report = {
                "source_sha256": SOURCE_FINGERPRINTS,
                "git_commit": subprocess.run(
                    ["git", "rev-parse", "HEAD"],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    check=True,
                ).stdout.strip(),
                "baseline": {"status": "PROVED"},
                "tool_version_logs": {},
                "mutants": [],
            }
            with self.assertRaisesRegex(ValueError, "Missing baseline evidence"):
                validate_campaign_evidence(report, root)

            baseline = root / "baseline"
            (baseline / "compiled.json").write_text("{}", encoding="utf-8")
            (baseline / "compile.log").write_text("compiled\n", encoding="utf-8")
            (baseline / "solver.log").write_text(
                "SAT solving finished - no model found: SUCCESS!\n",
                encoding="utf-8",
            )
            (root / "version.log").write_text("tool version\n", encoding="utf-8")
            report["baseline"]["solver_exit_code"] = 0
            report["tool_version_logs"] = {"test_tool": str(root / "version.log")}
            with self.assertRaisesRegex(FileNotFoundError, "mutants.csv"):
                validate_campaign_evidence(report, root)

    def test_campaign_classification_preserves_unresolved_states(self):
        from formal.mutation_audit import campaign_status

        base = {"baseline": {"status": "PROVED"}, "mutants": []}
        for expected in ("TIMEOUT", "UNKNOWN", "TOOL_ERROR", "NOT_RUN"):
            report = {
                **base,
                "mutants": [{"classification": expected}],
            }
            self.assertEqual(campaign_status(report), expected)
        self.assertEqual(
            campaign_status(
                {
                    "baseline": {"status": "NOT_RUN"},
                    "mutants": [{"classification": "NOT_RUN"}],
                }
            ),
            "NOT_RUN",
        )
        self.assertEqual(
            campaign_status(
                {
                    "baseline": {"status": "NOT_RUN"},
                    "mutants": [{"classification": "FAIL"}],
                }
            ),
            "FAIL",
        )
        self.assertEqual(
            campaign_status({**base, "mutants": [{"classification": "FAIL"}]}),
            "FAIL",
        )

    def test_repeat_comparison_requires_semantic_not_exact_counterexample_equality(self):
        examples = {
            "ADD_DROP_CARRY": ((255, 1, 0, 256, 0), (255, 2, 0, 257, 1)),
            "SUB_TRUNCATE_TO_8": ((0, 1, 1, 65535, 255), (1, 2, 1, 65535, 255)),
            "MUL_TRUNCATE_TO_8": ((16, 16, 2, 256, 0), (20, 20, 2, 400, 144)),
            "DIV_ZERO_GUARD_ERROR": ((7, 0, 3, 0, 65535), (5, 0, 3, 0, 65535)),
            "DIV_ROUND_UP": ((5, 2, 3, 2, 3), (10, 3, 3, 3, 4)),
            "AND_SIGN_EXTENSION": ((128, 128, 4, 128, 65408), (129, 129, 4, 129, 65409)),
            "SHL_USE_FULL_B": ((1, 8, 7, 1, 256), (2, 9, 7, 4, 1024)),
        }

        def result(index):
            mutants = []
            for mutation in MUTATIONS:
                a, b, opcode, expected, faulty = examples[mutation.identifier][index]
                mutants.append({
                    "mutant_id": mutation.identifier,
                    "source_sha256": f"mutant-{mutation.identifier}",
                    "classification": "KILLED",
                    "python_validation": "PASS",
                    "simulation_replay": "PASS",
                    "counterexample": {
                        "a": a,
                        "b": b,
                        "opcode": opcode,
                        "expected_output": expected,
                        "specification_output": expected,
                        "mutant_output": faulty,
                    },
                })
            return {
                "git_commit": "commit",
                "source_sha256": SOURCE_FINGERPRINTS,
                "tool_versions": {"yosys": "same", "iverilog": "same"},
                "baseline": {"status": "PROVED"},
                "mutants": mutants,
            }

        report = compare_campaigns(result(0), result(1))
        self.assertEqual(report["status"], "PASS")
        self.assertTrue(report["semantic_reproducibility"])
        self.assertFalse(report["exact_counterexample_reproducibility"])

    def test_replay_tool_versions_are_captured(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            compiler_version = capture_version("iverilog", root / "iverilog.log")
            runtime_version = capture_version("vvp", root / "vvp.log")
        self.assertIn("Icarus Verilog", compiler_version)
        self.assertIn("Icarus Verilog", runtime_version)

    def test_version_timeout_is_not_reported_as_tool_error_or_pass(self):
        with tempfile.TemporaryDirectory() as temporary:
            log = Path(temporary) / "version.log"
            with patch(
                "formal.mutation_audit.subprocess.run",
                side_effect=subprocess.TimeoutExpired(["yosys", "-V"], 1),
            ):
                with self.assertRaises(TimeoutError):
                    capture_version("yosys", log)
            self.assertIn("timed out", log.read_text().lower())


if __name__ == "__main__":
    unittest.main()
