// fc4-nx (2026-11-10, banjo_renut_color_to_depth): colour target words into the depth target over the same EDRAM.
//
// Renut gives every view of EDRAM (base, pitch, samples, format) its own host target; on the console a colour target
// and a depth target at one base are the same memory. Far Cry 4 restores its scene depth and stencil before the lighting
// that way: the depth texture's words, drawn through an 8_8_8_8 view into a colour target at EDRAM base 0x540, then a
// D24FS8 target bound at 0x540 for the light volumes (stencil marks from the G-buffer pass, EQUAL 1 / 2), the sky and the
// particles. Without it the lighting drew nothing (black), the auto-exposure climbed to its maximum and the sky covered
// the screen: the white picture of the dinner scene and gameplay.
//
// When a depth target is bound and the 8_8_8_8 target over its EDRAM was written after it, the depth comes from the
// colour words in one pass (color_to_depth_ps, SV_Depth) and the stencil in eight more, one bit each (the stencil
// cleared, then each bit set with REPLACE through its write mask where the word has it): no shader stencil export.
#include "renut_engine/gpu/render/edram_transfer.h"

#include <array>
#include <memory>
#include <unordered_map>

#include <plume_render_interface.h>

#include "renut_engine/gpu/backend/backend.h"
#include "renut_engine/gpu/backend/gpu_profile.h"
#include "renut_engine/gpu/backend/video.h"
#include "renut_engine/gpu/banjo_renut_tuning.h"
#include "renut_engine/gpu/log.h"
#include "renut_engine/gpu/render/surfaces.h"
#include "renut_engine/gpu/render/textures.h"

#include "host_shaders/color_to_depth_ps.spirv.h"
#include "host_shaders/smaa_vs.spirv.h"
#if defined(PLUME_DEKO3D)
#include "host_shaders/color_to_depth_ps.deko3d.h"
#include "host_shaders/smaa_vs.deko3d.h"
#endif
#if defined(_WIN32)
#include "host_shaders/color_to_depth_ps.dxil.h"
#include "host_shaders/smaa_vs.dxil.h"
#endif

REXCVAR_DEFINE_BOOL(banjo_renut_color_to_depth, true, "Banjo/Renut",
                    "fc4-nx (2026-11-10): a depth target bound after the 8_8_8_8 colour target over its EDRAM was "
                    "written takes that target's words as its depth and stencil (Far Cry 4's depth restore before the "
                    "lighting: without it the lighting is black and the sky covers the screen)");

REXCVAR_DEFINE_BOOL(banjo_renut_diag_color_to_depth, false, "Banjo/Diagnostics",
                    "fc4-nx (2026-11-10): log the stencil bytes (histogram) of some colour words banjo_renut_color_to_depth "
                    "takes");

