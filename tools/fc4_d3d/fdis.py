#!/usr/bin/env python3
"""fc4-nx: prints whole functions of FC4's image (bounds from .pdata) with callers and named calls.
  python -P tools/fc4_d3d/fdis.py 0x83F18AB0 [0x...] [--brief] [--nocallers]
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fc4lib as L

def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    brief = '--brief' in sys.argv
    g = L.load()
    for a in args:
        s = int(a, 16)
        f = L.func_of(g, s)
        st, en = f if f else (s, L.func_end(g, s))
        print(f'==== {L.name(g, st)} {st:08X}-{en:08X} ({(en - st) // 4} ins)')
        if '--nocallers' not in sys.argv:
            cs = L.callers(g, st)
            print('callers:', ' '.join(f'{x[0]:08X}{"" if x[1] == "bl" else "(b)"}<{L.name(g, x[2]) if x[2] else "?"}>' for x in cs[:40]), f'({len(cs)})')
        if brief:
            print('calls:', ' '.join(L.name(g, t) for t in L.calls(g, st, en)))
            print('tails:', ' '.join(L.name(g, t) for t in L.tails(g, st, en)))
            print('disps>=10000:', sorted({d for _, _, d, r in L.disps(g, st, en) if d >= 10000}))
        else:
            L.dis(g, st, en)
if __name__ == "__main__":
    main()
