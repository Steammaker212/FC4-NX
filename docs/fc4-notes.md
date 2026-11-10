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
