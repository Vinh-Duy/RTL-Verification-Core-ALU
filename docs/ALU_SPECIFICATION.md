# ALU functional specification

## Interface and domain

`alu_8bit` is a clockless combinational module with unsigned 8-bit `a` and `b`,
a 3-bit `opcode`, and an unsigned 16-bit `result`. The core verification domain is
all 256 × 256 × 8 = 524,288 fully known binary input combinations. All eight
binary opcodes are valid; division by zero is a defined input, not illegal traffic.
There is no reset, handshake, registered state, signed interpretation or flag output.

Let A and B be integers in [0,255], and s = B mod 8 = b[2:0].

| Opcode | Operation | Mathematical result | Range |
|---|---|---|---|
| 000 | ADD | A + B | 0…510 |
| 001 | SUB | (A − B) mod 65536 | 0…255 or 65281…65535 |
| 010 | MUL | A × B | 0…65025 |
| 011 | DIV | 0 if B = 0; otherwise floor(A / B) | 0…255 |
| 100 | AND | bitwise A AND B, zero extended | 0…255 |
| 101 | OR | bitwise A OR B, zero extended | 0…255 |
| 110 | XOR | bitwise A XOR B, zero extended | 0…255 |
| 111 | SHL | A × 2^s | 0…32640 |

## Width, overflow, and compatibility

The implementation explicitly zero-extends operands to 16 bits before arithmetic
and logic. Assignment retains 16 bits. ADD's ninth carry bit is retained; it cannot
overflow the 16-bit output. SUB deliberately wraps modulo 65536, so 0−1 is 0xffff
and 0−255 is 0xff01. This is unsigned modular arithmetic, not saturation or an
8-bit wrapped result. Equal inputs subtract to zero. MUL retains the full product
of two 8-bit operands: 255×255 = 65025 (0xfe01). DIV discards the remainder, e.g.
255/2 = 127; 0/B is zero for every B, including zero by the explicit guard.
Bitwise operations have zero upper bytes. SHL shifts a 16-bit zero-extended operand;
it does not truncate to eight bits. B's upper five bits are ignored: B=0 and B=248
both shift by zero, and B=7 and B=255 both shift by seven.

The original expressions were context-sized by their 16-bit assignment target.
No confirmed arithmetic bug was found in those expressions. Explicit widths clarify
intent and preserve known-input behavior. An exhaustive run of the original source
against this specification passed; see the recorded evidence in the verification
report. There is **no intentional functional change** to either DUT.

## Timing and four-state behavior

RTL evaluation has zero modeled hardware delay but occurs through simulator event
scheduling. Testbenches allow 1 ns after a drive before sampling, solely to settle
delta-cycle evaluation; this is not a measured circuit propagation delay or a
performance claim. Physical latency, synthesis timing and timing violations are
outside this RTL experiment. The bridge holds inputs for another 1 ns and checks
that the output remains identical. An OOP driver advances only on a scoreboard
acknowledgment, independently of its settling delay.

X/Z inputs are outside the core mathematical domain. The DUT preserves ordinary
SystemVerilog four-state expression behavior: arithmetic with unknown operands
can yield X; bitwise masking can produce known bits; unknown low shift bits yield
an unknown result. Unknown upper bits of B do not affect SHL. The DIV ternary can
merge branch bits if its condition is unknown; it is not an assertion that every
unknown operand always makes all output bits unknown. An exactly zero divisor
selects zero even for an unknown numerator. A plain `case` with any X/Z opcode
matches none of the binary labels and returns zero through the existing default.
This fallback is a simulation behavior, not a hardware error detector.

Portable known-input tests reject any X/Z output, even if a reference value also
contains unknowns. A separate ten-case four-state bench checks selected masking,
propagation, ignored shift bits, zero-divisor guard, and opcode-fallback behaviors.
It is not exhaustive X/Z verification. The Python oracle accepts only the finite
known-value domain; it does not attempt four-state arithmetic.

## Adder

The original educational adder remains separate: unsigned A+B with a 9-bit sum,
range 0…510. Its explicit 9-bit operand extension preserves the carry.
