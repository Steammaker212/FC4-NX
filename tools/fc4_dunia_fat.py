#!/usr/bin/env python3
"""fc4-nx (2026-11-09): list, verify and extract Far Cry 4's Dunia 2 archives (Xbox 360): a `.fat` index and its `.dat`.

Layout, worked out from the game's own files (docs/fc4-shaders.md, "The archive"; Gibbed's Dunia tools are the public
reference for the family, version 9 = Far Cry 4):

  .fat header (little endian, 24 bytes):
    +0x00  'FAT2' (bytes 32 54 41 46)        +0x04  version (9)
    +0x08  flags: byte 0 platform (2 = Xbox 360), byte 1 = 4, high half 0
    +0x0C  sub-FAT entry total (0 here)      +0x10  sub-FAT count (0 here)
    +0x14  entry count
  entries (big endian on the Xbox 360, 20 bytes each, sorted by hash):
    +0x00  name hash, 64 bits
    +0x08  uncompressed size << 2 (0 = stored as is; low 2 bits taken as offset bits 34-35, always 0 so far)
    +0x0C  offset >> 2
    +0x10  (offset & 3) << 30 | compressed size (30 bits)
  after the entries: two 32-bit words (0 0 here: localisation and sub-FAT tables, empty).

  .dat: the entries' data back to back, no gaps. A compressed entry is
    1 byte   N: how many of the entry's last bytes are stored as they are, at the end (0-12 seen)
    5 bytes  LZMA properties (5D 00 00 80 00: lc 3, lp 0, pb 2, 8 MiB dictionary)
    ...      raw LZMA stream without end marker, decoding to uncompressed size - N bytes
    N bytes  the entry's last N bytes.

Names are not stored (only the 64-bit hashes), so entries are written as <hash>.bin, with index.tsv beside them.

  python tools/fc4_dunia_fat.py list    game/installation1/shadersobj.fat
  python tools/fc4_dunia_fat.py verify  game/installation1/shadersobj.fat
  python tools/fc4_dunia_fat.py extract game/installation1/shadersobj.fat out/fc4_shaders/raw
"""
import argparse
import collections
import lzma
import os
import struct
import sys

PLATFORMS = {0: 'any', 1: 'pc', 2: 'xbox360', 3: 'ps3'}


class Entry:
    __slots__ = ('index', 'hash', 'offset', 'csize', 'usize', 'flag')

    def __init__(self, index, h, offset, csize, usize):
        self.index, self.hash, self.offset, self.csize, self.usize = index, h, offset, csize, usize
        self.flag = None

    @property
    def name(self):
        return '%016x' % self.hash


def read_fat(path):
    fat = open(path, 'rb').read()
    magic, version, flags, sub_total, sub_count, count = struct.unpack_from('<4sIIIII', fat, 0)
    if magic != b'2TAF':
        raise SystemExit('%s: not a Dunia FAT2 index (magic %r)' % (path, magic))
    if version != 9:
        raise SystemExit('%s: FAT2 version %d; this tool reads version 9 (Far Cry 4)' % (path, version))
    platform = flags & 0xFF
    end = 0x18 + 20 * count
    if end > len(fat):
        raise SystemExit('%s: %d entries do not fit in %d bytes' % (path, count, len(fat)))
    # Entries in the platform's byte order: big endian for the Xbox 360 and PS3, little for the PC.
    order = '>' if platform in (2, 3) else '<'
    entries = []
    for i in range(count):
        hi, lo, c, d, e = struct.unpack_from(order + '5I', fat, 0x18 + 20 * i)
        offset = ((c & 3) << 34) | (d << 2) | (e >> 30)
        entries.append(Entry(i, (hi << 32) | lo, offset, e & 0x3FFFFFFF, c >> 2))
    header = {'version': version, 'platform': PLATFORMS.get(platform, str(platform)), 'flags': flags,
              'subfat_entries': sub_total, 'subfats': sub_count, 'entries': count,
              'tail': fat[end:].hex(), 'size': len(fat)}
    return header, entries


def unpack(entry, dat):
    """The entry's bytes, decompressed. Raises ValueError on a size mismatch or an unknown header."""
    blob = dat[entry.offset:entry.offset + entry.csize]
    if len(blob) != entry.csize:
        raise ValueError('entry %s runs past the end of the .dat' % entry.name)
    if entry.usize == 0:
        return blob
    tail = entry.flag = blob[0]
    props = blob[1]
    if props >= 9 * 5 * 5 or tail > entry.usize or 6 + tail > len(blob):
        raise ValueError('entry %s: unknown compressed header %s' % (entry.name, blob[:6].hex()))
    # The first byte is how many of the entry's last bytes follow the LZMA stream as they are; the stream (no end
    # marker) gives the rest. Decoding the tail bytes as stream input instead gets the last bytes wrong.
    lzma1 = {'id': lzma.FILTER_LZMA1, 'lc': props % 9, 'lp': props // 9 % 5, 'pb': props // 45,
             'dict_size': struct.unpack_from('<I', blob, 2)[0]}
    try:
        out = lzma.LZMADecompressor(lzma.FORMAT_RAW, filters=[lzma1]).decompress(blob[6:len(blob) - tail],
                                                                                 entry.usize - tail)
    except lzma.LZMAError as ex:
        raise ValueError('entry %s: %s' % (entry.name, ex))
    if len(out) != entry.usize - tail:
        raise ValueError('entry %s: %d bytes decoded, %d expected' % (entry.name, len(out), entry.usize - tail))
    return out + blob[len(blob) - tail:]


