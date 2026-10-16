"""Custom functional coverage, sampled only after a successful DUT comparison."""
from collections import Counter
from .model import OPS

CATEGORIES = ('zero', 'one', 'max', 'other')
EDGES = ('ADD.carry', 'ADD.no_carry', 'SUB.underflow', 'SUB.no_underflow',
         'MUL.high', 'MUL.low', 'DIV.zero', 'DIV.remainder', 'DIV.exact')


def category(value):
    return {0: 'zero', 1: 'one', 255: 'max'}.get(value, 'other')


def eligible_bins():
    bins = {f'op.{op}' for op in OPS}
    bins |= {f'{operand}.{c}' for operand in ('a', 'b') for c in CATEGORIES}
    bins |= {f'relation.{r}' for r in ('lt', 'eq', 'gt')}
    bins |= {f'{op}.{operand}.{c}' for op in OPS
             for operand in ('a', 'b') for c in CATEGORIES}
    bins |= {f'{op}.relation.{r}' for op in OPS for r in ('lt', 'eq', 'gt')}
    bins |= {f'edge.{e}' for e in EDGES}
    bins |= {f'shift.amount.{s}' for s in range(8)}
    bins |= {f'shift.upper.{u}' for u in ('clear', 'set')}
    bins |= {f'shift.cross.{s}.{u}' for s in range(8) for u in ('clear', 'set')}
    return bins


class Coverage:
    def __init__(self):
        self.hits = Counter({b: 0 for b in sorted(eligible_bins())})
        self.samples = 0

    def sample(self, a, b, opcode):
        op = OPS[opcode]
        ca, cb = category(a), category(b)
        rel = 'lt' if a < b else 'gt' if a > b else 'eq'
        bins = [f'op.{op}', f'a.{ca}', f'b.{cb}', f'relation.{rel}',
                f'{op}.a.{ca}', f'{op}.b.{cb}', f'{op}.relation.{rel}']
        if opcode == 0:
            bins.append('edge.ADD.carry' if a + b > 255 else 'edge.ADD.no_carry')
        elif opcode == 1:
            bins.append('edge.SUB.underflow' if a < b else 'edge.SUB.no_underflow')
        elif opcode == 2:
            bins.append('edge.MUL.high' if a * b > 255 else 'edge.MUL.low')
        elif opcode == 3:
            bins.append('edge.DIV.zero' if b == 0 else
                        'edge.DIV.remainder' if a % b else 'edge.DIV.exact')
        elif opcode == 7:
            s, u = b % 8, 'set' if b >= 8 else 'clear'
            bins += [f'shift.amount.{s}', f'shift.upper.{u}', f'shift.cross.{s}.{u}']
        for name in bins:
            if name not in self.hits:
                raise ValueError(f'Unplanned coverage bin {name}')
            self.hits[name] += 1
        self.samples += 1

    def report(self):
        uncovered = [b for b, hits in self.hits.items() if not hits]
        hit = len(self.hits) - len(uncovered)
        return {'metric': 'custom functional coverage', 'samples': self.samples,
                'eligible': len(self.hits), 'hit': hit,
                'percent': 100 * hit / len(self.hits), 'uncovered': uncovered,
                'bins': dict(self.hits)}
