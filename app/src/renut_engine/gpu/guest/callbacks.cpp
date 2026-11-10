/**
 * @file    gpu/guest/callbacks.cpp
 */
#include "renut_engine/gpu/guest/callbacks.h"

#include <atomic>
#include <chrono>
#include <condition_variable>
#include <deque>
#include <mutex>
#include <vector>

#include <rex/cvar.h>
#include <rex/hook.h>
#include <rex/ppc.h>
#include <rex/system/kernel_state.h>
#include <rex/system/xthread.h>

#include "renut_engine/gpu/log.h"
#include "renut_engine/gpu/backend/render_thread.h"
#include "renut_engine/gpu/render/textures.h"
#include "renut_engine/gpu/banjo_renut_checks.h"  // banjo-nx (package 27c)

// banjo-nx (2026-10-20, from sa2-nx): see g_waiting.
REXCVAR_DEFINE_BOOL(banjo_renut_callbacks_fast, true, "Banjo/Enhancements",
                    "Renut's renderer: every draw, clear and resolve hook first runs the guest's GPU callbacks the "
                    "render thread has reached; with none waiting (nearly always) it returns without "
                    "taking the two locks it took to find that out. Off: the locks every time")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);

REXCVAR_DEFINE_BOOL(renut_callback_thread, true, "Renut/Renderer",
                    "Renut's renderer: the game's D3D callbacks run on their own guest thread, as the console's GPU "
                    "interrupt runs them (Far Cry 4 needs it). Off: on a game thread at its next D3D call")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);

namespace renut::gpu {

namespace {

struct Callback {
  uint64_t seq = 0;
  u32 function = 0;
  u32 context = 0;
};

std::mutex g_mutex;
std::deque<Callback> g_callbacks;  // inserted, not run yet, in order
uint64_t g_last_seq = 0;
// Set while a thread runs callbacks: they run one at a time, in order.
bool g_running = false;
// banjo-nx (2026-10-20, from sa2-nx, banjo_renut_callbacks_fast): g_callbacks.size(), kept with it under g_mutex and read without it.
// A hook that reads 0 while another thread inserts one runs it at its next call; on the inserting thread the count is
// in program order.
std::atomic<size_t> g_waiting{0};

} // namespace

namespace {
bool CallbackThreadOn();
}

void InsertCallback(u32 function, u32 context) {
  CallbackThreadOn();  // fc4-nx: the interrupt thread exists before the render thread reaches this callback
  uint64_t seq;
  {
    std::lock_guard lock(g_mutex);
    seq = ++g_last_seq;
    g_callbacks.push_back({seq, function, context});
    g_waiting.store(g_callbacks.size(), std::memory_order_release);
  }
  // The linear textures of the work before it are read now, not when the
  // command list is submitted: after the callback the game may rewrite them
  // (the XMV player's frames).
  // banjo-nx (package 27c): the vertex fills too, for the same reason.
  banjo::renut_gpu::checks::QueueKickFlush();
  render_thread::QueueCallbackMarker(seq);
}

uint64_t LastCallback() {
  std::lock_guard lock(g_mutex);
  return g_last_seq;
}

std::atomic<int> g_hook_fast_paths{0};  // banjo-nx (from sa2-nx): callbacks.h

bool HookFastPathsInit() {
  const bool on = REXCVAR_GET(banjo_renut_callbacks_fast);
  g_hook_fast_paths.store(on ? 1 : -1, std::memory_order_relaxed);
  return on;
}

namespace {
void RunReadyCallbacksHere();
// fc4-nx (2026-11-09, renut_callback_thread): the console runs D3D callbacks on the GPU interrupt's thread, not inside
// the game's next D3D call. Far Cry 4 depends on it: its allocator's GPU-done callback (sub_827B34F0) waits while its
// queue is full, and only the game's own threads drain it - run inline on one of them it spun forever (docs/fc4-notes.md).
// On, a guest-capable host thread ("GPU Interrupt", as the SDK's command processor makes "GPU Commands") runs every
// callback the render thread reaches, and RunReadyCallbacks only wakes it.
std::mutex g_thread_mutex;
std::condition_variable g_thread_cv;
bool g_thread_wake = false;
std::atomic<int> g_thread_state{0};  // 0 not started, 1 running, -1 off
rex::system::object_ref<rex::system::XHostThread> g_interrupt_thread;

bool CallbackThreadOn() {
  int s = g_thread_state.load(std::memory_order_acquire);
  if (s)
    return s > 0;
  static std::mutex start_mutex;
  std::lock_guard lock(start_mutex);
  s = g_thread_state.load(std::memory_order_acquire);
  if (s)
    return s > 0;
  auto *ks = rex::system::kernel_state();
  if (!REXCVAR_GET(renut_callback_thread) || !ks) {
    g_thread_state.store(-1, std::memory_order_release);
    return false;
  }
  g_interrupt_thread = rex::system::object_ref<rex::system::XHostThread>(
      new rex::system::XHostThread(ks, 256 * 1024, 0, [] {
        for (;;) {
          {
            std::unique_lock lock(g_thread_mutex);
            g_thread_cv.wait_for(lock, std::chrono::milliseconds(2), [] { return g_thread_wake; });
            g_thread_wake = false;
          }
          RunReadyCallbacksHere();
        }
        return 0;
      }));
  g_interrupt_thread->set_name("GPU Interrupt");
  g_interrupt_thread->Create();
  RGPU_INFO("[renut] D3D callbacks run on their own thread (renut_callback_thread)");
  g_thread_state.store(1, std::memory_order_release);
  return true;
}
}  // namespace

void NotifyCallbacksReached() {
  if (g_thread_state.load(std::memory_order_acquire) <= 0)
    return;
  {
    std::lock_guard lock(g_thread_mutex);
    g_thread_wake = true;
  }
  g_thread_cv.notify_one();
}

void RunReadyCallbacks() {
  if (HookFastPathsOn() && g_waiting.load(std::memory_order_acquire) == 0)
    return;  // banjo-nx (from sa2-nx): nothing inserted and not run
  if (CallbackThreadOn()) {
    NotifyCallbacksReached();
    return;
  }
  RunReadyCallbacksHere();
}

namespace {
void RunReadyCallbacksHere() {
  if (g_waiting.load(std::memory_order_acquire) == 0)
    return;
  const uint64_t reached = render_thread::CallbacksReached();
  std::vector<Callback> ready;
  {
    std::lock_guard lock(g_mutex);
    if (g_running || g_callbacks.empty() || g_callbacks.front().seq > reached)
      return;
    while (!g_callbacks.empty() && g_callbacks.front().seq <= reached) {
      ready.push_back(g_callbacks.front());
      g_callbacks.pop_front();
    }
    g_waiting.store(g_callbacks.size(), std::memory_order_release);
    g_running = true;
  }
  for (const Callback &callback : ready) {
    PPCFunc *function = rex::runtime::ResolveIndirectFunction(callback.function);
    if (!function) {
      RGPU_ERROR("InsertCallback: no guest function at {:08X}", callback.function);
      continue;
    }
    rex::ppc::GuestToHostFunction<void>(function, callback.context);
  }
  {
    std::lock_guard lock(g_mutex);
    g_running = false;
  }
  render_thread::CallbacksRun(ready.back().seq);
}
}  // namespace

} // namespace renut::gpu
