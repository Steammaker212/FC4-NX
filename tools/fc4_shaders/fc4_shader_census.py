#!/usr/bin/env python3
"""fc4-nx (2026-11-09): translation census of Far Cry 4's shader containers through the base's chain
(tools/switch_shaders.ps1), one shader at a time so that one failure never hides another:

  1. translate  Renut's XenosRecomp (RENUT_RECOMP) on the container alone: `XenosRecomp <container> <out.hlsl>
                <shader_common.h>` writes the HLSL (shader_common.h inside) its directory mode would dump;
  2. dxil       DXC with XenosRecomp's own DXIL arguments (lib_6_3 when the shader reads specialization constants),
                as the PC build's shader cache compiles it;
  3. spirv      DXC with the deko3d arguments (BANJO_DEKO3D_SPIRV_DIR: -spirv -fvk-use-dx-layout -DBANJO_DEKO3D);
                needs a DXC built with SPIR-V code generation (the Windows SDK's is not);
  4. glsl, uam  tools/deko3d_shaders.py's step per shader: SPIRV-Cross -> tools/deko3d_glsl.py -> uam (default
                variant), with the SPIRV-Cross and uam given here.

A stage whose tool is missing is reported as not run. Output (<out>, default out/fc4_shaders/census): hlsl/, dxil/,
spirv/, vk/, glsl/, dksh/, census.tsv (a line per shader) and report.txt (counts, failure classes with examples,
sizes). Runs at most --jobs processes (default 6) at below-normal priority.

  python tools/fc4_shaders/fc4_shader_census.py [--containers out/fc4_shaders/containers] [--out out/fc4_shaders/census]
      [--dxc <folder with dxc.exe>] [--dxc-spirv <folder with a SPIR-V-capable dxc.exe>] [--spirv-cross <exe>]
      [--uam <exe>] [--jobs 6] [--limit N]
"""
import argparse
import collections
import concurrent.futures
import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
OUT_DEFAULT = os.path.join(ROOT, 'out', 'fc4_shaders')
XENOS_RECOMP = os.path.join(OUT_DEFAULT, 'build', 'xenos_recomp', 'XenosRecomp-ALL', 'XenosRecomp', 'XenosRecomp.exe')
SHADER_COMMON = os.path.join(ROOT, 'app', 'thirdparty', 'reblue-XenosRecomp', 'XenosRecomp', 'shader_common.h')
UAM = os.path.join(OUT_DEFAULT, 'build', 'uam', 'uam.exe')
SDK_DXC = r'C:\Program Files (x86)\Windows Kits\10\bin\10.0.26100.0\x64'
TIMEOUT = 300
FLAGS = 0x00004000 if os.name == 'nt' else 0  # BELOW_NORMAL_PRIORITY_CLASS

if os.name == 'nt':
    import ctypes
    # No crash dialogs from children (inherited): a crashing translator must return, not wait for a click.
    ctypes.windll.kernel32.SetErrorMode(0x0001 | 0x0002 | 0x8000)


def run(cmd, **kw):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, errors='replace', timeout=TIMEOUT,
                           creationflags=FLAGS, **kw)
        return r.returncode, (r.stdout or '') + (r.stderr or '')
    except subprocess.TimeoutExpired:
        return 'timeout', ''


def first_error(log):
    for line in log.splitlines():
        if 'error' in line.lower():
            return line.strip()
    return log.strip().splitlines()[0].strip() if log.strip() else ''


def error_class(detail):
    """A failure's message without what differs per shader (paths, positions, numbers, names of registers)."""
    d = re.sub(r'^.*?\.hlsl:\d+:\d+:\s*', '', detail)
    d = re.sub(r'0x[0-9a-fA-F]+|\b[0-9a-f]{16}\b', 'H', d)
    d = re.sub(r'\d+', 'N', d)
    d = re.sub(r"'[^']*'", "'X'", d)
    return d[:170]


