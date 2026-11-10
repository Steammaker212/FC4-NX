// fc4-nx (2026-11-09): each C++ throw on the Switch build is written to stderr (rex_stderr.log) before it unwinds:
// the type, what() for std::exception, and the address that threw (aarch64-none-elf-addr2line -e app/out/switch/renut
// <address - module base>; the line gives the base). Linked with -Wl,--wrap=__cxa_throw (app/CMakeLists.txt).
// Stock Ryubing cannot unwind with GCC 16's libgcc (it reads GCSPR_EL0, an MRS its JIT does not know), so there the
// throw is the last thing the NRO says.
#include <cstdio>
#include <cstdlib>
#include <exception>
#include <typeinfo>

#include <cxxabi.h>
#include <unwind.h>

extern "C" [[noreturn]] void __real___cxa_throw(void* object, std::type_info* type, void (*destroy)(void*));

extern "C" [[noreturn]] void __wrap___cxa_throw(void* object, std::type_info* type, void (*destroy)(void*)) {
  const char* what = "";
  void* adjusted = object;
  if (type && typeid(std::exception).__do_catch(type, &adjusted, 1))
    what = static_cast<const std::exception*>(adjusted)->what();
  int status = -1;
  char* name = type ? abi::__cxa_demangle(type->name(), nullptr, nullptr, &status) : nullptr;
  std::fprintf(stderr, "[throw] %s: %s (from %p)\n", name ? name : (type ? type->name() : "?"), what,
               __builtin_return_address(0));
  std::free(name);
  __real___cxa_throw(object, type, destroy);
}

// Every unwind start, std::rethrow_exception's and __cxa_rethrow's too (they do not go through __cxa_throw): the stack
// as return addresses. _Unwind_Backtrace has no GCS code, so it runs on Ryubing too.
extern "C" _Unwind_Reason_Code __real__Unwind_RaiseException(_Unwind_Exception* exception);

extern "C" _Unwind_Reason_Code __wrap__Unwind_RaiseException(_Unwind_Exception* exception) {
  std::fprintf(stderr, "[unwind] raise, class 0x%016llX, stack:",
               static_cast<unsigned long long>(exception ? exception->exception_class : 0));
  int frames = 0;
  _Unwind_Backtrace(
      [](_Unwind_Context* context, void* count) -> _Unwind_Reason_Code {
        std::fprintf(stderr, " %p", reinterpret_cast<void*>(_Unwind_GetIP(context)));
        return ++*static_cast<int*>(count) < 32 ? _URC_NO_REASON : _URC_END_OF_STACK;
      },
      &frames);
  std::fprintf(stderr, "\n");
  return __real__Unwind_RaiseException(exception);
}
