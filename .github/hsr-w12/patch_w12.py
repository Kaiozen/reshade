#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 7:
    raise SystemExit(
        "usage: patch_w12.py <addon.cpp> <common.hlsl> "
        "<uber0> <uber1> <uber2> <uber3>"
    )

addon_path = Path(sys.argv[1])
common_path = Path(sys.argv[2])
shader_paths = [Path(x) for x in sys.argv[3:7]]

addon = addon_path.read_text(encoding="utf-8")
common = common_path.read_text(encoding="utf-8")

for token in [
    "KAIOZEN_HSR_44_W10_COMPILE_ONLY_FULL_HDR",
    "force_pipeline_cloning = false;",
    "RUNTIME_FALLBACK=OFF",
]:
    if token not in addon:
        raise SystemExit(f"FAIL: W12 prerequisite missing: {token}")

include_anchor = '#include <include/reshade.hpp>\n'
if addon.count(include_anchor) != 1:
    raise SystemExit("FAIL: W12 DXGI include anchor")
addon = addon.replace(
    include_anchor,
    include_anchor + "#include <dxgi1_6.h>\n",
    1,
)

namespace_end = "}  // namespace\n\nextern \"C\""
if addon.count(namespace_end) != 1:
    raise SystemExit("FAIL: W12 namespace anchor")

hdr_helper = r'''
void KaiozenW12InitSwapchain(
    reshade::api::swapchain* swapchain,
    bool resize) {
  if (swapchain == nullptr) return;

  auto* native_swapchain =
      reinterpret_cast<IDXGISwapChain*>(swapchain->get_native());
  if (native_swapchain == nullptr) return;

  IDXGISwapChain3* swapchain3 = nullptr;
  HRESULT hr = native_swapchain->QueryInterface(
      IID_PPV_ARGS(&swapchain3));
  if (FAILED(hr) || swapchain3 == nullptr) {
    reshade::log::message(
        reshade::log::level::error,
        "[Kaiozen] W12_HDR10_SWAPCHAIN=FAIL NO_SWAPCHAIN3");
    return;
  }

  DXGI_SWAP_CHAIN_DESC1 desc = {};
  hr = swapchain3->GetDesc1(&desc);
  if (FAILED(hr) ||
      desc.Format != DXGI_FORMAT_R8G8B8A8_UNORM ||
      desc.Width < 1000 ||
      desc.Height < 700) {
    swapchain3->Release();
    return;
  }

  constexpr DXGI_COLOR_SPACE_TYPE kHDR10 =
      DXGI_COLOR_SPACE_RGB_FULL_G2084_NONE_P2020;

  UINT support = 0;
  const HRESULT support_hr =
      swapchain3->CheckColorSpaceSupport(kHDR10, &support);

  if (FAILED(support_hr) ||
      (support &
       DXGI_SWAP_CHAIN_COLOR_SPACE_SUPPORT_FLAG_PRESENT) == 0) {
    reshade::log::message(
        reshade::log::level::error,
        "[Kaiozen] W12_HDR10_SWAPCHAIN=FAIL "
        "COLORSPACE_UNSUPPORTED hr=0x%08X support=0x%08X",
        static_cast<unsigned int>(support_hr),
        support);
    swapchain3->Release();
    return;
  }

  const HRESULT color_hr =
      swapchain3->SetColorSpace1(kHDR10);

  HRESULT metadata_hr = E_NOINTERFACE;
  IDXGISwapChain4* swapchain4 = nullptr;

  if (SUCCEEDED(native_swapchain->QueryInterface(
          IID_PPV_ARGS(&swapchain4))) &&
      swapchain4 != nullptr) {
    DXGI_HDR_METADATA_HDR10 metadata = {};
    metadata.RedPrimary[0] = 34000;
    metadata.RedPrimary[1] = 16000;
    metadata.GreenPrimary[0] = 13250;
    metadata.GreenPrimary[1] = 34500;
    metadata.BluePrimary[0] = 7500;
    metadata.BluePrimary[1] = 3000;
    metadata.WhitePoint[0] = 15635;
    metadata.WhitePoint[1] = 16450;
    metadata.MaxMasteringLuminance = 1000u * 10000u;
    metadata.MinMasteringLuminance = 0;
    metadata.MaxContentLightLevel = 1000;
    metadata.MaxFrameAverageLightLevel = 400;

    metadata_hr = swapchain4->SetHDRMetaData(
        DXGI_HDR_METADATA_TYPE_HDR10,
        sizeof(metadata),
        &metadata);

    swapchain4->Release();
  }

  reshade::log::message(
      SUCCEEDED(color_hr) && SUCCEEDED(metadata_hr)
          ? reshade::log::level::info
          : reshade::log::level::error,
      SUCCEEDED(color_hr) && SUCCEEDED(metadata_hr)
          ? "[Kaiozen] W12_HDR10_SWAPCHAIN=ACTIVE "
            "EVENT=INIT_SWAPCHAIN PRESENT_CALLBACK=NO "
            "RESHADE_FINAL_COPY=NO "
            "color_hr=0x%08X metadata_hr=0x%08X resize=%u"
          : "[Kaiozen] W12_HDR10_SWAPCHAIN=FAIL "
            "color_hr=0x%08X metadata_hr=0x%08X resize=%u",
      static_cast<unsigned int>(color_hr),
      static_cast<unsigned int>(metadata_hr),
      resize ? 1u : 0u);

  swapchain3->Release();
}

'''
addon = addon.replace(
    namespace_end,
    hdr_helper + namespace_end,
    1,
)

