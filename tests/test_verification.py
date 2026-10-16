import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from verification.model import reference
from verification.coverage import Coverage, eligible_bins
from verification import stimuli

ROOT = Path(__file__).resolve().parents[1]


class OracleTests(unittest.TestCase):
    def test_literal_answers(self):
        for name, a, b, op, expected in stimuli.known_answers():
            with self.subTest(name=name):
                self.assertEqual(reference(a, b, op), expected)

    def test_invalid_inputs(self):
        for args in ((-1, 0, 0), (256, 0, 0), (0, 256, 0), (0, 0, 8)):
            with self.assertRaises(ValueError):
                reference(*args)

    def test_subtraction_round_trip(self):
        for a in range(256):
            for b in (0, 1, 127, 255):
                self.assertEqual((reference(a, b, 1) + b) % 65536, a)

    def test_division_identity(self):
        for a in range(256):
            for b in range(1, 256):
                q = reference(a, b, 3)
                self.assertTrue(q * b <= a < (q + 1) * b)

    def test_random_reproduction_and_distribution(self):
        first = stimuli.randomized(1000, 2026)
        self.assertEqual(first, stimuli.randomized(1000, 2026))
        self.assertNotEqual(first, stimuli.randomized(1000, 2027))
        self.assertEqual({r[3] for r in first}, set(range(8)))
        self.assertTrue(any(b == 0 and op == 3 for _, _, b, op, _ in first))
        with self.assertRaises(ValueError):
            stimuli.randomized(7, 0)

    def test_coverage_closure_reachability(self):
        cov = Coverage()
        for _, a, b, op, _ in stimuli.closure():
            cov.sample(a, b, op)
        self.assertEqual(cov.report()['uncovered'], [])
        self.assertEqual(len(eligible_bins()), 142)

    def test_empty_coverage_is_zero(self):
        self.assertEqual(Coverage().report()['percent'], 0)

    def test_exhaustive_plan_unique(self):
        seen = {(a, b, op) for _, a, b, op, _ in stimuli.exhaustive()}
        self.assertEqual(len(seen), 524288)


class FailurePropagationTests(unittest.TestCase):
    def run_cli(self, *args, env=None):
        return subprocess.run([sys.executable, '-m', 'verification.run', *args],
                              cwd=ROOT, env=env, capture_output=True, text=True, timeout=30)

    def test_missing_simulator_nonzero(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc = self.run_cli('--mode', 'directed', '--output', tmp,
                                env={**os.environ, 'PATH': '/nonexistent'})
            self.assertEqual(proc.returncode, 1)
            self.assertIn('Missing iverilog', proc.stderr)

    def test_bad_count_nonzero(self):
        proc = self.run_cli('--mode', 'random', '--count', '0')
        self.assertEqual(proc.returncode, 2)

    def test_faulty_dut_runner_nonzero(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Path(tmp) / 'alu_8bit.sv'
            original = (ROOT / 'rtl/alu_8bit.sv').read_text()
            fixture.write_text(original.replace('result = a_extended ^ b_extended;',
                                                'result = a_extended | b_extended;'))
            self.assertNotEqual(original, fixture.read_text())
            proc = self.run_cli('--mode', 'directed', '--rtl', str(fixture), '--output', tmp)
            self.assertEqual(proc.returncode, 1)
            self.assertIn('MISMATCH', proc.stdout)
            self.assertNotIn('REGRESSION PASS', proc.stdout)

class BridgeIntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.folder = Path(cls.tmp.name)
        cls.exe = cls.folder / 'bridge.vvp'
        subprocess.run(['iverilog', '-g2012', '-s', 'tb_alu_vectors', '-o', str(cls.exe),
                        str(ROOT / 'rtl/alu_8bit.sv'), str(ROOT / 'tb/tb_alu_vectors.sv')],
                       check=True, capture_output=True, timeout=10)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def bridge(self, content, count):
        stimulus = self.folder / 'input.txt'
        stimulus.write_text(content)
        return subprocess.run(['vvp', str(self.exe), f'+VECTORS={stimulus}',
                               f'+OUTPUT={self.folder / "output.csv"}',
                               f'+COUNT={count}', '+SEED=2026'],
                              capture_output=True, text=True, timeout=10)

    def test_missing_transaction_fails(self):
        proc = self.bridge('0 01 01 0 0002\n', 2)
        self.assertNotEqual(proc.returncode, 0)
        self.assertNotIn('Status: PASS', proc.stdout)

    def test_out_of_order_transaction_fails(self):
        proc = self.bridge('1 01 01 0 0002\n', 1)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn('Unexpected transaction id', proc.stdout)

    def test_malformed_stimulus_fails(self):
        proc = self.bridge('0 01 01\n', 1)
        self.assertNotEqual(proc.returncode, 0)

    def test_unknown_expectation_fails(self):
        proc = self.bridge('0 01 01 0 xxxx\n', 1)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn('MISMATCH', proc.stdout)

    def test_unknown_input_cannot_hide_behind_masking(self):
        proc = self.bridge('0 xx 00 4 0000\n', 1)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn('MISMATCH', proc.stdout)


if __name__ == '__main__':
    unittest.main()
