// fc4-nx (2026-11-10, diagnostic, banjo_renut_diag_cpu_reads): see cpu_read_watch.cpp.
#pragma once

#include "renut_engine/gpu/guest/guest_memory.h"

namespace renut::gpu {
// Makes the guest CPU's views of a resolve destination fault on first access (Windows; elsewhere nothing).
void WatchResolveForCpuReads(u32 physical_base, u32 bytes, u32 width, u32 height, u32 format);
// Logs the accesses caught since the last call (render thread).
void ReportCpuReadsLocked();
} // namespace renut::gpu