register_anchor = '      if (!reshade::register_addon(h_module)) return FALSE;\n'
if addon.count(register_anchor) != 1:
    raise SystemExit("FAIL: W12 register addon anchor")
addon = addon.replace(
    register_anchor,
    register_anchor
    + '      reshade::register_event<reshade::addon_event::init_swapchain>('
      'KaiozenW12InitSwapchain);\n',
    1,
)

detach_anchor = (
    "    case DLL_PROCESS_DETACH:\n"
    "      reshade::unregister_addon(h_module);\n"
)
if addon.count(detach_anchor) != 1:
    raise SystemExit("FAIL: W12 detach anchor")
addon = addon.replace(
    detach_anchor,
    "    case DLL_PROCESS_DETACH:\n"
    "      reshade::unregister_event<reshade::addon_event::init_swapchain>("
    "KaiozenW12InitSwapchain);\n"
    "      reshade::unregister_addon(h_module);\n",
    1,
)

addon = addon.replace(
    "KAIOZEN_HSR_44_W10_COMPILE_ONLY_FULL_HDR",
    "KAIOZEN_HSR_44_W12_SHADER_NATIVE_PQ",
    1,
)

w10_log = (
    '"[Kaiozen] W10_COMPILE_ONLY_FULL_HDR=ACTIVE '
    'FORCE_PIPELINE_CLONING=OFF RUNTIME_FALLBACK=OFF '
    'ALL_5_HSR_SHADERS=YES W5=OFF"'
)
if addon.count(w10_log) != 1:
    raise SystemExit("FAIL: W12 W10 log anchor")
addon = addon.replace(
    w10_log,
    '"[Kaiozen] W12_SHADER_NATIVE_PQ=ACTIVE '
    'FORCE_PIPELINE_CLONING=OFF RUNTIME_FALLBACK=OFF '
    'ALL_5_HSR_SHADERS=YES FINAL_PQ_SHADERS=4 '
    'RESHADE_FINAL_COPY=OFF PRESENT_CALLBACK=NO W5=OFF"',
    1,
)

common_anchor = '''float3 PostToneMapScale(float3 color) {
  color = renodx::color::gamma::DecodeSafe(color, 2.2f);
  color *= injectedData.toneMapGameNits / injectedData.toneMapUINits;
  color = renodx::color::gamma::EncodeSafe(color, 2.2f);

  return color;
}
'''
if common.count(common_anchor) != 1:
    raise SystemExit("FAIL: W12 common PostToneMapScale anchor")

