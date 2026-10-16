"""Named literal, boundary, random, and DUT metamorphic transaction plans."""
import csv
import random
from pathlib import Path
from .model import reference


def known_answers():
    with Path(__file__).with_name('known_answers.csv').open() as f:
        return [(r['name'], int(r['a']), int(r['b']), int(r['opcode']),
                 int(r['expected'])) for r in csv.DictReader(f)]


def vector(name, a, b, op):
    return name, a, b, op, reference(a, b, op)


def directed():
    rows = known_answers()
    for op in range(8):
        for a, b in ((0, 0), (255, 255), (0, 255), (255, 0),
                     (1, 1), (170, 85), (85, 170)):
            rows.append(vector('boundary', a, b, op))
    for _ in range(4):
        rows.append(vector('repeated_identical', 255, 255, 2))
    for _ in range(3):
        for op in range(8):
            rows.append(vector('rapid_opcode_extremes', 255 if op % 2 else 0,
                               0 if op % 2 else 255, op))
    return rows


def closure():
    # Category combinations and relations, selected after inspecting initial bins.
    rows = []
    for op in range(8):
        for a in (0, 1, 2, 127, 255):
            for b in (0, 1, 2, 127, 255):
                rows.append(vector('coverage_operand_closure', a, b, op))
    for amount in range(8):
        for upper in (0, 248):
            rows.append(vector('coverage_shift_closure', 255, amount + upper, 7))
    rows.append(vector('coverage_exact_division', 254, 2, 3))
    return rows


def randomized(count, seed):
    if count < 8:
        raise ValueError('Random count must be >= 8 to exercise every opcode')
    rng = random.Random(seed)
    boundary = (0, 1, 2, 127, 128, 254, 255)
    rows = []
    for i in range(count):
        op = i % 8  # Exactly balanced +/- one transaction, not random op selection.
        a = rng.choice(boundary) if rng.random() < .35 else rng.randrange(256)
        b = rng.choice(boundary) if rng.random() < .35 else rng.randrange(256)
        rows.append(vector('biased_random', a, b, op))
    return rows


def properties():
    rows, checks = [], []

    def add(a, b, op):
        rows.append(vector('metamorphic', a, b, op))
        return len(rows) - 1

    for a, b in ((0, 255), (1, 254), (127, 128), (170, 85), (255, 255)):
        for op in (0, 2, 4, 5, 6):
            checks.append(('equal', add(a, b, op), add(b, a, op)))
        for op, rhs, expected in ((6, a, 0), (4, 0, 0), (5, 0, a),
                                   (2, 0, 0), (3, 1, a), (7, 248, a)):
            checks.append(('constant', add(a, rhs, op), expected))
        # Three DUT evaluations establish (a XOR b) XOR b = a without using
        # the reference model to choose the intermediate operand.
        checks.append(('xor_inverse', add(a, b, 6), (a, b)))
    return rows, checks


def exhaustive():
    for op in range(8):
        for a in range(256):
            for b in range(256):
                yield vector('exhaustive', a, b, op)
