// fc4-nx (2026-11-12, hw24, banjo_renut_upscale_filter 2): the second pass of the FSR 1-style upscale
// (render/ui_scale.cpp): robust contrast-adaptive sharpening after AMD FidelityFX Super Resolution 1.0's RCAS (the
// algorithm as AMD published it, MIT; Renut's own code), over ui_upscale_easu_ps.hlsl's result at the display's size.
//   translate    the source's host size (the same as the target's)
//   textureIndex the source (the EASU pass's texture)
//   param0       the sharpness: 2^-stops (banjo_renut_fsr_sharpness; 1 the most)
// A 5-tap cross: the centre less a negative lobe of its four neighbours, the lobe as large as it can be without taking any
// channel past the neighbours' range (no clipping, no ringing), smaller where the cross looks like noise.
#include "utility.hlsli"

float Luma(float3 c)
{
    return c.g + 0.5 * (c.r + c.b);
}

float4 main(float4 position : SV_Position, float2 uv : TEXCOORD0) : SV_Target0
{
    Texture2D<float4> source = g_Textures[g_Push.textureIndex];
    const int2 last = int2(g_Push.translate) - 1;
    const int2 p = min(int2(uv * g_Push.translate), last);
    //   b
    // d e f
    //   h
    const float4 e4 = source.Load(int3(p, 0));
    const float3 b = source.Load(int3(max(p + int2(0, -1), int2(0, 0)), 0)).rgb;
    const float3 d = source.Load(int3(max(p + int2(-1, 0), int2(0, 0)), 0)).rgb;
    const float3 f = source.Load(int3(min(p + int2(1, 0), last), 0)).rgb;
    const float3 h = source.Load(int3(min(p + int2(0, 1), last), 0)).rgb;
    const float3 e = e4.rgb;

    const float3 mn4 = min(min(b, d), min(f, h));
    const float3 mx4 = max(max(b, d), max(f, h));
    // The lobe w (negative) at which the result (w (b + d + f + h) + e) / (4w + 1) reaches 0 or 1 in some channel.
    const float3 hitMin = min(mn4, e) / max(4.0 * mx4, 1.0 / 65536.0);
    const float3 hitMax = (1.0 - max(mx4, e)) / min(4.0 * mn4 - 4.0, -1.0 / 65536.0);
    const float3 lobeRGB = max(-hitMin, hitMax);
    const float kLimit = 0.25 - 1.0 / 16.0;  // the strongest lobe: not quite a box's -1/4
    float lobe = max(-kLimit, min(max(lobeRGB.r, max(lobeRGB.g, lobeRGB.b)), 0.0)) * g_Push.param0;

    // Noise: the centre far from its neighbours' mean against the cross's whole range halves the lobe.
    const float bL = Luma(b), dL = Luma(d), eL = Luma(e), fL = Luma(f), hL = Luma(h);
    const float range = max(max(max(bL, dL), max(fL, hL)), eL) - min(min(min(bL, dL), min(fL, hL)), eL);
    const float nz = saturate(abs(0.25 * (bL + dL + fL + hL) - eL) / max(range, 1.0 / 65536.0));
    lobe *= 1.0 - 0.5 * nz;

    const float3 rgb = (lobe * (b + d + f + h) + e) / (4.0 * lobe + 1.0);
    return float4(saturate(rgb), e4.a);
}
