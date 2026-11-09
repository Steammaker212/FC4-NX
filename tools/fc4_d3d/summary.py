#!/usr/bin/env python3
"""fc4-nx: one line per .pdata function in a range of FC4's image: size, callers (outside / inside the range), calls,
device-field stores / loads (D-form displacement >= 0x2800 or a small set of public fields), data references.
  python -P tools/fc4_d3d/summary.py [lo hi] > out/fc4_d3d/funcs_summary.txt
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fc4lib as L
from ppc_mini import decode

def starts(g, lo, hi):
    """.pdata functions plus leaf functions without .pdata (bl / b targets and state-table entries not inside a
    .pdata function), each leaf ending at the next start."""
    import struct
    if g._callers is None:
        L.callers(g, lo)
    ss = {a: b for a, b in zip(g.fstart, g.fend) if lo <= a < hi}
    extra = {t for t, v in g._callers.items() if lo <= t < hi and any(k == 'bl' for _, k in v)}
    for base, n in ((0x84174F78, 101), (0x84175438, 20)):
        for j in range(n):
            extra.update(x for x in struct.unpack_from('>II', g.data, base - L.BASE + 12 * j) if lo <= x < hi)
    for t in extra:
        if t not in ss and not L.func_of(g, t):
            ss[t] = None
    keys = sorted(ss)
    for k, a in enumerate(keys):
        e = ss[a]
        if e is None:
            e = keys[k + 1] if k + 1 < len(keys) else a + 0x40
        yield a, e

def main():
    lo, hi = (int(sys.argv[1], 16), int(sys.argv[2], 16)) if len(sys.argv) > 2 else (0x83F00000, 0x83F60000)
    g = L.load()
    for s, e in starts(g, lo, hi):
        cs = L.callers(g, s)
        ext = sum(1 for c in cs if not (lo <= c[0] < hi))
        st, ld = [], []
        for a, op, d, ra in L.disps(g, s, e):
            if ra == 1 or d < 0x28:
                continue
            (st if op.startswith('st') else ld).append(d)
        calls = [L.name(g, t).replace('__imp__', '!') for t in L.calls(g, s, e)]
        tl = [L.name(g, t).replace('__imp__', '!') for t in L.tails(g, s, e)]
        dr = sorted({f'{v:08X}' for _, v in L.data_refs(g, s, e) if 0x82000000 <= v < 0x84400000})
        print(f'{s:08X} n={(e - s) // 4} cal={ext}/{len(cs) - ext} st={sorted(set(st))} ld={sorted(set(ld))} '
              f'calls={",".join(calls)} tail={",".join(tl)} data={",".join(dr)}')
if __name__ == "__main__":
    main()