pq_helper = r'''
// W12: reproduce the proven W3 RGBA8 PQ carrier directly in the game's
// four final UberPost replacement shaders. This removes the custom ReShade
// final-copy draw and its resolved back-buffer resource path.
float3 KaiozenW12SRGBDecode(float3 v) {
  v = saturate(v);
  float3 lo = v / 12.92f;
  float3 hi = pow((v + 0.055f) / 1.055f, 2.4f);
  return lerp(lo, hi, step(0.04045f, v));
}

float3 KaiozenW12BT709ToBT2020(float3 c) {
  return float3(
      dot(c, float3(0.6274040f, 0.3292820f, 0.0433136f)),
      dot(c, float3(0.0690970f, 0.9195400f, 0.0113612f)),
      dot(c, float3(0.0163916f, 0.0880132f, 0.8955950f)));
}

float KaiozenW12PQ1(float nits) {
  const float m1 = 2610.0f / 16384.0f;
  const float m2 = 2523.0f / 32.0f;
  const float c1 = 3424.0f / 4096.0f;
  const float c2 = 2413.0f / 128.0f;
  const float c3 = 2392.0f / 128.0f;

  float L = saturate(max(nits, 0.0f) / 10000.0f);
  float p = pow(L, m1);
  return pow((c1 + c2 * p) / (1.0f + c3 * p), m2);
}

float3 KaiozenW12PQEncode(float3 nits) {
  return float3(
      KaiozenW12PQ1(nits.r),
      KaiozenW12PQ1(nits.g),
      KaiozenW12PQ1(nits.b));
}

float3 KaiozenW12PQCarrier(float3 encoded709) {
  float3 linear709 = KaiozenW12SRGBDecode(encoded709);

  const float SATURATION_RETENTION = 1.06f;
  const float luma709 =
      dot(linear709, float3(0.2126f, 0.7152f, 0.0722f));
  linear709 =
      lerp(luma709.xxx, linear709, SATURATION_RETENTION);

  float3 linear2020 =
      max(KaiozenW12BT709ToBT2020(linear709), 0.0f);

  const float SDR_WHITE_NITS = 400.0f;
  float3 nits2020 = linear2020 * SDR_WHITE_NITS;

  const float peak =
      max(max(linear2020.r, linear2020.g), linear2020.b);
  const float shine = smoothstep(0.55f, 1.00f, peak);
  nits2020 *= 1.0f + 0.06f * shine;

  return saturate(KaiozenW12PQEncode(nits2020));
}
'''

common = common.replace(
    common_anchor,
    common_anchor + pq_helper,
    1,
)

tail = (
    "  o0.rgb = renodx::color::srgb::EncodeSafe(r0.rgb);\n"
    "  o0.xyz = PostToneMapScale(o0.xyz);\n"
)
replacement = (
    tail
    + "  o0.rgb = KaiozenW12PQCarrier(o0.rgb);"
      "  // KAIOZEN_W12_FINAL_PQ\n"
)

for sp in shader_paths:
    s = sp.read_text(encoding="utf-8")
    if s.count(tail) != 1:
        raise SystemExit(
            f"FAIL: W12 final-output tail count={s.count(tail)} in {sp}"
        )
    s = s.replace(tail, replacement, 1)
    sp.write_text(s, encoding="utf-8", newline="\n")

addon_path.write_text(addon, encoding="utf-8", newline="\n")
common_path.write_text(common, encoding="utf-8", newline="\n")

print("W12_PATCH=PASS")
print("SHADER_NATIVE_PQ=YES")
print("FINAL_PQ_SHADERS=4")
print("RESHADE_FINAL_COPY=OFF")
print("PRESENT_CALLBACK=NO")
print("HDR_TAG_EVENT=INIT_SWAPCHAIN")
print("W3_PQ_MATH_PRESERVED=YES")
