#!/usr/bin/env python3
"""fc4-nx: lists Renut's Direct3D hooks as the tree has them (katamari-nx's addresses, N&B's in the comments) and
sa2-nx's hook blocks, for the FC4 hook map (docs/fc4-d3d-map.md).

  python -P tools/fc4_d3d/list_hooks.py [--sa2 ../refs/sa2-nx] > out/fc4_d3d/hooks_list.txt
Output: file  kind  katamari_addr  nb_addr  name  [sa2 address if sa2-nx hooks the same name]
"""
import argparse, os, re
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LINE = re.compile(r'^\s*BANJO_RENUT_(UNHOOKED_)?(HOOK|HOOK_SHARED|HOOK_RAW|HOOK_RAW_SHARED)\((sub_[0-9A-F]{8})(?:,\s*(\w+))?\)?(.*)$')
NB = re.compile(r'N&B (sub_[0-9A-F]{8})')
NAME = re.compile(r'//\s*(\w+)')
BR = re.compile(r'\[0x([0-9A-F]{8})\]')

def scan(root):
    out = []
    d = os.path.join(root, 'app', 'src', 'renut_engine', 'gpu', 'd3d', 'hooks')
    for f in sorted(os.listdir(d)):
        if not f.endswith('.cpp'):
            continue
        for ln in open(os.path.join(d, f), encoding='utf-8', errors='replace'):
            m = LINE.match(ln)
            if not m:
                continue
            un, kind, sub, fn, rest = m.groups()
            nm = NAME.search(rest)
            nb = NB.search(rest)
            br = BR.search(rest)
            out.append(dict(file=f, un=bool(un), kind=kind, sub=sub, fn=fn or '', name=nm.group(1) if nm else (fn or ''),
                            nb=nb.group(1) if nb else (('sub_' + br.group(1)) if br else ''), rest=rest.strip()))
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sa2', default=os.path.join(ROOT, '..', 'refs', 'sa2-nx'))
    a = ap.parse_args()
    fc4 = scan(ROOT)
    sa2 = scan(a.sa2)
    sa2_by_nb = {h['nb']: h for h in sa2 if h['nb']}
    sa2_by_name = {h['name']: h for h in sa2}
    for h in fc4:
        nb = h['nb'] or (h['sub'] if h['un'] else '')
        s = sa2_by_nb.get(nb) or sa2_by_name.get(h['name'])
        sa = s['sub'] if s and not s['un'] and s['file'] != 'state.cpp' else '-'
        print(f"{h['file']:<13}{'UN' if h['un'] else 'H '} {h['kind']:<16}{h['sub']}  nb={nb or '?':<13} sa2={sa:<13} {h['name']}")
    print('# sa2-nx hooks not matched by name/N&B:')
    names = {h['name'] for h in fc4}
    for s in sa2:
        if s['file'] != 'state.cpp' and s['name'] not in names and not s['un']:
            print(f"#  {s['file']} {s['sub']} nb={s['nb']} {s['name']} {s['rest'][:100]}")
if __name__ == "__main__":
    main()
