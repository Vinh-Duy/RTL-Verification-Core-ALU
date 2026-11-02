import tempfile
import unittest
from pathlib import Path

from formal.mutation_audit import (
    MUTATIONS,
    capture_version,
    generate_mutant,
    parse_counterexample_vcd,
    read_sat_status,
)
from verification.model import reference
from verification.run import simulate


ROOT = Path(__file__).resolve().parents[1]
RTL = ROOT / "rtl" / "alu_8bit.sv"


class FormalMutationTests(unittest.TestCase):
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
        vcd = """$date test $end
$scope module alu_formal_miter $end
$var wire 8 a0 a $end
$var wire 8 b0 b $end
$var wire 3 op opcode $end
$var wire 16 dut dut_result $end
$var wire 16 spec spec_result $end
$upscope $end
$enddefinitions $end
#0
b11111111 a0
b00000001 b0
b000 op
b0000000000000000 dut
b0000000100000000 spec
"""
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "counterexample.vcd"
            path.write_text(vcd, encoding="utf-8")
            model = parse_counterexample_vcd(path)
        self.assertEqual(model, {
            "a": 255,
            "b": 1,
            "opcode": 0,
            "dut_result": 0,
            "spec_result": 256,
        })

    def test_vcd_counterexample_parser_rejects_unknown_signals(self):
        vcd = """$scope module alu_formal_miter $end
$var wire 8 a0 a $end
$var wire 8 b0 b $end
$var wire 3 op opcode $end
$var wire 16 dut dut_result $end
$var wire 16 spec spec_result $end
$upscope $end
$enddefinitions $end
#0
bxxxxxxxx a0
b00000001 b0
b000 op
b0000000000000000 dut
b0000000100000000 spec
"""
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "counterexample.vcd"
            path.write_text(vcd, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "fully known binary"):
                parse_counterexample_vcd(path)

    def test_solver_status_requires_successful_process_exit(self):
        self.assertEqual(read_sat_status("model found: FAIL!", 0), "SAT")
        self.assertEqual(read_sat_status("model found: FAIL!", 1), "TOOL_ERROR")
        self.assertEqual(read_sat_status("solver timeout", 1), "TIMEOUT")
        self.assertEqual(read_sat_status("", None), "TIMEOUT")
        self.assertEqual(
            read_sat_status("$ yosys -timeout 60\nread error", 1),
            "TOOL_ERROR",
        )
        self.assertEqual(read_sat_status("SAT solving finished - timeout", 0), "TIMEOUT")

    def test_replay_tool_versions_are_captured(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            compiler_version = capture_version("iverilog", root / "iverilog.log")
            runtime_version = capture_version("vvp", root / "vvp.log")
        self.assertIn("Icarus Verilog", compiler_version)
        self.assertIn("Icarus Verilog", runtime_version)


if __name__ == "__main__":
    unittest.main()
