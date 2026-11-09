#!/usr/bin/env python3
"""fc4-nx: scans the loaded game image (out/renut_image.bin, rexglue's REXGLUE_DUMP_IMAGE, based at 0x82000000).

  python tools/fc4_image_scan.py sections     PE sections of the image
  python tools/fc4_image_scan.py jmpbuf       setjmp / longjmp candidates by shape: a run of stfd/lfd f14..f31 and
                                              std/ld (or stw/lwz) r13..r31 at one base register (r3)
"""
import os
import struct
import sys

BASE = 0x82000000
IMG = os.path.join(os.path.dirname(__file__), "..", "out", "renut_image.bin")


def load():
    return open(IMG, "rb").read()


def sections(b):
    lfanew = struct.unpack_from("<I", b, 0x3C)[0]
    assert b[lfanew:lfanew + 4] == b"PE\0\0", "no PE header"
    nsec = struct.unpack_from("<H", b, lfanew + 6)[0]
    optsz = struct.unpack_from("<H", b, lfanew + 20)[0]
    off = lfanew + 24 + optsz
    out = []
    for i in range(nsec):
        name = b[off:off + 8].split(b"\0")[0].decode("latin-1")
        vsize, va, rawsz, rawptr = struct.unpack_from("<IIII", b, off + 8)
        flags = struct.unpack_from("<I", b, off + 36)[0]
        out.append((name, BASE + va, vsize, flags))
        off += 40
    return out


def code_ranges(b):
    return [(va, va + sz) for name, va, sz, fl in sections(b) if fl & 0x20000000]  # IMAGE_SCN_MEM_EXECUTE


def words(b, start, end):
    for a in range(start, end, 4):
        o = a - BASE
        if o + 4 > len(b):
            return
        yield a, struct.unpack_from(">I", b, o)[0]


def jmpbuf(b):
    """Find functions storing (setjmp) or loading (longjmp) f14..f31 and r13..r31 relative to r3."""
    for lo, hi in code_ranges(b):
        fp_st, fp_ld, gp_st, gp_ld = {}, {}, {}, {}
        for a, w in words(b, lo, hi):
            op, rt, ra = w >> 26, (w >> 21) & 31, (w >> 16) & 31
            if ra != 3:
                continue
            if op == 54 and 14 <= rt:           # stfd
                fp_st.setdefault(a & ~0xFF, set()).add(rt)
            elif op == 50 and 14 <= rt:         # lfd
                fp_ld.setdefault(a & ~0xFF, set()).add(rt)
            elif (op == 62 and (w & 3) == 0) or op == 36:   # std / stw
                if 13 <= rt:
                    gp_st.setdefault(a & ~0xFF, set()).add(rt)
            elif (op == 58 and (w & 3) == 0) or op == 32:   # ld / lwz
                if 13 <= rt:
                    gp_ld.setdefault(a & ~0xFF, set()).add(rt)

        def report(tag, fps, gps):
            for blk in sorted(fps):
                regs = set(fps[blk]) | fps.get(blk + 0x100, set()) | fps.get(blk - 0x100, set())
                g = gps.get(blk, set()) | gps.get(blk + 0x100, set()) | gps.get(blk - 0x100, set())
                if len(regs) >= 18 and len(g) >= 18:
                    # first matching instruction in the block
                    first = next(a for a, w in words(b, blk - 0x100, blk + 0x200)
                                 if (w >> 26) in ((54,) if tag == "setjmp" else (50,)) and ((w >> 16) & 31) == 3
                                 and ((w >> 21) & 31) >= 14)
                    print(f"{tag:7s} candidate near 0x{blk:08X} (first f-reg access 0x{first:08X}): "
                          f"{len(regs)} fprs, {len(g)} gprs")

        report("setjmp", fp_st, gp_st)
        report("longjmp", fp_ld, gp_ld)


def main():
    b = load()
    cmd = sys.argv[1] if len(sys.argv) > 1 else "sections"
    if cmd == "sections":
        for name, va, sz, fl in sections(b):
            print(f"{name:8s} 0x{va:08X}-0x{va + sz:08X} size 0x{sz:08X} ({sz / 1048576:6.2f} MiB) flags 0x{fl:08X}")
    elif cmd == "jmpbuf":
        jmpbuf(b)
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
