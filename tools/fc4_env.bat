@echo off
rem fc4-nx host toolchain for THIS PC (adapted from tools\pc_env.bat, which names the katamari author's paths):
rem   - VS 18 Build Tools (MSVC 14.51 + Windows SDK) via vcvars64, with its bundled CMake and Ninja
rem   - LLVM clang from C:\Program Files\LLVM (devkitPro's msys2 clang64 package is not installed here)
rem   - Python 3.15 at C:\Python315
set "VSROOT=C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools"
set "PATH=C:\Program Files (x86)\Microsoft Visual Studio\Installer;%PATH%"
call "%VSROOT%\VC\Auxiliary\Build\vcvars64.bat" >nul || exit /b 1
set "PATH=%VSROOT%\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin;%VSROOT%\Common7\IDE\CommonExtensions\Microsoft\CMake\Ninja;C:\Python315;%PATH%"
set "LLVM_BIN=C:/Program Files/LLVM/bin"
set REX_CMAKE_COMPILERS="-DCMAKE_C_COMPILER=%LLVM_BIN%/clang.exe" "-DCMAKE_CXX_COMPILER=%LLVM_BIN%/clang++.exe" -DCMAKE_C_COMPILER_TARGET=x86_64-pc-windows-msvc -DCMAKE_CXX_COMPILER_TARGET=x86_64-pc-windows-msvc -DCMAKE_LINKER_TYPE=LLD "-DCMAKE_RC_COMPILER=%LLVM_BIN%/llvm-rc.exe" "-DCMAKE_AR=%LLVM_BIN%/llvm-ar.exe" "-DCMAKE_C_FLAGS=-march=x86-64-v2" "-DCMAKE_CXX_FLAGS=-march=x86-64-v2" -DPYTHON_EXECUTABLE=C:/Python315/python.exe -DPython3_EXECUTABLE=C:/Python315/python.exe
set "REXGLUE_DUMP_IMAGE=%~dp0..\out\renut_image.bin"
