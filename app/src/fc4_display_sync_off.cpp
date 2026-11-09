// fc4-nx (2026-11-09): banjo::display_sync for builds without Renut's renderer (BANJO_RENUT_RENDERER=OFF, the first
// boots on the SDK's emulated GPU). The real one (src/renut_engine/display_sync.cpp) lives in the Renut GPU library and
// reads its video back end. Here there is no display anchor: NextRelease returns 0, so the frame limiter in
// katamari_keys.cpp paces from its own clock (its "else" branch).
#include "renut_engine/display_sync.h"

namespace banjo::display_sync {
void Start() {}
uint64_t NextRelease(uint64_t, uint64_t, uint64_t, bool* anchored) {
  if (anchored) *anchored = false;
  return 0;
}
void NoteRelease(uint64_t, bool) {}
void NotePresented(uint64_t) {}
std::string Report() { return {}; }
}  // namespace banjo::display_sync
