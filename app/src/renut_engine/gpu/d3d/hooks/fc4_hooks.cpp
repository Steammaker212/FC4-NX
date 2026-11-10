// fc4-nx (2026-11-09): Far Cry 4's own D3D hooks for Renut's renderer (not from sa2-nx; tools/fc4_d3d/apply_sa2_d3d.py
// does not touch this file).
//
// sub_83F18B88 (D3D, unnamed: an async resource lock): reserves one of 32 slots in a shift register at device +0x5F60
// (24416; bit 63 = the slot 32 reservations ago is still held), writes GPU waits on the slot's words, returns the slot.
// The game frees it later (sub_838B8598 -> sub_83F18790) once a refcount reaches zero. While bit 63 is set the original
// spins in guest code. renut1-8 hung there at frame ~78: the frees come from work that only runs after the GPU's
// callbacks, which Renut runs on a game thread at its next D3D call (guest/callbacks.h) - and the spinning thread makes
// none. The hook waits here instead, running the callbacks the render thread has reached, then calls the original.
#include <chrono>
#include <thread>

#include <rex/hook.h>
#include <rex/types.h>

#include "renut_engine/gpu/banjo_renut_select.h"
#include "renut_engine/gpu/backend/render_thread.h"
#include "renut_engine/gpu/guest/callbacks.h"
#include "renut_engine/gpu/guest/guest_memory.h"
#include "renut_engine/gpu/log.h"

#include <rex/cvar.h>

using namespace renut::gpu;

// The game's async locks (byte 0x84126AF8, static data, nothing writes it; read by sub_827EF948 and five others): on,
// they never free (async2: 32 slots taken by frame ~77, then the hook below waits forever with every GPU callback run).
// Their wait for the GPU is GPU-side packets Renut's renderer does not execute. Off, the game takes its other path
// (sub_827AE6F8 / sub_827AE738 and events).
REXCVAR_DEFINE_BOOL(fc4_renut_async_locks, true, "FC4/Renut",
                    "Renut's renderer: keep Far Cry 4's async resource locks (byte 0x84126AF8). Off: the game's "
                    "synchronous path (the async one hangs at frame ~77)")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);

namespace fc4::renut {
// renut_app.h OnPostSetup, the XEX loaded and no guest thread started.
void BootPatches() {
  constexpr u32 kAsyncLocks = 0x84126AF8;
  u8 *flag = GuestPtr<u8>(kAsyncLocks);
  if (!flag)
    return;
  const u8 was = *flag;
  if (!REXCVAR_GET(fc4_renut_async_locks))
    *flag = 0;
  RGPU_INFO("[fc4] async locks byte {:08X}: {} -> {}", kAsyncLocks, was, *flag);
}
}  // namespace fc4::renut

BANJO_RENUT_HOOK_RAW(sub_83F18B88) {
  const u32 device = ctx.r3.u32, flags = ctx.r8.u32;
  const volatile u8 *slots = GuestPtr<u8>(device + 24416);  // big-endian qword: byte 0 bit 7 = bit 63
  if (slots && !(flags & 2) && (slots[0] & 0x80)) {
    const auto start = std::chrono::steady_clock::now();
    bool logged = false;
    // trace1: the game frees 18 of 32 and then schedules no more unlock jobs. The ring only orders the GPU (its
    // waits are GPU packets, which Renut's renderer does not execute), so after 2 s the oldest slot is retired here:
    // its late free shifts by 64 or more and clears nothing.
    while (slots[0] & 0x80) {
      RunReadyCallbacks();
      if (std::chrono::steady_clock::now() - start > std::chrono::seconds(2)) {
        auto *word = reinterpret_cast<std::atomic<u8> *>(const_cast<u8 *>(slots));
        word->fetch_and(u8(0x7F));
        static std::atomic<uint32_t> retired{0};
        const uint32_t n = retired.fetch_add(1) + 1;
        if (n <= 3 || (n & (n - 1)) == 0)
          RGPU_WARN("[fc4] async lock 83F18B88: slot ring full, oldest retired (#{}; callbacks inserted {}, reached {})",
                    n, LastCallback(), render_thread::CallbacksReached());
        break;
      }
      std::this_thread::yield();
    }
    (void)logged;
  }
  __imp__sub_83F18B88(ctx, base);
}

// fc4-nx (2026-11-09, debug, fc4_renut_async_trace): counts of the async lock's steps (lock site sub_82831850, unlock
// job sub_838B8998 and its gate sub_824C1D38, unlock body sub_838B8598, slot free sub_83F18790).
#include <atomic>
REXCVAR_DEFINE_BOOL(fc4_renut_async_trace, false, "FC4/Renut", "Debug: log the async lock steps' counts");
namespace {
std::atomic<uint32_t> g_async_counts[5];
void AsyncNote(int i, const char *what, u32 a, u32 b) {
  const uint32_t n = g_async_counts[i].fetch_add(1) + 1;
  if (REXCVAR_GET(fc4_renut_async_trace) && (n <= 4 || (n & (n - 1)) == 0))
    RGPU_INFO("[fc4 async] {} #{} ({:08X} {:08X}) | lock {} job {} body {} free {}", what, n, a, b,
              g_async_counts[0].load(), g_async_counts[1].load(), g_async_counts[2].load(), g_async_counts[3].load());
}
}  // namespace
BANJO_RENUT_HOOK_RAW(sub_82831850) { AsyncNote(0, "lock site", ctx.r3.u32, 0); __imp__sub_82831850(ctx, base); }
BANJO_RENUT_HOOK_RAW(sub_838B8998) {
  const u32 job = ctx.r3.u32;
  __imp__sub_838B8998(ctx, base);
  AsyncNote(1, "unlock job", job, ctx.r3.u32);
}
BANJO_RENUT_HOOK_RAW(sub_838B8598) { AsyncNote(2, "unlock body", ctx.r3.u32, 0); __imp__sub_838B8598(ctx, base); }
BANJO_RENUT_HOOK_RAW(sub_83F18790) { AsyncNote(3, "slot free", ctx.r3.u32, ctx.r4.u32); __imp__sub_83F18790(ctx, base); }
