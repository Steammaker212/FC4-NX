# Far Cry 4 (Xbox 360) -> Switch: port notes

Started 2026-11-09 from katamari-nx (base, files copied without history), with renut-nx's `docs/` as the method docs and
sa2-nx for reference. Game data is never committed or distributed (`app/assets` is a junction to `../../game`,
outside the repo).

## The disc

`Far Cry 4 (USA) (En,Fr,Es,Pt).iso`: XGD3, game partition at `0x2080000`, 7.29 GB of files.

| File | What it is |
|---|---|
| `default.xex` | The XUI **installer** (original PE name `installer.exe`, image 2.2 MiB, entry `0x82152690`). Copies `installation1/` to the HDD on a real console |
| `game.xex` | **The game** (original PE name `default.exe`, image 35.6 MiB at `0x82000000`, entry `0x83F3F630`). Codegen target |
| `UplayBrowser.xex` | Uplay overlay; not needed |
| `installation1/*.dat/.fat` | Install-to-HDD data: `worlds/fcc_main` (2.1 GB, Kyrat), `multicommon` (1.2 GB), `common`, `ige`, `shadersobj` (7.6 MB: the shader package) |
| `sound*.dat/.fat`, `worlds/*_<lang>.dat` | Audio and localized data, streamed from disc |

Dunia 2 (Ubisoft Montreal). Data in `.dat` archives indexed by `.fat` files.

## game.xex header

- Title ID `555308CA`, media ID `1482D1EF`, version 0.0.0.5, disc 1/1.
- XDK **2.0.21256** QFE 0 (D3D9, D3DX9, XAUDIO2, XMCORE, XHV2, XONLINE ...): the same XDK as Peggle 2, the newest in
  renut-nx's `docs/xdk-versions.md` table, so reNut's D3D layout work for 21256 applies.
- Two compilers linked: C1/C2 16.0.11886 (XDK libraries) and 16.10.16045 (the game). Linker 10.10.16045.
- Imports: xam.xex 282 records, xboxkrnl.exe 368 records (min kernel 2.0.16537).
- Encrypted (1) and compressed (2, normal LZX): rexglue decrypts and decompresses.

## Decisions

- Internal project name stays `renut` (as katamari-nx did), so the base's CMake and post-codegen passes work unchanged.
- Katamari's codegen addresses removed: `app/renut_config.toml` (setjmp/longjmp, keep lists), `app/config/renut_funcs.toml`,
  `app/overrides.toml`. First codegen runs WITHOUT `non_volatile_as_local`, `elide_lr_stores` and
  `non_argument_as_local`; each needs its audit on FC4's code first.
- **Frame-rate target (the user, 2026-11-09):** a stable 30 fps floor, higher whenever the frame allows it, lower only
  when it must, and **game speed constant at all times** whatever the frame rate. So: no fixed 60 target; the game's
  own pacing (its present interval / vsync wait) is not forced to 30 as a cap, and its simulation must run on real time,
  not on frames. To check on the first boots: how Dunia steps its simulation (variable delta from the timebase /
  `KeQueryPerformanceFrequency`, or a fixed step per frame or per vblank), and whether uncapping changes game speed.
  Renut's dynamic resolution (`banjo_renut_dynamic_steps`, by GPU time) is the tool for holding the floor on the GPU
  side.
