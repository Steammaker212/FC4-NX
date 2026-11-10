# Far Cry 4's shaders: extraction and translation census

Started 2026-11-09. Covers where the game's Xbox 360 shaders are, how they come out of the Dunia archive, and how many
get through the base's translation chain (Renut's XenosRecomp -> DXC -> SPIRV-Cross -> uam, `tools/switch_shaders.ps1`).
Method docs: renut-nx `docs/shader.md` and `docs/deko3d-shader-optimisations.md`. Everything extracted stays in `out/`
(ignored); game data is never committed.

## Summary

| | Count |
| --- | --- |
| `shadersobj.fat` entries | 6,765 (6,557 shader objects, 205 render-state texts, 3 `HEAD` tables) |
| Xbox 360 shader containers | 6,557: one per shader object (5,295 pixel, 1,262 vertex) |
| Unique by XXH3 (Renut's shader hash) | **6,523: 5,262 pixel, 1,261 vertex** |
| Containers in `game.xex` (`out/renut_image.bin`) | 0 |
| Translated by XenosRecomp | **6,523 of 6,523**: no crash, no translator warning |
| Compiled by DXC to DXIL (Windows SDK DXC 1.8.2502.11) | **6,523 of 6,523** |
| SPIR-V (deko3d), DXC 1.9.2609 | 6,201: all 5,262 pixel, 939 of 1,261 vertex. **322 vertex shaders fail: one class, `FOG0` / `PSIZE0` vertex inputs without a location** |
| GLSL (SPIRV-Cross + `deko3d_glsl.py`) and uam | every shader that reached SPIR-V: 6,201 |
| With the location fix (2 rows in `shader_common.h`, tested on a copy) | **6,523 of 6,523 through uam** |

So: Katamari had 195 shaders and Nuts & Bolts 4,881; Far Cry 4 ships 6,523, all in one archive and none in the
executable.

## The archive (`installation1/shadersobj.fat` + `.dat`)

Dunia 2 `FAT2` index, version 9 (Far Cry 4), worked out from the files themselves; Gibbed's Dunia tools are the public
reference for the family. `tools/fc4_dunia_fat.py` lists, verifies and extracts it.

`.fat` header (little endian, 24 bytes):

| Offset | Field | shadersobj |
| --- | --- | --- |
| 0x00 | magic `32 54 41 46` ("FAT2" read as a little-endian word) | |
| 0x04 | version | 9 |
| 0x08 | flags: byte 0 platform, byte 1 unknown, high half 0 | `02 04 00 00`: platform 2 = Xbox 360 |
| 0x0C | sub-FAT entry total | 0 |
| 0x10 | sub-FAT count | 0 |
| 0x14 | entry count | 0x1A6D = 6,765 |

Entries follow at 0x18, 20 bytes each, **big endian** (the platform's order), sorted by hash:

| Offset | Field |
| --- | --- |
| 0x00 | 64-bit name hash (names are not stored) |
| 0x08 | uncompressed size << 2 (0 = stored as is). The low 2 bits are taken as offset bits 34-35: always 0 here |
| 0x0C | offset >> 2 |
| 0x10 | (offset & 3) << 30, compressed size in the low 30 bits |

After the entries, two 32-bit zero words (empty localisation / sub-FAT tables): the file is 24 + 20 x 6,765 + 8 =
135,332 bytes. The `.dat` holds the entries back to back with no gaps (the tool checks this): 7,939,004 bytes.

A compressed entry in the `.dat`:

| Bytes | What |
| --- | --- |
| 1 | N: how many of the entry's **last** bytes are stored as they are, after the stream (0-2 in shadersobj, up to 12 in common) |
| 5 | LZMA properties `5D 00 00 80 00` (lc 3, lp 0, pb 2, 8 MiB dictionary) |
| ... | raw LZMA stream, no end marker, decoding to uncompressed size - N bytes |
| N | the entry's last N bytes |

The leading byte matters. A plain `.lzma` decode of everything after the properties (the tail bytes read as stream
input) differs or fails on: 3 of shadersobj's 24 entries with N > 0 (wrong last bytes); in common 118 wrong, 63 short
and 35 failing of 307; in ige 62 wrong, 54 short and 7 failing of 534.

shadersobj: 3,918 entries compressed (N = 0: 3,894, N = 1: 22, N = 2: 2), 2,847 stored; 10,952,467 bytes
uncompressed. Kinds by first bytes: 6,557 shader objects (`8D 06 08 00`), 205 render-state texts
(`AlphaBlendEnable=True\nSrcBlend=...`, D3D state blocks by name), 3 `HEAD` tables (80-192 KB, big endian offset
tables; not shaders).

The same reader decodes every entry of `common.fat` (2,695 entries, 269.6 MB uncompressed), `ige.fat` (6,901,
117.3 MB) and `sound_english.fat` (19,979, all stored, platform byte 0), with no failures.

## The shader objects

Every shader object (all 6,557) is a 12-byte header, a binding table, then one Xenos shader container that ends the
file:

| Offset | Field |
| --- | --- |
| 0x00 | `8D 06 08 00` |
| 0x04 | big-endian u16: offset of the container = 12 + 8 x N |
| 0x06 | 0 |
| 0x08 | 4 |
| 0x09 | N, the number of binding records |
| 0x0A | 0 |
| 0x0C | N records of 8 bytes: a 32-bit hash (a constant or sampler name) and 4 register bytes (index / set / count) |
| 12 + 8N | the shader container (magic `10 2A 11 xx`, low bit 1 = vertex shader), virtual + physical size to the end |

`tools/fc4_shaders/fc4_shader_containers.py` scans every extracted entry with `tools/renut_shader_dump.py`'s
`find_shader_headers` (aligned and unaligned) and checks each shader object's header against it: the scan finds
exactly the one container the header names in all 6,557, and none in the render-state texts or `HEAD` tables.

30 containers appear in more than one shader object (28 twice, 1 three times, 1 five times), so 6,523 are unique. Microcode (the container's physical part):

| | Unique | Median | Max | Total |
| --- | --- | --- | --- | --- |
| Vertex | 1,261 | 1,216 B | 3,244 B | 1.40 MB |
| Pixel | 5,262 | 664 B | 4,680 B | 5.98 MB |

`out/renut_image.bin` (game.xex's loaded image, 37.3 MB) holds **no** containers, aligned or not. So the
renderer gets every shader from shadersobj. The container hash this census names shaders by
(`{vs,ps}_<xxh3_64>.bin`, as `tools/renut_shader_dump.py` and XenosRecomp do) is Renut's lookup key only if the game
hands `D3DDevice_Create*Shader` the container bytes as stored (from offset 12 + 8N of the loaded object). The first PC
runs' shader capture should confirm that.

## Translation census

`tools/fc4_shaders/fc4_shader_census.py` runs `tools/switch_shaders.ps1`'s steps on one shader at a time, so a
failure never hides another:

1. **translate**: `XenosRecomp <container> <out.hlsl> <shader_common.h>`, the translator's single-file mode. Same
   `recompile()` and same text as the directory mode's HLSL dump. A crash shows as an exit code, and the translator's
   stderr warnings are kept.
2. **dxil**: `dxc.exe` with XenosRecomp's own DXIL arguments (`-T vs_6_0|ps_6_0 -HV 2021 -all-resources-bound
   -Wno-ignored-attributes -Qstrip_reflect -Qstrip_debug -DRENUT_RECOMP`; `lib_6_3` for a shader that reads
   specialization constants).
3. **spirv**: the deko3d arguments (`-spirv -fvk-use-dx-layout -DBANJO_DEKO3D`, as `BANJO_DEKO3D_SPIRV_DIR`
   compiles).
4. **glsl, uam**: `tools/deko3d_shaders.py`'s per-shader step: SPIRV-Cross, then `tools/deko3d_glsl.py`, then uam on
   the default variant.

It runs 6 processes at below-normal priority. The whole chain over 6,523 shaders takes 300 s.

Results (2026-11-09; DXIL with the Windows SDK's DXC 1.8.2502.11, SPIR-V with Microsoft's DXC release 1.9.2609,
SPIRV-Cross `adec7ac`, uam 1.1.0 from `app/thirdparty/uam`):

| Step | Vertex | Pixel |
| --- | --- | --- |
| translate | 1,261 / 1,261 | 5,262 / 5,262 |
| dxil | 1,261 / 1,261 | 5,262 / 5,262 |
| spirv (deko3d) | **939 / 1,261** | 5,262 / 5,262 |
| glsl | 939 / 939 | 5,262 / 5,262 |
| uam (default variant) | 939 / 939 | 5,262 / 5,262 |

- Translation: nothing crashed or timed out, and nothing printed one of the translator's three warnings ("vfetch by
  computed index from bound input N beyond the N described", "vfetch from constant N outside the vertex fetch range",
  "eA not written from a stream constant register").
- No shader reads XenosRecomp's specialization constants (`g_SpecConstants()`, `tfetchR11G11B10`). All compile as
  `vs_6_0` / `ps_6_0`.

### The one failure class: vertex inputs `FOG0` and `PSIZE0` have no SPIR-V location

322 vertex shaders, e.g. `vs_00b30cee5a4e3c3d`, `vs_00f3abdbebac4ded`, `vs_02323c6b24f1728f`. DXC (SPIR-V) says:
"error: partial explicit stage input location assignment via vk::location(X) unsupported".

- The containers declare vertex elements of usage `Fog` (308 shaders) and `PointSize` (226): both in 212, only Fog in
  96, only PointSize in 14.
- XenosRecomp gives each input the location from `RENUT_VERTEX_INPUT_LOCATIONS` in
  `app/thirdparty/reblue-XenosRecomp/XenosRecomp/shader_common.h`. That table "covers every vertex element N&B's shaders
  declare" and has no `Fog` or `PointSize` row, so those inputs come out as `in float4 iFog0 : FOG0` with no
  `[[vk::location]]`. DXIL does not care; SPIR-V refuses the mix.
- **Tested fix**, on a copy built into `out/fc4_shaders/exp_fog_psize` (the tree untouched). Two rows after
  `X(TexCoord, 10, 22)`:

  ```c
  X(PointSize, 0, 23) \
  X(Fog,       0, 24)
  ```

  With them, all 322 translate, compile to SPIR-V, convert to GLSL and compile with uam (100 s). `tools/deko3d_glsl.py`
  already renumbers vertex inputs to uam's 0-15 (at most 16 at once). That makes **6,523 of 6,523**.
- For the renderer, not done here: the same table feeds the host input layout
  (`app/src/renut_engine/gpu/render/vertex_format.cpp`, `RENUT_VERTEX_INPUT_LOCATIONS(RENUT_ROW)`). The fix belongs
  there with whatever format handling Fog / PointSize elements need. The main session owns `app/`.

### The generic bound vertex fetch is common

232 of the 1,261 vertex shaders call `vfetchBound` (`shader_common.h`: the vertex fetch that switches over the Xenos
formats at run time). That is the fetch Nuts & Bolts' water spent 2,494 instructions a vertex on, in 8 shaders there
(renut-nx `docs/shader.md`, "The water's vertex fetch"). Here it is in 232. **All 213 vertex shaders with a DKSH over
30 KB are among them**, up to 109 KB of code (`vs_1eab8341d54a269c`, `vs_a13928209edd0ea9`, `vs_dec51bb9e3dcb4bc`:
358 KB of GLSL each). `banjo_gpu_fetch_spec` (pass `fetchspec`) and how often these shaders draw are the thing to look
at once the game draws on the console.

### Sizes

The HLSL body is the translator's text without the 57,390-byte `shader_common.h` it includes. SPIR-V, GLSL and DKSH
cover all 6,523 shaders, with the 322 from the location-fix run.

| | Vertex median / max / total | Pixel median / max / total |
| --- | --- | --- |
| Container (header + microcode) | 1,396 / 3,436 B / 1.62 MB | 796 / 4,804 B / 6.65 MB |
| HLSL body | 22.2 / 29.2 KB / 27.7 MB | 19.7 / 38.4 KB / 115.1 MB |
| DXIL | 9.6 / 59.8 KB / 17.6 MB | 7.7 / 29.8 KB / 49.2 MB |
| SPIR-V (deko3d) | 14.4 / 247 KB / 44.8 MB | 10.7 / 56 KB / 79.6 MB |
| GLSL for uam (before `deko3d_glsl_opt.py`) | 9.3 / 358 KB / 53.7 MB | 5.9 / 32.7 KB / 43.8 MB |
| DKSH, default variant | 4.6 / 109 KB / 18.6 MB | 2.6 / 20.3 KB / 20.4 MB |
| Translation time | 14 / 205 ms | 14 / 213 ms |

So the deko3d GLSL package starts from about 97 MB of GLSL before its passes and compression. One compiled default
variant of every shader is 39 MB of DKSH.

Against the bases: Nuts & Bolts' library is 4,881 shaders (3,936 pixel, 945 vertex). Far Cry 4 has 1.34x as many,
with the same vertex share (19 %). The deko3d GLSL package and the console's uam cache grow in proportion.

## SPIR-V tools (downloaded 2026-11-09, approved by the user)

The deko3d half of the chain needs two tools this PC did not have. Both are under `out/` (not committed):

- **A DXC with SPIR-V code generation.** XenosRecomp's vendored `thirdparty/dxc-bin` has the headers only (no
  `bin/`, no `lib/`). The Windows SDK's DXC (1.8.2502.11) and Unity's (1.7.2308) both stop with "SPIR-V CodeGen not
  available. Please recompile with -DENABLE_SPIRV_CODEGEN=ON". **The PC build with Renut will hit the same gap**:
  `app/cmake`'s XenosRecomp ExternalProject uses that dxc-bin.
  - Used: Microsoft's release v1.9.2609 (2026-09-29), `dxc_2026_09_29.zip` from
    github.com/microsoft/DirectXShaderCompiler/releases, 32,287,592 bytes. Its SHA-256
    `ad31b1fc8443175d204f77a611fdb3ef2ec42759bdc2f1167368de24a4a7e7f1` matches the release page's digest.
  - It is kept in `out/fc4_shaders/dxc_download/` and unpacked to `out/fc4_shaders/dxc` (`bin/x64/dxc.exe`,
    `dxcompiler.dll`, `dxil.dll`, `lib/x64/dxcompiler.lib`: the layout `dxc-bin` and `FC4_DXC_DIR` expect).
- **SPIRV-Cross.** `sdk/thirdparty/moltenvk/MoltenVKShaderConverter/SPIRV-Cross` is an empty submodule (MoltenVK
  fetches it with CPM). It is cloned at MoltenVK's commit `adec7acbf41a988713cdb85f93f26c8ca5ea863e` into
  `out/fc4_shaders/spirv-cross-src` and built as `out/fc4_shaders/build/spirv-cross/spirv-cross.exe`
  ("Git commit: adec7ac").

`tools\fc4_shaders\build_host_tools.bat xenos out\fc4_shaders\dxc` builds XenosRecomp against the release's DXC.
`tools/switch_shaders.ps1`'s directory-mode run needs that (its SPIR-V step is in-process). The census calls
`dxc.exe` itself.

## Host tools (`tools/fc4_shaders/build_host_tools.bat`, into `out/fc4_shaders/build/`, -j 6)

- **XenosRecomp**: `tools/fc4_shaders/xenos_recomp/CMakeLists.txt` builds `app/thirdparty/reblue-XenosRecomp` with
  `XENOS_RECOMP_RENUT=ON` and defines the two DXC targets itself: `FC4_DXC_DIR` (a release zip's layout) or the Windows
  SDK's DXC. The toolchain is `tools/fc4_env.bat` (LLVM clang, MSVC target). 50 steps, under a minute.
- **uam**: `app/thirdparty/uam` (the console's patched 1.1.0). Its `c11/threads.h` includes `pthread.h`, so the
  MSVC-target clang fails (4 files). It builds with MSYS2's `C:\msys64\mingw64` gcc 16.2, static: `uam 1.1.0`. The base
  used devkitPro's msys2 clang64, which is not installed here.
- **SPIRV-Cross**: the CLI from `out/fc4_shaders/spirv-cross-src` with `tools/fc4_env.bat`'s clang, 19 steps.

## Reproduce

From `fc4-nx/`, with `C:\Python315\python.exe` (`xxhash` installed in its user site):

```bat
python tools/fc4_dunia_fat.py verify ../game/installation1/shadersobj.fat
python tools/fc4_dunia_fat.py extract ../game/installation1/shadersobj.fat out/fc4_shaders/raw
python tools/fc4_shaders/fc4_shader_containers.py --raw out/fc4_shaders/raw --image out/renut_image.bin --out out/fc4_shaders --unaligned
tools\fc4_shaders\build_host_tools.bat all
python tools/fc4_shaders/fc4_shader_census.py --dxc-spirv out/fc4_shaders/dxc/bin/x64 --spirv-cross out/fc4_shaders/build/spirv-cross/spirv-cross.exe
```

First, the two downloads ("SPIR-V tools"):

- Unpack `dxc_2026_09_29.zip` into `out/fc4_shaders/dxc`.
- Fetch SPIRV-Cross into `out/fc4_shaders/spirv-cross-src`: `git init`, `git remote add origin
  https://github.com/KhronosGroup/SPIRV-Cross.git`, `git fetch --depth 1 origin
  adec7acbf41a988713cdb85f93f26c8ca5ea863e`, then `git checkout FETCH_HEAD`.

The location-fix run: copy `app/thirdparty/reblue-XenosRecomp` to `out/fc4_shaders/exp_fog_psize/src` and add the
two rows. Build it with `out/fc4_shaders/exp_fog_psize/build.bat` (it passes `-DFC4_XENOS_RECOMP_SRC` to
`tools/fc4_shaders/xenos_recomp`). Then run the census with `--containers out/fc4_shaders/exp_fog_psize/containers`
(the 322 failing containers), `--out out/fc4_shaders/exp_fog_psize/census`,
`--xenos-recomp out/fc4_shaders/exp_fog_psize/build/XenosRecomp-ALL/XenosRecomp/XenosRecomp.exe` and
`--shader-common out/fc4_shaders/exp_fog_psize/src/XenosRecomp/shader_common.h`.

Outputs: `out/fc4_shaders/raw/` (entries + `index.tsv`), `out/fc4_shaders/containers/` and `containers.tsv`,
`out/fc4_shaders/census/` (`hlsl/`, `dxil/`, then `spirv/`, `vk/`, `glsl/`, `dksh/`; `log/`, `census.tsv`,
`report.txt`). `out/fc4_shaders/census.log` is the last run's console.
