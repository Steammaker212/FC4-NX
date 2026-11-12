# fc4-nx — Far Cry 4 (Xbox 360) on the Nintendo Switch (work in progress)

A static recompilation port of the Xbox 360 version of **Far Cry 4** (title `555308CA`) to the Switch, drawing with
deko3d. Not an emulator: the PowerPC code of `game.xex` is translated to C++ with [ReXGlue](https://github.com/rexglue/rexglue-sdk)
and compiled for the Switch; the game's Direct3D calls are drawn by [reNut](https://github.com/masterspike52/reNut)'s
Direct3D-level renderer on [plume](https://github.com/renderbag/plume)'s deko3d back end.

**Status: in-game on the console, work in progress.** Runs on an Atmosphère Switch (title takeover) and on PC. The 3D
image renders at 540p handheld / 648p docked with the HUD at 720p; gameplay runs at roughly 15-20 fps. Known problems:
dark water surfaces, occasional black frames, frame rate below 30. See [docs/fc4-notes.md](docs/fc4-notes.md) for what
has been found and decided (newest sections at the end), and its "Feasibility" section before expecting a frame rate.

Started from [katamari-nx](https://github.com/ChanseyIsTheBest/katamari-nx) (files, not history), with the method of
[renut-nx](https://github.com/ChanseyIsTheBest/renut-nx)'s `docs/` and [sa2-nx](https://github.com/ChanseyIsTheBest/sa2-nx).

## You need

Your own Far Cry 4 disc image. Nothing from the game is in this repository; `app/assets` points at your extracted copy
and everything made from it (`app/generated`, `out/`, shaders) stays on your computer.

## Build
```bat
tools\fc4_build_rexglue.bat   :: the code generator (VS 18 Build Tools + LLVM; paths in tools\fc4_env.bat)
tools\fc4_codegen.bat         :: code generation on app\renut_manifest.toml (game.xex)
tools\fc4_build_glslang.bat   :: host glslangValidator for the EDRAM transfer shaders
tools\fc4_deko3d_tools.bat    :: SPIRV-Cross and uam for the deko3d host shaders
tools\fc4_build_pc.bat        :: the Windows build (RENUT=ON for the deko3d-equivalent renderer on D3D12)
tools\fc4_build_switch.bat    :: the Switch NRO (devkitPro devkitA64 + libnx): app\out\switch\renut.nro
```
`tools/fc4_iso.py` lists or extracts the disc and reads XEX headers; `tools/fc4_image_scan.py` reads the loaded image.
The game's shaders are translated from your disc into `deko3d_glsl.bin` / `deko3d_shaders.bin`, which go beside the NRO
in `sdmc:/switch/fc4-nx/` (docs/fc4-notes.md, "First Switch NRO" and "Console runs").

## Contributing
Issues and pull requests are welcome. Never commit anything from the game or made from it (the disc, `game.xex`,
extracted files, generated code, shader packages, pipeline caches, icons made from game art) or any console keys or
firmware: `.gitignore` covers the known ones. Licence: GPL-3.0 for the port's code (`LICENSE`), BSD-3-Clause for `sdk/`.

## Credits and licence

ReXGlue (Tom Clay, on Xenia's work), reNut's renderer (masterspike52; reused with its author's permission for these
ports), katamari-nx, renut-nx, sa2-nx (ChanseyIsTheBest), nfsmw-nx (StevensND), NetherSX2_nx, plume, deko3d and uam
(fincs), devkitPro and libnx. GPL-3.0 like the ports it builds on; the SDK keeps BSD-3-Clause
([THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)). Far Cry is a trademark of Ubisoft; no affiliation with Ubisoft,
Microsoft or Nintendo.
