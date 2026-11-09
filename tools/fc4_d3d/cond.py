import sys, re
lo, hi = int(sys.argv[1], 16), int(sys.argv[2], 16)
mn = int(sys.argv[3]) if len(sys.argv) > 3 else 10944
for ln in open('out/fc4_d3d/funcs_summary.txt'):
    a = int(ln[:8], 16)
    if not lo <= a < hi: continue
    f = dict(re.findall(r'(\w+)=(\[[^\]]*\]|\S*)', ln))
    def hi_(k): return [x for x in eval(f[k]) if x >= mn]
    c = f['calls'].split(',') if f['calls'] else []
    print(f"{a:08X} {f['n']:>4} c{f['cal']:<6} st{hi_('st')} ld{hi_('ld')} -> {','.join(c[:8])}{'..' if len(c) > 8 else ''} {('T:' + f['tail']) if f['tail'] else ''} {('D:' + f['data']) if f['data'] else ''}")
