// banjo-nx (2026-10-18): a colour resolve drawn instead of copied (draw.cpp, DrawResolveCopy). deko3d copies images on
// the copy engine, which needs the whole GPU idle before and after it; a draw is ordered like any other. The destination
// pixel plus g_Push.translate is the source texel, read with Load through a view of the surface's own format (the
// destination has the same format, so every texel is written back with its bits). present_vs draws the fullscreen
// triangle; the scissor limits it to the resolved rect.
#include "utility.hlsli"

// fc4-nx (2026-11-11): a float's 7e3 code (Xenos 2_10_10_10_FLOAT: 3-bit exponent biased by 3, 7-bit mantissa,
// 0..31.875), rounded to nearest even.
uint Float7e3(float value)
{
    const uint f32 = asuint(clamp(value, 0.0, 31.875));
    const uint denormal = ((f32 & 0x7FFFFFu) | 0x800000u) >> min(125u - (f32 >> 23u), 24u);
    const uint biased = f32 < 0x3E800000u ? denormal : f32 - (124u << 23u);
    return ((biased + 0x7FFFu + ((biased >> 16u) & 1u)) >> 16u) & 0x3FFu;
}

float4 main(float4 position : SV_Position) : SV_Target0
{
    const int2 texel = int2(position.xy) + int2(g_Push.translate);
    float4 color = g_Textures[NonUniformResourceIndex(g_Push.textureIndex)].Load(int3(texel, 0));
    // fc4-nx (2026-11-11, banjo_renut_resolve_7e3_bits): param0 == 7, the source holds 7e3 values and the console
    // resolves it through a fixed 2_10_10_10 view: each channel's 7e3 code read as 10-bit unorm, alpha as 2-bit.
    if (g_Push.param0 == 7.0)
        color = float4(float(Float7e3(color.r)), float(Float7e3(color.g)), float(Float7e3(color.b)),
                       round(saturate(color.a) * 3.0)) / float4(1023.0, 1023.0, 1023.0, 3.0);
    // fc4-nx (2026-11-10): param1 > 0, a resolve into a fixed-point texture: the console writes the value times its
    // exponent bias (param1 = 2^bias), clamped to 0..1 (unsigned).
    if (g_Push.param1 > 0.0)
        color = saturate(color * g_Push.param1);
    // fc4-nx (2026-11-10): param1 < 0, such a resolve into a texture fetched as integers (num_format 1): the value
    // times the bias, unclamped (the integer the console stores; the fetch's exponent adjust brings it back).
    else if (g_Push.param1 < 0.0)
        color *= -g_Push.param1;
    return color;
}
