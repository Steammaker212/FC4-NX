// fc4-nx (2026-11-10): Far Cry 4's own player settings for the Switch build (katamari.toml beside the NRO; the
// built-in defaults are app/katamari_switch_defaults.toml).
#include <rex/cvar.h>

// The first console runs (hw1, hw2): the gameplay at 13-15 fps with the renderer thread at ~45 ms a frame and the GPU
// at ~32 ms at the stock handheld clocks (CPU 1020 MHz, GPU 460.8 MHz). Held through sys-clk (src/ui/switch_sysclk.cpp
// Force), released when the game exits cleanly; nothing happens without sys-clk.
REXCVAR_DEFINE_INT32(fc4_clock_cpu_mhz, 1785, "FC4/Switch",
                     "CPU clock held through sys-clk while the game runs: 1785 (the boost clock games use while "
                     "loading), 1020 (stock), 0 = leave it to the system and sys-clk's own profile")
    .range(0, 2397)
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_INT32(fc4_clock_gpu_mhz, 768, "FC4/Switch",
                     "GPU clock held through sys-clk while the game runs: 768 (the docked clock), 460 (stock handheld), "
                     "0 = leave it to the system and sys-clk's own profile")
    .range(0, 1305)
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
