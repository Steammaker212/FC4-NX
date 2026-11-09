@echo off
rem fc4-nx: the PC tools the Switch build's deko3d host shaders need, where app/cmake/banjo_renut_gpu.cmake looks
rem (tools/deko3d_build_tools.sh needs msys2 clang64, not installed here):
rem  - SPIRV-Cross: the one the shader work built (out\fc4_shaders\build\spirv-cross\spirv-cross.exe);
rem  - uam: devkitPro's uam 1.1.0 (C:\devkitPro\tools\bin\uam.exe), the upstream version app\thirdparty\uam patches.
rem    Its patches (threads, in-memory DKSH, logging, no exit, resident frontend) are for the console-side library;
rem    app\thirdparty\uam itself needs pthreads, which this PC's MSVC/clang-cl toolchain lacks.
set "ROOT=%~dp0.."
set "OUT=%ROOT%\out\deko3d_tools"
if not exist "%OUT%\spirv-cross-build" mkdir "%OUT%\spirv-cross-build"
if not exist "%OUT%\uam-build" mkdir "%OUT%\uam-build"
copy /y "%ROOT%\out\fc4_shaders\build\spirv-cross\spirv-cross.exe" "%OUT%\spirv-cross-build\spirv-cross.exe" >nul || exit /b 1
copy /y "C:\devkitPro\tools\bin\uam.exe" "%OUT%\uam-build\uam.exe" >nul || exit /b 1
"%OUT%\uam-build\uam.exe" --version
