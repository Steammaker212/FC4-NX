// fc4-nx (2026-11-09): debug-only, PC only, every key off by default. Finds who writes a bad value into guest memory.
//
// boot7-10 crash on garbage pointers that were never allocated (docs/fc4-notes.md): the job system's free list
// (popped by sub_83AC94B8) holds head 0x20611840. Two tools:
//
//  - fc4_watch_pop = true: a hook on sub_83AC94B8 logs the list address (r3), the head words and a host backtrace
//    the first time a list's head word equals fc4_watch_value (or, with no value, is not 8-byte aligned).
//  - fc4_watch_addr = "0x...": an x64 hardware data breakpoint (DR0, 4 bytes, on writes) on the host address of that
//    guest word, set on every thread of the process and again every 20 ms for threads created later. Each write is
//    logged with the value now there, the writing thread and a host backtrace (renut.exe+offset: symbolise with
//    llvm-symbolizer --obj=renut.exe 0x140000000+offset); with fc4_watch_value only writes of that value are logged.
//
// Data breakpoints trap after the write, so the backtrace's first frame is the instruction after the store.
#include <atomic>
#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <mutex>
#include <set>
#include <string>
#include <thread>

#include <fmt/format.h>

#include <rex/cvar.h>
#include <rex/hook.h>
#include <rex/logging.h>
#include <rex/system/kernel_state.h>
#include <rex/system/xmemory.h>

REXCVAR_DEFINE_STRING(fc4_watch_addr, "", "FC4/Debug",
                      "Debug: guest address of a 32-bit word to watch for writes with a hardware breakpoint (PC)");
REXCVAR_DEFINE_STRING(fc4_watch_value, "", "FC4/Debug",
                      "Debug: only report writes (and pop heads) equal to this 32-bit value (hex)");
REXCVAR_DEFINE_BOOL(fc4_watch_pop, false, "FC4/Debug",
                    "Debug: log the job free list (sub_83AC94B8) whose head matches fc4_watch_value");

#if defined(_WIN32)
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include <tlhelp32.h>

namespace fc4::watch {
namespace {

uint8_t* g_host = nullptr;          // host address of the watched guest word
uint32_t g_value = 0;
bool g_has_value = false;
std::atomic<uint32_t> g_reports{0};
uintptr_t g_module_lo = 0, g_module_hi = 0;

uint32_t ParseHex(const std::string& s) { return s.empty() ? 0 : static_cast<uint32_t>(std::strtoul(s.c_str(), nullptr, 16)); }

uint32_t Be32(const uint8_t* p) { return uint32_t(p[0]) << 24 | uint32_t(p[1]) << 16 | uint32_t(p[2]) << 8 | p[3]; }

std::string Backtrace(int skip) {
  void* frames[28];
  const USHORT n = RtlCaptureStackBackTrace(skip, 28, frames, nullptr);
  std::string out;
  for (USHORT i = 0; i < n; ++i) {
    const auto a = reinterpret_cast<uintptr_t>(frames[i]);
    if (a >= g_module_lo && a < g_module_hi)
      out += fmt::format(" renut.exe+0x{:X}", a - g_module_lo);
    else
      out += fmt::format(" 0x{:X}", a);
  }
  return out;
}

LONG CALLBACK OnException(EXCEPTION_POINTERS* info) {
  if (info->ExceptionRecord->ExceptionCode != EXCEPTION_SINGLE_STEP || !(info->ContextRecord->Dr6 & 0xF))
    return EXCEPTION_CONTINUE_SEARCH;
  info->ContextRecord->Dr6 = 0;
  const uint32_t now = Be32(g_host);
  if ((!g_has_value || now == g_value) && g_reports.fetch_add(1) < 400) {
    const uintptr_t rip = info->ContextRecord->Rip;
    REXLOG_WARN("[fc4 watch] write: word now {:08X} {:08X}, thread {}, rip {}; stack:{}", now, Be32(g_host + 4),
                GetCurrentThreadId(),
                rip >= g_module_lo && rip < g_module_hi ? fmt::format("renut.exe+0x{:X}", rip - g_module_lo)
                                                        : fmt::format("0x{:X}", rip),
                Backtrace(1));
  }
  return EXCEPTION_CONTINUE_EXECUTION;
}

void ArmThreads(std::set<DWORD>& armed) {
  const DWORD self = GetCurrentThreadId(), pid = GetCurrentProcessId();
  HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0);
  if (snap == INVALID_HANDLE_VALUE) return;
  THREADENTRY32 te{};
  te.dwSize = sizeof(te);
  for (BOOL ok = Thread32First(snap, &te); ok; ok = Thread32Next(snap, &te)) {
    if (te.th32OwnerProcessID != pid || te.th32ThreadID == self || armed.count(te.th32ThreadID)) continue;
    HANDLE t = OpenThread(THREAD_GET_CONTEXT | THREAD_SET_CONTEXT | THREAD_SUSPEND_RESUME, FALSE, te.th32ThreadID);
    if (!t) continue;
    if (SuspendThread(t) != DWORD(-1)) {
      CONTEXT c{};
      c.ContextFlags = CONTEXT_DEBUG_REGISTERS;
      if (GetThreadContext(t, &c)) {
        c.Dr0 = reinterpret_cast<DWORD64>(g_host);
        c.Dr7 = (c.Dr7 & ~0xF0003ull) | 1ull | (1ull << 16) | (3ull << 18);  // L0, write, 4 bytes
        if (SetThreadContext(t, &c)) armed.insert(te.th32ThreadID);
      }
      ResumeThread(t);
    }
    CloseHandle(t);
  }
  CloseHandle(snap);
}

}  // namespace

