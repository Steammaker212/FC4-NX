#!/usr/bin/env python3
"""Xbox 360 disc image (XDVDFS) lister/extractor and XEX2 header reader. Own code, stdlib only.

  python fc4_iso.py list    <iso> [out.txt]
  python fc4_iso.py extract <iso> <out_dir> [--only <name>...]
  python fc4_iso.py xexinfo <default.xex>
"""
import os
import struct
import sys

SECTOR = 2048
MAGIC = b"MICROSOFT*XBOX*MEDIA"
BASES = [(0x02080000, "XGD3"), (0x0FD90000, "XGD2"), (0x18300000, "XGD1"), (0, "raw")]


def find_base(fh):
    for base, name in BASES:
        fh.seek(base + 32 * SECTOR)
        if fh.read(20) == MAGIC:
            return base, name
    raise SystemExit("no XDVDFS volume descriptor found")


def walk(fh, base, sector, size, prefix=""):
    """Yield (path, start_sector, size, is_dir) for a directory table (binary tree of entries)."""
    if size == 0:
        return
    fh.seek(base + sector * SECTOR)
    table = fh.read(size)
    seen = set()
    stack = [0]
    while stack:
        off = stack.pop()
        if off in seen or off + 14 > len(table):
            continue
        seen.add(off)
        left, right, start, fsize, attr, nlen = struct.unpack_from("<HHIIBB", table, off)
        if left == 0xFFFF:
            continue
        name = table[off + 14: off + 14 + nlen].decode("latin-1")
        path = prefix + name
        is_dir = bool(attr & 0x10)
        yield path, start, fsize, is_dir
        if is_dir:
            yield from walk(fh, base, start, fsize, path + "/")
        if left:
            stack.append(left * 4)
        if right:
            stack.append(right * 4)


def open_volume(iso):
    fh = open(iso, "rb")
    base, kind = find_base(fh)
    fh.seek(base + 32 * SECTOR + 20)
    root_sector, root_size = struct.unpack("<II", fh.read(8))
    return fh, base, kind, root_sector, root_size


def cmd_list(iso, out=None):
    fh, base, kind, rs, rsz = open_volume(iso)
    lines = [f"# {kind} partition at 0x{base:X}"]
    total = 0
    for path, start, size, is_dir in sorted(walk(fh, base, rs, rsz)):
        if not is_dir:
            total += size
        lines.append(f"{'D' if is_dir else 'F'} {size:12d} {path}")
    lines.append(f"# total file bytes {total}")
    text = "\n".join(lines) + "\n"
    if out:
        open(out, "w", encoding="utf-8").write(text)
    else:
        sys.stdout.write(text)


def cmd_extract(iso, out_dir, only=None):
    fh, base, kind, rs, rsz = open_volume(iso)
    for path, start, size, is_dir in walk(fh, base, rs, rsz):
        if only and path.lower() not in only:
            continue
        dest = os.path.join(out_dir, *path.split("/"))
        if is_dir:
            os.makedirs(dest, exist_ok=True)
            continue
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        if os.path.exists(dest) and os.path.getsize(dest) == size:
            continue
        fh.seek(base + start * SECTOR)
        left = size
        with open(dest, "wb") as o:
            while left:
                chunk = fh.read(min(left, 8 << 20))
                if not chunk:
                    raise SystemExit(f"short read in {path}")
                o.write(chunk)
                left -= len(chunk)
        print(path, size)


def be32(b, o):
    return struct.unpack_from(">I", b, o)[0]


