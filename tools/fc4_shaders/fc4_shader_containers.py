#!/usr/bin/env python3
"""fc4-nx (2026-11-09): the Xbox 360 shader containers in Far Cry 4's shader package and in game.xex's image.

Input: the entries tools/fc4_dunia_fat.py extracted from installation1/shadersobj (<hash>.bin + index.tsv) and,
optionally, the loaded image (out/renut_image.bin). Every file is scanned with tools/renut_shader_dump.py's
find_shader_headers (containers at 4-byte offsets; with --unaligned also at any byte), and each shader object
(8D 06 08 00) is also read by its own header, as a check that the scan found its one container.

Output: <out>/containers/{vs,ps}_<xxh3_64 of the container>.bin (the name Renut's renderer and XenosRecomp use),
<out>/containers.tsv (one line per container found: source, offset, kind, hash, sizes) and a summary on stdout.

  python tools/fc4_shaders/fc4_shader_containers.py --raw out/fc4_shaders/raw --image out/renut_image.bin
                                                    --out out/fc4_shaders
"""
import argparse
import collections
import os
import struct
import sys

import xxhash

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from renut_shader_dump import find_shader_headers  # noqa: E402

SHADEROBJ_MAGIC = b'\x8d\x06\x08\x00'


def shaderobj_container(data):
    """The container offset a shader object's header names, or None. Header (12 bytes): magic 8D 06 08 00, big-endian
    u16 container offset, u16 0, u8 4, u8 binding count N, u16 0; then N 8-byte records (a 32-bit name hash and four
    register bytes), the container right after them, ending the file. Same for all 6,557 objects."""
    if data[:4] != SHADEROBJ_MAGIC or len(data) < 12:
        return None
    off = struct.unpack_from('>H', data, 4)[0]
    count = data[9]
    return off if off == 12 + 8 * count else None


def container_info(data, o):
    flags, virt, phys = struct.unpack_from('>III', data, o)
    return {'kind': 'vs' if flags & 1 else 'ps', 'virt': virt, 'phys': phys, 'blob': data[o:o + virt + phys]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--raw', required=True, help='tools/fc4_dunia_fat.py extract output (shadersobj)')
    ap.add_argument('--image', help='the loaded game.xex image (out/renut_image.bin)')
    ap.add_argument('--out', required=True)
    ap.add_argument('--unaligned', action='store_true', help='also look for containers at unaligned offsets')
    a = ap.parse_args()
    cdir = os.path.join(a.out, 'containers')
    os.makedirs(cdir, exist_ok=True)

    kinds = {}
    idx = os.path.join(a.raw, 'index.tsv')
    if os.path.isfile(idx):
        for line in open(idx).read().splitlines()[1:]:
            f = line.split('\t')
            kinds[f[0]] = f[5]
    sources = [(os.path.join(a.raw, n), n[:-4]) for n in sorted(os.listdir(a.raw)) if n.endswith('.bin')]
    if a.image:
        sources.append((a.image, 'image'))

    rows, unique, per_source_kind = [], {}, collections.Counter()
    objs_ok = objs_bad = 0
    for path, name in sources:
        data = open(path, 'rb').read()
        found = set(find_shader_headers(data, aligned=True))
        if a.unaligned:
            found |= set(find_shader_headers(data, aligned=False))
        kind = 'image' if name == 'image' else kinds.get(name, '?')
        if kind == 'shaderobj':
            off = shaderobj_container(data)
            ok = off is not None and found == {off}
            if ok:
                c = container_info(data, off)
                ok = off + len(c['blob']) == len(data)
            objs_ok += ok
            objs_bad += not ok
            if not ok:
                print('shader object %s: header names 0x%s, the scan found %s' %
                      (name, '%x' % off if off is not None else '-', sorted(found)), file=sys.stderr)
        for o in sorted(found):
            c = container_info(data, o)
            if len(c['blob']) != c['virt'] + c['phys']:
                continue
            h = xxhash.xxh3_64_hexdigest(c['blob'])
            per_source_kind[(kind, c['kind'])] += 1
            rows.append((name, kind, o, c['kind'], h, c['virt'], c['phys']))
            fn = '%s_%s.bin' % (c['kind'], h)
            if fn not in unique:
                unique[fn] = (c, set())
                with open(os.path.join(cdir, fn), 'wb') as f:
                    f.write(c['blob'])
            unique[fn][1].add(kind)

    with open(os.path.join(a.out, 'containers.tsv'), 'w', newline='\n') as f:
        f.write('source\tsource_kind\toffset\tstage\txxh3\tvirtual_size\tphysical_size\n')
        for r in rows:
            f.write('%s\t%s\t0x%x\t%s\t%s\t%d\t%d\n' % r)

    print('shader objects: %d read by their header, %d not' % (objs_ok, objs_bad))
    for (src, stage), n in sorted(per_source_kind.items()):
        print('containers found: %-10s %s %5d' % (src, stage, n))
    for stage in ('vs', 'ps'):
        u = {fn: v for fn, v in unique.items() if fn.startswith(stage)}
        phys = sorted(v[0]['phys'] for v in u.values())
        only_image = sum(1 for v in u.values() if v[1] == {'image'})
        both = sum(1 for v in u.values() if 'image' in v[1] and len(v[1]) > 1)
        if phys:
            print('unique %s: %5d (%d only in the image, %d in both); microcode bytes min %d median %d max %d total %d'
                  % (stage, len(u), only_image, both, phys[0], phys[len(phys) // 2], phys[-1], sum(phys)))
    print('%d unique containers written to %s' % (len(unique), cdir))
    return 1 if objs_bad else 0


if __name__ == '__main__':
    sys.exit(main())
