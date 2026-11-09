// fc4-nx (2026-11-09): what sa2-nx's copied renderer files (sa2_renut_pacing.cpp) take from sa2-nx's app.
#pragma once
namespace sa2::enh {
// sa2-nx's enhancement toggle; FC4 has no relaxed-vsync enhancement: always off.
struct Enhancement {
  bool active = false;
};
}  // namespace sa2::enh
inline ::sa2::enh::Enhancement g_vsync_relaxed;
