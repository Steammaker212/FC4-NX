#!/usr/bin/env python3
"""fc4-nx: shared helpers for reading Far Cry 4's Direct3D in the decrypted image (out/renut_image.bin), read-only.

  import fc4lib as L
  img = L.load()                  # image, .pdata functions, import thunks, names (out/fc4_d3d/names.txt)
  L.func_of(img, 0x83F18AE0)      # (start, end) from .pdata
  L.dis(img, 0x83F18AB0)          # listing of the whole function, calls named
  L.callers(img, 0x83F188E8)      # [(site, kind 'bl'|'b', containing function start)]
  L.calls(img, 0x83F18AB0)        # bl targets in order
  L.disps(img, 0x83F18AB0)        # [(addr, op, disp, base reg)] of D-form loads / stores

Callers are indexed once over .text and cached in out/fc4_d3d/callers.pickle (keyed by the image's size and mtime).
"""
import os
import pickle
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from ppc_mini import Image, decode, text  # noqa: E402

BASE = 0x82000000
TEXT = (0x82400000, 0x840B9110)
PDATA = (0x822F3E00, 0x823F8E60)
OUT = os.path.join(ROOT, 'out', 'fc4_d3d')
IMAGE = os.path.join(ROOT, 'out', 'renut_image.bin')


class Fc4:
    pass


def load(path=IMAGE):
    g = Fc4()
    g.img = Image(path, BASE)
    g.data = g.img.data
    # .pdata: {BeginAddress, PrologLen:8 | FuncLen(words):22 | flags:2}
    starts, ends = [], []
    for off in range(PDATA[0] - BASE, PDATA[1] - BASE, 8):
        b, w = struct.unpack_from('>II', g.data, off)
        if not b:
            continue
        n = (w >> 8) & 0x3FFFFF
        starts.append(b)
        ends.append(b + 4 * n)
    order = sorted(range(len(starts)), key=starts.__getitem__)
    g.fstart = [starts[i] for i in order]
    g.fend = [ends[i] for i in order]
    g.imports = {}
    p = os.path.join(OUT, 'imports.txt')
    if os.path.exists(p):
        for ln in open(p):
            a, n = ln.split()
            g.imports[int(a, 16)] = n
    g.names = {}
    p = os.path.join(OUT, 'names.txt')
    if os.path.exists(p):
        for ln in open(p, encoding='utf-8'):
            ln = ln.split('#')[0].split()
            if len(ln) >= 2:
                g.names[int(ln[0], 16)] = ln[1]
    g._callers = None
    return g


def word(g, a):
    return struct.unpack_from('>I', g.data, a - BASE)[0]


def func_of(g, a):
    import bisect
    i = bisect.bisect_right(g.fstart, a) - 1
    if i >= 0 and g.fstart[i] <= a < g.fend[i]:
        return g.fstart[i], g.fend[i]
    return None


def func_end(g, start):
    import bisect
    i = bisect.bisect_left(g.fstart, start)
    if i < len(g.fstart) and g.fstart[i] == start:
        return g.fend[i]
    # not a .pdata start: walk to the next start
    return g.fstart[i] if i < len(g.fstart) else start + 0x400


def name(g, a):
    if a in g.imports:
        return '__imp__' + g.imports[a]
    if a in g.names:
        return g.names[a]
    return f'sub_{a:08X}'


def ins_range(g, lo, hi):
    for a in range(lo, hi, 4):
        yield decode(word(g, a), a)


def dis(g, start, end=None, show=True):
    end = end or func_end(g, start)
    out = []
    for a in range(start, end, 4):
        w = word(g, a)
        ins = decode(w, a)
        t = text(ins)
        if ins.op == 'b' and ins.target is not None:
            t += f'    ; {name(g, ins.target)}'
        out.append(f'{a:08X}  {w:08X}  {t}')
    s = '\n'.join(out)
    if show:
        print(s)
    return s


def calls(g, start, end=None):
    end = end or func_end(g, start)
    return [i.target for i in ins_range(g, start, end) if i.op == 'b' and i.link]


def tails(g, start, end=None):
    end = end or func_end(g, start)
    return [i.target for i in ins_range(g, start, end) if i.op == 'b' and not i.link and not (start <= i.target < end)]


def _index(g):
    key = (len(g.data), int(os.path.getmtime(IMAGE)))
    p = os.path.join(OUT, 'callers.pickle')
    if os.path.exists(p):
        with open(p, 'rb') as f:
            k, idx = pickle.load(f)
        if k == key:
            return idx
    idx = {}
    lo, hi = TEXT
    words = struct.unpack_from('>%dI' % ((hi - lo) // 4), g.data, lo - BASE)
    for i, w in enumerate(words):
        if (w >> 26) != 18:
            continue
        li = w & 0x03FFFFFC
        if li & 0x02000000:
            li -= 0x04000000
        a = lo + 4 * i
        t = (li if w & 2 else a + li) & 0xFFFFFFFF
        idx.setdefault(t, []).append((a, 'bl' if w & 1 else 'b'))
    os.makedirs(OUT, exist_ok=True)
    with open(p, 'wb') as f:
        pickle.dump((key, idx), f)
    return idx


def callers(g, target):
    if g._callers is None:
        g._callers = _index(g)
    out = []
    for site, kind in g._callers.get(target, []):
        f = func_of(g, site)
        out.append((site, kind, f[0] if f else None))
    return out


def disps(g, start, end=None, minimum=0):
    """D-form loads/stores: (addr, op, disp, base)."""
    end = end or func_end(g, start)
    out = []
    for ins in ins_range(g, start, end):
        w = ins.word
        p = w >> 26
        if p in (32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 48, 49, 50, 51, 52, 53, 54, 55, 58, 62):
            ra = (w >> 16) & 31
            d = w & 0xFFFF
            if p in (58, 62):
                d &= 0xFFFC
            if d & 0x8000:
                d -= 0x10000
            if d >= minimum:
                out.append((ins.addr, text(ins).split()[0], d, ra))
    return out


def addis(g, start, end=None):
    """addi rX,rY,imm with imm >= 0x100 (device field addresses) and li values."""
    end = end or func_end(g, start)
    out = []
    for ins in ins_range(g, start, end):
        w = ins.word
        if w >> 26 == 14:
            ra = (w >> 16) & 31
            d = w & 0xFFFF
            if d & 0x8000:
                d -= 0x10000
            out.append((ins.addr, 'li' if ra == 0 else 'addi', d, ra))
    return out


def data_refs(g, start, end=None):
    """lis rX,hi then addi/ori/load/store lo(rX): absolute addresses, in order."""
    end = end or func_end(g, start)
    hi = {}
    out = []
    for ins in ins_range(g, start, end):
        w = ins.word
        p = w >> 26
        rt = (w >> 21) & 31
        ra = (w >> 16) & 31
        imm = w & 0xFFFF
        if p == 15 and ra == 0:  # lis
            hi[rt] = imm << 16
            continue
        if ra in hi and p in (14, 24, 32, 34, 36, 38, 40, 44, 48, 50, 52, 54, 58):
            s = imm - 0x10000 if (imm & 0x8000 and p != 24) else imm
            out.append((ins.addr, (hi[ra] + s) & 0xFFFFFFFF))
        if p in (14, 15, 24, 32, 34, 40, 42, 58) and rt in hi and rt != ra:
            hi.pop(rt, None)
    return out