def cmd_xexinfo(path):
    b = open(path, "rb").read()
    if b[:4] != b"XEX2":
        raise SystemExit("not XEX2")
    flags, pe_off, _, sec_off, count = struct.unpack_from(">IIIII", b, 4)
    print(f"module_flags=0x{flags:08X} pe_data_offset=0x{pe_off:X} security_offset=0x{sec_off:X} headers={count}")
    hdr = {}
    for i in range(count):
        k, v = struct.unpack_from(">II", b, 24 + i * 8)
        hdr[k] = v
        print(f"  key 0x{k:08X} value 0x{v:08X}")

    def blob(k):
        v = hdr[k]
        if (k & 0xFF) in (0, 1):
            return None
        if (k & 0xFF) == 0xFF:
            return b[v: v + be32(b, v)]
        return b[v: v + (k & 0xFF) * 4]

    if 0x00040006 in hdr:
        e = blob(0x00040006)
        media, ver, basever, tid = struct.unpack_from(">IIII", e, 0)
        plat, etype, dnum, dcount = e[16], e[17], e[18], e[19]
        v = lambda x: f"{x >> 28}.{(x >> 24) & 0xF}.{(x >> 8) & 0xFFFF}.{x & 0xFF}"
        print(f"title_id={tid:08X} media_id={media:08X} version={v(ver)} base_version={v(basever)} disc={dnum}/{dcount}")
    if 0x00010201 in hdr:
        print(f"image_base=0x{hdr[0x00010201]:08X}")
    if 0x00010100 in hdr:
        print(f"entry_point=0x{hdr[0x00010100]:08X}")
    if 0x00020200 in hdr:
        print(f"default_stack_size=0x{hdr[0x00020200]:X}")
    if 0x00020401 in hdr:
        print(f"default_heap_size=0x{hdr[0x00020401]:X}")
    if 0x000183FF in hdr:
        print("original_pe_name=" + blob(0x000183FF)[4:].split(b"\0")[0].decode("latin-1"))
    if 0x000003FF in hdr:
        f = blob(0x000003FF)
        enc, comp = struct.unpack_from(">HH", f, 4)
        print(f"file_format encryption={enc} compression={comp}")
    if 0x000200FF in hdr:
        s = blob(0x000200FF)
        print("static libraries:")
        for o in range(4, len(s) - 15, 16):
            name = s[o:o + 8].split(b"\0")[0].decode("latin-1")
            maj, mnr, bld = struct.unpack_from(">HHH", s, o + 8)
            print(f"  {name:10s} {maj}.{mnr}.{bld} qfe={s[o + 15]} approval={s[o + 14]}")
    if 0x000103FF in hdr:
        s = blob(0x000103FF)
        strsz, nstr = struct.unpack_from(">II", s, 4)
        names, p = [], 12
        end = 12 + strsz
        while len(names) < nstr and p < end:
            z = s.index(b"\0", p)
            names.append(s[p:z].decode("latin-1"))
            p = z + 1
            while p < end and s[p] == 0:
                p += 1
        p = end
        print("import libraries:")
        while p + 40 <= len(s):
            lsz = be32(s, p)
            ver, vmin = be32(s, p + 28), be32(s, p + 32)
            idx, cnt = struct.unpack_from(">HH", s, p + 36)
            v = lambda x: f"{x >> 28}.{(x >> 24) & 0xF}.{(x >> 8) & 0xFFFF}.{x & 0xFF}"
            print(f"  {names[idx] if idx < len(names) else idx}: version {v(ver)} min {v(vmin)} records {cnt}")
            if lsz == 0:
                break
            p += lsz
    if sec_off:
        hsz, img = be32(b, sec_off), be32(b, sec_off + 4)
        load = be32(b, sec_off + 0x110)
        print(f"security: header_size=0x{hsz:X} image_size=0x{img:X} ({img / 1048576:.1f} MiB) load_address=0x{load:08X}")
    print(f"file size {len(b)} ({len(b) / 1048576:.1f} MiB)")


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        raise SystemExit(__doc__)
    if a[0] == "list":
        cmd_list(a[1], a[2] if len(a) > 2 else None)
    elif a[0] == "extract":
        only = None
        if "--only" in a:
            i = a.index("--only")
            only = {x.lower() for x in a[i + 1:]}
            a = a[:i]
        cmd_extract(a[1], a[2], only)
    elif a[0] == "xexinfo":
        cmd_xexinfo(a[1])
    else:
        raise SystemExit(__doc__)
