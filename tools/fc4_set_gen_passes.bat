@echo off
rem fc4-nx: switches every optional post-codegen pass of the PC build (app\out\pc) ON or OFF in one reconfigure.
rem OFF compiles the generated statements as they were before each pass (each pass keeps the original behind its
rem switch), so a crash that disappears with OFF comes from a pass; then bisect with single -D options.
rem   tools\fc4_set_gen_passes.bat OFF     (then tools\fc4_build_pc.bat; a full recompile, no codegen)
rem   tools\fc4_set_gen_passes.bat ON      (the shipped setting)
call "%~dp0fc4_env.bat" || exit /b 1
set "V=%~1"
if "%V%"=="" set "V=OFF"
set "D="
for %%P in (RO_CONSTANTS FLOAT_LOADS LEAF_LOCALS LOOP_LOCALS PROMOTED_CALLS VPERM1 FP_SIGN_OPS LEAF_DEAD DEAD_DEFS SINGLE_FLOATS INLINE_MEMCALLS VEC_UNALIGNED NARROW_LOOP_BARRIER VECTOR_LOCALS_BY_VALUE RO_CFG FLUSH_HOIST SWITCH_THREAD LR_WRITE_SAME R1_LOCAL VSEL_NEON INLINE_LEAVES STORE_CARDS) do call set "D=%%D%% -DBANJO_GEN_%%P=%V%"
cmake -S "%~dp0..\app" -B "%~dp0..\app\out\pc" %D%
