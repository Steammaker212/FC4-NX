# fc4-nx — Far Cry 4 (Xbox 360) on the Nintendo Switch (work in progress)

A static recompilation port of the Xbox 360 version of **Far Cry 4** (title `555308CA`) to the Switch, drawing with
deko3d. Not an emulator: the PowerPC code of `game.xex` is translated to C++ with [ReXGlue](https://github.com/rexglue/rexglue-sdk)
and compiled for the Switch; the game's Direct3D calls are drawn by [reNut](https://github.com/masterspike52/reNut)'s
Direct3D-level renderer on [plume](https://github.com/renderbag/plume)'s deko3d back end.

**Status: early bring-up.** Nothing boots yet. See [docs/fc4-notes.md](docs/fc4-notes.md) for what has been found and
decided, and its "Feasibility" section before expecting a frame rate.

Started from [katamari-nx](https://github.com/ChanseyIsTheBest/katamari-nx) (files, not history), with the method of
[renut-nx](https://github.com/ChanseyIsTheBest/renut-nx)'s `docs/` and [sa2-nx](https://github.com/ChanseyIsTheBest/sa2-nx).

## You need

Your own Far Cry 4 disc image. Nothing from the game is in this repository; `app/assets` points at your extracted copy
and everything made from it (`app/generated`, `out/`, shaders) stays on your computer.

## Build (so far)

```bat
tools\fc4_build_rexglue.bat   :: the code generator (VS 18 Build Tools + LLVM; paths in tools\fc4_env.bat)
tools\fc4_codegen.bat         :: code generation on app\renut_manifest.toml (game.xex)
```

`tools/fc4_iso.py` lists or extracts the disc and reads XEX headers; `tools/fc4_image_scan.py` reads the loaded image.

## Credits and licence

ReXGlue (Tom Clay, on Xenia's work), reNut's renderer (masterspike52; reused with its author's permission for these
ports), katamari-nx, renut-nx, sa2-nx (ChanseyIsTheBest), nfsmw-nx (StevensND), NetherSX2_nx, plume, deko3d and uam
(fincs), devkitPro and libnx. GPL-3.0 like the ports it builds on; the SDK keeps BSD-3-Clause
([THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)). Far Cry is a trademark of Ubisoft; no affiliation with Ubisoft,
Microsoft or Nintendo.
