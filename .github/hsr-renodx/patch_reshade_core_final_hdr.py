#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 3:
    raise SystemExit(
        "usage: patch_reshade_core_final_hdr.py <runtime.cpp> <copy_ps.hlsl>"
    )

runtime_path = Path(sys.argv[1])
shader_path = Path(sys.argv[2])

runtime = runtime_path.read_text(encoding="utf-8")

marker = "O_CORE_FINAL_HDR_COPY=ON"

if marker in runtime:
    raise SystemExit("FAIL: core HDR patch already present")

anchor = "\t_back_buffer_color_space = _swapchain->get_color_space();\n"

if runtime.count(anchor) != 1:
    raise SystemExit(
        f"FAIL: runtime color-space anchor count={runtime.count(anchor)}"
    )

insert = (
    anchor
    + "\n"
    + "\t// Kaiozen HOTFIX O: force ReShade's stable resolve/copy path on\n"
    + "\t// HSR's native DX11 RGBA8 swap chain. The final copy pixel shader\n"
    + "\t// performs the complete SDR->BT.2020/PQ transport after game UI.\n"
    + "\tconst bool kaiozen_hsr_core_final_hdr =\n"
    + "\t\t_device->get_api() == api::device_api::d3d11 &&\n"
    + "\t\t_back_buffer_format == api::format::r8g8b8a8_unorm;\n"
    + "\n"
    + "\tif (kaiozen_hsr_core_final_hdr)\n"
    + "\t\tlog::message(log::level::info, \"[Kaiozen] O_CORE_FINAL_HDR_COPY=ON\");\n"
)

runtime = runtime.replace(anchor, insert, 1)

old_condition = "\tif (back_buffer_desc.texture.samples > 1 ||\n"
new_condition = (
    "\tif (kaiozen_hsr_core_final_hdr ||\n"
    "\t\tback_buffer_desc.texture.samples > 1 ||\n"
)

if runtime.count(old_condition) != 1:
    raise SystemExit(
        f"FAIL: resolve-condition anchor count={runtime.count(old_condition)}"
    )

runtime = runtime.replace(old_condition, new_condition, 1)

if runtime.count(marker) != 1:
    raise SystemExit("FAIL: runtime marker verification")
if runtime.count("kaiozen_hsr_core_final_hdr") != 3:
    raise SystemExit("FAIL: core HDR runtime wiring verification")

runtime_path.write_text(runtime, encoding="utf-8", newline="\n")

shader = r'''Texture2D t0 : register(t0);
SamplerState s0 : register(s0);

// KAIOZEN_HSR_CORE_HDR_COPY_O
//
// Input: HSR finished frame in native R8G8B8A8_UNORM, sRGB encoded.
// Output: raw BT.2020 ST.2084 PQ code values in the same RGBA8 swap chain.
// HOTFIX M sets that swap chain to HDR10/PQ + BT.2020.
//
// No BT.2446A, no saturation compensation, no global contrast expansion.
// The source curve is preserved through 98% luminance. Only the extreme
// highlight tip expands from 203 nits toward 400 nits.

float SRGBToLinear(float x)
{
    if (x <= 0.04045)
        return x / 12.92;

    return pow((x + 0.055) / 1.055, 2.4);
}

float3 BT709ToBT2020(float3 c)
{
    return float3(
        dot(c, float3(0.6274040, 0.3292820, 0.0433136)),
        dot(c, float3(0.0690970, 0.9195400, 0.0113612)),
        dot(c, float3(0.0163916, 0.0880132, 0.8955950))
    );
}

float PQEncodeNits1(float nits)
{
    const float m1 = 0.1593017578125;
    const float m2 = 78.84375;
    const float c1 = 0.8359375;
    const float c2 = 18.8515625;
    const float c3 = 18.6875;

    float x = max(nits, 0.0) / 10000.0;
    float p = pow(x, m1);
    return pow((c1 + c2 * p) / (1.0 + c3 * p), m2);
}

float3 PQEncodeNits(float3 nits)
{
    return float3(
        PQEncodeNits1(nits.r),
        PQEncodeNits1(nits.g),
        PQEncodeNits1(nits.b)
    );
}

void main(
    float4 vpos : SV_POSITION,
    float2 uv : TEXCOORD0,
    out float4 col : SV_TARGET)
{
    float3 encoded709 = saturate(t0.Sample(s0, uv).rgb);

    float3 linear709 = float3(
        SRGBToLinear(encoded709.r),
        SRGBToLinear(encoded709.g),
        SRGBToLinear(encoded709.b)
    );

    float3 linear2020 = max(BT709ToBT2020(linear709), 0.0);

    const float3 K709 = float3(0.2126729, 0.7151522, 0.0721750);
    float y = max(dot(linear709, K709), 0.0);

    const float REFERENCE_NITS = 203.0;
    const float HDR_PEAK_NITS = 400.0;
    const float HIGHLIGHT_START = 0.98;

    float h = saturate((y - HIGHLIGHT_START) / (1.0 - HIGHLIGHT_START));
    h = h * h * (3.0 - 2.0 * h);

    float gain = lerp(
        1.0,
        HDR_PEAK_NITS / REFERENCE_NITS,
        h
    );

    float3 nits2020 = min(
        linear2020 * REFERENCE_NITS * gain,
        HDR_PEAK_NITS
    );

    col.rgb = saturate(PQEncodeNits(nits2020));
    col.a = 1.0;
}
'''

shader_path.write_text(shader, encoding="utf-8", newline="\n")

print("RUNTIME_FORCE_FINAL_COPY=PASS")
print("CORE_COPY_SHADER=BT2020_PQ")
print("BT2446A=ABSENT")
print("SATURATION_HACK=ABSENT")
print("REFERENCE_WHITE=203")
print("CONTENT_PEAK=400")
print("HIGHLIGHT_KNEE=0.98")
print("HOTFIX=O")
