#!/usr/bin/env python3

from pathlib import Path
import sys

if len(sys.argv) != 3:
    raise SystemExit(
        "usage: patch_reshade_core_final_hdr.py "
        "<runtime.cpp> <copy_ps.hlsl>"
    )

runtime_path = Path(sys.argv[1])
shader_path = Path(sys.argv[2])

runtime = runtime_path.read_text(encoding="utf-8")

anchor = (
    "\t_back_buffer_color_space = "
    "_swapchain->get_color_space();\n"
)

if runtime.count(anchor) != 1:
    raise SystemExit(
        "FAIL: runtime color-space anchor invalid"
    )

insert = (
    anchor
    + "\n"
    + "\t// Kaiozen HOTFIX P: neutral final-frame HDR carrier.\n"
    + "\tconst bool kaiozen_hsr_core_final_hdr =\n"
    + "\t\t_device->get_api() == api::device_api::d3d11 &&\n"
    + "\t\t_back_buffer_format == api::format::r8g8b8a8_unorm;\n"
    + "\n"
    + "\tif (kaiozen_hsr_core_final_hdr)\n"
    + "\t\tlog::message(\n"
    + "\t\t\tlog::level::info,\n"
    + "\t\t\t\"[Kaiozen] P_CORE_FINAL_HDR_NEUTRAL=ON\");\n"
)

runtime = runtime.replace(
    anchor,
    insert,
    1
)

old = (
    "\tif (back_buffer_desc.texture.samples > 1 ||\n"
)

new = (
    "\tif (kaiozen_hsr_core_final_hdr ||\n"
    "\t\tback_buffer_desc.texture.samples > 1 ||\n"
)

if runtime.count(old) != 1:
    raise SystemExit(
        "FAIL: resolve condition anchor invalid"
    )

runtime = runtime.replace(
    old,
    new,
    1
)

runtime_path.write_text(
    runtime,
    encoding="utf-8",
    newline="\n"
)

shader = r'''Texture2D t0 : register(t0);
SamplerState s0 : register(s0);

// KAIOZEN_HSR_CORE_HDR_COPY_P
//
// FINAL-FRAME TRANSPORT ONLY.
//
// There is deliberately NO inverse tonemap here.
// There is deliberately NO highlight expansion here.
// There is deliberately NO saturation adjustment here.
// There is deliberately NO contrast adjustment here.
//
// HSR RenoDX's final PostToneMapScale uses gamma 2.2,
// so this pass inverts gamma 2.2 instead of assuming sRGB.
//
// 1.0 source white is mapped to 80 nits.
// This preserves SDR appearance inside the HDR10 carrier.

float3 Gamma22Decode(float3 v)
{
    return pow(
        max(v, 0.0),
        2.2);
}

float3 BT709ToBT2020(float3 c)
{
    return float3(
        dot(
            c,
            float3(
                0.6274040,
                0.3292820,
                0.0433136)),
        dot(
            c,
            float3(
                0.0690970,
                0.9195400,
                0.0113612)),
        dot(
            c,
            float3(
                0.0163916,
                0.0880132,
                0.8955950))
    );
}

float PQ1(float nits)
{
    const float m1 = 0.1593017578125;
    const float m2 = 78.84375;
    const float c1 = 0.8359375;
    const float c2 = 18.8515625;
    const float c3 = 18.6875;

    float L =
        saturate(
            max(nits, 0.0)
            / 10000.0);

    float p =
        pow(
            L,
            m1);

    return pow(
        (c1 + c2 * p)
        / (1.0 + c3 * p),
        m2);
}

float3 PQEncode(float3 nits)
{
    return float3(
        PQ1(nits.r),
        PQ1(nits.g),
        PQ1(nits.b));
}

void main(
    float4 vpos : SV_POSITION,
    float2 uv : TEXCOORD0,
    out float4 col : SV_TARGET)
{
    float3 encoded709 =
        saturate(
            t0.Sample(
                s0,
                uv).rgb);

    float3 linear709 =
        Gamma22Decode(
            encoded709);

    float3 linear2020 =
        max(
            BT709ToBT2020(
                linear709),
            0.0);

    // scRGB / RenoDX reference convention:
    // 1.0 linear == 80 nits.
    const float SDR_WHITE_NITS = 80.0;

    float3 nits2020 =
        linear2020
        * SDR_WHITE_NITS;

    col.rgb =
        saturate(
            PQEncode(
                nits2020));

    col.a = 1.0;
}
'''

shader_path.write_text(
    shader,
    encoding="utf-8",
    newline="\n"
)

print("HOTFIX=P")
print("CORE_COPY=NEUTRAL")
print("SOURCE_TRANSFER=GAMMA_2_2")
print("SDR_WHITE_NITS=80")
print("HIGHLIGHT_EXPANSION=NONE")
print("CONTRAST_OPERATION=NONE")
print("SATURATION_OPERATION=NONE")
print("BT2446A=NONE")
