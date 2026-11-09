#!/usr/bin/env python3
"""fc4-nx: wraps the decrypted game image (out/renut_image.bin, based at 0x82000000) as a 32-bit big-endian PowerPC ELF
that IDA / Ghidra load at the right addresses without an XEX loader plugin.

- one section per PE section (code ones executable, data ones writable), one PT_LOAD for the whole image;
- function symbols: every .pdata entry (start + length), the functions declared in app/config/renut_funcs.toml and
  app/overrides.toml, and the names found so far (setjmp, longjmp, the XAPI fiber functions, Direct3D_CreateDevice);
- entry point: game.xex's (0x83F3F630).

The image holds game code: the ELF is game-derived, keep it out of git (out/ is ignored) and never distribute it.
VMX128 vector instructions need IDA's Xbox 360 PowerPC variant; set the processor options after loading if they show
as data.

  python tools/fc4_image_elf.py [--image out/renut_image.bin] [--out out/fc4_image.elf]
"""
import argparse
import os
import re
import struct

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = 0x82000000
ENTRY = 0x83F3F630
NAMES = {
    0x83FBE870: "setjmp", 0x83FC0A80: "longjmp",
    0x83F45F20: "ConvertThreadToFiber", 0x83F45FB0: "ConvertFiberToThread", 0x83F46000: "CreateFiber",
    0x83F460E0: "DeleteFiber", 0x83F46140: "SwitchToFiber", 0x83F4EAC0: "XapiSwitchFiberContext",
    0x83F18AB0: "Direct3D_CreateDevice", 0x83F4EAB0: "XapiFiberStartStub", ENTRY: "start",
}


def pe_sections(img):
    lfanew = struct.unpack_from("<I", img, 0x3C)[0]
    nsec = struct.unpack_from("<H", img, lfanew + 6)[0]
    off = lfanew + 24 + struct.unpack_from("<H", img, lfanew + 20)[0]
    out = []
    for _ in range(nsec):
        name = img[off:off + 8].split(b"\0")[0].decode("latin-1")
        vsize, va = struct.unpack_from("<II", img, off + 8)
        flags = struct.unpack_from("<I", img, off + 36)[0]
        out.append((name, BASE + va, vsize, flags))
        off += 40
    return out


def functions(img, secs):
    funcs = {}
    for name, va, size, _ in secs:
        if name == ".pdata":
            for o in range(va - BASE, va - BASE + size - 7, 8):
                beg, info = struct.unpack_from(">II", img, o)
                if beg:
                    funcs[beg] = ((info >> 8) & 0x3FFFFF) * 4
    for rel in ("app/config/renut_funcs.toml", "app/overrides.toml"):
        p = os.path.join(ROOT, rel)
        if os.path.exists(p):
            for m in re.finditer(r'^"0x([0-9A-Fa-f]{8})"', open(p, encoding="utf-8").read(), re.M):
                funcs.setdefault(int(m.group(1), 16), 0)
    for a in NAMES:
        funcs.setdefault(a, 0)
    return funcs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", default=os.path.join(ROOT, "out", "renut_image.bin"))
    ap.add_argument("--out", default=os.path.join(ROOT, "out", "fc4_image.elf"))
    a = ap.parse_args()
    img = open(a.image, "rb").read()
    secs = [s for s in pe_sections(img) if s[2]]
    funcs = functions(img, secs)
    data_off = 0x1000

    shstr = bytearray(b"\0")
    def sname(s):
        shstr.extend(s.encode() + b"\0")
        return len(shstr) - len(s) - 1

    strtab = bytearray(b"\0")
    syms = [struct.pack(">IIIBBH", 0, 0, 0, 0, 0, 0)]
    code_idx = {}
    sec_hdrs = [struct.pack(">10I", *([0] * 10))]
    for i, (name, va, size, flags) in enumerate(secs, start=1):
        shf = 0x2 | (0x4 if flags & 0x20000000 else 0) | (0x1 if flags & 0x80000000 else 0)
        is_bss = flags & 0x80 and not flags & 0x40
        sec_hdrs.append(struct.pack(">10I", sname(name), 8 if is_bss else 1, shf, va, data_off + va - BASE, size,
                                    0, 0, 4, 0))
        code_idx[(va, va + size)] = i
    for addr in sorted(funcs):
        shndx = next((i for (lo, hi), i in code_idx.items() if lo <= addr < hi), 0)
        if not shndx:
            continue
        nm = NAMES.get(addr, f"sub_{addr:08X}")
        strtab.extend(nm.encode() + b"\0")
        syms.append(struct.pack(">IIIBBH", len(strtab) - len(nm) - 1, addr, funcs[addr], (1 << 4) | 2, 0, shndx))

    body = bytearray(img)
    tail_off = data_off + len(body)
    strtab_off = tail_off
    symtab_off = (strtab_off + len(strtab) + 3) & ~3
    symtab = b"".join(syms)
    shstr_name_symtab, shstr_name_strtab, shstr_name_shstr = sname(".symtab"), sname(".strtab"), sname(".shstrtab")
    shstr_off = symtab_off + len(symtab)
    shoff = (shstr_off + len(shstr) + 3) & ~3
    strtab_idx = len(sec_hdrs) + 1
    sec_hdrs.append(struct.pack(">10I", shstr_name_symtab, 2, 0, 0, symtab_off, len(symtab), strtab_idx, 1, 4, 16))
    sec_hdrs.append(struct.pack(">10I", shstr_name_strtab, 3, 0, 0, strtab_off, len(strtab), 0, 0, 1, 0))
    sec_hdrs.append(struct.pack(">10I", shstr_name_shstr, 3, 0, 0, shstr_off, len(shstr), 0, 0, 1, 0))
    shstrndx = len(sec_hdrs) - 1

    ehdr = (b"\x7fELF" + bytes([1, 2, 1, 0]) + bytes(8) +
            struct.pack(">HHIIIIIHHHHHH", 2, 20, 1, ENTRY, 52, shoff, 0, 52, 32, 1, 40, len(sec_hdrs), shstrndx))
    phdr = struct.pack(">8I", 1, data_off, BASE, BASE, len(body), len(body), 7, 0x1000)
    with open(a.out, "wb") as f:
        f.write(ehdr + phdr)
        f.write(bytes(data_off - f.tell()))
        f.write(body)
        f.write(strtab)
        f.write(bytes(symtab_off - f.tell()))
        f.write(symtab)
        f.write(shstr)
        f.write(bytes(shoff - f.tell()))
        f.write(b"".join(sec_hdrs))
    print(f"{a.out}: {len(secs)} sections, {len(syms) - 1} function symbols, entry 0x{ENTRY:08X}, "
          f"{os.path.getsize(a.out) / 1048576:.1f} MiB")


if __name__ == "__main__":
    main()
