@echo off
rem fc4-nx: tools\build_glslang.bat with this PC's toolchain (tools\fc4_env.bat). Builds the host glslangValidator
rem (out\glslang\StandAlone\glslangValidator.exe) that compiles the native renderer's EDRAM transfer shaders.
call "%~dp0fc4_env.bat" || exit /b 1
cmake -S "%~dp0..\sdk\thirdparty\glslang" -B "%~dp0..\out\glslang" -G Ninja -DCMAKE_BUILD_TYPE=Release %REX_CMAKE_COMPILERS% -DENABLE_OPT=OFF -DGLSLANG_TESTS=OFF -DENABLE_GLSLANG_BINARIES=ON -DENABLE_HLSL=OFF -DGLSLANG_ENABLE_INSTALL=OFF -DCMAKE_POLICY_VERSION_MINIMUM=3.5 || exit /b 1
cmake --build "%~dp0..\out\glslang" --target glslangValidator -j 6
