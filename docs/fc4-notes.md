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
- Not run yet: `tools/pointer_fixpoint.py` and `tools/gap_sweep.py` (functions only reachable through data pointers or
  computed addresses; Katamari needed 111 + 85) and `tools/switch_check.py` (jump tables). Each pass of the first two
  is a scratch codegen plus a real one, so about 45 minutes a pass here.
