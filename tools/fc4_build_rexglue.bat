@echo off
rem Configures and builds only the ReXGlue code generator (rexglue.exe) for the host, in sdk\out\host.
call "%~dp0fc4_env.bat" || exit /b 1
set "SDK=%~dp0..\sdk"
if not exist "%SDK%\out\host\build.ninja" (
  cmake -S "%SDK%" -B "%SDK%\out\host" -G Ninja -DCMAKE_BUILD_TYPE=Release %REX_CMAKE_COMPILERS% -DREXGLUE_ENABLE_TRACY=OFF -DREXGLUE_ENABLE_PERF_COUNTERS=OFF || exit /b 1
)
cmake --build "%SDK%\out\host" --target rexglue -j 16