bool PopWatchOn() { return REXCVAR_GET(fc4_watch_pop); }

void Start() {
  auto* ks = rex::system::kernel_state();
  if (!ks) return;
  HMODULE m = GetModuleHandleW(nullptr);
  auto* dos = reinterpret_cast<IMAGE_DOS_HEADER*>(m);
  auto* nt = reinterpret_cast<IMAGE_NT_HEADERS*>(reinterpret_cast<uint8_t*>(m) + dos->e_lfanew);
  g_module_lo = reinterpret_cast<uintptr_t>(m);
  g_module_hi = g_module_lo + nt->OptionalHeader.SizeOfImage;
  g_has_value = !REXCVAR_GET(fc4_watch_value).empty();
  g_value = ParseHex(REXCVAR_GET(fc4_watch_value));
  const uint32_t guest = ParseHex(REXCVAR_GET(fc4_watch_addr));
  if (!guest) return;
  g_host = ks->memory()->TranslateVirtual(guest);
  AddVectoredExceptionHandler(1, OnException);
  REXLOG_WARN("[fc4 watch] hardware write breakpoint on guest {:08X} (host {}), value filter {}", guest,
              static_cast<void*>(g_host), g_has_value ? fmt::format("{:08X}", g_value) : std::string("none"));
  std::thread([] {
    std::set<DWORD> armed;
    for (;;) {
      ArmThreads(armed);
      std::this_thread::sleep_for(std::chrono::milliseconds(20));
    }
  }).detach();
}

std::string HostBacktrace() { return Backtrace(2); }

}  // namespace fc4::watch

// The job system's lock-free free-list pop (docs/fc4-notes.md, boot7). Hooked only to report; always runs the original.
REX_EXTERN(__imp__sub_83AC94B8);
REX_HOOK_RAW(sub_83AC94B8) {
  if (fc4::watch::PopWatchOn()) {
    const uint32_t list = ctx.r3.u32;
    const uint8_t* p = rex::memory::GuestPtr(base, list);  // 0xE0000000+: 4 KB host offset on Windows
    const uint32_t head = uint32_t(p[0]) << 24 | uint32_t(p[1]) << 16 | uint32_t(p[2]) << 8 | p[3];
    const uint32_t tag = uint32_t(p[4]) << 24 | uint32_t(p[5]) << 16 | uint32_t(p[6]) << 8 | p[7];
    const std::string v = REXCVAR_GET(fc4_watch_value);
    const bool hit = v.empty() ? (head & 7) != 0 : head == static_cast<uint32_t>(std::strtoul(v.c_str(), nullptr, 16));
    static std::atomic<int> calls{0};
    if (calls.fetch_add(1) < 3)
      REXLOG_WARN("[fc4 watch] pop hook live: list {:08X} head {:08X} tag {:08X} filter '{}'", list, head, tag, v);
    if (hit) {
      static std::mutex mu;
      static std::set<uint32_t> seen;
      std::lock_guard<std::mutex> lock(mu);
      if (seen.insert(list).second)
        REXLOG_WARN("[fc4 watch] pop: list {:08X} head {:08X} tag {:08X}, caller lr {:08X}; stack:{}", list, head, tag,
                    static_cast<uint32_t>(ctx.lr), fc4::watch::HostBacktrace());
    }
  }
  __imp__sub_83AC94B8(ctx, base);
}

// boot12: the pop's list pointer itself is the bad value. sub_83AD5350 passes list = *(*(r3) + 32) to sub_83ACFCF0
// (which pops from it). Logs where that word lives the first time it holds fc4_watch_value (or is not 4-aligned).
REX_EXTERN(__imp__sub_83AD5350);
REX_HOOK_RAW(sub_83AD5350) {
  if (fc4::watch::PopWatchOn()) {
    auto be = [&](uint32_t a) {
      const uint8_t* p = rex::memory::GuestPtr(base, a);
      return uint32_t(p[0]) << 24 | uint32_t(p[1]) << 16 | uint32_t(p[2]) << 8 | p[3];
    };
    const uint32_t owner = ctx.r3.u32;
    const uint32_t obj = owner ? be(owner) : 0;
    const uint32_t list = obj ? be(obj + 32) : 0;
    const std::string v = REXCVAR_GET(fc4_watch_value);
    const bool hit = v.empty() ? (list & 3) != 0 : list == static_cast<uint32_t>(std::strtoul(v.c_str(), nullptr, 16));
    static std::atomic<int> calls{0};
    if (calls.fetch_add(1) < 3)
      REXLOG_WARN("[fc4 watch] 83AD5350 live: r3 {:08X} obj {:08X} list {:08X}", owner, obj, list);
    static std::atomic<bool> once{false};
    if (hit && !once.exchange(true))
      REXLOG_WARN("[fc4 watch] bad list: r3 {:08X} -> obj {:08X}, word at {:08X} = {:08X}; obj words {:08X} {:08X} {:08X} "
                  "{:08X} {:08X} {:08X} {:08X} {:08X} {:08X} {:08X}, lr {:08X}; stack:{}",
                  owner, obj, obj + 32, list, be(obj), be(obj + 4), be(obj + 8), be(obj + 12), be(obj + 16),
                  be(obj + 20), be(obj + 24), be(obj + 28), be(obj + 36), be(obj + 40), static_cast<uint32_t>(ctx.lr),
                  fc4::watch::HostBacktrace());
  }
  __imp__sub_83AD5350(ctx, base);
}

#else
namespace fc4::watch {
void Start() {}
}  // namespace fc4::watch
#endif
