@echo off
rem fc4-nx: configure + build the Windows (PC) app (tools\build_pc.bat with this PC's toolchain, tools\fc4_env.bat).
rem   BUILD_DIR (env) defaults to app\out\pc. RENUT (env) = ON builds Renut's renderer in (BANJO_RENUT_RENDERER);
rem   default OFF for the first boots: the SDK's emulated GPU (gpu_plugin = "xenos") separates CPU / kernel problems
rem   from renderer problems (peggle2-nx's and katamari-nx's order of work).
call "%~dp0fc4_env.bat" || exit /b 1
set "ROOT=%~dp0.."
if "%BUILD_DIR%"=="" set "BUILD_DIR=%ROOT%\app\out\pc"
if "%RENUT%"=="" set "RENUT=OFF"
if not exist "%BUILD_DIR%\CMakeCache.txt" (
  cmake -S "%ROOT%\app" -B "%BUILD_DIR%" -G Ninja -DCMAKE_BUILD_TYPE=Release %REX_CMAKE_COMPILERS% -DREXGLUE_ENABLE_TRACY=OFF -DREXGLUE_USE_D3D12=ON -DREXGLUE_USE_VULKAN=ON "-DREXSDK_DIR=%ROOT%\sdk" -DBANJO_RENUT_RENDERER=%RENUT% || exit /b 1
)
cmake --build "%BUILD_DIR%" -j 16 %*
