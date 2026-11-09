@echo off
rem Runs the ReXGlue code generator on app\renut_manifest.toml (game.xex). The loaded image is dumped to
rem out\renut_image.bin (REXGLUE_DUMP_IMAGE, set by fc4_env.bat). Log: out\codegen.log.
call "%~dp0fc4_env.bat" || exit /b 1
if not exist "%~dp0..\out" mkdir "%~dp0..\out"
set "REXGLUE_EXE=%~dp0..\sdk\out\win-amd64\rexglue.exe"
if not exist "%REXGLUE_EXE%" (echo rexglue.exe not built & exit /b 1)
echo using %REXGLUE_EXE%
pushd "%~dp0..\app"
"%REXGLUE_EXE%" codegen renut_manifest.toml > "%~dp0..\out\codegen.log" 2>&1
set "RC=%ERRORLEVEL%"
popd
echo codegen exit %RC%
exit /b %RC%
