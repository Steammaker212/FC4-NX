#!/usr/bin/env python3
"""fc4-nx (2026-11-09): Renut's Direct3D layer for Far Cry 4 = sa2-nx's (SA2's XDK 2.0.21076 has FC4's device layout,
docs/fc4-d3d-map.md) at FC4's addresses.

Copies sa2-nx's app/src/renut_engine/gpu/d3d/{d3d.h, d3d_native.h, d3d_native_state.cpp, hooks/*} over this tree's
(katamari-nx's, whose 2.0.5632 layout is wrong for FC4) and rewrites every SA2 address:
  - hooks: BANJO_RENUT_HOOK*(sub_<SA2>, ...) -> FC4's address from out/fc4_d3d/hook_map.txt (by SA2 address, then by
    the function name in the line's comment). A hook FC4 does not link (DrawVerticesUP) is commented out.
    _SHARED forms become plain ones: FC4 has no native renderer of its own hooking the same addresses.
  - other code addresses (helpers the hooks call, guest data) from DATA below (each found in FC4's code, see notes).
Each rewritten line keeps the SA2 address in a trailing `fc4-nx: SA2 0x...` note. Idempotent: always starts from
sa2-nx's files. Reports every 0x82xxxxxx left in code (not comments) that is not an FC4 address.

  python tools/fc4_d3d/apply_sa2_d3d.py [--sa2 ../refs/sa2-nx] [--dry-run]
"""
import argparse
import os
import re
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DST = os.path.join(ROOT, 'app', 'src', 'renut_engine', 'gpu', 'd3d')
FILES = ['d3d.h', 'd3d_native_state.cpp', 'hooks/device.cpp', 'hooks/draw.cpp', 'hooks/resource.cpp',
         'hooks/shader.cpp', 'hooks/state.cpp', 'hooks/hooks_common.h']

# SA2 -> FC4 for addresses that are not hook targets (docs/fc4-d3d-map.md "Guest data" and fc4-notes.md).
DATA = {
    '82000710': '82000A9C',  # VdGlobalDevice import slot
    '82980268': '84175650',  # XDK build qword (device +11008)
    '82E506F0': '84174F78',  # render state table (101)
    '82E50BD0': '84175438',  # sampler state table (20)
    '82183B00': '822969C0',  # D3DCAPS9 (GetDeviceCaps memcpy source)
    '82FA36C8': '842DACD0',  # HiZ owner
    '820018DC': '82296788',  # full viewport {0, 0, 0xFFFF, 0xFFFF, 0, 1} (EndTiling's SetViewport argument)
    '820052F8': '82296708',  # GPU format table, 64 u16 (FindTextureSize; right before the viewport)
    '82F39E34': '842DC280',  # XPhysicalAlloc's no-large-pages flag (83F3F960 / 83F3F9E8)
    '828074B8': '8241E898',  # the game's XMemFree (what D3DResource_Destroy calls)
    # helpers named in sa2-nx's hooks (docs/fc4-d3d-map.md)
    '8255CDA0': '83F36E40', '8255C808': '83F368A8', '8255C878': '83F36918', '8254D040': '83F2D3A8',
    '825527D8': '83F21FE8', '82557FC0': '83F18FB0',
}
NOT_LINKED = {'D3DDevice_DrawVerticesUP'}
# Words FC4 has no equivalent for (N&B's GPU-workaround switches that sa2-nx left at N&B's addresses; SA2's Fusion flag,
# whose D3D_IsFusion hook FC4 does not place): 0 = absent, and the reads below are guarded.
ABSENT = {'82FAD204', '82FAD208', '82F597B4'}
TEXT_FIXES = [
    ('if (GuestWord(kSkipExportNanVertex))', 'if (kSkipExportNanVertex && GuestWord(kSkipExportNanVertex))'),
    ('if (GuestWord(kSkipExport512Pixels))', 'if (kSkipExport512Pixels && GuestWord(kSkipExport512Pixels))'),
    ('return LoadGuestU32(kFusionVa) != 0 ? 1 : 0;', 'return kFusionVa && LoadGuestU32(kFusionVa) != 0 ? 1 : 0;'),
]


# ---- merges with katamari-nx's newer renderer (the rest of app/src/renut_engine/gpu is katamari-nx's) ----
KAT = os.path.join(ROOT, '..', 'refs', 'katamari-nx', 'app', 'src', 'renut_engine', 'gpu')


