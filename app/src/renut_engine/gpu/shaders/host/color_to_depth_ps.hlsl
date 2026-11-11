// fc4-nx (2026-11-10, banjo_renut_color_to_depth): a 32-bit colour target's words as the depth target over the same
// EDRAM (render/edram_transfer.cpp). On the console a colour target and a depth target at one EDRAM base are the same
// memory: Far Cry 4 restores its scene depth and stencil for the lighting by drawing the depth texture's words through
// an 8_8_8_8 view into a colour target, then binding a D24S8 / D24FS8 target at that base. The guest word is
// R | G << 8 | B << 16 | A << 24 (8_8_8_8 bytes, least significant first): depth in the top 24 bits, stencil in the
// low 8. smaa_vs.hlsl's triangle: uv 0..1 over the destination.
//   textureIndex the colour target's slot (SurfaceSampleSlotLocked)
//   translate    its host size
//   param0       1 for D24FS8 (20e4 float depth), 0 for D24S8 (24-bit unorm)
//   param1       < 0: the depth pass; 0..7: the pass for that stencil bit (pixels without it are discarded)
//   scale.x      fc4-nx (2026-11-12, banjo_renut_color_to_depth_swap): 40 guest pixels in host pixels, 0 = off. In
//                the EDRAM a depth tile (80x16 samples) holds its two 40-sample halves the other way round from a colour
//                tile, so the depth at x is the colour word written at x + 40 or x - 40 of the same tile (the console's
//                restores write the words so swapped).
#define UTILITY_OWN_TEXTURE_TABLE
#include "utility.hlsli"

Texture2D<float4> g_Color[] : register(t0, space0);

// 20e4: a 4-bit exponent (bias 15) above a 20-bit mantissa; exponent 0 counts steps of 2^-34 (depth_resolve.hlsli's
// EncodeFloat20e4 the other way).
float DecodeFloat20e4(uint bits)
{
    const uint exponent = bits >> 20;
    const uint mantissa = bits & 0xFFFFF;
    if (exponent == 0)
        return float(mantissa) * (1.0 / 17179869184.0);
    return asfloat(((exponent + 112) << 23) | (mantissa << 3));
}

float main(float4 position : SV_Position, float2 uv : TEXCOORD0) : SV_Depth
{
    const int2 size = int2(g_Push.translate);
    int2 texel = min(int2(uv * g_Push.translate), size - 1);
    if (g_Push.scale.x > 0.0)
    {
        const float half_tile = floor(g_Push.scale.x + 0.5);  // float: uam has no integer division by a variable
        const bool first_half = frac((float(texel.x) + 0.5) / (2.0 * half_tile)) < 0.5;
        texel.x += int(first_half ? half_tile : -half_tile);
        texel.x = clamp(texel.x, 0, size.x - 1);
    }
    const float4 color = g_Color[NonUniformResourceIndex(g_Push.textureIndex)].Load(int3(texel, 0));
    const uint4 bytes = uint4(saturate(color) * 255.0 + 0.5);
    const uint word = bytes.x | (bytes.y << 8) | (bytes.z << 16) | (bytes.w << 24);
    if (g_Push.param1 >= 0.0 && ((word >> uint(g_Push.param1)) & 1u) == 0u)
        discard;
    const uint depth24 = word >> 8;
    return g_Push.param0 != 0.0 ? DecodeFloat20e4(depth24) : float(depth24) * (1.0 / 16777215.0);
}