class Census:
    def __init__(self, a):
        self.a = a
        self.shader_common = a.shader_common
        self.common = open(a.shader_common, encoding='utf-8', errors='replace').read()
        for d in ('hlsl', 'dxil', 'spirv', 'vk', 'glsl', 'dksh', 'log'):
            os.makedirs(os.path.join(a.out, d), exist_ok=True)
        self.dxc = os.path.join(a.dxc, 'dxc.exe') if a.dxc else None
        self.dxc_spirv = os.path.join(a.dxc_spirv, 'dxc.exe') if a.dxc_spirv else None
        self.deko = None
        if a.spirv_cross and os.path.isfile(a.spirv_cross):
            import deko3d_shaders
            deko3d_shaders.SPIRV_CROSS = a.spirv_cross
            deko3d_shaders.UAM = a.uam
            deko3d_shaders.NO_UAM = not os.path.isfile(a.uam)
            self.deko = deko3d_shaders

    def path(self, sub, stem, ext):
        return os.path.join(self.a.out, sub, stem + ext)

    def note(self, stem, stage, log):
        with open(self.path('log', stem, '.%s.txt' % stage), 'w', encoding='utf-8') as f:
            f.write(log)

    def dxc_args(self, stem, spec, spirv):
        args = ['-T', 'lib_6_3' if spec and not spirv else ('ps_6_0' if stem.startswith('ps') else 'vs_6_0'),
                '-HV', '2021', '-all-resources-bound']
        args += ['-spirv', '-fvk-use-dx-layout', '-DBANJO_DEKO3D'] if spirv else ['-Wno-ignored-attributes',
                                                                                  '-Qstrip_reflect']
        return args + ['-Qstrip_debug', '-DRENUT_RECOMP']

    def one(self, container):
        stem = os.path.basename(container)[:-4]
        r = {'stem': stem, 'stage': stem[:2], 'microcode': os.path.getsize(container)}
        hlsl = self.path('hlsl', stem, '.hlsl')
        t0 = time.time()
        rc, log = run([self.a.xenos_recomp, container, hlsl, self.shader_common])
        r['translate_ms'] = int((time.time() - t0) * 1000)
        if rc != 0 or not os.path.isfile(hlsl) or os.path.getsize(hlsl) == 0:
            self.note(stem, 'translate', log)
            r['translate'] = 'timeout' if rc == 'timeout' else ('exit 0x%08X' % (rc & 0xFFFFFFFF) if rc
                                                                else 'no output')
            r['translate_detail'] = first_error(log)
            return r
        r['translate'] = 'ok'
        # What the translator says on stderr about a shader it still translates (a vfetch it cannot place, an eA
        # export it does not recognise): the HLSL exists but may be wrong there.
        warns = sorted(set(l.strip() for l in log.splitlines() if l.strip()))
        if warns:
            self.note(stem, 'translate', log)
            r['translate_warn'] = ' | '.join(warns)[:300]
        text = open(hlsl, encoding='utf-8', errors='replace').read()
        body = text[len(self.common):] if text.startswith(self.common) else text
        r['hlsl_body'] = len(body)
        spec = 'g_SpecConstants()' in body or 'tfetchR11G11B10(' in body
        r['spec'] = int(spec)
        for stage, exe, spirv, ext in (('dxil', self.dxc, False, '.dxil'), ('spirv', self.dxc_spirv, True, '.spv')):
            if not exe:
                r[stage] = 'not run'
                continue
            out = self.path(stage, stem, ext)
            rc, log = run([exe] + self.dxc_args(stem, spec, spirv) + [hlsl, '-Fo', out])
            if rc != 0 or not os.path.isfile(out):
                self.note(stem, stage, log)
                r[stage] = 'failed'
                r[stage + '_detail'] = first_error(log)
            else:
                r[stage] = 'ok'
                r[stage + '_bytes'] = os.path.getsize(out)
        if r.get('spirv') != 'ok' or not self.deko:
            r['glsl'] = 'not run'
            return r
        _, reason, detail, size, warnings = self.deko.one(self.path('spirv', stem, '.spv'), self.a.out)
        if reason in ('spirv-cross', 'convert'):
            r['glsl'], r['glsl_detail'] = 'failed: ' + reason, detail
            return r
        r['glsl'] = 'ok'
        r['glsl_bytes'] = os.path.getsize(self.path('glsl', stem, '.glsl'))
        if self.deko.NO_UAM:
            r['uam'] = 'not run'
        elif reason == 'uam':
            r['uam'], r['uam_detail'] = 'failed', detail
        else:
            r['uam'], r['dksh_bytes'] = 'ok', size
        return r


COLUMNS = ['stem', 'stage', 'microcode', 'translate', 'translate_ms', 'translate_warn', 'hlsl_body', 'spec', 'dxil',
           'dxil_bytes', 'spirv', 'spirv_bytes', 'glsl', 'glsl_bytes', 'uam', 'dksh_bytes', 'detail']