def dat_path(fat_path, dat=None):
    return dat or os.path.splitext(fat_path)[0] + '.dat'


def kind_of(data):
    """A short label for what an entry holds, from its first bytes (Far Cry 4's shadersobj kinds)."""
    if data[:4] == b'\x8d\x06\x08\x00':
        return 'shaderobj'
    if data[4:8] == b'HEAD':
        return 'head'
    if data[:1].isalpha() and b'=' in data[:64]:
        return 'renderstate'
    return data[:4].hex()


def cmd_list(a):
    header, entries = read_fat(a.fat)
    print('# %s: %s' % (a.fat, ' '.join('%s=%s' % kv for kv in header.items())))
    print('hash\toffset\tcompressed\tuncompressed')
    for e in entries:
        print('%s\t0x%x\t%d\t%d' % (e.name, e.offset, e.csize, e.usize))


def check_layout(entries, dat_size):
    """Problems with where the entries sit: overlaps, holes, past the end."""
    problems = []
    spans = sorted((e.offset, e.offset + e.csize, e.name) for e in entries)
    pos = 0
    for start, end, name in spans:
        if start != pos:
            problems.append('%s at 0x%x: %s of %d bytes before it' % (name, start, 'hole' if start > pos else 'overlap',
                                                                      abs(start - pos)))
        pos = max(pos, end)
    if pos != dat_size:
        problems.append('entries end at 0x%x, the .dat at 0x%x' % (pos, dat_size))
    return problems


def cmd_verify(a):
    header, entries = read_fat(a.fat)
    dat = open(dat_path(a.fat, a.dat), 'rb').read()
    problems = check_layout(entries, len(dat))
    kinds, flags, failed = collections.Counter(), collections.Counter(), 0
    for e in entries:
        try:
            data = unpack(e, dat)
        except ValueError as ex:
            failed += 1
            problems.append(str(ex))
            continue
        kinds[kind_of(data)] += 1
        flags['stored' if e.usize == 0 else 'lzma flag %d' % e.flag] += 1
    for p in problems[:20]:
        print('problem:', p)
    print('%s: %s %d entries, %d compressed, %d bytes in the .dat, %d uncompressed; %d failed; layout %s'
          % (a.fat, header['platform'], len(entries), sum(1 for e in entries if e.usize), len(dat),
             sum(e.usize or e.csize for e in entries), failed, 'contiguous' if not check_layout(entries, len(dat))
             else 'NOT contiguous'))
    print('  storage:', ', '.join('%s %d' % kv for kv in sorted(flags.items())))
    top = kinds.most_common(12)
    print('  kinds:', ', '.join('%s %d' % kv for kv in top) +
          (', %d more kinds' % (len(kinds) - len(top)) if len(kinds) > len(top) else ''))
    return 1 if problems else 0


def cmd_extract(a):
    header, entries = read_fat(a.fat)
    dat = open(dat_path(a.fat, a.dat), 'rb').read()
    os.makedirs(a.out, exist_ok=True)
    failed = 0
    with open(os.path.join(a.out, 'index.tsv'), 'w', newline='\n') as idx:
        idx.write('hash\toffset\tcompressed\tuncompressed\tlzma_flag\tkind\n')
        for e in entries:
            try:
                data = unpack(e, dat)
            except ValueError as ex:
                print('failed:', ex, file=sys.stderr)
                failed += 1
                continue
            with open(os.path.join(a.out, e.name + '.bin'), 'wb') as f:
                f.write(data)
            idx.write('%s\t0x%x\t%d\t%d\t%s\t%s\n' % (e.name, e.offset, e.csize, e.usize,
                                                     '' if e.flag is None else e.flag, kind_of(data)))
    print('%s: %d of %d entries written to %s (%d failed)' % (a.fat, len(entries) - failed, len(entries), a.out,
                                                               failed))
    return 1 if failed else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    for name, fn in (('list', cmd_list), ('verify', cmd_verify), ('extract', cmd_extract)):
        p = sub.add_parser(name)
        p.add_argument('fat')
        if name == 'extract':
            p.add_argument('out')
        if name != 'list':
            p.add_argument('--dat', help='the .dat (default: beside the .fat)')
        p.set_defaults(fn=fn)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == '__main__':
    sys.exit(main())
