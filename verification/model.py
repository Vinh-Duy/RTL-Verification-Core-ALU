"""Unsigned integer specification oracle; no simulator or DUT dependency."""
OPS = ('ADD', 'SUB', 'MUL', 'DIV', 'AND', 'OR', 'XOR', 'SHL')


def reference(a: int, b: int, opcode: int) -> int:
    if not (0 <= a <= 255 and 0 <= b <= 255 and 0 <= opcode < 8):
        raise ValueError('Operands/opcode must be known unsigned values in range')
    if opcode == 0:
        return a + b
    if opcode == 1:
        return (a - b) % 65536
    if opcode == 2:
        return a * b
    if opcode == 3:
        return 0 if b == 0 else a // b
    if opcode == 4:
        return a & b
    if opcode == 5:
        return a | b
    if opcode == 6:
        return a ^ b
    return a * (2 ** (b % 8))
