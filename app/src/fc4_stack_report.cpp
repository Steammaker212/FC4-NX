// fc4-nx (2026-11-10): how deep the guest threads' host stacks go, to size them for the Switch
// (guest_thread_host_stack_kb). PC only: a Windows thread's committed stack (its TEB's StackBase - StackLimit) only grows,
// so it is the thread's high-water mark. Every fc4_stack_report_s seconds, one log line: the deepest and the top five.

#include <rex/cvar.h>
#include <fmt/format.h>
#include <rex/logging.h>

REXCVAR_DEFINE_INT32(fc4_stack_report_s, 0, "FC4/Diagnostics",
                     "PC: every N seconds, log the guest threads' deepest host stack use (0 = off)")
    .range(0, 3600)
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);

#if defined(_WIN32)
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>

#include <algorithm>
#include <chrono>
#include <string>
#include <thread>
#include <vector>

#include <rex/system/kernel_state.h>
#include <rex/system/xthread.h>
#include <rex/thread.h>

namespace fc4 {
namespace {
struct BasicInfo {  // THREAD_BASIC_INFORMATION
  LONG exit_status;
  PVOID teb;
  PVOID client_id[2];
  ULONG_PTR affinity;
  LONG priority, base_priority;
};
using QueryFn = LONG(WINAPI *)(HANDLE, int, PVOID, ULONG, PULONG);

void Report(QueryFn query) {
  auto *kernel = rex::system::kernel_state();
  if (!kernel)
    return;
  std::vector<std::pair<size_t, std::string>> depth;
  for (auto &thread : kernel->object_table()->GetObjectsByType<rex::system::XThread>()) {
    if (!thread || !thread->is_guest_thread() || !thread->thread())
      continue;
    BasicInfo info{};
    if (query(static_cast<HANDLE>(thread->thread()->native_handle()), 0, &info, sizeof(info), nullptr) != 0 || !info.teb)
      continue;
    // The committed stack may be the whole reservation (it is here): the deepest non-zero word from the bottom is the
    // high-water mark (a fresh stack is zero).
    const NT_TIB *tib = static_cast<const NT_TIB *>(info.teb);
    const uint64_t *p = static_cast<const uint64_t *>(tib->StackLimit);
    const uint64_t *top = static_cast<const uint64_t *>(tib->StackBase);
    while (p < top && *p == 0)
      ++p;
    depth.emplace_back(size_t(reinterpret_cast<const char *>(top) - reinterpret_cast<const char *>(p)),
                       thread->thread()->name());
  }
  if (depth.empty())
    return;
  std::sort(depth.begin(), depth.end(), [](auto &a, auto &b) { return a.first > b.first; });
  std::string top;
  for (size_t i = 0; i < depth.size() && i < 5; ++i)
    top += fmt::format("{}{} {} KB", i ? ", " : "", depth[i].second, depth[i].first >> 10);
  REXLOG_INFO("[stacks] guest threads' host stack high-water: deepest {} KB of {} threads ({})", depth[0].first >> 10,
              depth.size(), top);
}
}  // namespace

void StartStackReport() {
  const int every = REXCVAR_GET(fc4_stack_report_s);
  if (every <= 0)
    return;
  auto query = reinterpret_cast<QueryFn>(GetProcAddress(GetModuleHandleA("ntdll.dll"), "NtQueryInformationThread"));
  if (!query)
    return;
  std::thread([every, query] {
    for (;;) {
      std::this_thread::sleep_for(std::chrono::seconds(every));
      Report(query);
    }
  }).detach();
}
}  // namespace fc4
#else
namespace fc4 {
void StartStackReport() {}
}  // namespace fc4
#endif
