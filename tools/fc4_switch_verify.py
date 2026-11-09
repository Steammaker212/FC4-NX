#!/usr/bin/env python3
"""fc4-nx: checks every generated switch of the absolute-table shape Far Cry 4's compiler emits, which
tools/switch_check.py does not recognise (it found 0 absolute tables against 428 generated switches):

    [cmplwi crN,rI,B ; bgt crN,default]
    lis r12,HI ; rlwinm r0,rI,2,0,29 ; addi r12,r12,LO ; lwzx r0,r12,r0 ; mtctr r0 ; bctr

For each `switch (ctx.rI.u32)` in app/generated it reads the table base from the lis/addi comments above it, the
bound from the nearest cmplwi on rI, and the cases below it, then compares each case target with the table word in
out/renut_image.bin. Reports: count mismatch (cases vs bound + 1), wrong targets, unparsed shapes.

  python tools/fc4_switch_verify.py [--gen app/generated] [--image out/renut_image.bin]
"""
import argparse
import glob
import os
import re
import struct

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = 0x82000000


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gen", default=os.path.join(ROOT, "app", "generated"))
    ap.add_argument("--image", default=os.path.join(ROOT, "out", "renut_image.bin"))
    a = ap.parse_args()
    img = open(a.image, "rb").read()
    word = lambda ea: struct.unpack_from(">I", img, ea - BASE)[0]
    stats = {"switches": 0, "checked": 0, "ok": 0, "count_mismatch": 0, "wrong_target": 0, "unparsed": 0}
    problems = []
    for path in sorted(glob.glob(os.path.join(a.gen, "renut_recomp.*.cpp"))):
        lines = open(path, errors="replace").read().split("\n")
        func = "?"
        for i, line in enumerate(lines):
            m = re.match(r"DEFINE_REX_FUNC\((\w+)\)", line)
            if m:
                func = m.group(1)
                continue
            m = re.match(r"\s*switch \((?:ctx\.)?r(\d+)\w*\.u32\) \{", line)
            if not m:
                continue
            stats["switches"] += 1
            reg = m.group(1)
            back = lines[max(0, i - 40):i]
            text = "\n".join(back)
            lis = re.findall(r"// lis r12,(-?\d+)", text)
            addi = re.findall(r"// addi r12,r12,(-?\d+)", text)
            kind = None
            if lis and addi and "// lwzx r0,r12,r0" in text:
                kind = "abs"
            mo = re.search(r"// (lbzx|lhzx) r0,r12,r\d+\n(?:.*\n)*?\s*// lis r12,(-?\d+)\n(?:.*\n)*?\s*// addi r12,r12,(-?\d+)"
                           r"\n(?:.*\n)*?\s*// add r12,r12,r0", text)
            if mo and len(lis) >= 2:
                kind = mo.group(1)
            if not kind:
                stats["unparsed"] += 1
                continue
            if kind != "abs":
                # offset table: first lis/addi pair = table, second = base; target = base + (entry << shift)
                pairs = re.findall(r"// lis r12,(-?\d+)\n(?:.*\n)*?\s*// addi r12,r12,(-?\d+)", text)
                tbl = ((int(pairs[-2][0]) << 16) + int(pairs[-2][1])) & 0xFFFFFFFF
                basev = ((int(pairs[-1][0]) << 16) + int(pairs[-1][1])) & 0xFFFFFFFF
                shift_m = re.search(r"// rlwinm r0,r0,(\d+),", text[text.find(kind):])
                shift = int(shift_m.group(1)) if shift_m else 0
                esz = 1 if kind == "lbzx" else 2
                bound = None
                for l in reversed(back):
                    mb = re.search(rf"// cmplwi cr\d,r{reg},(\d+)", l)
                    if mb:
                        bound = int(mb.group(1))
                        break
                cases = {}
                j = i + 1
                while j < len(lines) and lines[j].strip() != "}" and not lines[j].strip().startswith("default"):
                    mc = re.match(r"\s*case (\d+):", lines[j])
                    mt = re.search(r"goto loc_([0-9A-F]+);", lines[j + 1]) if mc and j + 1 < len(lines) else None
                    if mt:
                        cases[int(mc.group(1))] = int(mt.group(1), 16)
                    j += 1
                stats["checked"] += 1
                bad = []
                if bound is not None and len(cases) != bound + 1:
                    stats["count_mismatch"] += 1
                    bad.append(f"{len(cases)} cases, bound {bound} (+1)")
                for k, tgt in cases.items():
                    off = tbl - BASE + esz * k
                    e = img[off] if esz == 1 else struct.unpack_from(">H", img, off)[0]
                    real = (basev + (e << shift)) & 0xFFFFFFFF
                    if real != tgt and tgt < 0xF0000000:
                        bad.append(f"case {k}: generated 0x{tgt:08X}, table 0x{real:08X} ({kind} shift {shift})")
                if any(b.startswith("case") for b in bad):
                    stats["wrong_target"] += 1
                if bad:
                    problems.append(f"{func} {kind} table 0x{tbl:08X} base 0x{basev:08X} r{reg}: " + "; ".join(bad[:4]))
                else:
                    stats["ok"] += 1
                continue
            table = ((int(lis[-1]) << 16) + int(addi[-1])) & 0xFFFFFFFF
            bound = None
            for l in reversed(back):
                mb = re.search(rf"// cmplwi cr\d,r{reg},(\d+)", l)
                if mb:
                    bound = int(mb.group(1))
                    break
            cases = {}
            j = i + 1
            while j < len(lines) and not lines[j].strip().startswith("default") and lines[j].strip() != "}":
                mc = re.match(r"\s*case (\d+):", lines[j])
                if mc:
                    mt = re.search(r"goto loc_([0-9A-F]+);", lines[j + 1]) if j + 1 < len(lines) else None
                    if mt:
                        cases[int(mc.group(1))] = int(mt.group(1), 16)
                j += 1
            stats["checked"] += 1
            bad = []
            if bound is not None and len(cases) != bound + 1:
                stats["count_mismatch"] += 1
                bad.append(f"{len(cases)} cases, bound {bound} (+1)")
            for k, tgt in cases.items():
                if table - BASE + 4 * k + 4 > len(img):
                    bad.append(f"case {k}: table outside image")
                    break
                real = word(table + 4 * k)
                if real != tgt and tgt < 0xF0000000:
                    bad.append(f"case {k}: generated 0x{tgt:08X}, table 0x{real:08X}")
            if any(b.startswith("case") for b in bad):
                stats["wrong_target"] += 1
            if bad:
                problems.append(f"{func} table 0x{table:08X} r{reg}: " + "; ".join(bad[:4]))
            else:
                stats["ok"] += 1
    print(stats)
    for p in problems[:60]:
        print(" ", p)


if __name__ == "__main__":
    main()
