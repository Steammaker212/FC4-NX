@echo off
rem fc4-nx (2026-11-09): the host tools of the shader census (docs/fc4-shaders.md), with this PC's toolchain
rem (tools\fc4_env.bat), into out\fc4_shaders\build\ at -j 6 (a PC build may run alongside):
rem   xenos_recomp\XenosRecomp-ALL\XenosRecomp\XenosRecomp.exe   Renut's translator (tools\fc4_shaders\xenos_recomp)
rem   uam\uam.exe                                                app\thirdparty\uam (the console's patched uam 1.1.0),
rem                                                              with C:\msys64\mingw64's gcc (static)
rem   spirv-cross\spirv-cross.exe                                out\fc4_shaders\spirv-cross-src (MoltenVK's commit)
rem   build_host_tools.bat [xenos^|uam^|spirv-cross^|all] [DXC release folder for XenosRecomp, default: the SDK's]
setlocal
set "WHAT=%~1"
if "%WHAT%"=="" set "WHAT=all"
set "DXC=%~2"
call "%~dp0..\fc4_env.bat" || exit /b 1
set "OUT=%~dp0..\..\out\fc4_shaders\build"
if /i "%WHAT%"=="uam" goto uam
if /i "%WHAT%"=="spirv-cross" goto spirvcross
cmake -S "%~dp0xenos_recomp" -B "%OUT%\xenos_recomp" -G Ninja -DCMAKE_BUILD_TYPE=Release %REX_CMAKE_COMPILERS% "-DFC4_DXC_DIR=%DXC%" -DCMAKE_POLICY_VERSION_MINIMUM=3.5 || exit /b 1
cmake --build "%OUT%\xenos_recomp" --target XenosRecomp -j 6 || exit /b 1
if /i "%WHAT%"=="xenos" exit /b 0
:uam
rem uam's c11/threads.h needs pthreads: MinGW (MSYS2's mingw64 gcc here; the base used devkitPro's msys2 clang64).
set "PATH=C:\msys64\mingw64\bin;%PATH%"
cmake -S "%~dp0..\..\app\thirdparty\uam" -B "%OUT%\uam" -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_COMPILER=gcc -DCMAKE_CXX_COMPILER=g++ -DCMAKE_EXE_LINKER_FLAGS=-static || exit /b 1
cmake --build "%OUT%\uam" --target uam_tool -j 6 || exit /b 1
"%OUT%\uam\uam.exe" --version
if /i "%WHAT%"=="uam" exit /b 0
:spirvcross
rem SPIRV-Cross at MoltenVK's pinned commit (sdk/thirdparty/moltenvk/ExternalRevisions), cloned to
rem out\fc4_shaders\spirv-cross-src (docs/fc4-shaders.md, "Host tools"); the CLI only.
cmake -S "%~dp0..\..\out\fc4_shaders\spirv-cross-src" -B "%OUT%\spirv-cross" -G Ninja -DCMAKE_BUILD_TYPE=Release %REX_CMAKE_COMPILERS% -DSPIRV_CROSS_ENABLE_TESTS=OFF -DSPIRV_CROSS_SHARED=OFF -DSPIRV_CROSS_ENABLE_C_API=OFF || exit /b 1
cmake --build "%OUT%\spirv-cross" --target spirv-cross -j 6 || exit /b 1
"%OUT%\spirv-cross\spirv-cross.exe" --revision
