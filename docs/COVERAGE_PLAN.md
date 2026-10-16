# Custom functional coverage plan

The mandatory metric is a Python **custom functional coverage** collector, not
simulator code coverage, assertion coverage, native covergroup coverage, or the
transaction pass rate. Its implementation is `verification/coverage.py`.

## Eligible bins

| Dimension | Bins | Definition |
|---|---:|---|
| Opcode | 8 | ADD, SUB, MUL, DIV, AND, OR, XOR, SHL |
| Operand categories | 8 | Each of A/B: zero=0, one=1, max=255, other=2…254 |
| Relationship | 3 | A<B, A=B, A>B |
| Opcode × operand category | 64 | 8 opcodes × 2 separately observed operands × 4 categories |
| Opcode × relationship | 24 | 8 × 3 |
| Operation-specific edges | 9 | ADD carry/no carry; SUB underflow/no underflow; MUL >255/≤255; DIV zero/remainder/exact |
| Shift amount | 8 | B mod 8 = 0…7, only for SHL |
| Shift upper bits | 2 | B[7:3] all zero / any bit set, only for SHL |
| Shift amount × upper bits | 16 | Eight amounts × clear/set, only for SHL |
| **Total** | **142** | Every defined bin is reachable |

DIV.exact requires B>0 and A mod B=0, including numerator zero. DIV.remainder
requires B>0 and A mod B≠0. ADD carry means the sum exceeds 255, not 65535.
SUB underflow means A<B. MUL.high means product>255. Edge bins are conditional
operation-specific crosses; e.g. a DIV-zero bin for AND is neither created nor
counted. Full A-category × B-category × relation crosses are excluded because
some combinations are impossible and this small plan does not need that expansion.
No difficult reachable bin is removed for closure.

## Sampling and computation

Each simulator row has an ID, driven inputs, expected value, actual value,
stable-output indicator and status. Python checks input/ID ordering, parses the
actual value and compares it to the independent expected integer. Only a known,
matching, stable, actually returned transaction increments coverage. Missing,
failed or unknown-output transactions do not sample bins. A failing run may still
contain previously hit bins; coverage alone must never make that run pass.

Hit bins = count of eligible bins with at least one sample.
Coverage percentage = 100 × hit bins / 142. All bins carry equal weight, despite
different bin populations. Reports contain each bin's sample count and an explicit
uncovered list. `coverage_summary.json` and `uncovered_bins.txt` are written per run.
Repeated vectors increment hit counts, not the number of distinct bins.

## Closure experiment

`make coverage SEED=2026 COUNT=1000` executes 116 directed plus 1,000 biased random
transactions before closure, then re-executes those 1,116 vectors with 217 directed
closure vectors appended. The measured initial gaps were shift amounts 3,4,5,6
with the upper bits of B clear. Random B usually has upper bits set; cycling
opcodes alone did not force the rarer low B values.

Closure explicitly exercises each shift amount with B=s and B=248+s. It also
uses the reachable boundary/category grid for every opcode and exact division.
The original plan remains unchanged. The actual before/after values are generated
in RESULTS.md. The unit test verifies that each eligible bin has a concrete
closure-vector witness; actual coverage still comes only from simulation.

## Other metrics and limitations

The optional native covergroup in `tb_alu_coverage.sv` measures opcode, A/B
categories and opcode/category crosses. It is a **different, smaller plan**;
its simulator weighting must not be compared numerically with these 142 bins.
It remains NOT RUN here. No code-coverage or native assertion-coverage result is
claimed. An exhaustive known-input run checks all finite combinations, separately
from achieving every bin in this selected functional plan.
