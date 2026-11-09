#!/usr/bin/env python3
"""fc4-nx: finds Far Cry 4's Direct3D render / sampler state tables without a reference image: runs of 12-byte records
{getter, setter, default} whose getter and setter are .pdata function starts in .text (katamari-nx found N&B's and
Katamari's this way, by defaults at stride 12). Prints every run of >= 15 records with its records.

  python -P tools/fc4_d3d/state_tables.py [--min 15] [--dump]
"""
import bisect, os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fc4lib as L

def main():
    mn = 15
    if '--min' in sys.argv:
        mn = int(sys.argv[sys.argv.index('--min') + 1])
    g = L.load()
    starts = set(g.fstart)
    d = g.data
    def ok(v):
        return v in starts
    runs = []
    for lo, hi in ((0x82000600, 0x822F3D2C), (0x840F6000, 0x842F0FD8)):
        for phase in range(0, 12, 4):
            off = lo - L.BASE + phase
            n, first = 0, None
            while off + 12 <= hi - L.BASE:
                gt, st, df = struct.unpack_from('>III', d, off)
                if ok(gt) and ok(st):
                    if first is None:
                        first = off
                    n += 1
                else:
                    if n >= mn:
                        runs.append((first + L.BASE, n))
                    n, first = 0, None
                off += 12
    runs = sorted(set(runs))
    for a, n in runs:
        print(f'run {a:08X} {n} records')
        if '--dump' in sys.argv:
            for i in range(n):
                gt, st, df = struct.unpack_from('>III', d, a - L.BASE + 12 * i)
                print(f'  {i:3d} get {gt:08X} set {st:08X} default {df:08X}')
if __name__ == "__main__":
    main()