namespace renut::gpu {
namespace {

// banjo_renut_diag_color_to_depth: a 256x256 corner of the colour words, read back three frames later.
struct WordsProbe {
  std::unique_ptr<plume::RenderBuffer> buffer;
  uint64_t frame = 0;
  uint32_t w = 0, h = 0;
  bool pending = false;
};
WordsProbe g_probe;

void ProbeWordsLocked(VideoState &s, HostSurface *color) {
  if (g_probe.pending) {
    if (TextureFrameLocked() < g_probe.frame + 3)
      return;
    if (const auto *data = static_cast<const uint8_t *>(g_probe.buffer->map())) {
      uint32_t counts[256] = {};
      for (uint32_t y = 0; y < g_probe.h; ++y)
        for (uint32_t x = 0; x < g_probe.w; ++x)
          ++counts[data[(size_t(y) * 256 + x) * 4]];
      std::string top;
      for (int n = 0; n < 8; ++n) {
        uint32_t best = 0;
        for (uint32_t v = 1; v < 256; ++v)
          if (counts[v] > counts[best])
            best = v;
        if (!counts[best])
          break;
        top += fmt::format(" {:02X}:{}", best, counts[best]);
        counts[best] = 0;
      }
      RGPU_INFO("[c2d] stencil bytes of the colour words (value:texels):{}", top);
      g_probe.buffer->unmap();
    }
    g_probe.pending = false;
    return;
  }
  static uint32_t every = 0;
  if (every++ % 200)
    return;
  if (!g_probe.buffer)
    g_probe.buffer = s.device->createBuffer(plume::RenderBufferDesc::ReadbackBuffer(256 * 256 * 4));
  if (!g_probe.buffer)
    return;
  g_probe.w = std::min(256u, color->scale.Size(color->width));
  g_probe.h = std::min(256u, color->scale.Size(color->height));
  TransitionSurfaceLocked(color, plume::RenderTextureLayout::COPY_SOURCE);
  const plume::RenderBox box(0, 0, int32_t(g_probe.w), int32_t(g_probe.h));
  s.command_list->copyTextureRegion(
      plume::RenderTextureCopyLocation::PlacedFootprint(g_probe.buffer.get(), color->format, g_probe.w, g_probe.h, 1, 256),
      plume::RenderTextureCopyLocation::Subresource(color->texture.get(), 0, 0), 0, 0, 0, &box);
  g_probe.frame = TextureFrameLocked();
  g_probe.pending = true;
}

struct TransferPass {
  std::unique_ptr<plume::RenderShader> vs, ps;
  bool failed = false;
  // Per depth format: [0] the depth pass, [1 + bit] the stencil bit passes.
  std::unordered_map<uint32_t, std::array<std::unique_ptr<plume::RenderPipeline>, 9>> pipelines;
  std::unordered_map<const HostSurface *, std::pair<uint64_t, std::unique_ptr<plume::RenderFramebuffer>>> framebuffers;
};
TransferPass g_pass;

plume::RenderPipeline *Pipeline(VideoState &s, plume::RenderFormat format, uint32_t index) {
  TransferPass &p = g_pass;
  if (!p.vs || !p.ps) {
    p.vs = CreateHostShader(s.device.get(), RENUT_HOST_SHADER(smaa_vs), "smaa_vs");
    p.ps = CreateHostShader(s.device.get(), RENUT_HOST_SHADER(color_to_depth_ps), "color_to_depth_ps");
    if (!p.vs || !p.ps) {
      p.failed = true;
      RGPU_WARN("[renut] the colour-to-depth pass's shaders could not be made (banjo_renut_color_to_depth)");
      return nullptr;
    }
  }
  auto &pipeline = p.pipelines[uint32_t(format)][index];
  if (!pipeline) {
    plume::RenderGraphicsPipelineDesc desc;
    desc.pipelineLayout = s.utility_layout.get();
    desc.vertexShader = p.vs.get();
    desc.pixelShader = p.ps.get();
    desc.primitiveTopology = plume::RenderPrimitiveTopology::TRIANGLE_LIST;
    desc.cullMode = plume::RenderCullMode::NONE;
    desc.renderTargetCount = 0;
    desc.depthTargetFormat = format;
    if (index == 0) {
      desc.depthEnabled = true;
      desc.depthWriteEnabled = true;
      desc.depthFunction = plume::RenderComparisonFunction::ALWAYS;
    } else {
      desc.depthEnabled = false;
      desc.depthWriteEnabled = false;
      desc.depthFunction = plume::RenderComparisonFunction::ALWAYS;
      desc.stencilEnabled = true;
      desc.stencilReadMask = 0xFF;
      desc.stencilWriteMask = 1u << (index - 1);
      desc.stencilReference = 0xFF;
      plume::RenderStencilFaceDesc face;
      face.passOp = plume::RenderStencilOp::REPLACE;
      face.failOp = plume::RenderStencilOp::KEEP;
      face.depthFailOp = plume::RenderStencilOp::REPLACE;
      face.compareFunction = plume::RenderComparisonFunction::ALWAYS;
      desc.stencilFrontFace = face;
      desc.stencilBackFace = face;
    }
    pipeline = s.device->createGraphicsPipeline(desc);
    if (!pipeline) {
      p.failed = true;
      RGPU_WARN("[renut] the colour-to-depth pass's pipeline could not be made (banjo_renut_color_to_depth)");
      return nullptr;
    }
    pipeline->setName(index ? "renut colour to stencil bit" : "renut colour to depth");
  }
  return pipeline.get();
}

} // namespace

bool ColorToDepthBeforeBindLocked(HostSurface *depth) {
  static const bool on = REXCVAR_GET(banjo_renut_color_to_depth);
  if (!on || g_pass.failed || !depth || !depth->depth || !depth->texture ||
      depth->samples != plume::RenderSampleCount::COUNT_1)
    return false;
  HostSurface *color = ColorOverDepthLocked(depth);
  if (!color || !color->texture || color->write_seq <= depth->write_seq || color->write_seq == depth->transfer_seq ||
      color->samples != plume::RenderSampleCount::COUNT_1 || color->scale != depth->scale)
    return false;
  VideoState &s = State();
  if (!s.command_list)
    return false;
  const bool stencil = plume::RenderFormatIsStencil(depth->format);
  plume::RenderPipeline *depth_pipeline = Pipeline(s, depth->format, 0);
  if (!depth_pipeline)
    return false;
  const uint32_t source_slot = SurfaceSampleSlotLocked(color);
  if (source_slot == kInvalidDescriptor)
    return false;
  auto &fb = g_pass.framebuffers[depth];
  if (!fb.second || fb.first != depth->generation) {
    fb.second = s.device->createFramebuffer(plume::RenderFramebufferDesc(nullptr, 0, depth->texture.get()));
    fb.first = depth->generation;
    if (!fb.second)
      return false;
  }
  if (REXCVAR_GET(banjo_renut_diag_color_to_depth))
    ProbeWordsLocked(s, color);
  static const uint32_t kLabel = gpu_profile::Label("colour to depth");
  gpu_profile::Mark(s, kLabel);
  TransitionSurfaceLocked(color, plume::RenderTextureLayout::SHADER_READ);
  TransitionSurfaceLocked(depth, plume::RenderTextureLayout::DEPTH_WRITE);
  plume::RenderCommandList *cmd = s.command_list;
  const uint32_t width = std::min(depth->scale.Size(depth->width), color->scale.Size(color->width));
  const uint32_t height = std::min(depth->scale.Size(depth->height), color->scale.Size(color->height));
  UtilityPush push{};
  push.translate[0] = float(width);
  push.translate[1] = float(height);
  push.texture_index = source_slot;
  push.sampler_index = kPointClampSamplerSlot;
  // D3DFMT_D24FS8 (GPU texture format 24_8_FLOAT) stores 20e4 float depth.
  push.param0 = (depth->format_word & 0x3F) == 23 ? 1.0f : 0.0f;
  push.param1 = -1.0f;
  cmd->setGraphicsPipelineLayout(s.utility_layout.get());
  cmd->setGraphicsDescriptorSet(s.texture_set.get(), 0);
  cmd->setGraphicsDescriptorSet(s.sampler_set.get(), 1);
  cmd->setFramebuffer(fb.second.get());
  cmd->setViewports(plume::RenderViewport(0.0f, 0.0f, float(width), float(height)));
  cmd->setScissors(plume::RenderRect(0, 0, int32_t(width), int32_t(height)));
  cmd->setPipeline(depth_pipeline);
  cmd->setGraphicsPushConstants(0, &push, 0, sizeof(push));
  cmd->drawInstanced(3, 1, 0, 0);
  if (stencil) {
    cmd->clearDepthStencil(false, true, 0.0f, 0);
    for (uint32_t bit = 0; bit < 8; ++bit) {
      plume::RenderPipeline *pipeline = Pipeline(s, depth->format, 1 + bit);
      if (!pipeline)
        break;
      push.param1 = float(bit);
      cmd->setPipeline(pipeline);
      cmd->setGraphicsPushConstants(0, &push, 0, sizeof(push));
      cmd->drawInstanced(3, 1, 0, 0);
    }
    depth->stencil_used = true;
  }
  ++depth->writes;
  depth->write_seq = NextSurfaceWriteSeq();
  depth->transfer_seq = color->write_seq;
  static uint32_t logged = 0;
  if (logged++ < 4)
    RGPU_INFO("[renut] depth target {:08X} ({}x{}) takes the words of colour target {:08X} over its EDRAM "
              "(banjo_renut_color_to_depth)", depth->guest_va, depth->width, depth->height, color->guest_va);
  return true;
}

} // namespace renut::gpu