def merge_native_header(sa2_src):
    """katamari-nx's d3d_native.h (touch tracking the command buffers use) with sa2-nx's private device offsets."""
    const = re.compile(r'(\s*constexpr u32 (\w+)\s*=\s*)([0-9xA-Fa-f]+)(\s*;)')
    sa2 = {}
    for l in open(os.path.join(sa2_src, 'd3d_native.h'), encoding='utf-8'):
        m = const.match(l)
        if m:
            sa2[m.group(2)] = m.group(3)
    out = []
    for l in open(os.path.join(KAT, 'd3d', 'd3d_native.h'), encoding='utf-8').read().split('\n'):
        m = const.match(l)
        if m and m.group(2) in sa2 and int(m.group(3), 0) != int(sa2[m.group(2)], 0):
            l = m.group(1) + sa2[m.group(2)] + m.group(4) + l[m.end():] + '  // fc4-nx: SA2/FC4 layout (katamari-nx ' + m.group(3) + ')'
        # the private render state: N&B 0x2E00-0x2EFF, katamari-nx 0x2DF4, SA2/FC4 +0x1A0 (the vertex declaration
        # N&B 0x2E30 -> 12240); a wider range only marks more chunks dirty.
        l = l.replace('TouchBits(0x2DF4, 0x108);', 'TouchBits(0x2F80, 0x140);  // fc4-nx: SA2/FC4 private render state')
        out.append(l)
    return '\n'.join(out)


# guest/resources.h stays katamari-nx's (its draw / command-buffer code needs its records; docs/fc4-notes.md)
SA2_EXTRA = ['sa2_renut_pacing.h', 'sa2_renut_pacing.cpp']
FILE_FIXES = {
    'hooks/device.cpp': [
        ('#include "sa2_capture.h"                            // sa2-nx: lockstep captures\n', ''),
        ('#include "me/sa2_render_mode.h"                     // sa2-nx (1.0.3.1): the PC\'s docked test toggles\n', ''),
        ('extern std::atomic<uint64_t> g_sa2_game_frames;',
         'std::atomic<uint64_t> g_sa2_game_frames{0};  // fc4-nx: defined here (sa2-nx\'s app defines it)'),
        ('  sa2::render::OnPresented(game_frame);\n', '  (void)game_frame;  // fc4-nx: no sa2-nx render-mode toggles\n'),
        ('  const uint64_t capture_ticket = sa2::capture::RenutLockstepOn() ? RequestFrameCapture() : 0;\n', ''),
        ('  if (capture_ticket) {\n    rex::ui::RawImage image;\n    const bool ok = WaitFrameCapture(capture_ticket, image, 2000);\n'
         '    sa2::capture::RenutLockstepFrame(game_frame, ok ? &image : nullptr);\n  }\n', ''),
        ('    if (REXCVAR_GET(sa2_renut_gamma_ramp))\n      Video::SetGammaRamp(device + kSa2DeviceOffsetGammaRamp);\n',
         "    // fc4-nx: no gamma ramp at scan-out yet (sa2-nx's Video::SetGammaRamp / present.cpp not ported)\n"),
    ],
    'sa2_renut_pacing.cpp': [
        ('  bool hold = ::banjo::display_sync::TakeHold();',
         "  bool hold = false;  // fc4-nx: katamari-nx's display_sync has no TakeHold (sa2_renut_queue_drain)"),
        ('#include "cpu/sa2_enhancements.h"', '#include "renut_engine/gpu/fc4_sa2_shim.h"  // fc4-nx: sa2-nx\'s enhancement toggle'),
    ],
}


