#!/usr/bin/env python3
"""fc4-nx: questions to IDA 9.3 (idalib, headless) about the game image database out/fc4_image.elf.i64
(made by tools/fc4_image_elf.py + one auto-analysis). REA's IDA adapter has no PowerPC lane, so this is the way in.

  python tools/fc4_ida.py decompile 0x83AC94B8 [0x...]   Hex-Rays pseudocode
  python tools/fc4_ida.py callers   0x83AC94B8            code references to a function, with their functions
  python tools/fc4_ida.py xrefs     0x84123456            every reference to an address (code and data)
  python tools/fc4_ida.py strings   "engine\\\\shaders"     strings matching a regex, with their references
  python tools/fc4_ida.py disasm    0x83AC94B8 [count]    IDA's listing
  python tools/fc4_ida.py func      0x83AC9500            the function containing an address

Several commands can be chained with ';' as separate arguments: decompile 0x1 ; callers 0x1 (one database open).
Game-derived output: keep it in out/ or the conversation, never in git.
"""
import os
import re
import sys

os.environ.setdefault("IDADIR", r"C:\Program Files\IDA Professional 9.3")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "out", "fc4_image.elf.i64")

import idapro  # noqa: E402  (must come before the ida_* modules)


def fn_name(ea):
    import ida_funcs, ida_name
    f = ida_funcs.get_func(ea)
    if not f:
        return "?"
    return f"{ida_name.get_name(f.start_ea)}+0x{ea - f.start_ea:X}"


def cmd_decompile(args):
    import ida_hexrays, ida_funcs
    ida_hexrays.init_hexrays_plugin()
    for a in args:
        ea = int(a, 16)
        f = ida_funcs.get_func(ea)
        print(f"===== decompile 0x{ea:08X} ({fn_name(ea)})")
        try:
            print(str(ida_hexrays.decompile(f.start_ea if f else ea)))
        except Exception as e:
            print(f"decompile failed: {e}")


def cmd_callers(args):
    import idautils
    for a in args:
        ea = int(a, 16)
        refs = sorted(set(r for r in idautils.CodeRefsTo(ea, 0)))
        print(f"===== callers of 0x{ea:08X}: {len(refs)}")
        for r in refs:
            print(f"  0x{r:08X}  {fn_name(r)}")


def cmd_xrefs(args):
    import idautils, ida_xref
    for a in args:
        ea = int(a, 16)
        print(f"===== xrefs to 0x{ea:08X}")
        for x in idautils.XrefsTo(ea):
            print(f"  0x{x.frm:08X}  type {x.type:2d} {'code' if x.iscode else 'data'}  {fn_name(x.frm)}")


def cmd_strings(args):
    import idautils
    rx = re.compile(args[0], re.I)
    n = 0
    for s in idautils.Strings():
        t = str(s)
        if rx.search(t):
            refs = [x.frm for x in idautils.XrefsTo(s.ea)]
            print(f"0x{s.ea:08X} {t[:120]!r}  refs: " + ", ".join(f"0x{r:08X} ({fn_name(r)})" for r in refs[:6]))
            n += 1
            if n >= 200:
                print("... (200 shown)")
                break


def cmd_disasm(args):
    import idc
    ea, count = int(args[0], 16), int(args[1]) if len(args) > 1 else 40
    for _ in range(count):
        print(f"0x{ea:08X}  {idc.generate_disasm_line(ea, 0)}")
        ea = idc.next_head(ea, idc.BADADDR)


def cmd_func(args):
    import ida_funcs
    for a in args:
        ea = int(a, 16)
        f = ida_funcs.get_func(ea)
        print(f"0x{ea:08X}: " + (f"{fn_name(ea)} [0x{f.start_ea:08X}-0x{f.end_ea:08X}]" if f else "no function"))


CMDS = {"decompile": cmd_decompile, "callers": cmd_callers, "xrefs": cmd_xrefs, "strings": cmd_strings,
        "disasm": cmd_disasm, "func": cmd_func}


def main():
    argv = sys.argv[1:]
    if not argv or argv[0] not in CMDS:
        raise SystemExit(__doc__)
    groups, cur = [], []
    for x in argv:
        if x == ";":
            groups.append(cur)
            cur = []
        else:
            cur.append(x)
    groups.append(cur)
    if idapro.open_database(DB, False) != 0:
        raise SystemExit(f"cannot open {DB}")
    try:
        for g in groups:
            if g:
                CMDS[g[0]](g[1:])
    finally:
        idapro.close_database(False)


if __name__ == "__main__":
    main()
