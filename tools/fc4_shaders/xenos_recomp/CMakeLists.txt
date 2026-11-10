# fc4-nx (2026-11-09): Renut's XenosRecomp (app/thirdparty/reblue-XenosRecomp, RENUT_RECOMP) as a standalone host tool
# for the shader census (docs/fc4-shaders.md), built by tools/fc4_shaders/build_xenos_recomp.bat into
# out/fc4_shaders/build/xenos_recomp.
#
# The vendored thirdparty/dxc-bin has only DXC's headers (no bin/ or lib/), so the two DXC targets are defined here:
#   FC4_DXC_DIR = a folder laid out like an official DirectXShaderCompiler release zip (bin/x64/dxcompiler.dll,
#                 bin/x64/dxil.dll, lib/x64/dxcompiler.lib). The deko3d chain needs one: its DXC must have SPIR-V.
#   empty       = the Windows SDK's DXC (vcvars' WindowsSdkDir / WindowsSDKVersion). It compiles DXIL only ("SPIR-V
#                 CodeGen not available"), so every shader then fails at XenosRecomp's SPIR-V step.
cmake_minimum_required(VERSION 3.20)
project(fc4_xenos_recomp C CXX)

get_filename_component(FC4_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../../.." ABSOLUTE)
set(FC4_XENOS_RECOMP_SRC "${FC4_ROOT}/app/thirdparty/reblue-XenosRecomp" CACHE PATH
    "XenosRecomp source (a patched copy for experiments; docs/fc4-shaders.md)")
set(FC4_DXC_DIR "" CACHE PATH "DXC release folder (bin/x64, lib/x64); empty = the Windows SDK's (no SPIR-V)")

if(FC4_DXC_DIR)
    set(_dxc_dll "${FC4_DXC_DIR}/bin/x64/dxcompiler.dll")
    set(_dxil_dll "${FC4_DXC_DIR}/bin/x64/dxil.dll")
    set(_dxc_lib "${FC4_DXC_DIR}/lib/x64/dxcompiler.lib")
else()
    file(TO_CMAKE_PATH "$ENV{WindowsSdkDir}" _sdk)
    string(REGEX REPLACE "[\\/]+$" "" _sdkver "$ENV{WindowsSDKVersion}")
    set(_dxc_dll "${_sdk}/bin/${_sdkver}/x64/dxcompiler.dll")
    set(_dxil_dll "${_sdk}/bin/${_sdkver}/x64/dxil.dll")
    set(_dxc_lib "${_sdk}/Lib/${_sdkver}/um/x64/dxcompiler.lib")
endif()
foreach(_f "${_dxc_dll}" "${_dxil_dll}" "${_dxc_lib}")
    if(NOT EXISTS "${_f}")
        message(FATAL_ERROR "No ${_f} (FC4_DXC_DIR='${FC4_DXC_DIR}')")
    endif()
endforeach()
message(STATUS "fc4 XenosRecomp: DXC ${_dxc_dll}")

foreach(_t Microsoft::DirectXShaderCompiler Microsoft::DXIL)
    add_library(${_t} SHARED IMPORTED GLOBAL)
    target_include_directories(${_t} INTERFACE "${FC4_XENOS_RECOMP_SRC}/thirdparty/dxc-bin/inc")
    set_property(TARGET ${_t} PROPERTY IMPORTED_IMPLIB "${_dxc_lib}")
endforeach()
set_property(TARGET Microsoft::DirectXShaderCompiler PROPERTY IMPORTED_LOCATION "${_dxc_dll}")
set_property(TARGET Microsoft::DXIL PROPERTY IMPORTED_LOCATION "${_dxil_dll}")

set(XENOS_RECOMP_RENUT ON CACHE BOOL "" FORCE)
add_subdirectory("${FC4_XENOS_RECOMP_SRC}" XenosRecomp-ALL)
