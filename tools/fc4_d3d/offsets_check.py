#!/usr/bin/env python3
"""fc4-nx: checks sa2-nx's Direct3D device offsets (the 0x6080 layout, XDK 2.0.21076) against Far Cry 4's code.

For every device-private literal (10944 .. 24703, or 0x2AC0 .. 0x607F) in sa2-nx's renderer sources
(app/src/renut_engine/gpu/**: d3d.h, d3d_native.h, hooks, render, ...), it looks for the same displacement in FC4's
Direct3D (0x83F18000-0x83F42000: D-form loads / stores on a non-stack base and addi immediates). When the line also
names an SA2 function that tools/fc4_d3d/fc4_hook_map_hand.txt pairs with an FC4 one, the offset must appear in that
FC4 function too. The public part below 10944 is N&B's in every 2.0.2xxxx layout (sa2-nx's d3d.h) and is not listed.

  python -P tools/fc4_d3d/offsets_check.py   -> out/fc4_d3d/offsets_check.txt
"""
import collections, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fc4lib as L
from summary import starts

SA2 = os.path.join(L.ROOT, '..', 'refs', 'sa2-nx', 'app', 'src', 'renut_engine', 'gpu')
NUM = re.compile(r'(?<![0-9A-Za-z_.])(0x[0-9A-Fa-f]+|\d+)(?:u|U)?(?![0-9A-Za-z_.])')
SUB = re.compile(r'(?:sub_|0x)(825[0-9A-F]{5})\b')
SKIP = re.compile(r'kRingDataSize|kRingSinkSize|chrono|milliseconds|<<|sizeof|static_assert\(sizeof|0x[0-9A-F]{8}')
BRACKET = re.compile(r'\[(?:0x[0-9A-Fa-f]+|\d+)(?:, (?:0x[0-9A-Fa-f]+|\d+))*\]')  # N&B's value in brackets: a line sa2-nx moved to SA2's layout


def main():
    g = L.load()
    hand = {}
    for ln in open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fc4_hook_map_hand.txt'), encoding='utf-8'):
        if ln.strip() and not ln.startswith('#'):
            p = ln.split(None, 4)
            if p[1] != '-' and p[2] != '-':
                hand[p[2].rstrip('?').upper()] = (int(p[1], 16), p[0])
    names = {}
    for ln in open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fc4_hook_map_hand.txt'), encoding='utf-8'):
        if ln.strip() and not ln.startswith('#'):
            p = ln.split(None, 4)
            if p[1] != '-':
                names[int(p[1], 16)] = p[0]
    use = collections.defaultdict(set)
    fn_use = collections.defaultdict(set)
    for s, e in starts(g, 0x83F18000, 0x83F42000):
        for a, op, d, ra in L.disps(g, s, e):
            if ra != 1 and 10944 <= d < 0x6080:
                use[d].add(s)
                fn_use[s].add(d)
        for a, op, d, ra in L.addis(g, s, e):
            if op == 'addi' and ra != 1 and 10944 <= d < 0x6080:
                use[d].add(s)
                fn_use[s].add(d)
    found = collections.OrderedDict()
    for d, _, fs in os.walk(SA2):
        for f in sorted(fs):
            if not f.endswith(('.h', '.cpp', '.inc')):
                continue
            path = os.path.join(d, f)
            for i, ln in enumerate(open(path, encoding='utf-8', errors='replace'), 1):
                code = ln.split('//')[0]
                rel0 = os.path.relpath(path, SA2).replace(os.sep, '/')
                # SA2's layout only: d3d.h / d3d_native.h, or a line sa2-nx marked; d3d_native_state.cpp and hooks/state.cpp
                # (N&B's native state code) are not built on SA2 and keep N&B's values
                if rel0 in ('d3d/d3d_native_state.cpp', 'd3d/hooks/state.cpp'):
                    continue
                if rel0 not in ('d3d/d3d.h', 'd3d/d3d_native.h') and 'sa2' not in ln.lower() and not BRACKET.search(ln):
                    continue
                if SKIP.search(code):
                    continue
                for m in NUM.finditer(code):
                    t = m.group(1)
                    v = int(t, 16) if t.lower().startswith("0x") else int(t, 10)
                    if not 10944 <= v < 0x6080:
                        continue
                    if m.group(1).isdigit() and v % 4 and v not in (11069, 11070, 11071):
                        pass
                    subs = SUB.findall(ln)
                    rel = os.path.relpath(path, SA2).replace('\\', '/')
                    found.setdefault(v, []).append((f'{rel}:{i}', subs, ln.strip()[:110]))
    out = []
    missing, pair_bad = [], []
    for v in sorted(found):
        fc = sorted(use.get(v, ()))
        where = found[v]
        chk = []
        for loc, subs, txt in where:
            for s in subs:
                if s in hand:
                    fa, nm = hand[s]
                    ok = v in fn_use.get(fa, ())
                    chk.append(f'{nm}@{fa:08X}:{"yes" if ok else "NO"}')
                    if not ok:
                        pair_bad.append((v, loc, nm, fa))
        if not fc:
            missing.append((v, where[0][0]))
        fnames = ', '.join(names.get(a, f'sub_{a:08X}') for a in fc[:6]) + (' ...' if len(fc) > 6 else '')
        out.append(f'{v:6d} 0x{v:04X}  FC4 uses: {len(fc):3d} fn  [{fnames}]  pairs: {" ".join(chk) or "-"}  sa2: {where[0][0]} ({len(where)} sites)  | {where[0][2]}')
    path = os.path.join(L.OUT, 'offsets_check.txt')
    with open(path, 'w', encoding='utf-8') as f:
        f.write('# fc4-nx: sa2-nx device offsets (>= 10944) against FC4\'s Direct3D code. tools/fc4_d3d/offsets_check.py.\n'
                '# "FC4 uses" = FC4 Direct3D functions with that displacement / addi immediate; "pairs" = the offset in the FC4\n'
                '# function paired with an SA2 function named on the same source line (yes / NO).\n')
        f.write('\n'.join(out) + '\n')
        f.write(f'\n# {len(found)} offsets; {len(found) - len(missing)} used by FC4\'s Direct3D at the same value; '
                f'{len(missing)} not seen: {", ".join(f"{v}({w})" for v, w in missing)}\n')
        f.write(f'# paired-function checks failing: {len(pair_bad)}: ' + '; '.join(f'{v} {loc} {nm}@{fa:08X}' for v, loc, nm, fa in pair_bad) + '\n')
    print(path, len(found), 'offsets;', len(found) - len(missing), 'seen;', len(missing), 'not seen;', len(pair_bad), 'pair failures')


if __name__ == '__main__':
    main()