- Testing: the user's Ryubing (canary 1.3.272, `C:\Users\Saif Khan\Documents\Emulation\Emulator's\ryujinx-canary-1.3.272-win_x64\publish\Ryujinx.exe`,
  keys and firmware in `%APPDATA%\Ryujinx`). This port gets its own data folder (system, keys, firmware copied; not
  the user's sdcard), started with `-r <folder>`. Console: the user's Atmosphere Switch.
- Git: local commits as the work goes; the user pushes.
- Host toolchain on this PC: `tools/fc4_env.bat` (VS 18 Build Tools 14.51, LLVM 23.1.3 at `C:\Program Files\LLVM`,
  Python 3.15). devkitPro's msys2 `clang64` is not installed here.

## Feasibility (read before expecting 60 fps)

- Banjo-Kazooie: Nuts & Bolts (2008), the most optimised port of this family, reaches 20-21 fps in its heaviest scene on
  stock clocks (render thread ~8 us a draw at ~5,000 draws; GPU ~40 ms at 648 lines). Katamari: 60 fps in menus, 19-47 fps
  in big stages.
- Far Cry 4 (2014) is a late, heavily threaded open-world title that already ran at a target of 30 fps (with drops) on
  the Xbox 360's six hardware threads at 3.2 GHz. The Switch has three usable A57 cores at 1020 MHz (four via a
  forwarder), and recompiled PPC code carries byte-swap and context overhead.
- **60 fps is not a realistic target.** The game's simulation is also very likely tied to a 30 Hz step. A first
  realistic goal is booting to the menu and in-game on the PC build, then the Switch build drawing, then measuring.

## The loaded image (`out/renut_image.bin`, `tools/fc4_image_scan.py sections`)

| Section | Range | Size |
|---|---|---|
| `.rdata` | `0x82000600-0x822F3D2C` | 2.95 MiB |
| `.pdata` | `0x822F3E00-0x823F8E60` | 1.02 MiB: **133,644 function entries** |
| `.text` | `0x82400000-0x840B9110` | **28.72 MiB** of PPC code |
| `BINK`, `RADCODE` | `0x840B9200-0x840E458C` | Bink video (RAD): movies are `.bik` |
| `.data` | `0x840F6000-0x842F0FD8` | 1.98 MiB |

Scale against the base: Katamari's code range was 8 MiB with 37,763 functions; Far Cry 4 has ~3.6x the code and
~3.5x the functions. Expect generated C++ around 0.8-1 GB, long Switch compile times, and an NRO of a few hundred MB
(Katamari: 60 MB for 8 MiB of PPC with 1,500 machine copies).

- **setjmp `0x83FBE870`, longjmp `0x83FC0A80`** (by shape; `app/renut_config.toml` has the instructions).
- **Fibers: the game uses them.** XAPI's fiber functions are linked statically: ConvertThreadToFiber `0x83F45F20`,
  ConvertFiberToThread `0x83F45FB0`, CreateFiber `0x83F46000`, DeleteFiber `0x83F460E0`, SwitchToFiber `0x83F46140`
  (`b 0x83F4EAC0`, the body that swaps r1 / LR / non-volatiles through `*(*(r13+0x100)+0x164)`). Callers: a fiber
  scheduler at `0x83ACF2C0`-`0x83ADD49C` (ConvertThreadToFiber + CreateFiber at `0x83ADD434` / `0x83ADD450`, four
  SwitchToFiber sites). Recompiled code cannot swap the guest stack in place, so the five are hooked to the SDK's host
  fibers (`[rexcrt]` in `app/config/renut_crt.toml`; `sdk/src/kernel/crt/threading.cpp`, `core/fiber_*.cpp`). On the
  Switch that is `fiber_switch.cpp`: a fiber switch costs a host context switch; count them on the first runs.

## Shaders

`installation1/shadersobj.fat` is a Dunia `FAT2` index, version 9, **6,765 entries**; `shadersobj.dat` holds them
LZMA-compressed (`5D 00 00 80 00` headers). Katamari had 195 shaders and Banjo ~1,000s: the deko3d shader package and
on-console uam compile cache (`deko3d_shaders.bin`) will be much larger, and first-play stutter longer. The renderer
census must also check whether shaders are created at run time from this package (XGRegisterVertexShader / PixelShader
hooks capture them).

## Renderer starting point

XDK 2.0.21256 is next to SA2's 2.0.21076 and Sonic Transformed's 2.0.21119, which share one Direct3D device layout
(sa2-nx `docs/renut-renderer.md`, "SA2's Direct3D against N&B's": device 0x6080 bytes, bound objects +376, 0x3400 on
+400-412 against N&B). Start FC4's Renut hook map and device offsets from **sa2-nx's** (`d3d/d3d.h`, `d3d_native.h`, the
"sa2-nx" hook blocks), not from N&B's or Katamari's (2.0.5632).

First evidence (2026-11-09): **`Direct3D_CreateDevice` is `0x83F18AB0`** (SA2 `0x8254FC10`): `*r8 = 0`, then
`li r4,0x80; li r3,0x6080; bl 0x83F188E8` (the allocator), `0x8007000E` (E_OUTOFMEMORY) when it returns null. The
device is **0x6080 bytes, exactly SA2's** (N&B 0x5E00, Katamari 0x5700); `li rN,0x6080` appears nowhere else in `.text`.
The XDK's code sits at the end of `.text` (`0x83Fxxxxx`, with setjmp/longjmp and the fiber switch).

## Code generation

Each run takes 20-24 minutes on this PC (i9-12900K), single-threaded in the analysis phases (GapFill is most of it).

- **Run 1** (1,216 s): failed validation, 18 "target not in any function" at 13 addresses, every one a function start
  after a terminator reached only by thunk tail jumps (`app/config/renut_funcs.toml`, each with its instructions).
- **Run 2** (1,416 s, setjmp / longjmp set): **passed**. 947 files, 507 MB of C++ (Katamari: 269 files, ~220 MB). One
  warning: the unresolved `b 0x83F4EAC0` in SwitchToFiber, answered by the rexcrt fiber hooks (above).
- Post-codegen passes (`tools/post_codegen.py`): **179,905 functions**; store cards on ~480,000 guest stores; 16,930
  tiny leaves inlined across files. About 15 minutes.
- `tools/pointer_fixpoint.py` / `tools/gap_sweep.py` (functions only reachable through data pointers or computed
  addresses; Katamari needed 111 + 85) and `tools/switch_check.py` (jump tables): running (below). Each pass of the
  first two is a scratch codegen plus a real one, so about 45 minutes a pass here. Pass 1 of the pointer sweep: 94,342
  gaps, 600 candidates.

### Base tools that named default.xex (fixed 2026-11-09)

The base's tools assume the game is `default.xex`. For Far Cry 4 that is the installer, so:

- `tools/post_codegen.py` gave `ro_constants.py` / `ro_constants_cfg.py` the installer's XEX for the import records
  (loads of imported kernel variables must stay loads). The first PC build's generated tree was processed with the
  wrong records; it is regenerated from scratch by the next codegen. Now `app/assets/game.xex`.
- `tools/pointer_fixpoint.py`'s scratch manifest: now `game.xex`. Its first try ran the scratch codegen on the
  installer with `REXGLUE_DUMP_IMAGE` set in the shell, which overwrote `out/renut_image.bin` with the installer's
  2.2 MiB image: never export `REXGLUE_DUMP_IMAGE` around the sweeps (`tools/codegen.ps1` sets it for the real
  codegen). Re-dumped from a scratch codegen stopped after the "written to" line (`out/imgdump`).
- The SDK loads `game:\default.xex` unless the app says otherwise: `OnLoadXexImage` in `app/src/renut_app.h` now
  returns `game:\game.xex`.

## First PC boots (2026-11-09, SDK presenter + emulated Xenos, `tools/fc4_run_pc.ps1`)

- **boot1-3:** nothing after D3D12 init: the app's path wizard (an ImGui dialog) waited for input with the paths
  already on the command line. Without Renut the app now creates no dialogs (`renut_app.h`, OnCreateDialogs), as
  katamari-nx does under the emulated renderer. Link fix: `src/fc4_display_sync_off.cpp` (the frame limiter's display
  anchor lives in the Renut library).
- **boot4:** game.xex loads; 180,229 recompiled functions registered; imports resolve (xam 141, xboxkrnl 190); the
  game creates six job threads `Core_0..2 - Thread 0/1`, each `ConvertThreadToFiber` + `CreateFiber(0x83ADD348,
  128 KB)` on host fibers (works). It then opens `game:\common.dat`, `game:\shadersobj.dat` and
  `game:\generated\databases\generic\datapaths.ndb` and stops in `XamShowDirtyDiscErrorUI`: the installed archives
  are expected in the game's root.
- **The installed layout:** `tools/fc4_install_layout.py <game>` hard-links every file of `installation1/` to the same
  path under the game folder (what the disc's installer does on the console, without copying 3.6 GB).
- **boot5:** the archives open, no dirty-disc error; then `Call to invalid or unregistered function at guest address
  0x82470838` (a function after a `b`, no stored pointer: the gap-sweep case). Expected probes that fail harmlessly:
  `cmdline.ini`, `startup.dat`, `update:\patch.dat` (no title update), `sound_german/russian.dat`, `game:\Output\Xenon`
  (a debug output folder on a read-only device).
- **Function sweeps (2026-11-09):** `tools/pointer_fixpoint.py` 575 accepted (3 later removed: rexcrt-hooked fiber
  functions), `tools/gap_sweep.py` 628 accepted; 1,200 declared in `app/overrides.toml`. boot6 then stopped on
  `0x82468860`, which the pointer sweep had rejected ("tail branch into a function body": its `bne` lands on the next
  registered function); declared with `end = 0x82468870` in `app/config/renut_funcs.toml`.
- **boot7:** past XAM / XMP setup; XAudio's render driver registers and frames flow (SDL, 48 kHz); the controller is
  found; `NetDll_XHttpStartup` / `XHttpOpen` are stubs. Paths come out as `(null)engine\shaders\...` and
  `(null)engine\settings\overriderenderprofilerconfig.xml` (a root-path string is NULL: find who formats them) and
  `engine\shaders\obj\index.vso/.pso/.rs` resolve to no device. Then three guest access violations: thread F80000B4 in
  `sub_83AC94B8` (the fiber scheduler's range, 0x83ACxxxx), F800014C in `sub_83930888`, F8000094 in `sub_824FB800`
  (symbolised with LLVM's llvm-symbolizer on renut.exe + renut.pdb). Next: read the three in IDA (`out/fc4_image.elf.i64`,
  Hex-Rays works) and the path-root NULL.
- A stale precompiled header after a codegen + post-codegen run ("renut_pch.h has been modified since the precompiled
  header"): delete `app/out/pc/CMakeFiles/renut_recomp.dir/cmake_pch.hxx.pch` and build again.

## Reverse-engineering tools (2026-11-09)

- IDA Pro 9.3 with the Hex-Rays PowerPC decompiler, headless through idalib: `tools/fc4_image_elf.py` wraps the image
  as a PPC ELF (`out/fc4_image.elf`, analysed once into `out/fc4_image.elf.i64`: 158,734 functions, 263 s), and
  `tools/fc4_ida.py decompile|callers|xrefs|strings|disasm|func` answers questions in about 6 s each.
- REA 6.8.0 is registered for Claude Code (IDA provider), but its IDA adapter has no PowerPC lane and its Windows
  Ghidra lane takes PE files only: `open_binary` refuses this image. `tools/fc4_ida.py` is the way in.

## boot7's crashes, first reading

- `sub_83AC94B8`: a lock-free pop on a {head, tag} doubleword (`ldarx` / `stdcx.` 64-bit), 21 callers, all in the fiber
  job scheduler (0x83ACxxxx-0x83ADxxxx). The generated C++ is a faithful 64-bit CAS; the head word itself was bad
  (0x20611840, unmapped).
- `sub_824FB800`: a hash-map find (Park-Miller hash of `key ^ 0xDEADBEEF`, 157 callers); `sub_83930888`: a `std::map`
  walk. Both read garbage (0x2D2DB5B1, 0x5EF8576B: hash-like values used as pointers).
- Three threads (job threads Core_0/Core_1 - Thread 0 and an audio thread) failing at once on garbage points at one
  memory corruption. Checked and ruled out: the fiber context layout (fiber data at +0, 0xA50 bytes, KTHREAD+0x164 all
  match the game's XAPI); the SDK's SwitchToFiber saves and restores r1 and the non-volatiles. The XAPI fiber functions
  are now hooked to host fibers with 256 KB host stacks.
- A/B: `tools/fc4_set_gen_passes.bat OFF` builds with every optional post-codegen pass compiled out (boot8_safe).

### boot8-10: narrowing the corruption (2026-11-09)

- **Not the post-codegen passes:** boot8_safe (every optional pass compiled out, `tools/fc4_set_gen_passes.bat OFF`)
  crashes identically: same threads, same addresses (0x20611840, 0x2D2DB5B1). The PC build is still configured OFF.
- **Not the controller:** boot10 with `--input_backend=xinput` (no SDL controller events) crashes identically.
- **Not jump tables:** `tools/fc4_switch_verify.py` checks every generated switch against its table in the image,
  including the shapes `tools/switch_check.py` misses (FC4's compiler puts `rlwinm` between `lis` and `addi`, and
  uses `lbzx`/`lhzx` offset tables with a separate base): 404 of 404 correct (counts and targets).
- **Not the fiber save area:** the SDK saves r14-r31, f14-f31, v14-v31, v64-v127, cr2-cr4 and FPSCR, as XAPI does.
- **The bad values were never allocated:** `--log_level=trace --log_noisy=true` traces every NtAllocateVirtualMemory
  (1,450), NtFreeVirtualMemory (1,020), MmAllocatePhysicalMemoryEx (2,488); none covers 0x20611840 (virtual results
  0x00100000-0x40800000, physical 0xB3xxxxxx-0xFBxxxxxx). The values do not occur in the image either: they are
  computed or loaded garbage, deterministic from run to run.
- Crash report with guest backtraces: `app/out/pc/logs/crash.txt` (the SDK writes it). Thread Core_0 - Thread 0 on its
  thread fiber: sub_83F4F470 -> sub_83FC6CC0 -> sub_83FC6C40 -> sub_83ADCB28 (the job thread) -> sub_83ADC048 ->
  sub_83ADD850 -> sub_83ADCA50 -> sub_83ADB4E8 -> sub_83ADA078 -> sub_83AD9F28 -> sub_83AD5350 -> sub_83ACFCF0 (a node
  from a free list, else `NMalloc(8)`) -> sub_83AC94B8 (the pop).
- The game's allocator: vtable {sub_8242FF98 alloc, sub_82429258 free, sub_82425FA0 realloc} at 0x84197920, installed
  by sub_8242C900 into dword_84165890 ("NMalloc"); blocks of 256 bytes or less from a small-block allocator
  (sub_8242FDF8), larger from sub_824257E0.
- TLS: the XEX asks for 64 slots and 0x14 bytes of static TLS (0x842F1000); the SDK copies it per thread (Xenia's
  layout). Not yet ruled out.
- Next: find who stores the garbage head into the free list (watch the list head object: a mid-asm hook or a guest
  store watch on that address), and whether Xenia Canary boots this disc (a shared-kernel vs recompiler question).

## Base-tool audit for FC4's address range (2026-11-09)

- direct_calls.py / llamadas_directas.py / localize_native.py only treated `82xxxxxx` addresses as hooked; now
  `8[2-9]xxxxxx`. direct_calls --redo: 590 hooked addresses (was 572), 15 files changed; calls to sub_83AC94B8 now
  reach the watch hook.
- leaf_dead_stores.py ENTRY_POINT 0x826F46F0 (Banjo) -> 0x83F3F630. lr_preserve.py / r1_preserve.py: Banjo's
  no-return addresses removed (TODO: FC4's own abort/exit/bugcheck from IDA). inline_memcalls.py defaults no longer
  Banjo's memcpy/memset (TODO: FC4's CRT memcpy/memset; [rexcrt] can also take memcpy/memset/strings).
- All of these are guarded by BANJO_GEN_* switches (currently OFF) except direct_calls, so they cannot explain boot7-10.
- sub_83AC94B8 is a tagged (head+counter) ldarx/stdcx. pop: ABA-safe under CAS emulation. The garbage head most
  likely comes from a write into a node already back on the free list (use-after-free) -> run the write watch.
- app/config hot lists, renut_hooks.toml, choice JSONs: already empty. Katamari address hooks (me_ring_wait, FPS) sit
  behind KATAMARI_BANJO_ADDRESS_HOOKS=0.

## Boot crash narrowed: a texture copy overwrites live job objects (2026-11-09, boot11-15)

- The pop's *list pointer* is the bad value, not the list head: sub_83AD5350 passes list = *(*(r3) + 0x20) to
  sub_83ACFCF0 -> sub_83AC94B8. Bad case (boot14): r3 0x4001DE34 -> obj 0xF905C280, word at 0xF905C2A0 = 0x20611840.
  The obj's words are DXT1 blocks (08200000 0B0B0B0C 18400820 2BAB2B2B ...): texture data on top of job objects
  (the good ones sit at 0xF905BF00 / 0xF905C180 / 0xF905F980).
- Hardware write watch (boot15, --fc4_watch_addr=F905C2A0 --fc4_watch_value=20611840): the writer is guest thread
  0xF8000094 in sub_83FBF760 (CRT memcpy) <- sub_82476528 (128-byte chunk copy dest <- src, texture upload)
  <- sub_827B7CF8 (DDS / D3D texture load: 83F1DFE0, 83F1ED98, 83F1BA30) <- sub_827B9DA0 <- sub_827D57F0 <- job
  sub_83ADCA50. All simultaneous crashes follow from this one overwrite.
- So two physical-memory users overlap: the texture's memory and the job pool. Next: who allocated each (the
  texture's base address vs the job block containing 0xF905C280) - SDK physical allocator (XPhysicalAlloc /
  MmAllocatePhysicalMemoryEx, 4 KB 0xE0000000 heap vs 64 KB 0xA0000000 view) or the game's own heap.
- Watch-tool note: hooks must read guest memory through rex::memory::GuestPtr (0xE0000000+ has a 4 KB host offset
  on Windows); `base + addr` read the wrong bytes there.

## Xenia Canary reference run (user, 2026-11-09)

Xenia Canary (D3D12, RTV/DSV path) runs FC4 to gameplay (bus intro, De Pleur's mansion, Bell Tower mission, menus,
save/quit) without crashing. Issues seen there: characters' skin/clothes black (eyes, teeth, hair fine), black
pistol/animals, screen-space blocky/checkerboard tiles, black terrain patches, much dialogue silent, reload not
working. game-compatibility #969: `readback_resolve = true` fixes dark/black graphics. For this port: the game reads
resolved render targets back on the CPU (Renut's renderer must support resolve readback); dialogue is likely XMA
(check the APU path once in game). These are Xenia's bugs, not this port's; they are hints for the renderer phase.

## Boot crash FIXED: ranged physical allocations one page high (2026-11-09, boot16-18) -> title screen

- boot16 trace: at start the main thread allocates physical windows by exact range, e.g. MmAllocatePhysicalMemoryEx
  size 0x6000 min 0x1905B000 max 0x19060FFF. The kernel returned 0xF905B000 = physical 0x1905C000-0x19061FFF (the
  0xE0000000 heap is physical +0x1000): one page above the window, past max. Every ranged block did this.
- Cause: BaseHeap::AllocRange rounded the inclusive high bound UP to the alignment (0x19010FFF -> 0x19011000), so the
  top-down search could start one page higher. (Xenia's memory.cc has the same line.)
- boot17: the overwriting texture copy is exactly that window (sub_82476528 dst 0xF905B000 src 0x40645A68 size
  0x6000, lr 827B7F8C); the job pointer at 0x4001DE34 pointed into it (the game's physical arithmetic disagreed with
  where the block really was).
- Fix (sdk/src/system/xmemory.cpp, BaseHeap::AllocRange): high bound inclusive, not rounded; only pages ending at or
  below it count. boot18: no access violation in 150 s, textures loading, **title screen "PRESS A TO START"**
  (out/pc_runs/boot18/captura_009_0135s.png), XMA audio registers being written.

## Intro runs on PC (2026-11-09, intro1-5)

- Scripted input (`--input_script`) gets from the title through Campaign -> New Game -> START (OFFLINE) (needs DOWN:
  START (ONLINE) does nothing offline): `10..65 every 5 s :A, 70:DOWN, 73..98 :A`. The intro cutscene plays (mountain
  flyover, bus, Kyrat border, Pagan Min's helicopter) with faces lit correctly (out/pc_runs/intro5/sheet.png).
- `--readback_resolve=fast` (Xenia's fix for black characters, compat #969): D3D12 TDR (DEVICE_HUNG) ~36 s in;
  `--gpu_backend=vulkan`: NVIDIA's shader compiler (nvgpucomp64.dll) crashes creating a pipeline. Both are the PC-only
  emulated GPU (xenos plugin, Xenia-derived); the Switch uses Renut's D3D-level renderer instead, where the black
  characters need the same thing done natively: CPU readback of the resolve the game reads (character lighting).
- Audio: no APU/XMA errors in the log; XMA decoding runs (~1250 frames / 10 s). Missing dialogue not confirmed or
  ruled out in this build yet (needs a listen). The XAudio ducker getters are stubs that leave f1 unset, but the game
  never calls them (no STUB warnings), so they are not the cause.
- tools/fc4_ida.py: `funcs LO HI`, `noreturn`. CRT: memcpy = sub_83FBF760 (0x488 bytes, 2046 callers),
  strncpy = sub_83FBF6F8, memset = sub_83FC34D0 (987 callers; inline_memcalls.py defaults now point at both).
- Optimisation passes back ON (tools/fc4_set_gen_passes.bat ON) after the crash fix; the SDK change re-ran codegen +
  post_codegen with the fixed tools: 1072 memcpy / 347 memset constant-size calls inlined. opt1: the scripted intro
  runs 330 s with no access violation or GPU error (out/pc_runs/opt1/sheet.png).

## Switch build bring-up (2026-11-09)

- `tools/fc4_build_switch.bat` (tools/build_switch.bat with Python 3.15; NVK_SDK defaults to sdk/thirdparty/vulkan-headers:
  no Mesa/NVK SDK on this PC, the build is deko3d only). `tools/fc4_deko3d_tools.bat` stages the host-shader tools:
  SPIRV-Cross from out/fc4_shaders, uam = devkitPro's uam 1.1.0 (app/thirdparty/uam needs pthreads; its patches are
  for the console-side library).
- app/thirdparty/plume/CMakeLists.txt: the NVK library must exist only when PLUME_SWITCH_NVK_LINK is ON.
- Configure now stops at app/out/renut_switch/shader_cache_switch.cpp: build the PC tree with RENUT=ON first, then
  tools/renut_switch_shader_cache.py. So the order is: Renut retargeted to FC4 (sa2-nx's d3d layer: d3d.h,
  d3d_native.h, hooks; FC4 addresses from out/fc4_d3d/hook_map.txt) -> PC Renut build + boot -> shader cache -> NRO.

## Renut retarget, in progress (2026-11-09)

- tools/fc4_d3d/apply_sa2_d3d.py copies sa2-nx's d3d layer (d3d.h, d3d_native.h, d3d_native_state.cpp, hooks/*)
  and moves it to FC4: 204 hooks, 26 data/helper addresses (format table 0x82296708, full viewport 0x82296788,
  XPhysicalAlloc no-large-pages flag 0x842DC280, XMemFree sub_8241E898; state tables, caps, HiZ, qword,
  VdGlobalDevice from docs/fc4-d3d-map.md). DrawVerticesUP commented out (not linked); N&B's skip-export switches
  and SA2's Fusion flag absent (guarded). gpu.cmake: hooks/state.cpp not built (sa2-nx's design).
- Build: `set BUILD_DIR=...\app\out\pc_renut & set RENUT=ON & tools\fc4_build_pc.bat -- -k 0`.
  - DXC binaries copied into app/thirdparty/reblue-XenosRecomp/thirdparty/dxc-bin/{bin,lib} (gitignored).
  - Shader containers: app/cmake/banjo_renut_gpu.cmake -> out/fc4_shaders/containers (6,523; none in game.xex).
  - FOG0/PSIZE0: shader_common.h rows X(PointSize,0,23) X(Fog,0,24) + `PointSize = 4` alias in
    render/vertex_format.cpp. Shader cache now builds (6,523).
  - BANJO_RENUT_EARLY_ALPHA=OFF in app/out/pc_renut for now (the failing run may have been the FOG0 error; recheck).
- Remaining C++ errors (sa2-nx's d3d layer against katamari-nx's newer renderer):
  - d3d_native.h: keep katamari-nx's (touch tracking: kTouch*, TouchBit, TagChunks, TakeTouches, g_tags_apart,
    g_touch_compare, used by guest/command_buffers.cpp and banjo_renut_tuning.cpp) and put sa2-nx's private device
    offsets in it (FenceCompletion 11024 ... AutoBackBuffer 15236, see sa2-nx's file); kStateTagChunks' private
    render-state range (katamari 0x2DF4) must move to SA2's layout too. backend/queued.cpp static_assert
    kDeltaReadChunks.count == 39 follows from it.
  - hooks/shader.cpp: plume::RenderShader is held as unique_ptr in sa2-nx, raw pointer here (lines 213-244).
  - hooks/resource.cpp:1702 ReleaseGuestDeclarationLocked undeclared.
  - hooks/device.cpp includes renut_engine/gpu/sa2_renut_pacing.h (sa2-nx's pacing; copy or stub).
- Merge decision (after trying sa2-nx's guest/resources.h: it drops katamari-nx's GroupSummary, PrefetchShader*,
  draw_summary, HostShaderOf, stream_order/count that render/draw.cpp and guest/command_buffers.cpp use):
  shader.cpp and guest/resources.h stay katamari-nx's; add sa2-nx's observe-only parts (its D3DResource_Destroy-only
  resource model needs them): RegisterGuestDeclaration / FindGuestDeclarationLocked / ReleaseGuestDeclarationLocked,
  its CreateVertexDeclaration RAW observe hook (katamari-nx's replacing hook off), XGRegisterVertex/PixelShader hooked,
  and sa2-nx's FindGuestDeclarationLocked lookup in render/draw.cpp (sa2-nx draw.cpp ~4114). Also pending:
  sa2_renut_pacing.cpp uses banjo::display_sync::TakeHold (sa2-nx addition); device.cpp uses Video::SetGammaRamp and
  a 2-argument call (sa2-nx's video API).
- **Renut builds and boots on PC (2026-11-09, renut7/8):** the game runs through Renut (D3D12): ~78 frames in the
  first 13 s, resolves at 1280x704 / 960x544 (FC4's dynamic resolution), audio running, no crash in 280 s. Fixes on
  the way: the path wizard waited for a click with the paths given (renut_app.h: skipped when --game_data_root is
  set); Katamari's touch slots in d3d_native_state.cpp. Errors left: a few colour targets with garbage sizes
  (11623x31137: likely a medium-confidence surface hook) and some pipeline creations failing.
  PC window captures (tools/fc4_window_shot.ps1, PrintWindow) come out black: unclear whether that is the D3D12
  flip-model swapchain or the image itself. Hang dumper: FC4_HANG_DUMP_S=N writes fc4_hang_dump.txt (all threads).
  Run: tools/fc4_run_pc.ps1 -Build pc_renut -Visible -Extra "--banjo_renderer=renut".

## 2026-11-09: Renut PC stalls after ~80 frames (renut8 -> irq1)

The window is not black from the capture: the renderer's own capture (nfsmw_captura) reports "no game image" because
the game stops swapping at frame ~78. Causes found, in order (thread dumps: FC4_HANG_DUMP_S=N FC4_HANG_DUMP_N=k):

1. **Async resource lock ring** (D3D sub_83F18B88, called once from sub_82831850): 32-slot shift register at device
   +0x5F60; spins while bit 63 is set. Slots are freed by the game's unlock jobs (sub_838B8998 -> sub_838B8598 ->
   sub_83F18790). trace1: frees keep pace for ~18 locks, then stop. Hook in gpu/d3d/hooks/fc4_hooks.cpp waits, running
   ready callbacks, and after 2 s retires the oldest slot (the waits are GPU packets Renut ignores).
   Note: direct_calls.py must be re-run (--redo) after adding a hook on a game function, or callers keep calling
   __imp__sub_X directly and the hook never runs (the first fc4_hooks build).
2. **GPU callbacks run inline**: the allocator's GPU-done callback sub_827B34F0 pushes onto a lock-free queue
   (0x84239250) and spins while it is full; only the allocator (sub_827BA778) drains it. Renut ran callbacks on a game
   thread inside its next D3D call -> deadlock. Now guest/callbacks.cpp runs them on a "GPU Interrupt" XHostThread
   (renut_callback_thread, default on), as the console's interrupt does.
3. **Command buffers** (open): sub_827ADB78 / sub_827EF9C0 call D3DDevice_BeginCommandBuffer 83F29B28, which calls the
   buffer's allocation callback (+0xB0, context +0xA4) when it has no memory (+0x98); the callback is null -> FATAL
   "invalid function 0" at lr 0x83F29AB0 (frame ~87). FC4 has no Begin/End/Run hooks (sa2-nx never needed them);
   device.cpp's D3DDevice_*CommandBuffer_hook bodies use N&B device offsets: FC4's 0x34xx-0x3Bxx block is N&B + 0x194
   (CommandBuffer 0x3660, 0x3BE4 = N&B 0x3A50, 0x3BD8 = 0x3A44, 0x3BD4 = 0x3A40, 0x3664.. = 0x34D0..); the tiling path
   (flags & 3, used: flags = 1 from sub_827ADB78) touches other regions still to map. D3DCommandBuffer layout matches
   (+0x08 fence, +0x6C flags, +0x98 memory, +0xA8 allocator size).
   fc4_renut_async_locks = false (byte 0x84126AF8) takes the game's synchronous path, which hits the same crash sooner.

Also: the invalid-function trap now logs lr and r3 (sdk function_dispatcher.cpp).

## 2026-11-09: Renut renders FC4 on PC (async command buffers, front buffer)

- Item 3 above was not the sync path: FC4 uses **async command buffer calls**. Main thread: sub_827B4908 ->
  D3DDevice_InsertAsyncCommandBufferCall 83F2A4B0 (device, call, predication, flags) + InsertFence 83F2EF80 + a GPU
  callback sub_827B34F0(holder). Workers (job sub_838B8998 -> sub_838B8598 -> sub_827EF9C0): BeginCommandBuffer
  83F29B28 on one of the 8 type-2 devices, record, D3DAsyncCommandBufferCall_FixupAndSignal 83F2AB60 (call, buffers[],
  predications[], count, flags). CreateAsyncCommandBufferCall = 83F29518, the game's CreateCommandBuffer-like = 83F290F0
  (r4 alloc callback +0xAC = sub_827BAAB0, +0xB0/+0xB4 nullsub, r7 context +0xA4, r8 size +0xA8; 256 made at boot).
- Renut: FC4's originals of Begin/End are kept (they set/clear device +13920, which is Renut's recording test);
  fc4_hooks.cpp adds BeginRecording after Begin, and command_buffers.cpp QueueAsyncCommandBufferCall /
  SignalAsyncCommandBufferCall: the render thread waits at the insert's place (1 s timeout) for the call's fixup (either
  order) and replays its buffers with the title device's state at the insert.
- The holders come back through the GPU-done queue 0x84239250, which only the game's allocator drains (when D3D calls
  the buffer's memory callback, which Renut's ring rewinds never do): drained at each Begin (pop sub_82476A68,
  sub_827B8570 -> free list 0x8423A3C8). Without it the 256 ran out -> Begin with a null buffer -> FATAL 83F29AB0.
- **Front buffer**: FC4 resolves into one header (e.g. B4D58068, base 0x14DC0000) and swaps another (B59D0508/0540)
  whose fetch constant holds the virtual address (0xF4DBF000 = physical 0x14DC0000 in the E heap). Present looked up
  only by header -> no image (black window, "no hay imagen"). draw.cpp FrontBufferTextureLocked falls back to the resolve
  destination at that page (textures.cpp FindResolveTargetLocked maps the A/C/E views back).
- Result (fb2, rintro1-3): Far Cry 4 logo animation, title "PRESS A TO START", Dunia logo, autosave notice and the
  Campaign menu's 3D elephant scene render correctly at 30 fps, no crash in 300 s.
- Menu script for this build: title A presses 10..35 s, Campaign shows NEW GAME / UPLAY by ~42 s (UPLAY and START
  (ONLINE) give "requires Xbox Live"); then NEW GAME, DOWN, START (OFFLINE).

## First Switch NRO in stock Ryubing (2026-11-09)

- Build: `generated/renut_register.cpp` (one function, ~181k `SetFunction` calls) sat 1h40m in GCC at `-O3 -g`; it is
  now `-O1 -g0 -fno-var-tracking` (app/CMakeLists.txt) and compiles in seconds. The link wanted `-lzstd -lz` from
  devkitPro portlibs, which are not installed here: plume's and rexglue_switch_nvk's no-NVK branches linked them for
  the NVK driver only; Renut links its own `renut_zstd`. NRO 134 MB.
- `tools/fc4_run_ryujinx.ps1`: the game_root junction needs `$env:ComSpec` (Git Bash's `cmd` is msys2's script).
- Ryubing starts a command-line NRO with no folder in argv[0]: `GetExecutableFolder()` is empty, so no game_root and
  no katamari.toml ("--game_data_root was not provided", exit at 12 s; the SaltyNX profiler thread then faults in
  `fprintf(stderr)` on the closed stream at 35 s). `RenutApp::AppFolder()` falls back to `sdmc:/switch/fc4-nx`.
  Toml cvars load after the paths, so `game_data_root` in katamari.toml cannot fix it.
- Then: `AllocFixed: could not commit ... Failure 0xE401` (InvalidHandle). Without hbloader there is no process
  handle; guest_memory_switch.cpp uses `CUR_PROCESS_HANDLE` for `svcMapProcessCodeMemory`, which stock Ryubing
  (canary, reports 1.3.352) rejects. katamari-nx was tested on "the user's patched Ryubing" (another PC); only the
  stock build is on this one. On a console hbloader passes the real handle.
- Later the same night, stock Ryubing boots the game (run `emu14`: 300 s, ~30 game frames a second, 200k draws, heap
  905 MB free at the end) with these fixes:
  - `REX_SWITCH_FALLBACK_EXE` (app/CMakeLists.txt) named katamari-nx's NRO: now `/switch/fc4-nx/fc4-nx.nro`. The
    rooted form matters: `sdmc:/...` is relative to libstdc++, `std::filesystem::absolute` made it `/sdmc:/...` and
    `status` threw in `Runtime::SetupVfs`. `RenutApp::AppFolder()` is just `GetExecutableFolder()` again.
  - guest_memory_switch.cpp: without a loader, a real process handle from a session to itself (nx-hbloader's way,
    plus an empty reply: closing the session without one never wakes the sender in Ryubing). Taken in `RexGmInit`
    before `virtmemLock`: `threadCreate` takes that lock for the stack, so under it the NRO hung.
  - switch_code_blocks.cpp: the emulator-only swap self-test is opt-in (`REX_CODE_BLOCKS_SELF_TEST`): Eden accepted
    the pseudo-handle, ran it and died (access violation in eden.exe). Eden then dies elsewhere (0xC0000409, no log
    line); the user prefers Ryubing (closer to the console), so Eden is not pursued.
  - Any C++ throw kills the NRO in stock Ryubing: GCC 16's libgcc unwinder holds `mrs x1, gcspr_el0` (behind
    `chkfeat`, never run on an A57) and Ryubing's JIT fails to translate it. `src/switch_throw_trace.cpp`
    (`--wrap=__cxa_throw`, `--wrap=_Unwind_RaiseException`) writes each throw and its stack to rex_stderr.log.
  - surfaces.cpp: colour/depth targets over 8192 a side (FC4's garbage sizes, 11623x28197) are not created; deko3d
    had made one of 1.4 GB and Ryubing ran out of device memory at 61 s.
- Still black: `no GLSL package (deko3d_glsl.bin beside the NRO, or built in): no game shaders` (101 "Creating
  shader failed", uam 0 compiles), and the front buffer lookup misses. Next: the deko3d GLSL package for FC4's 6,523
  shaders (docs/fc4-shaders.md; tools/switch_shaders.ps1, tools/renut_release_shaders.py).
- **First picture on the Switch build (2026-11-10, stock Ryubing, run `emu17`):** Ubisoft logo, Dunia Engine, the Far
  Cry 4 title screen ("PRESS A TO START"), ~29 game frames a second for 300 s, no crash. The deko3d GLSL package:
  the census's 6,201 GLSL files (`out/fc4_shaders/census/glsl`, renamed to upper-case hashes, which
  `deko3d_glsl_opt.py` and the packager require) -> `tools/deko3d_glsl_opt.py` -> `tools/deko3d_shader_package.py
  --out out/deko3d_pkg` (76 MB of GLSL, 8.4 MB package); `tools/fc4_run_ryujinx.ps1` copies `deko3d_glsl.bin` beside
  the NRO. Missing: the 322 vertex shaders with Fog/PointSize inputs (docs/fc4-shaders.md: needs the location rows
  and vertex_format.cpp).
- Memory: docked at 1080 (render targets 1.5x) the heap ran out (`emu16`: 94 MB free, std::bad_alloc in the capture
  thread). `banjo_renut_render_height_docked = 720` held it at 239 MB free; menus still draw at the HUD's 1.5x
  (surfaces.cpp: display scale until a 3D composite is seen). GPU region peak 1.85 GB.
- **New Game on the Switch build (2026-11-10, stock Ryubing, run `emu20`, `input_script` in out/emu_test.toml):** title ->
  Campaign menu (the 3D elephant scene) -> New Game -> the KYRAT loading screen, 15-22 game fps. Then at ~190 s a
  deko3d fence never signals (2 s, 4 s) and Ryubing's host Vulkan device is lost: a GPU job that does not finish
  (next to find: which draw).
  - The user's run before: the heap ran out at New Game. Fixes: 720 internal and output in both modes (built-in
    defaults: render targets 561 -> 223 MB), `banjo_renut_textures_reserve_mb` 384 -> 768 (the title's textures had
    reached 926 MB), stream cache 128 -> 64 MB, and the capture thread skips a shot with under 96 MB of heap (its
    std::bad_alloc was the fatal throw; in Ryubing any throw is fatal).
  - Still: deko3d's image memory reaches 1.1 GB while Renut counts ~256 MB of targets and textures (image heap chunks
    kept until newlib's room < 256 MB, plume_deko3d.cpp heapRoomShort; the GPU region gives back only from its
    bottom). Garbage texture sizes too (4002x5094, 328 MB, refused for lack of memory).
  - Stutter: uam compiles take ~3 s each in Ryubing and the generic variants draw meanwhile (5-18 fps in the user's
    visible run). Next: the PC's pipeline_list.bin into a prebuilt DKSH cache (tools/deko3d_variant_cache.py).
  - Katamari leftovers to clean up: banjo_pool_lock hooks sub_82333388/sub_823333F0 by Katamari's addresses (only a
    mutex around the original), and 17 unused banjo_cpu_native_sub_* keys in katamari_switch_defaults.toml.
- **Ryubing's limits (2026-11-10, the user's run `mine2`):** the KYRAT load ran on, then Ryubing died with
  "OutOfMemoryException: Failed to allocate in new Cache Region!": its JIT cache grew in 256 MB regions to 2.25 GB and
  stopped. The NRO has 105 MB of AArch64 code (largest function 166 KB, so it is the total, not one function). With
  the unwinder's GCSPR_EL0 and the refused pseudo-handle, the third emulator-only limit; a console runs the code
  natively. `input_script` replaces player 1 (the user's controller did nothing): out/emu_user.toml has none.
- Prebuilt DKSH cache: `tools/deko3d_variant_cache.py --list app/out/pc_renut/pipeline_list.bin --generic --glsl
  out/deko3d_shaders/glsl --out out/deko3d_pkg_noopt/deko3d_shaders.bin` (6,162 variants, 28 MB, none failed; 562
  stages without GLSL); tools/fc4_run_ryujinx.ps1 copies out/deko3d_pkg/deko3d_shaders.bin beside the NRO. It must
  come from the same GLSL as the package (now the unoptimised one, testing whether deko3d_glsl_opt.py's passes cause
  the GPU hang).
- `banjo_deko3d_bind_trace` (plume: Deko3DSetBindTrace): the last 256 pipeline binds' shader names, logged when a
  fence does not signal in 2 s. Hang suspects: vs_26DE92239ADAE756 / vs_F33E59F6A6DE49DD divide by repeated
  subtraction (`for (uint x = r; x >= d; ) x -= d;`, d = max(v[65].y, 1) + 1: a loop for ever only if the
  tessellation factor is 0xFFFFFFFF).

## Console runs hw1/hw2 (2026-11-10, the user's Atmosphere Switch)
- **Runs on the console** (title takeover, NRO + deko3d_glsl.bin + deko3d_shaders.bin + game_root on the SD): title,
  menus, New Game, the KYRAT load, the bus intro and the Pagan Min scene drawn right at 15-17 fps. Ryubing's three
  limits do not apply. Album files of an emuMMC are in `sdmc:/emuMMC/SD00/Nintendo/Album`.
- **Broken: the hood scene (green/magenta tiles) and De Pleur's compound (blocks).** FC4 resolves through one header
  into memory that moves with its dynamic resolution (bases 0x133FC, 0x133E8, 0x133B6 ... for 1280x704, 1280x672,
  960x608 ...) and its temporal passes sample the previous frame's at its own base. ResolveTarget kept one host texture
  per header and retired it at each new base; BindTextureLocked then made the texture from guest memory the resolve
  never wrote ("[flash] ... dropped for a fetch of other data": 126 a run). Now (banjo_renut_resolve_any_size, on):
  resolve destinations by base page (a synthetic g_textures key, 0xF0000000 | page), ResolvedAlias accepts one held
  under that key for the same header, a fetch of the same memory/format/dimension at another size keeps the image, and
  a depth resolve sampled at another size (1280x720 over 1280x704) uses its words (copy box clamped). PC: [flash]
  139 -> 4 per run.
- **Speed (hw2 rex_profile.log, handheld):** clocks CPU 1020 / GPU 460.8 / EMC 1331 (apm 0x92220008); gameplay 13-15
  fps with the game thread at ~61 ms a frame, the render thread ~45 ms (~720 draws, 95 MB/s of vertex fetch copies,
  9 % of draws through the address window) and the GPU ~32 ms. `fc4_clock_cpu_mhz` / `fc4_clock_gpu_mhz` (default
  1785 / 768, src/fc4_switch_settings.cpp) hold the clocks through sys-clk's override (sdk switch_sysclk.cpp Force),
  released at a clean exit.
- **Audio static:** at 15 fps 107 audio requests without data in 10 s. FC4's `Dare::AudioRenderer` thread (~2 % of a
  core) waited at the guest priority (0x3B, 10 ms slices) behind ~10 busy threads: it now goes to 0x3A when it names
  itself (xthread.cpp set_name). The menus also mix about twice the usual blocks a second (two clients).
- Still to do: the texture fetch exponent adjust (650 binds; shader_common.h tfetch* and draw.cpp BindingWords, index
  bits 20-25 are free: 8192 slots), the 322 Fog/PointSize vertex shaders, the vertex-copy cost (address window).

## Exponent adjust, all 6,523 shaders, core spread (2026-11-10)
- **Texture fetch exponent adjust** (Xenos fetch dword 3 bits 13-18, signed: the fetched value times 2^adjust; ~780
  binds per 10 s in gameplay, 645 negative). draw.cpp BindingWords puts it in descriptor index bits 20-25
  (textures.h kExpAdjustShift); shader_common.h masks the index (RENUT_DESCRIPTOR_INDEX_MASK, 0xFFFFF) and
  XenosRecomp multiplies each tfetch by renutExpScale(index) = exp2(signed bits 20-25). Suspected cause of the black
  after the Pagan Min scene on PC (the luminance chain 320x176 -> 80x44 -> 64x64 read 2^n too bright or dark).
- **Census with the current tree** (`fc4_shader_census.py --out out/fc4_shaders/census_exp --dxc "" --dxc-spirv
  out/fc4_shaders/dxc/bin/x64 --spirv-cross ...`): all 6,523 translate to GLSL and uam (the 322 Fog/PointSize vertex
  shaders included). Package: out/deko3d_shaders/glsl_exp (upper-case names) -> out/deko3d_pkg/deko3d_glsl.bin
  (10.6 MB). Run `py -3`: Git Bash has no `python`.
- **Cores (hw2 profile):** the process has cores 0-2. sa2-nx's layout (sa2_renut_core_layout) kept the guest main
  thread alone on core 0 and every other guest thread on cores 1-2 preferring 2; FC4's main thread is idle in
  gameplay (0 %) while its six job threads (Core_0/1/2 - Thread, ~165 % of a core in all) and the render thread
  (core 1, 0x2C, ~23 %) shared two cores. Now: the layout off in the Switch defaults, and each guest thread prefers the
  Switch core of the Xbox core the game put it on (hardware threads 0-1, 2-3, 4-5 -> cores 0, 1, 2; mask 0x7;
  cvar xbox_core_spread, xthread.cpp PreferXboxCore).
- **Where hw2's frame went:** title/menus 12-18 fps with the render thread ~4 ms and the GPU ~8 ms (the game's threads
  are the limit); gameplay 12-15 fps with the render thread 44-52 ms a frame and the GPU 25-38 ms (at 1428 / 614 MHz
  in that interval). Render thread per 10 s: ~95k draws, 977 MB of upload ring cleaned (armDCacheClean ~17 ms/s),
  16.5k kicks, 3.8k pipelines made. `switch_profile_stacks = true` (1 kHz stack samples in rex_profile.log, image
  offsets for addr2line on the ELF) is the next step for the render thread's functions.
- **Audio in the recordings** (WinRT MediaTranscoder to WAV, no ffmpeg): the menu/title recordings have no
  discontinuities; the intro cutscenes and gameplay have 10-58 a second in clusters 16-48 samples apart, not on
  256-sample block edges (likely the scenes' own transients, not the mixer).

## The dinner scene after the bus (2026-11-10, PC runs pchood2-7)
- The bus ride and the Pagan Min scenes up to "Enjoy the Crab Rangoon" are a movie (34 draws a frame on PC; it plays
  right on the console). A presses do not skip it. The in-engine dinner scene starts ~430 s into the scripted run
  (~1,300 draws a frame); on PC its picture is black, on the console dark with green bloom.
- **Resolve exponent bias:** FC4's D3D_ResolveCore (sub_83F2C200, recompiled) puts `(Flags >> 26) & 0x3F` into
  RB_COPY_DEST_INFO bits 16-21 (copy_dest_exp_bias). FC4 resolves its HDR scene with EC000000 (2^-5) and the 64x64
  16_16 targets and a 640x352 4x view with 2C000000 (2^11), and samples them with fetch exponent adjusts of the other
  sign (PC: ~1,400 negative and ~600 positive adjusts per 10 s). Renut copies resolves as they are: now each resolve
  destination keeps its bias (HostTexture::resolve_exp_bias) and a bind adds it to the fetch's adjust (BindingWords).
- **EDRAM views of other formats:** the HDR scene (1280x704, 16_16_16_16_FLOAT) is also resolved through a
  16_16_16_16 surface over the same EDRAM, which had a Renut target of its own that nothing drew (0 writes):
  banjo_renut_view_float16 (surfaces.cpp) gives such a surface the float target once the view has been float.
  Not done yet: a 640x352 4x-MSAA view of the same 1280x704 memory (the Xbox 360's free 2x2 downsample; resolve 35,
  B3259834) still reads a target nothing drew.
- The frame's end: the scene composite goes to a 1280x720 RGBA8 view, is resolved (rect 1280x704) into two textures,
  depth/stencil cleared (clear flags 0x30), two quads drawn (the letterbox bars: no texture, opaque) and the view
  resolved into the front buffer.
- `banjo_renut_diag_show_texture` takes a list shown 10 s each, and "R<n>" = the previous frame's n-th resolve's
  destination (logged as "[diag] show texture"); resolve destinations held by base page are found by a walk.
- Launch PC runs from Bash: from PowerShell, `-Extra` reaches fc4_run_pc.ps1 cut at the first space.

## To do: New Game load time (the user's request, 2026-11-10)
- The KYRAT load after New Game takes ~2-2.5 min on the console (hw2 fc4.log: 131 s with no frame stats between
  02:25:22 and 02:27:33); the hw3 test (switch_profile_stacks on, threads spread by Xbox core) felt longer. To
  measure from hw3's rex_profile.log stacks: which threads run during the load and where (SD reads, the vfs/range
  cache, decompression, shader or texture creation), then cut it.

## Console runs hw3/hw4 (2026-11-10): faster, then out of memory at New Game
- Title and menus at 29-30 fps (12-18 in hw2): the cores spread and the sys-clk hold.
- hw3: three launches ended in std::bad_alloc in the capture thread (nfsmw_nativo_captura.cpp Bucle -> Chunk) at the
  title->menu spike (GPU images 1.0-1.1 GB). hw4 (captures off): the KYRAT load stalls (the loading screen keeps
  drawing at 29 fps, the bar stops): 491 "AllocFixed: could not commit" (guest backing 456 MB, process 3 MB unused,
  deko3d images 848 MB, Renut textures 913 of 915 MB). hw2 had images at 374-480 MB with a 754 MB spike.
- Cause: banjo_renut_resolve_any_size keyed resolve destinations by base page, and FC4's resolves move to a new page
  almost every frame; GPU-written images are never idle-evicted (banjo_renut_keep_gpu_written), so they piled up.
  Now a page-keyed destination that is not its header's latest goes after 8 unused frames
  (ReleaseStaleResolvePagesLocked). PC: 534 released in the first 10 s of boot, ~40 held after.
- hw5 (stale pages released): images steady at ~534 MB, but the KYRAT load still never finished: at New Game a
  junk-sized render target was made (a 562 MiB image heap chunk) and others refused (6234x3213, 4352x7292, 3983x2622:
  size words through bad descriptors; every run has ~15-30 of them), then 30 guest commit failures and the load
  stalled. Targets over 4 Mi samples (2048x2048 at 1x) are now refused like those over 8192 a side (surfaces.cpp).
- Still to do for load time: Renut's host texture copies reach ~1.2 GB during the load (all fresh, none cold to
  evict); a Switch option to drop large textures' top mip would cut that ~4x and the upload time with it.
- hw6 (junk targets refused, 32 of them): the load still stalled on 34 failed guest commits 13 s in (backing 504-536 MB;
  deko3d's GPU region 1,126 MB holding ~936 MB, Renut's own images ~480 MB of it; the loading screen draws at 25 fps,
  where hw2's loaded with no frames and images at ~400 MB). The guest's backing is memalign(2 MB, 2 MB) from newlib;
  ~170 MB was free but fragmented. Now (sdk guest_memory_switch.cpp): a granule that cannot be had falls back to the
  requested pages only (page-aligned), and a commit still short is retried for up to 3 s after
  RexGmSetMemoryPressureCallback (Renut: spare command buffers, RequestTextureRelief = host textures not drawn with for
  a second, plume Deko3DReleaseEmptyChunks).
- Icon: tools/switch/make_fc4_icon.py makes tools/switch/icon/fc4_icon.jpg (256x256) from the disc's SPLASH_720.PNG;
  git-ignored (game-derived), embedded by app/CMakeLists.txt (reconfigure after making it).
- hw7 (memory retry in): the KYRAT load finished in ~50 s (hw2: 131 s) and the intro movie played; it froze where the
  movie ends: "[threads] creating a thread with a 16384 KB stack failed ... heap has NO a 16448 KB block (free 135 MB in
  38,000 pieces)", four times, and the game waited for that thread for ever. 26 guest-thread stacks of 16 MB came from
  the heap (~420 MB). Now guest_thread_host_stack_kb (sdk xthread.cpp; the Switch defaults take 4096) and a creation
  that still fails tries halved stacks down to 1 MB (threading_posix.cpp). Measured on PC (fc4_stack_report_s, the
  deepest non-zero word of each zeroed stack): the deepest guest thread used 35 KB through boot, menus, load, the movie
  and the in-engine dinner scene, so 4 MB has >100x room.
- NSP forwarder: tools/switch/make_fc4_nsp.sh (nx-hbloader with its default NRO set to sdmc:/switch/fc4-nx/fc4-nx.nro,
  back to HOME when the game exits: tools/switch/forwarder; hacbrewpack 3.05 built from source, the rlaphoenix mirror
  of The-4n's, in ../nsp_tools; prod.keys filtered to 32/64-digit keys into out/nsp). Title ID 01FC4F00C4000000.

## In-engine rendering: black on PC, garbage on the console (2026-11-10, PC runs pcplay2-6)
- **Rectangle lists and point sprites:** every Renut vertex and pixel shader carries a FOG0 interpolator (XenosRecomp
  INTERPOLATORS, added for Katamari), but rectangle_list_gs / point_sprite_gs did not: D3D12 refused every pipeline
  with either (E_INVALIDARG, "Semantic 'POINTCOORD' is defined for mismatched hardware registers"; 32+ a run, all
  full-screen passes: the black picture), and on deko3d the geometry shaders read and wrote POINTCOORD/POINTSIZE one
  location off. Both now declare `float4 fog : FOG0` after BINORMAL0. `FC4_D3D12_DEBUG=1` turns the D3D12 debug layer
  on in a release build; a failed pipeline prints its HRESULT and the layer's messages to stderr (plume_d3d12.cpp).
- **Tiled G-buffer:** FC4 draws its G-buffer through D3D tiling (two tiles, 0-864 and 864-1280, in 880-pitch
  surfaces) and resolves the second tile at (864,0)-(1280,704). Renut's BeginTiling/EndTiling hooks (83F27938 /
  83F27ED8, raw hooks in d3d/hooks/draw.cpp) are never called in this game (no recompiled caller; the D3D runtime's own
  per-tile resolves still arrive), so the 880-wide targets clipped every draw past x 880: the right third of the
  picture was never drawn (console: garbage there). banjo_renut_resolve_extents (surfaces.cpp): a resolve whose rect
  starts inside its target and runs past the edge grows every target of that view shape (pitch, samples, scale) to it.
- **The 4x view:** the HDR scene's 640x352 4x-MSAA view (nothing draws it) is now the 2x2 box of the 1x float target
  over the same EDRAM (DownsampleSourceLocked + DownsampleResolveCopy, texture_mip_ps).
- **Resolves into fixed-point textures** (resolve trace: `dest fetch format`): the console writes unsigned data,
  value x 2^bias clamped to 0..1. FC4: the HDR scene -> k_2_10_10_10_AS_16_16_16_16 at 2^-5 (sampled at 2^+2/+3) and
  the 4x view -> k_16_16_16_16 at 2^+11, sampled at 2^-14 (a bright-pass mask, ~1 wherever the scene is lit). Renut
  copied the float values and applied the bias at the bind: the 4x copy came out ~2000x too bright and the picture
  white. banjo_renut_resolve_fixed_clamp (draw.cpp): such a resolve from a float/signed target, or with a bias, is
  drawn (resolve_copy_ps / texture_mip_ps, param1 = 2^bias, saturate) and its binds add no bias.
- Xenos 16_16 / 16_16_16_16 fixed render targets hold -32..32 (Xenia snorm16_render_target_full_range); Renut's SNORM
  targets hold -1..1. Xenia's resolve: EDRAM value (bits x 32/32767) x 2^bias, packed unorm-saturated into a fixed
  destination; FC4's 64x64 16_16 targets -> k_16_16 at 2^+11, sampled at 2^-16: matched by the clamp copy.
- Colour formats 10 (2_10_10_10_AS_10_10_10_10) and 12 (2_10_10_10_FLOAT_AS_16_16_16_16) fell to RGBA8 in
  ColorTargetFormat; now RGBA16 unorm / RGBA16 float.
- **PC (D3D12) gameplay still white, the Switch should not be:** FC4 draws its 3D passes with a reversed viewport depth
  range (VportZScale -1, VportZOffset 1: MinDepth 1 > MaxDepth 0; reverse-Z with clear 0 and GEQUAL; resolve trace
  `z scale -1 offset 1`). D3D12 never allowed MinDepth > MaxDepth (Xenia swaps them and negates NDC z in its vertex
  shaders, draw_util GetHostViewportInfo); here the G-buffer resolves come out as their clear colour (1,1,1,1) and the
  lit scene saturates. deko3d (plume_deko3d_commands.cpp setViewports) passes near 1 / far 0 to the GPU as they are.
  The D3D12 fix needs a z flip in the vertex shaders (XenosRecomp epilogue + a shared constant: a shader library and
  GLSL package rebuild). The palace/hood scene renders on PC.
- Diagnostics: the resolve trace now gives each resolve's destination fetch format, sign and exponent adjust, each clear's
  values, and the first three draws' depth/stencil/colour/clip/viewport state after every change of targets; a colour
  surface with an RB_COLOR_INFO exponent bias is logged (none of FC4's real targets has one).
- banjo_renut_tile_replays: in a target grown for tiling, draws with a later tile's window offset are not drawn (FC4's
  passes all run with window offset 0: it does not trigger in FC4).

## The white picture, found (2026-11-10, PC runs pcclear1 - pcc2d3)
- **Stencil reference on D3D12:** plume's D3D12 pipelines never set their stencil reference (OMSetStencilRef(0)): every
  stencil-tested G-buffer draw failed on PC. Fixed in plume_d3d12.cpp (`stencilRef = desc.stencilReference`).
- **Reversed depth on D3D12:** FC4's 3D passes use VportZScale -1 / ZOffset 1. D3D12 refuses MinDepth > MaxDepth, so the
  viewport is swapped and XenosRecomp's vertex epilogue flips z (`g_ScreenSpace & 2`: oPos.z = oPos.w - oPos.z).
- **Right third (tiled G-buffer):** the draws run once at full width into targets grown to 1280 (banjo_renut_resolve_
  extents), but the frame-start clear is the first tile's rect (0,0)-(864,704); on the console D3D replays it for every
  tile. The second tile kept the last frame's lighting stencil and every G-buffer draw failed there.
  banjo_renut_tiled_clears: such a clear of a grown target covers the whole target.
- **16_16 fixed targets hold -32..32:** Renut's SNORM targets clamped to -1..1. FC4's height map: 64x64 16_16 tiles of
  height / 32, resolved at 2^11 into k_16_16 textures **fetched as integers** (num_format 1, dword 3 bit 0) at 2^-16 and
  scaled by 1024 / 256 in the shaders. Fmt16_16 / Fmt16_16_16_16 targets are half float now (format.cpp), and
  banjo_renut_resolve_integer_fetch keeps value x 2^bias unclamped for such a destination (resolve_copy_ps param1 < 0).
  Xenia saturates these (its "black terrain patches / blocky tiles" in FC4).
- **The depth restore (the white):** before the lighting FC4 draws its depth texture's words through an 8_8_8_8 view
  into a colour target at EDRAM base 0x540 (ps_1999728a06a0c2bb: oC0 = tex.zyxw), then binds a D24FS8 target at 0x540
  for the light volumes (stencil EQUAL 1 / 2, NOT_EQUAL 0), the sky and the particles. Renut keeps one host target per
  view, so that depth target held stale data: the lighting drew nothing (black), the auto-exposure (c48.z, 24 -> 112)
  climbed to its maximum on a dark scene and the sky covered the screen. banjo_renut_color_to_depth
  (render/edram_transfer.cpp, color_to_depth_ps): a depth target bound after the 8_8_8_8 target over its EDRAM was written
  takes that target's words: depth in one pass (SV_Depth, 20e4 or unorm24), stencil in eight (one bit each through its
  write mask, no stencil export). Surfaces carry write_seq (NextSurfaceWriteSeq) to order the two.
- **Stencil in the depth words on PC:** the words' stencil byte (depth_resolve.hlsli) read 0 on D3D12 (no stencil view).
  plume_d3d12: an S8_UINT view of a depth-stencil texture is X32_TYPELESS_G8X24_UINT / X24_TYPELESS_G8_UINT, plane 1;
  the shader reads .y there and .x on Vulkan / deko3d. Gameplay stencil bytes now: 0x84, 0x08, 0x00, a few 0x01 / 0x02.
- **CPU readback:** FC4's CPU reads only its 80x44 16_16_FLOAT luminance grid (sub_838B6B48, vupkd3d128 FLOAT16_4).
  Its headers hold 0xE0000000-view addresses (0xF2BD9000 -> physical 0x12BDA000, one page up), and the guest reads it as
  soon as its fence passes, which Renut signals before the host GPU runs the work. banjo_renut_resolve_readback_texels
  (4096) / _formats ("31"): the last finished readback of each kind goes into each new destination at its resolve
  (a few frames old); old destinations are never written late (their pages are reused).
- Diagnostics added: banjo_renut_diag_skip_ps (draws by pixel shader hash not drawn), banjo_renut_diag_cpu_reads
  (Windows: page guards on the guest views of resolve destinations; first access logged with renut.exe+offset for
  llvm-symbolizer), banjo_renut_diag_show_texture "L<slot>" / "C<slot>" (a slot of the lighting / composite draw) and
  _after_s, banjo_renut_diag_readback_stats, banjo_renut_diag_color_to_depth (stencil byte histogram); the trace logs
  each draw's shader hashes (out/fc4_shaders/census_exp/hlsl/ps_<hash>.hlsl), the pixel shaders per target run, the
  composite / lighting pixel constants and window offset changes.
- **Still wrong (PC, 2026-11-10 22:15): near objects unlit.** After the lighting passes the HDR target is exactly 0 on
  everything closer than ~300 m (Pagan Min, the table, the pillars); distant scenery, sky and sun shafts are right, and
  the auto-exposure (c48.z 24 -> 112) climbs on the dark measure. Ruled out by runs: depth test (pctest1), depth +
  stencil tests of the 2-target lighting pass (pctest3), restored stencil (centre bytes 0x84 / 0x01 / 0x02, pcc2d4),
  shadow maps (all 768x768 depth-only draws skipped, pcnoshadow2), the height map (its passes skipped, pcnoheight; and
  banjo_renut_resolve_integer_fetch off, pctest2), the half-res light buffer (snapshot non-zero, pcsnap1). Lighting
  shaders: ps_731cb5fa99c50d91 / ps_a57633f52587b8f9 (dinner), ps_9269ca990424132c (gameplay), ps_3748ac14b5710605 and
  the 2-target NOT_EQUAL-0 pass; their near/far blend is saturate(dist / 32 - 9) (c76). Next: snapshot the lighting
  output per pass (banjo_renut_diag_snapshot takes textures only; a render-target variant is needed), or compare with
  the Switch build (hw10), whose depth words already carried the stencil.
- More diagnostics: banjo_renut_diag_snapshot ("<ps hash>:<slot>", shown by show_texture SNAP),
  banjo_renut_diag_skip_depth_only (width), banjo_renut_diag_tests_colors (target count for diag_gbuffer_tests).
- Switch hw10 NRO (D:\switch\fc4-nx\fc4-nx.nro; ELF out/switch_runs/renut_hw10.elf) has everything above.

## Console run hw10 (2026-11-10): the crash, and the dinner on the console
- **Crash (both runs, ~11 and ~8 minutes in):** std::terminate from std::bad_alloc in the profiler thread
  (sdk/src/ui/switch_perf.cpp, ProfilerMain -> Report's vectors), after `AllocFixed: could not commit 0x10000 bytes ...
  Failure 0xFFFF0001` (memalign of guest backing failed; backing 654 MB). Cause: plume's GPU region. In the boot's
  texture burst Renut made 1,422 MB of textures before the first cold check (every 32 frames; the loading frames are
  slow) released 268 of them; deko3d's image heap took 19 chunks of 64 MB and the region grew to 1,642 MB at the heap's
  top. It never gave any back (0 givebacks: live images pinned its bottom chunks, and release() needs 128 MB free at the
  bottom), so newlib kept 1,386 MB of the 3,028 MB heap for everything else: 2 MB never handed out, 99 MB free in
  81,745 pieces, and 807 MB free inside the region. hw8/hw9 had the same 1.6-1.7 GB region; hw10 ran out first.
  The same figure made the texture budget's "room" ~2 MB all game, so the memory policy evicted in urgent mode.
- Fixes: the image heap fills its highest chunks first (plume_deko3d.cpp chunkOrder; the bottom empties); with
  newlib's room short (heapRoomShort, < 256 MB) a released block gives back all the free space at the region's bottom
  (regionReleaseLocked), and the guest heap's pressure callback also trims it (Deko3DTrimGpuRegion); the cold texture
  check also runs by time (500 ms, 250 ms under pressure; render/textures.cpp); the profiler skips a report it cannot
  allocate (catch std::bad_alloc).
- **Dinner / palace on the console (clips):** frames alternate between the PC's picture (near objects unlit, bright
  windows), frames of full-screen noise in ~80 px vertical strips (EDRAM tile columns: scene edges visible, colours
  wild, as with garbage depth), quarter-size buffers in the top-left, and one frame of the normals G-buffer with only
  the forward-drawn chairs shaded (every lighting pass rejected). hw9 was mostly noise; gameplay outdoors (bus,
  checkpoint, Pagan's intro) renders right at ~30 fps; the dinner runs at 10 fps (GPU 96 %).
  - Found: BindTargets ran the colour-to-depth transfer before settling a depth hand-over (banjo_deko3d_depth_handover,
    deko3d only), so a resolve still sampling the depth image read the transferred depth. The hand-over's resolve is
    now drawn first whenever a transfer is due (edram_transfer.cpp ColorToDepthDueLocked), and the hand-over is off
    in FC4's Switch defaults (one depth copy a frame).
  - Ruled out on PC: the Switch's eviction pressure (run pcpress1: memory policy on, reserve over the budget: no noise
    frames). PC Vulkan (`--renut_gpu_backend=vulkan`) loses its device 3 s in (vkdin1): no PC repro of the SPIR-V path.
  - Lighting shader ps_731cb5fa99c50d91: oC0 = lerp(fog colour, surface, fog transmittance) x c48.z; the surface terms
    all scale with r15 = t5.rgb^2 x (1 - t7.z) (t5/t6/t7: the three 1280x704 G-buffer resolves, t0 the depth's float
    target, t2 the 2304x768 shadow atlas, t3 the 640x352 light buffer, t4 the height map). "Near objects unlit, far
    right" fits a zero surface term with only fog left.
  - G-buffer layout (traced, pctrace5; the resolve trace now names each destination's page): material shaders
    (ps_54aafaff197d9523, ps_86af00885343b934) write oC0 = sqrt(albedo), oC1 = normal x 0.5 + 0.5, oC2 = material
    params, oC3.x (no fourth target bound). Resolves RT0 -> E-view page F3D07 (physical 13D08), RT1 -> F4077 (14078),
    RT2 -> F43E7 (143E8); the lighting draw binds 13D08 / 14078 / 143E8 at slots 5 / 6 / 7, as its shader expects.
    The "L" show_texture role is the last lighting-type draw of the frame, whose slot order can differ: its slot 5/6
    views (normals-like / albedo-like) do not prove a swap. Near-objects-unlit is still open.
  - GPU clock: sys-clk accepted fc4_clock_gpu_mhz 768 but the console ran at 614.4 MHz handheld (sys-clk's own cap).
- Switch hw11 NRO (D:\switch\fc4-nx\fc4-nx.nro, hw10 kept as fc4-nx.hw10.nro.bak; ELF out/switch_runs/renut_hw11.elf):
  the crash fixes and the hand-over change above. hw10's 21 clips are in out/switch_runs/hw10/album (deleted from SD).

## Console run hw11 (2026-11-11): freeze at the first weapon, noise frames
- **Freeze:** the same guest heap exhaustion as hw10 (`AllocFixed: could not commit 0x10000 ... backing 674 MB`, from
  01:01:59; the game thread stalled on the commits at 01:03:36, no crash report). hw11's give-back never ran: the region
  still grew from 326 to 1,638 MB in 4.3 s inside one loading frame (00:42:50.8 - 55.1; no texture check can run in
  it), and after the eviction the emptied chunks (64 MiB given back nine times) were never at its bottom: 0 givebacks,
  742 MB free inside the region, newlib's room 2 MB.
  Fix: `banjo_deko3d_gpu_region_max_mb` (1024): the region grows no further; blocks past it take the heap path, and an
  image chunk made there is ordinary newlib memory once emptied (released when the room is short or on the guest
  heap's pressure callback). Gameplay held 755-900 MB of blocks in the region.
- **Noise frames (dinner, De Pleur's mansion):** UnuseTarget destroyed a render target the moment no surface header
  named its EDRAM view, and the next header naming it got a new, empty one. PC run pckeep1 counted 900 such targets in
  300 frames: 3 render targets destroyed and made again every frame. On PC a new texture comes up zeroed; deko3d's image
  heap hands out stale bytes (the noise, herringbone patterns of other textures, the quarter-size half-res pass left
  in the top-left of a target). `banjo_renut_keep_unused_targets` (on): the target keeps its image until idle 300
  frames (30 under memory pressure); the "[renut] targets" line counts kept / taken up again / reaped every 300 frames.
  PC picture unchanged (its near-objects-dark is the D3D12 reversed viewport depth range, above).
- hw11 clips: outdoor cutscenes right at 30 fps; dinner lit on the console (unlike PC) but overexposed, with noise
  frames; the mansion gameplay ~50 % noise frames; fps 7-30 (median 17.5).

## Console run hw12 (2026-11-11): no freeze; noise frames and overexposure in gameplay
- The freeze is gone (region cap). The run's log is in fc4.1.log + fc4.log on the SD (spdlog rotates at 5 MB, up to
  20 files: collect fc4*.log). Gameplay from the user's save: outdoor scenes blown out (white grass, blue-white rock),
  ~half the frames noise (purple / yellow or cyan herringbone that follows the scene's edges; particles, HUD and
  subtitles drawn right over it), a dark or red quarter-size image in the top-left of some frames; 11-21 fps.
- **PC does not reproduce it:** the user's save (renut/B13EBABEBABEBABE/555308CA on the SD, copied to
  out/pc_user/B13EBABEBABEBABE) loads on PC with the dinner input script (49:DOWN,52:A picks Continue (Offline) when a
  save exists; B closes the tutorial cards). Run pcplay7: the same jungle renders right, normal exposure, no noise;
  pcslow1 (banjo_renut_diag_frame_sleep_ms 70, 12.5 fps like the console): no noise either. So the cause is on the
  deko3d path (or the console's timing), not FC4's renderer emulation as such.
- Ruled out: Renut's dynamic resolution (off; x1 scale all run), target growth (the same one event as PC), the luminance
  grid's layout (texels as the GPU writes them, then the 8in32 swap), the readback's caches (map invalidates; L2 flushed
  after the copy), the ring cleaner (submits wait for its ticket), VS output pruning (masks, never renumbers).
- Found and fixed (banjo_renut_depth_words_supersede): a depth resolve's words stayed registered for its page (g_depth_words) until its texture was retired,
  so an 8_8_8_8 texture over memory FC4 had since reused for a colour resolve could sample old depth words (the noise
  looks like D24S8 words as colour). A colour resolve into the page now drops them ("[renut] colour resolve ... depth
  words dropped").
- hw13 is a diagnostic build: banjo_renut_diag_resolve_trace on, every 8 s (banjo_renut_diag_resolve_trace_every_s),
  with banjo_renut_diag_trace_probes: each traced frame's full-width colour resolves get a 96x64 centre patch read back
  and logged with mean and jitter ("[trace] probe ..."), so noisy traced frames name themselves and the resolve where the
  noise starts; banjo_renut_diag_readback_stats on (the luminance values behind the exposure; the traced lighting and
  composite draws log c48 too, comparable with PC's).
- Why the console and not PC: the console's GPU is slow enough that FC4's own dynamic resolution moves (960x608 and
  480x304 resolves in hw12; PC stays at 1280x704), and its resolve buffers then share pages between formats. A
  16_16_16_16 resolve (B3239834, the bright-pass mask) and an 8_8_8_8 one landed on one page; the page-keyed slot
  kept one, and the other was made from guest memory (hw12's [flash] lines): garbage values, white-out.
  banjo_renut_resolve_format_slots (on) keys page slots by format too, and a fetch whose page last took another
  format's resolve samples its own format's there. Not when the page's last is a depth resolve with its words
  registered: FC4 samples depth as 8_8_8_8, and PC run pcslot1 (the fallback without that guard) took an older colour
  resolve for depth.
- PC reproduces the white-out: from the user's save with sticks held, the player walks into the fire, burns, dies and
  respawns; around the fire and after the respawn the sky and ground go white with black stair-step blocks (runs
  pcslot1, pcab_noslot, pcab_none: with or without today's texture changes, so older). FC4's dynamic resolution moves
  there on PC too (the fire's particles), and the luminance grid's readback was kept by size (80x44 / 80x42 / 80x40):
  a new size had no readback, the CPU read what the memory held and the exposure ran away. The console changes size
  all the time: its white outdoor scenes. banjo_renut_resolve_readback_any_size (on): a size with no readback yet gets
  the newest one of the formats and width (80; FC4's 60-wide 16_16_FLOAT reads in the menus stay apart), resampled.
  The values written back are real in gameplay now (luminance means ~0.02; 1.0 / 0 in the menus).
- Not the white-out after all: PC run pcfinal2 (the readback fix) still has it. Its G-buffer probes say why: the
  three 1280x704 G-buffer resolves read 0.96 / 1.0 in every channel at the centre (normal frames ~0.38 / 0.62 / 0.07),
  which is FC4's G-buffer clear (colour 1 1 1 1): nothing drawn there, 75 draws into the G-buffer against ~124 in a
  good frame. Geometry (the ground) missing, with black stair-step blocks: the height map (64x64 16_16 tiles into an
  atlas) is the suspect. "Draw dropped" now logs its running count at powers of two past 16.
- Still open (pcfinal3, pcnokeep): no draw dropped in those frames, and banjo_renut_keep_unused_targets=false keeps
  the white-out. After the respawn the player lies looking up, so a G-buffer at its clear value there may simply be
  sky: then it is the sky (and the stair-step blocks its low-resolution parts) coming out white, i.e. the sky or
  exposure path, not missing ground. hw13's console traces settle which: probes of the G-buffer resolves at 1.0
  (nothing drawn) or at normal values with a high c48.z (exposure). (The red tint in those runs is the player burning: gameplay.)
- PC bisect runs need the menu input that survives the Xbox Live popup: `44:DOWN,45:A,52:DOWN,54:A` (a popup
  swallows DOWN; the menu's cursor starts on Continue (Online), one DOWN is Continue (Offline)).

## Console run hw13 (2026-11-11): two Switch-only causes found
- The user's run (log in fc4.log from 07:35, 7 clips in out/switch_runs/hw13/album; frames pulled with a small WinRT
  MediaComposition grabber, no ffmpeg): most gameplay frames corrupt. The G-buffer probes were normal (albedo ~0.3-0.5,
  normals ~0.5-0.78, as on PC), so the geometry pass is right; the damage is after it.
- **Cause 1, the white grass / cyan rock: renut_post_process_precision = "Game" in the Switch defaults** (PC: High).
  The trace's resolves differ from PC's in their host formats only: PC's 640x352 and 160x88 / 80x44 passes are
  R16G16B16A16 (FLOAT 10 / UNORM 11), the console's RGBA8 (20). FC4 binds the same 640x352 EDRAM as 2_10_10_10_FLOAT and
  as 8_8_8_8; with High the 8_8_8_8 view is 64-bit and banjo_renut_view_float16 joins it to the float target, with Game
  it is a separate RGBA8 host target holding other content. PC with --renut_post_process_precision=Game (run pcgame1)
  shows the console's picture: white grass, cyan-white rock, washed-out scenes. hw14: High on the Switch too.
- **Cause 2, the top-left quarter (and old content around it): Maxwell clips a draw to its smallest attachment**
  (usf4-nx's docs/deko3d-renderer-usf4.md, section 5). DropSmallerDepth left a smaller depth target out only when its
  render scale differed; at 1x (always, on the Switch) a quarter-size pass's depth target stayed bound for the
  full-screen passes and only their top-left 640x352 was drawn. Now by host size (draws, the fast path and clears);
  "[renut] depth target ... left out" logs the case, and colour targets of unequal sizes in one draw are logged.
- Generic shader variants: 1777 stages drew with their generic variant, 258 swapped in their own by the end of the
  run (the uam thread rests between background compiles). "Same pixels" by design; not shown wrong yet.

## Console run hw14 (2026-11-11): exposure right, noise frames remain
- The user's run (fc4.1.log + fc4.log from 08:11, 9 clips and 4 screenshots in out/switch_runs/hw14/album): the good
  frames now have the PC's exposure (post-process precision High). The purple / yellow herringbone frames remain:
  out/switch_runs measured with a colour-step metric (scratch tool), hw12 18 % of clip frames noisy, hw14 10 %.
  The user felt hw11 / hw12 played better (the phone scene, the tutorial cards loading); the trace's frames hitched
  every 8 / 20 s in hw13 / hw14.
- "[flash] ... made from guest memory": hw12 12, hw14 2 (banjo_renut_resolve_format_slots took B3239834's).
- Draws that test a smaller depth target (dynamic resolution: 1280x704 colour with a 640x336 or 1280x672 depth,
  640x352 with 640x336; VS 793395BDBC0250CA without a pixel shader, RB_DEPTHCONTROL 00700203 / 00704573): kept and
  cut on Maxwell. hw15: banjo_renut_grow_tested_depth grows such a depth target's view to the colour's size (once,
  from its next bind).
- **plume's deko3d discardTexture did nothing.** Images are sub-allocated from reused memory and render targets have
  hardware compression (colour always, depth with banjo_deko3d_depth_compression): a new target started with the
  previous image's bytes and compression state, which blends into it and reads of parts not yet drawn return.
  hw15: banjo_deko3d_discard_clears (Deko3DOptions::discardClears) clears a new render / depth target (bound alone,
  then the list's framebuffer again) wherever Renut discards one (new surfaces, resolve destinations, depth words).
- hw15 has the trace off (banjo_renut_diag_resolve_trace false).

## Console run hw15 (2026-11-11) and the hw16 self-test
- hw15 (fc4.log from 08:49, 9 clips in out/switch_runs/hw15/album): improved (the tutorial cards load faster with the
  trace off) but the noise frames remain, ~15 % of clip frames by the metric; their look is the same every time
  (purple / yellow stripes above, teal blocks along the ground), with particles and the HUD drawn clean over them.
  No GPU allocation failed; the texture reserve is under pressure all run (budget ~830-875 MB, 768 MB reserve).
- ReCoD4 (github.com/DevZer0D4Y/ReCoD4) is the PC CoD4 source (KisakCOD) on iOS, not an Xbox 360 recompilation:
  nothing for Xenos / EDRAM.
- hw16 measures it on the console: banjo_renut_diag_noise_probe reads back a 256x32 band of each frame's last
  full-screen 8_8_8_8 resolve (the front-buffer copy) and counts purple / yellow noise, by the in-run A/B state;
  banjo_renut_ab_targets "71,72,73,74,14,18,39" at 5 s halves. New A/B targets: 71 banjo_deko3d_barrier_lean (plume's
  missing image invalidation before writes and Renut's read-to-read transitions), 72 banjo_deko3d_barrier_merge, 73
  banjo_deko3d_draw_resolves, 74 banjo_deko3d_discard_clears. The A/B left a plume flag target (39, 68) off when its
  list moved on: AbApply now sets all of them as configured first. PC: 0.1 % (a few hits on fire), the console ~15 %.

## Console run hw16 (2026-11-11): the noise is the merged barriers; near objects black found
- "[noise]" at the run's end (fc4.log 09:0x-09:20): all on 415 / 2921 frames noisy (14 %); with 72
  (banjo_deko3d_barrier_merge) off 14 / 524 (3 %); 14 off 19 %, 18 off 14 %, 39 off 20 %, 71 off 12 %, 73 off 11 %,
  74 off 12 %. hw17: banjo_deko3d_barrier_merge false on the Switch. (Why merging breaks it is not pinned down: plume
  emits a held barrier at the next draw after that draw's buffer and texture binds and pushed constants, where unmerged
  barriers came before them; every work command flushes.)
- **Near objects black (the machete, foliage, the phone; PC too, its old "near objects unlit"):** FC4 restores its
  640x352 half-resolution depth through an 8_8_8_8 colour target at the depth's EDRAM (the words, then the depth target
  bound there). With renut_post_process_precision High an 8_8_8_8 target of half the screen is 64-bit, and
  ColorOverDepthLocked looked for RGBA8 only: no transfer, the light volumes tested a stale depth, the half-res light
  buffer (resolves of B2E7AF50 into 8_8_8_8) stayed 0. Now it takes the latest of the RGBA8 / R16G16B16A16 UNORM /
  FLOAT targets there (the shader's round(v * 255) gives the same bytes). PC run pcnear1: the phone scene and the near
  foliage lit; the light buffer probe 0 -> 0.56. hw11 / hw12 (precision Game) had it lit for this reason.
- New: banjo_renut_view_float16_8888 (false): an 8_8_8_8 view made 64-bit by High stays 16-bit unorm (clamped as the
  console's 8-bit) instead of joining a float target.
- Still open: near objects are now lit but too bright (white grass, cyan-white rock on PC, as the console's hw12). The
  exposure is not the cause: c48.x stays 3.341 in gameplay with near objects black (pcfinal1) and lit (pcnear3); the
  near lighting itself runs hot (suspects: the sun's shadow term from the 2304x768 atlas, the light buffer's scale).

## Console run hw17 (2026-11-11) and hw18: the overexposure is the 7e3 picture; the noise reproduced on PC
- hw17 "[noise]": windows at ~30 fps (GPU ~30 ms a frame) 0 % noisy, windows at 12-18 fps (GPU 66-86 ms, the fire
  scene) 25-58 %. No A/B target (14, 39, 71, 73, 74) removes it. A noisy frame: the whole scene behind a purple /
  yellow / teal herringbone, the fire and smoke right over it, now and then the scene black.
- **Overexposure (PC and console): the composite decodes 7e3 bits.** FC4 draws its HDR picture into a 7e3 target
  (D3DFMT 1A2201BF, 2_10_10_10_FLOAT_EDRAM) and resolves it through a second surface over the same EDRAM with the fixed
  format 1A2001B6 (2_10_10_10_AS_16_16_16_16), no exponent bias, into the texture the composite samples with exponent
  adjust +3 (t1 of ps_97f6587d89ad217a). The console's resolve reads the EDRAM's 7e3 bits as 10-bit unorm, so the
  texture holds each channel's 7e3 code; the composite takes floor(8 x t) as the exponent and frac as the mantissa and
  rebuilds the value with exp2 (then bloom, the particle buffer t3, a filmic curve, sqrt, a 3D LUT). Renut's float
  target copied the values, which the decode blew up exponentially: the white, washed-out picture, worst on bright near
  objects. New banjo_renut_resolve_7e3_bits (true): a target last written through a 7e3 view (HostSurface::
  written_format 63) resolved through a fixed 2_10_10_10 view into a 2_10_10_10 texture is copied as the 7e3 codes /
  1023 (resolve_copy_ps param0 7, Xenia's float-to-7e3 rounding). PC run pcbits1: normal exposure and colour (the phone
  scene, grass, rock, sky). The first resolve of the pair (the 7e3 view, bias -5, exp adjust +2) lands in the same page
  and is overwritten, as on the console.
- The light buffer (t3 of the lighting pass) is FC4's GI: ps_c1155dbb6bd3186c samples six 16_16 probe maps at the
  pixel's world XY (scale / bias in the shader), blends to a constant ambient with distance and writes sqrt; cleared to
  1 where the sky is (depth beyond c252.z). The lighting squares it, times c92.x, as the ambient of the diffuse and the
  reflection. Its view (L3) and the sun's 2304x768 three-cascade atlas (L2) look right.
- **Noise reproduced on PC:** run pcsmaa1 (banjo_renut_diag_frame_sleep_ms 50, so FC4 drops its resolution) has the
  console's frames in the fire scene: 143 of 2,828 frames noisy. (SMAA, Switch-only in the defaults, is not involved:
  "0 frames", FC4's composite is not in its list.) New: "[noise] frame N noisy" per frame, to match with the trace.
- **Noise cause: surface headers read a frame late.** pcnz1 (the same, trace every 2 s): noisy frames often every
  other frame (1721, 1723, ... 1737). Traced noisy frame 2287: the second HDR resolve's source was AD311B30, "view of
  AD314740 (info 00000000 format 1A2001B6)", a separate host target (host format 20) with other contents; in clean
  frames the same resolve's surfaces (AD3107E0, AD311B00, ... a new one each frame) join the 7e3 float target (view of
  B2F0AFE0, info 14000500), or never reach Renut. At a lowered resolution FC4 makes D3DSurface objects for its
  resolves every frame through its own D3D code (CreateSurface and Destroy are not hooked in FC4) and frees them; the
  console's GPU never reads a surface header (D3D writes RB_SURFACE_INFO / RB_COLOR_INFO at the bind), but Renut's
  render thread read them in guest memory when it replayed the draws and resolves, a frame or two behind the game: by
  then the memory was zeros (pitch 0: another target) or another surface's. Slow frames (the console's fire scene, a
  PC with banjo_renut_diag_frame_sleep_ms) put the render thread further behind and FC4 at the lower resolution.
  A first try copied the header at the SetRenderTarget / SetDepthStencilSurface hooks: no effect (pcsnap1: 33
  noisy frames), as d3d/hooks/state.cpp is not built for FC4 (its own D3D setters write the device); removed. pcsnap3
  logged the resolves of fixed 2_10_10_10 views: the bad ones had headers "info 00000000 colour info 00000000" or
  ASCII ("74656E73", "6974795F": the memory reused for strings), while the device's register copies at the resolve
  were right every time (surface info 14000500, colour info 00020000: pitch 1280, EDRAM base 0, the 7e3 target's).
  **Fix: banjo_renut_surface_registers (true).** D3D's SetRenderTarget / SetSurfaceInfo / SetDepthStencilSurface
  copy RB_SURFACE_INFO and RB_COLOR_INFO / RB_DEPTH_INFO into the device (m_DestinationPacket), which each draw's and
  resolve's device snapshot carries. GatherTargets and the resolves look up a slot's surface through
  GetHostSurfaceRegsLocked: a header that contradicts those registers (no pitch, another EDRAM base, RT0's pitch
  differing, a depth format in a colour slot) is placed by the registers instead (size kept within the pitch,
  format from the colour info when the header's does not match). pcregs1 (slowed as pcsmaa1): 0 of 2,831 frames
  noisy, the fire scene clean.
  At normal speed (pcfinal2: 0 of 4,799 noisy) the override also catches FC4 rewriting a surface object in place
  after the bind (header 8_8_8_8 at EDRAM 0x540, registers 2_10_10_10 at 0): the registers are what the console used.
- Also in hw18: GrowDepthForColorLocked ignores colour sizes beyond 1280x736 or 9/4 of the depth (the garbage-header
  sizes such as 1x2049 / 4257x704 had grown a depth target to 1280x1543); "[noise] frame N noisy" per frame.
- The minimap's background is black on PC only; the user reports the console's minimap fine.
- Switch hw18 NRO (D:\switch\fc4-nx\fc4-nx.nro, hw17 kept as fc4-nx.hw17.nro.bak; ELF out/switch_runs/renut_hw18.elf):
  banjo_renut_resolve_7e3_bits, banjo_renut_surface_registers, the growth limit; in-run A/B off
  (banjo_renut_ab_targets ""), the noise counter on. hw17's 13 clips are in out/switch_runs/hw17/album (deleted from SD).

## Console run hw18 (2026-11-11) and hw19: depth tiles, Zcull, 540p
- hw18 (out/switch_runs/hw18: 12 clips, 9 screenshots, logs, rex_profile.log): noise 2 of ~7,000 frames. Gameplay
  12-17 fps, GPU 60-80 ms a frame (light scenes 30 fps at 22-26 ms), render thread 20-55 ms at 600-1,100 draws a frame.
  The user's list: smoke through objects, shadows blocky at first when turning, lines in the sky at the wake-up,
  boxed leaves, a blocky wound decal, black blocks in the sky (melee and turning), the phone's screen slightly off.
- **Depth tile halves (PC and console):** the wake-up shot reproduces on PC (banjo_renut_diag_frame_sleep_ms 50,
  pcsky1 59 s): the sky behind the trees in vertical strips 40 guest pixels wide, staircases at the rock's edge. In
  the EDRAM a depth tile (80x16 samples) holds its 40-sample halves the other way round from a colour tile; FC4's
  depth restores (pass-through quads of words through an 8_8_8_8 view, then the depth bound at that base) write the
  words pre-swapped for the console's depth view, and Renut's colour-to-depth transfer copied them pixel for pixel:
  the restored depth (full and half resolution) was off by half a tile wherever the depth changes, which the sky,
  the light volumes and GI, the particles (GEQUAL on the half-res depth) and decals all test. New
  banjo_renut_color_to_depth_swap (true): the transfer reads each pixel's word from the other half of its tile
  (40 guest pixels in host pixels; single-sampled 32-bit views). pcsky2 / pcsky3: the sky clean; pcswap1 normal.
- Zcull off on the Switch (banjo_deko3d_zcull false): tile-sized wrong culling is a known deko3d hazard here (shader-
  written depth, reversed Z on the half-res depth, one depth image under several framebuffers). plume's
  Deko3DInvalidateZcull now drops it after Renut's colour-to-depth draw and after game draws whose pixel shader writes
  depth (only with Zcull on).
- Frame rate: the 3D image at 960x540 handheld / 1152x648 docked with the HUD at 720p (banjo_renut_render_height_*,
  the composite ps_97f6587d89ad217a as banjo_renut_smaa_after_ps, SMAA off); PC run pcscale1 (renut_resolution 480p,
  2/3 scale): FC4's passes right, no noise. msaa_level 2 (the half-res 4x target). The SD's katamari.toml: those two,
  switch_profile_stacks and banjo_deko3d_bind_trace off (the 1 kHz stack sampling cost CPU); its old copy in
  out/switch_runs/hw18/katamari.sd-before-hw19.toml. Noise probe and readback stats off. renut_gpu_profile 30: the
  next log has "GPU profile:" by pass.
- hw18's render thread (rex_profile.log, gameplay): memmove 15 %, ConvertVertices 9 %, FastDrawLocked 7 %,
  DropReplacedRanges 5 %, PmullHash 4 %, free 4 %, PushFloatConstants 3 %, the noise probe 2 %. PC GPU profile
  (pcprof1, 5.9 ms a frame): shadow cascades 15 % (305 depth draws into three 768x768 views), resolves 9 %, the
  G-buffer's terrain / foliage 8 %.
- Switch hw19 NRO (hw18 kept as fc4-nx.hw18.nro.bak; ELF out/switch_runs/renut_hw19.elf). hw18's album deleted from SD.

## Console run hw19 (2026-11-12) and hw20: the smoke is the stencil-only restore; 540p reverted
- hw19 (out/switch_runs/hw19/album: 12 clips, 4 screenshots, deleted from SD): the sky at the wake-up right (the depth
  tile swap stays); new black flashes, the scene drawn in a corner and a blown-out picture at times. The 540p / 648p
  3D image (banjo_renut_render_height_*, with ps_97f6587d89ad217a as the composite marker) is deko3d-only and never ran
  on PC; FC4 has three composites (97F6587D89AD217A, 4028C59B1F01C10D, C93EFBA9789F3658), so the scaled path switched
  on and off between frames. hw20: 720 / 720 and banjo_renut_smaa_after_ps "" again (defaults, the player's toml
  template and the SD's katamari.toml).
- **Smoke through objects (PC and console):** FC4's half-resolution depth B2F0AE00 (640x352, EDRAM 0x750) gets its
  depth from ps_0c610e898c7ca69a (SV_Depth, a downsample of the full depth), then its stencil marks from
  ps_73757ece81680f5e through an 8_8_8_8 view at the same base with only R enabled (RB_COLOR_MASK 1: the stencil byte
  of the D24S8 word). On the console that leaves the depth bytes as they were. Renut's colour-to-depth transfer took
  the colour target's whole words, its never-written G / B / A bytes over the downsampled depth: the half-resolution
  particles (GEQUAL on it: smoke, steam, fire) drew through everything. New banjo_renut_color_to_depth_mask (true):
  HostSurface::written_channels (the colour write masks since the last transfer, 0xF for clears) picks the passes: R
  alone, only the stencil bits; G / B / A, the depth. PC A/B pcmask0 / pcmask1 (fire scene, 110-125 s): the steam plume
  behind the trees drawn over them without, hidden with; the transfer log shows "channels 1" for the half-res depths
  and "channels F" for the full depth restores.
- The pasted Vulkan list (GTA IV on Xenia): stencil export would make the eight stencil-bit passes one, but
  Renut's deko3d path has no shader stencil export (hence the passes); depth clip is on as FC4 sets it (PA_CL_CLIP_CNTL
  0x00080000); border colours are the console's three; fragment shader interlock is for an ROV-style EDRAM, not
  Renut's host targets.
- Switch hw20 NRO (hw19 kept as fc4-nx.hw19.nro.bak; ELF out/switch_runs/renut_hw20.elf).

## Console run hw20 (2026-11-12) and hw21: white-outs, boxes
- hw20 (out/switch_runs/hw20: 10 clips, 4 screenshots, fc4.log; album deleted from SD): smoke fixed, no black flashes
  (scratch dark.py), phone and healing better. The picture blows out to white from 00:10:30 and stays so (blue-white
  rock, yellow leaves); hw18 / hw19 clips have short white stretches too. Boxed fire light on leaves and black blocks in
  the sky, both worse while turning; the user's hw19 image has the leaves too.
- **msaa_level 2 broke the half-resolution HDR copy.** FC4 makes it by resolving a 640x352 4x view nothing draws over
  the 1280x704 1x HDR target (DownsampleResolveCopy, the 2x2 box). DownsampleSourceLocked asked for a host target of 4
  samples; msaa_level 2 (hw19 / hw20) made it 2, the box path was skipped and the resolve read the empty 2x target.
  Now the view's own MSAA from its TargetKey (bits 26-27 = 2, 4x). PC pcmsaa2b: "resolve of a 4x view nothing drew"
  again with msaa_level 2. msaa_level back to 4 (template and the SD's katamari.toml; its old copy in
  out/switch_runs/hw20/katamari.sd-before-hw21.toml): FC4 never draws a 4x target, so 2 saved nothing.
- PC reproduces a white-out with banjo_renut_diag_frame_sleep_ms 50 (FC4's dynamic resolution), but not every run
  (pcslow1-3 white from the wake-up; pcslow4-6 and the A/Bs not). In a white traced frame the exposure constant c48.x
  (3.1-3.3, = E, 1/E, 8E, 1/8E) and the composite's bloom weight c65.x match the normal run; the composite is
  ps_4028c59b1f01c10d (no half-res particle buffer) instead of ps_97f6587d89ad217a, and decodes the 7e3 bits the same.
  The HDR picture is resolved twice into one page each frame (view 63 with bias 2^-5, then view 54 as bits: the
  [trace] "bits_7e3" line); both reach the same page-keyed destination in order. Ruled out by A/B (each off):
  clear_repeat, resolve_skip, resolve_extents (off leaves the lowered resolution's strip black), grow_tested_depth,
  color_to_depth_swap / _mask. The 80x44 16_16_FLOAT grid the CPU reads back is per-tile depth (reversed Z, near 1),
  not luminance.
- **Boxes:** plume never calls dkCmdBufResolveDepthValues, and depth targets have hardware compression
  (banjo_deko3d_depth_compression) while FC4 samples depth everywhere (lights, decals, sky, particles, fog). hw21 test:
  depth compression off (Zcull off in hw19 left the boxes). PC (no compression) has no leaf boxes in the fire scene.
- hw21 also traces a frame every 30 s (banjo_renut_diag_resolve_trace) for the white-outs' constants and resolves.
- Switch hw21 NRO (hw20 kept as fc4-nx.hw20.nro.bak; ELF out/switch_runs/renut_hw21.elf).

