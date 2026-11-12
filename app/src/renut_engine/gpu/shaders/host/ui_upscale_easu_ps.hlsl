// fc4-nx (2026-11-12, hw24, banjo_renut_upscale_filter 2, the user's request "can we implement FSR"): the first pass of
// an FSR 1-style upscale (render/ui_scale.cpp): edge-adaptive spatial upsampling after AMD FidelityFX Super Resolution
// 1.0's EASU (the algorithm as AMD published it, MIT; this is Renut's own code, not AMD's source). ui_upscale_rcas_ps.hlsl
// sharpens its result.
//   translate    the source's host size
//   textureIndex the source (the composite's target at the internal resolution)
// Per output pixel: the 12 source texels around it (a 4x4 block without its corners), the luma gradient of the four
// nearest (bilinearly weighted) gives the edge's direction and how much of an edge it is; each texel's weight is a
// windowed-Lanczos-2 approximation of its distance along that direction (stretched across the edge, shortened along it)
// and the result is clamped to the four nearest texels' range (no ringing).
#include "utility.hlsli"

float Luma(float3 c)
{
    return c.g + 0.5 * (c.r + c.b);  // only differences and ratios are used: no normalisation
}

// One of the four nearest texels: its horizontal and vertical luma gradient (up, left, centre, right, down), weighted.
void Analyse(inout float2 dir, inout float len, float w, float up, float left, float centre, float right, float down)
{
    const float dirX = right - left;
    const float lenX = saturate(abs(dirX) / max(max(abs(right - centre), abs(centre - left)), 1.0 / 65536.0));
    const float dirY = down - up;
    const float lenY = saturate(abs(dirY) / max(max(abs(down - centre), abs(centre - up)), 1.0 / 65536.0));
    dir += float2(dirX, dirY) * w;
    len += (lenX * lenX + lenY * lenY) * w;
}

void Accumulate(inout float3 sum, inout float total, float2 offset, float2 dir, float2 len2, float lob, float clp,
                float3 color)
{
    float2 v = float2(dot(offset, dir), dot(offset, float2(-dir.y, dir.x))) * len2;
    const float d2 = min(dot(v, v), clp);
    // (25/16 (2/5 d2 - 1)^2 - (25/16 - 1)) (lob d2 - 1)^2: Lanczos 2 without its sin and rcp.
    float wB = 0.4 * d2 - 1.0;
    float wA = lob * d2 - 1.0;
    wB *= wB;
    wA *= wA;
    const float w = (1.5625 * wB - 0.5625) * wA;
    sum += color * w;
    total += w;
}

float4 main(float4 position : SV_Position, float2 uv : TEXCOORD0) : SV_Target0
{
    Texture2D<float4> source = g_Textures[g_Push.textureIndex];
    const int2 last = int2(g_Push.translate) - 1;
    const float2 pp = uv * g_Push.translate - 0.5;
    const float2 fp = floor(pp);
    const float2 t = pp - fp;
    const int2 o = int2(fp);
    //     b c
    //   e f g h
    //   i j k l
    //     n o      f at o
#define TAP(x, y) source.Load(int3(clamp(o + int2(x, y), int2(0, 0), last), 0))
    const float3 b = TAP(0, -1).rgb, c = TAP(1, -1).rgb;
    const float3 e = TAP(-1, 0).rgb, h = TAP(2, 0).rgb;
    const float3 i = TAP(-1, 1).rgb, l = TAP(2, 1).rgb;
    const float3 n = TAP(0, 2).rgb, oo = TAP(1, 2).rgb;
    const float4 f4 = TAP(0, 0), g4 = TAP(1, 0), j4 = TAP(0, 1), k4 = TAP(1, 1);
#undef TAP
    const float3 f = f4.rgb, g = g4.rgb, j = j4.rgb, k = k4.rgb;
    const float bL = Luma(b), cL = Luma(c), eL = Luma(e), fL = Luma(f), gL = Luma(g), hL = Luma(h);
    const float iL = Luma(i), jL = Luma(j), kL = Luma(k), lL = Luma(l), nL = Luma(n), oL = Luma(oo);

    const float wf = (1.0 - t.x) * (1.0 - t.y), wg = t.x * (1.0 - t.y), wj = (1.0 - t.x) * t.y, wk = t.x * t.y;
    float2 dir = 0.0;
    float len = 0.0;
    Analyse(dir, len, wf, bL, eL, fL, gL, jL);
    Analyse(dir, len, wg, cL, fL, gL, hL, kL);
    Analyse(dir, len, wj, fL, iL, jL, kL, nL);
    Analyse(dir, len, wk, gL, jL, kL, lL, oL);

    const float dirR = dot(dir, dir);
    dir = dirR < 1.0 / 32768.0 ? float2(1.0, 0.0) : dir * rsqrt(max(dirR, 1.0 / 32768.0));
    len = len * 0.5;
    len *= len;
    // A diagonal edge reaches past the 4x4 block's corners: stretched by 1 / max(|x|, |y|) across, at most sqrt 2.
    const float stretch = 1.0 / max(abs(dir.x), abs(dir.y));
    const float2 len2 = float2(1.0 + (stretch - 1.0) * len, 1.0 - 0.5 * len);
    const float lob = 0.5 + ((1.0 / 4.0 - 0.04) - 0.5) * len;
    const float clp = 1.0 / lob;

    float3 sum = 0.0;
    float total = 0.0;
    Accumulate(sum, total, float2(0.0, -1.0) - t, dir, len2, lob, clp, b);
    Accumulate(sum, total, float2(1.0, -1.0) - t, dir, len2, lob, clp, c);
    Accumulate(sum, total, float2(-1.0, 1.0) - t, dir, len2, lob, clp, i);
    Accumulate(sum, total, float2(0.0, 1.0) - t, dir, len2, lob, clp, j);
    Accumulate(sum, total, float2(0.0, 0.0) - t, dir, len2, lob, clp, f);
    Accumulate(sum, total, float2(-1.0, 0.0) - t, dir, len2, lob, clp, e);
    Accumulate(sum, total, float2(1.0, 1.0) - t, dir, len2, lob, clp, k);
    Accumulate(sum, total, float2(2.0, 1.0) - t, dir, len2, lob, clp, l);
    Accumulate(sum, total, float2(2.0, 0.0) - t, dir, len2, lob, clp, h);
    Accumulate(sum, total, float2(1.0, 0.0) - t, dir, len2, lob, clp, g);
    Accumulate(sum, total, float2(1.0, 2.0) - t, dir, len2, lob, clp, oo);
    Accumulate(sum, total, float2(0.0, 2.0) - t, dir, len2, lob, clp, n);

    const float3 lo = min(min(f, g), min(j, k));
    const float3 hi = max(max(f, g), max(j, k));
    const float3 rgb = clamp(sum / max(total, 1.0 / 65536.0), lo, hi);
    const float alpha = f4.a * wf + g4.a * wg + j4.a * wj + k4.a * wk;
    return float4(rgb, alpha);
}
