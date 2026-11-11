// fc4-nx (2026-11-10, diagnostic, banjo_renut_diag_cpu_reads): which resolve destinations the guest CPU reads.
// Renut keeps a resolve's result in a host texture and never writes the guest memory it names; a game that reads a
// resolve back with the CPU (Far Cry 4's auto-exposure: its exposure constant climbs to 24-110 and the scene goes white)
// reads what the CPU last left there. On Windows the guest reaches physical memory through the 0xA0000000, 0xC0000000
// and 0xE0000000 views (separate mappings of the same pages, not the GPU's physical view), so their pages over a
// resolve's destination are made inaccessible after the resolve; the first guest access to each faults, is recorded
// (address, read or write, host code address) and the page is given back. The render thread prints the records.
#include "renut_engine/gpu/render/cpu_read_watch.h"

#include <atomic>
#include <algorithm>
#include <cstdint>
#include <mutex>
#include <unordered_map>
#include <unordered_set>

#include "renut_engine/gpu/guest/guest_memory.h"
#include "renut_engine/gpu/log.h"

#if defined(_WIN32)
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#endif

namespace renut::gpu {

#if defined(_WIN32)
namespace {

struct Watched {
  uintptr_t host_page = 0;
  u32 guest_va = 0;
  u32 tag = 0;  // the resolve destination's base page
  u32 info = 0; // width << 16 | height
  u32 format = 0;
};

constexpr size_t kMaxWatched = 1 << 16;
Watched g_watched[kMaxWatched];
std::atomic<size_t> g_watched_count{0};
std::mutex g_watch_mutex;
std::unordered_set<uintptr_t> g_watched_pages;
std::unordered_set<u32> g_tags_done;  // destinations already reported once
std::unordered_map<uint64_t, u32> g_sig_hits;  // reads seen per (width, height, format)

struct Hit {
  u32 guest_va, tag, info, format, write;
  uintptr_t rip_offset;
  DWORD thread;
};
constexpr size_t kMaxHits = 256;
Hit g_hits[kMaxHits];
std::atomic<size_t> g_hit_count{0};
size_t g_hits_printed = 0;
PVOID g_handler = nullptr;

LONG CALLBACK WatchHandler(EXCEPTION_POINTERS *info) {
  if (info->ExceptionRecord->ExceptionCode != EXCEPTION_ACCESS_VIOLATION ||
      info->ExceptionRecord->NumberParameters < 2)
    return EXCEPTION_CONTINUE_SEARCH;
  const uintptr_t address = uintptr_t(info->ExceptionRecord->ExceptionInformation[1]);
  const uintptr_t page = address & ~uintptr_t(0xFFF);
  const size_t count = std::min(g_watched_count.load(std::memory_order_acquire), kMaxWatched);
  for (size_t i = 0; i < count; ++i) {
    const Watched &w = g_watched[i];
    if (w.host_page != page)
      continue;
    DWORD old = 0;
    VirtualProtect(reinterpret_cast<void *>(page), 0x1000, PAGE_READWRITE, &old);
    const size_t n = g_hit_count.fetch_add(1, std::memory_order_acq_rel);
    if (n < kMaxHits) {
      HMODULE module = nullptr;
      const uintptr_t rip = uintptr_t(info->ContextRecord->Rip);
      GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                         reinterpret_cast<LPCSTR>(rip), &module);
      g_hits[n] = Hit{w.guest_va + u32(address - page), w.tag, w.info, w.format,
                      u32(info->ExceptionRecord->ExceptionInformation[0]), rip - uintptr_t(module),
                      GetCurrentThreadId()};
    }
    return EXCEPTION_CONTINUE_EXECUTION;
  }
  return EXCEPTION_CONTINUE_SEARCH;
}

} // namespace

void WatchResolveForCpuReads(u32 physical_base, u32 bytes, u32 width, u32 height, u32 format) {
  std::lock_guard lock(g_watch_mutex);
  const u32 tag = physical_base >> 12;
  const uint64_t sig = (uint64_t(width) << 40) | (uint64_t(height) << 16) | format;
  if (g_tags_done.count(tag) || uint64_t(width) * height > 65536 || g_sig_hits[sig] >= 4)
    return;
  if (!g_handler)
    g_handler = AddVectoredExceptionHandler(1, WatchHandler);
  bytes = std::min(bytes, 64u * 4096u);
  static const u32 kViews[] = {0xA0000000u, 0xC0000000u, 0xE0000000u};
  for (u32 view : kViews) {
    for (u32 offset = 0; offset < bytes; offset += 0x1000) {
      const u32 va = view + ((physical_base + offset) & 0x1FFFF000u);
      u8 *host = GuestPtr<u8>(va);
      if (!host)
        continue;
      const uintptr_t page = uintptr_t(host) & ~uintptr_t(0xFFF);
      if (!g_watched_pages.insert(page).second)
        continue;
      const size_t n = g_watched_count.load(std::memory_order_relaxed);
      if (n >= kMaxWatched)
        return;
      DWORD old = 0;
      if (!VirtualProtect(reinterpret_cast<void *>(page), 0x1000, PAGE_NOACCESS, &old))
        continue;
      g_watched[n] = Watched{page, va & ~0xFFFu, tag, (width << 16) | height, format};
      g_watched_count.store(n + 1, std::memory_order_release);
    }
  }
}

void ReportCpuReadsLocked() {
  const size_t count = std::min(g_hit_count.load(std::memory_order_acquire), kMaxHits);
  for (; g_hits_printed < count; ++g_hits_printed) {
    const Hit &h = g_hits[g_hits_printed];
    {
      std::lock_guard lock(g_watch_mutex);
      g_tags_done.insert(h.tag);
      ++g_sig_hits[(uint64_t(h.info >> 16) << 40) | (uint64_t(h.info & 0xFFFF) << 16) | h.format];
    }
    RGPU_INFO("[cpu-read] guest {} {:08X} of resolve destination page {:05X} ({}x{} format {}), thread {}, "
              "renut.exe+{:X} (banjo_renut_diag_cpu_reads)", h.write ? "WRITE" : "read", h.guest_va, h.tag,
              h.info >> 16, h.info & 0xFFFF, h.format, h.thread, h.rip_offset);
  }
}
#else
void WatchResolveForCpuReads(u32, u32, u32, u32, u32) {}
void ReportCpuReadsLocked() {}
#endif

} // namespace renut::gpu