def load_map():
    by_sa2, by_name = {}, {}
    for line in open(os.path.join(ROOT, 'out', 'fc4_d3d', 'hook_map.txt'), encoding='utf-8'):
        if line.startswith('#') or not line.strip():
            continue
        c = re.split(r'\s{2,}', line.rstrip('\n'))
        if len(c) < 6 or c[3] == '-':
            continue
        name, fc4, sa2 = c[2], c[3].upper(), c[4].upper()
        if sa2 != '-':
            by_sa2[sa2] = fc4
        by_name.setdefault(name, fc4)
    return by_sa2, by_name


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sa2', default=os.path.join(ROOT, '..', 'refs', 'sa2-nx'))
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()
    src = os.path.join(a.sa2, 'app', 'src', 'renut_engine', 'gpu', 'd3d')
    by_sa2, by_name = load_map()
    fc4_values = set(by_sa2.values()) | set(by_name.values()) | set(DATA.values()) | {'00000000'}
    hook_re = re.compile(r'BANJO_RENUT_(HOOK(?:_RAW)?)(_SHARED)?\(sub_([0-9A-F]{8})')
    stats = {'hooks': 0, 'disabled': 0, 'data': 0}
    leftovers = []
    for rel in FILES:
        text = open(os.path.join(src, rel), encoding='utf-8').read().split('\n')
        out = []
        for line in text:
            code, sep, comment = line.partition('//')
            m = hook_re.search(code)
            if m:
                kind, shared, sa2 = m.groups()
                name_m = re.search(r'//\s*(\w+)', line)
                name = name_m.group(1) if name_m else ''
                fc4 = by_sa2.get(sa2) or by_name.get(name)
                if name in NOT_LINKED or not fc4:
                    out.append('// fc4-nx: not linked in Far Cry 4: ' + line)
                    stats['disabled'] += 1
                    continue
                code = code[:m.start()] + 'BANJO_RENUT_%s(sub_%s' % (kind, fc4) + code[m.end():]
                line = code + sep + comment + '  // fc4-nx: SA2 sub_' + sa2
                stats['hooks'] += 1
            else:
                def sub(mm):
                    addr = mm.group(2).upper()
                    new = '00000000' if addr in ABSENT else DATA.get(addr) or by_sa2.get(addr)
                    if not new:
                        return mm.group(0)
                    stats['data'] += 1
                    return mm.group(1) + new
                new_code = re.sub(r'(sub_|0x)(82[0-9A-Fa-f]{6})\b', sub, code)
                if new_code != code:
                    line = new_code + sep + comment + ('' if 'fc4-nx: SA2' in comment else '  // fc4-nx: was SA2')
                code = new_code
            for old, new in TEXT_FIXES:
                line = line.replace(old, new)
            for addr in re.findall(r'(?:sub_|0x)(8[2-4][0-9A-Fa-f]{6})\b', line.partition('//')[0]):
                if addr.upper() not in fc4_values and rel != 'hooks/state.cpp':
                    leftovers.append('%s: %s' % (rel, addr))
            out.append(line)
        if not a.dry_run:
            dst = os.path.join(DST, rel)
            open(dst, 'w', encoding='utf-8', newline='\n').write('\n'.join(out))
    if not a.dry_run:
        open(os.path.join(DST, 'd3d_native.h'), 'w', encoding='utf-8', newline='\n').write(merge_native_header(src))
        gpu_src = os.path.dirname(src)
        for rel in SA2_EXTRA:
            shutil.copyfile(os.path.join(gpu_src, rel.replace('../gpu/', '')), os.path.join(os.path.dirname(DST), rel.replace('../gpu/', '')))
        # hooks/shader.cpp: katamari-nx's (its records feed its draw / command-buffer code) with sa2-nx's observe-only
        # hooks (tools/fc4_d3d/fc4_shader_observe.inc.txt) in place of its six hook lines.
        kat = open(os.path.join(KAT, 'd3d', 'hooks', 'shader.cpp'), encoding='utf-8').read().split('\n')
        kat = ['// fc4-nx: sa2-nx observe hooks below: ' + l if re.match(r'BANJO_RENUT_\w*HOOK\w*\(sub_', l) else l for l in kat]
        block = open(os.path.join(ROOT, 'tools', 'fc4_d3d', 'fc4_shader_observe.inc.txt'), encoding='utf-8').read()
        open(os.path.join(DST, 'hooks', 'shader.cpp'), 'w', encoding='utf-8', newline='\n').write(
            '\n'.join(kat).rstrip('\n') + '\n\n' + block)
        # d3d_native_state.cpp: sa2-nx's, plus katamari-nx's touch-slot functions (its d3d_native.h declares them).
        kst = open(os.path.join(KAT, 'd3d', 'd3d_native_state.cpp'), encoding='utf-8').read()
        touch = kst[kst.index('// banjo-nx (2026-10-26, banjo_renut_tags): the slots of d3d_native.h.'):kst.rindex('}  // namespace renut::gpu::native')]
        path = os.path.join(DST, 'd3d_native_state.cpp')
        st = open(path, encoding='utf-8').read()
        end = st.rindex('}  // namespace renut::gpu::native')
        open(path, 'w', encoding='utf-8', newline='\n').write(st[:end] + '// fc4-nx: katamari-nx' + chr(39) + 's touch slots' + '\n' + touch + st[end:])
        for rel, fixes in FILE_FIXES.items():
            path = os.path.join(DST if rel.startswith('hooks/') else os.path.dirname(DST), rel)
            text = open(path, encoding='utf-8').read()
            for old, new in fixes:
                if old not in text:
                    print('  FIX NOT APPLIED in', rel, ':', old.strip()[:70])
                text = text.replace(old, new)
            open(path, 'w', encoding='utf-8', newline='\n').write(text)
    print('apply_sa2_d3d: %(hooks)d hooks moved to FC4, %(disabled)d not linked, %(data)d data/helper addresses' % stats)
    for l in sorted(set(leftovers)):
        print('  left (check):', l)


if __name__ == '__main__':
    main()
