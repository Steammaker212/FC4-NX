// fc4-nx (2026-11-10, banjo_renut_color_to_depth): see edram_transfer.cpp.
#pragma once

namespace renut::gpu {
struct HostSurface;
// Before a depth target is bound: if a 32-bit colour target over the same EDRAM was written after it, the depth and
// stencil become that colour target's words (as on the console, where both are the same memory). Caller holds the
// render lock; the framebuffer bound before is unbound.
bool ColorToDepthBeforeBindLocked(HostSurface *depth);  // true: it drew (the bound state is gone)
// Whether ColorToDepthBeforeBindLocked would draw now (fc4-nx 2026-11-10: a depth hand-over is settled before it).
bool ColorToDepthDueLocked(HostSurface *depth);
} // namespace renut::gpu