def report(rows, a):
    lines = ['%d shader containers (%d vertex, %d pixel) from %s' % (
        len(rows), sum(r['stage'] == 'vs' for r in rows), sum(r['stage'] == 'ps' for r in rows), a.containers)]
    for stage in ('translate', 'dxil', 'spirv', 'glsl', 'uam'):
        c = collections.Counter((r['stage'], r.get(stage, '-')) for r in rows)
        parts = []
        for st in ('vs', 'ps'):
            ok = c[(st, 'ok')]
            other = {k[1]: v for k, v in c.items() if k[0] == st and k[1] != 'ok'}
            parts.append('%s %d ok%s' % (st, ok, ''.join(', %d %s' % (v, k) for k, v in sorted(other.items()))))
        lines.append('%-9s %s' % (stage, ' | '.join(parts)))
    for stage in ('translate', 'dxil', 'spirv', 'glsl', 'uam'):
        failed = [r for r in rows if r.get(stage) not in ('ok', 'not run', None)]
        if not failed:
            continue
        lines.append('\n[%s failures] %d' % (stage, len(failed)))
        by = collections.defaultdict(list)
        for r in failed:
            by[(r[stage], error_class(r.get(stage + '_detail', '')))].append(r)
        for (status, cls), items in sorted(by.items(), key=lambda kv: -len(kv[1]))[:25]:
            vs = sum(i['stage'] == 'vs' for i in items)
            lines.append('  %5d (%d vs, %d ps)  %s: %s   e.g. %s' % (len(items), vs, len(items) - vs, status, cls,
                                                                  ', '.join(i['stem'] for i in items[:3])))
    warned = [r for r in rows if r.get('translate_warn')]
    if warned:
        lines.append('\n[translated with translator warnings] %d' % len(warned))
        by = collections.defaultdict(list)
        for r in warned:
            for w in r['translate_warn'].split(' | '):
                by[error_class(w)].append(r)
        for cls, items in sorted(by.items(), key=lambda kv: -len(kv[1])):
            vs = sum(i['stage'] == 'vs' for i in items)
            lines.append('  %5d (%d vs, %d ps)  %s   e.g. %s' % (len(items), vs, len(items) - vs, cls,
                                                               ', '.join(i['stem'] for i in items[:3])))
    lines.append('\nreading specialization constants (DXIL as lib_6_3): %d vs, %d ps' % (
        sum(r.get('spec', 0) for r in rows if r['stage'] == 'vs'),
        sum(r.get('spec', 0) for r in rows if r['stage'] == 'ps')))
    lines.append('\n[sizes] bytes (microcode = the whole container): median / max / total')
    for key in ('microcode', 'hlsl_body', 'dxil_bytes', 'spirv_bytes', 'glsl_bytes', 'dksh_bytes', 'translate_ms'):
        for st in ('vs', 'ps'):
            v = sorted(r[key] for r in rows if r['stage'] == st and key in r)
            if v:
                lines.append('  %-12s %s %5d: %8d / %8d / %11d' % (key, st, len(v), v[len(v) // 2], v[-1], sum(v)))
    return '\n'.join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--containers', default=os.path.join(OUT_DEFAULT, 'containers'))
    ap.add_argument('--out', default=os.path.join(OUT_DEFAULT, 'census'))
    ap.add_argument('--xenos-recomp', default=XENOS_RECOMP)
    ap.add_argument('--shader-common', default=SHADER_COMMON, help='the shader_common.h XenosRecomp includes')
    ap.add_argument('--dxc', default=SDK_DXC, help='folder with dxc.exe for DXIL ("" to skip)')
    ap.add_argument('--dxc-spirv', default='', help='folder with a dxc.exe that has SPIR-V code generation')
    ap.add_argument('--spirv-cross', default='', help='spirv-cross.exe (for the GLSL and uam steps)')
    ap.add_argument('--uam', default=UAM)
    ap.add_argument('--jobs', type=int, default=6)
    ap.add_argument('--limit', type=int, default=0)
    a = ap.parse_args()
    for k in ('containers', 'out', 'xenos_recomp', 'shader_common', 'dxc', 'dxc_spirv', 'spirv_cross', 'uam'):
        if getattr(a, k):
            setattr(a, k, os.path.abspath(getattr(a, k)))
    files = sorted(os.path.join(a.containers, n) for n in os.listdir(a.containers)
                   if re.fullmatch(r'(vs|ps)_[0-9a-f]{16}\.bin', n))
    if a.limit:
        files = files[:a.limit]
    census = Census(a)
    rows, t0 = [], time.time()
    with concurrent.futures.ThreadPoolExecutor(a.jobs) as ex:
        for i, r in enumerate(ex.map(census.one, files)):
            rows.append(r)
            if (i + 1) % 500 == 0:
                print('%d/%d (%.0f s)' % (i + 1, len(files), time.time() - t0), flush=True)
    with open(os.path.join(a.out, 'census.tsv'), 'w', encoding='utf-8', newline='\n') as f:
        f.write('\t'.join(COLUMNS) + '\n')
        for r in rows:
            r['detail'] = next((r[k] for k in ('translate_detail', 'dxil_detail', 'spirv_detail', 'glsl_detail',
                                               'uam_detail') if k in r), '').replace('\t', ' ')
            f.write('\t'.join(str(r.get(c, '')) for c in COLUMNS) + '\n')
    text = report(rows, a) + '\n\n%.0f s, %d jobs' % (time.time() - t0, a.jobs)
    with open(os.path.join(a.out, 'report.txt'), 'w', encoding='utf-8') as f:
        f.write(text + '\n')
    print(text)


if __name__ == '__main__':
    sys.exit(main())
