#!/usr/bin/env python3
"""fc4-nx: maps SA2's Direct3D function addresses (those sa2-nx's sources name) to FC4's by shifting: SA2 (2.0.21076)
and FC4 (2.0.21256) link the same Direct3D objects with the same function sizes and order inside an object (unused
functions dropped, objects ordered differently). For every shift t = FC4 start - SA2 address seen among the pairs, it
counts how many SA2 addresses land on an FC4 function start (.pdata start, bl target or state-table entry); each SA2
address takes the shift with the most support among the addresses within +-0x1800 of it.

  python -P tools/fc4_d3d/sa2_shift.py [--sa2 ../refs/sa2-nx] > out/fc4_d3d/sa2_shift.txt
Output: SA2 address, FC4 address (or -), support (SA2 neighbours that land on starts with the same shift), shift.
"""
import collections, os, re, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fc4lib as L

def sa2_addrs(root):
    out = set()
    pat = re.compile(r'(?:sub_|0x)(8(?:24[89A-F]|25[0-9A-F])[0-9A-F]{4})\b')
    for d, _, fs in os.walk(os.path.join(root, 'app', 'src')):
        for f in fs:
            if f.endswith(('.cpp', '.h', '.inc')):
                for m in pat.finditer(open(os.path.join(d, f), encoding='utf-8', errors='replace').read()):
                    out.add(int(m.group(1), 16))
    return sorted(a for a in out if 0x82540000 <= a < 0x82580000)

def main():
    sa2root = os.path.join(L.ROOT, '..', 'refs', 'sa2-nx')
    g = L.load()
    L.callers(g, 0)
    starts = set(g.fstart) | {t for t, v in g._callers.items() if any(k == 'bl' for _, k in v)}
    for base, n in ((0x84174F78, 101), (0x84175438, 20)):
        for j in range(n):
            starts.update(struct.unpack_from('>II', g.data, base - L.BASE + 12 * j))
    pd = set(g.fstart)
    # the state setters / getters (leaf functions every few instructions, no .pdata) match any shift: left out
    d3d = sorted(s for s in starts if 0x83F18000 <= s < 0x83F42000 and (s in pd or not 0x83F1F900 <= s < 0x83F21C00))
    sa = sa2_addrs(sa2root)
    # candidate shifts: every (fc4 start - sa2 addr) where both lie in the D3D ranges
    cnt = collections.Counter()
    hits = collections.defaultdict(set)
    for a in sa:
        for s in d3d:
            t = s - a
            hits[t].add(a)
    for a in sa:
        near = [b for b in sa if abs(b - a) <= 0x1800 and b != a]
        best = None
        for t, hs in hits.items():
            if a not in hs:
                continue
            sup = sum(1 for b in near if b in hs)
            if best is None or sup > best[0]:
                best = (sup, t)
        if best and best[0] >= 1:
            alts = sorted(((sum(1 for b in near if b in hs), t) for t, hs in hits.items() if a in hs), reverse=True)[1:3]
            alt = ' '.join(f'{a + t:08X}:{n}' for n, t in alts)
            print(f'{a:08X} {a + best[1]:08X} support={best[0]}/{len(near)} shift={best[1]:#x}  next: {alt}')
        else:
            print(f'{a:08X} - support=0/{len(near)}')
if __name__ == "__main__":
    main()
