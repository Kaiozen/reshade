#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path


def find_function_span(text: str, signature: str) -> tuple[int, int]:
    start = text.find(signature)
    if start < 0:
        raise SystemExit(f"FAIL: function not found: {signature}")

    brace = text.find("{", start)
    if brace < 0:
        raise SystemExit("FAIL: opening brace not found")

    depth = 0
    i = brace
    in_string = False
    in_char = False
    in_line_comment = False
    in_block_comment = False
    escape = False

    while i < len(text):
        c = text[i]
        n = text[i + 1] if i + 1 < len(text) else ""

        if in_line_comment:
            if c == "\n":
                in_line_comment = False
            i += 1
            continue

        if in_block_comment:
            if c == "*" and n == "/":
                in_block_comment = False
                i += 2
            else:
                i += 1
            continue

        if in_string:
            if escape:
                escape = False
            elif c == "\\":
                escape = True
            elif c == '"':
                in_string = False
            i += 1
            continue

        if in_char:
            if escape:
                escape = False
            elif c == "\\":
                escape = True
            elif c == "'":
                in_char = False
            i += 1
            continue

        if c == "/" and n == "/":
            in_line_comment = True
            i += 2
            continue

        if c == "/" and n == "*":
            in_block_comment = True
            i += 2
            continue

        if c == '"':
            in_string = True
            i += 1
            continue

        if c == "'":
            in_char = True
            i += 1
            continue

        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return start, i + 1

        i += 1

    raise SystemExit("FAIL: closing brace not found")


REGISTER_ONLY = r'''
extern "C" __declspec(dllexport) const char*
KAIOZEN_HSR_LAB_VARIANT = "KAIOZEN_HSR_44_REGISTER_ONLY";

BOOL APIENTRY DllMain(HMODULE h_module, DWORD fdw_reason, LPVOID) {
  switch (fdw_reason) {
    case DLL_PROCESS_ATTACH:
      if (!reshade::register_addon(h_module))
        return FALSE;
      break;

    case DLL_PROCESS_DETACH:
      reshade::unregister_addon(h_module);
      break;
  }

  return TRUE;
}
'''


SHADER_ONLY = r'''
extern "C" __declspec(dllexport) const char*
KAIOZEN_HSR_LAB_VARIANT = "KAIOZEN_HSR_44_SHADER_ONLY";

BOOL APIENTRY DllMain(HMODULE h_module, DWORD fdw_reason, LPVOID) {
  switch (fdw_reason) {
    case DLL_PROCESS_ATTACH:
      if (!reshade::register_addon(h_module))
        return FALSE;

      renodx::mods::shader::force_pipeline_cloning = true;
      break;

    case DLL_PROCESS_DETACH:
      reshade::unregister_addon(h_module);
      break;
  }

  renodx::utils::settings::Use(
      fdw_reason,
      &settings,
      &OnPresetOff);

  renodx::mods::shader::Use(
      fdw_reason,
      custom_shaders,
      &shader_injection);

  return TRUE;
}
'''


EXTERNAL_TRIGGER_FP16 = r'''
extern "C" __declspec(dllexport) const char*
KAIOZEN_HSR_LAB_VARIANT =
    "KAIOZEN_HSR_44_EXTERNAL_TRIGGER_FP16";

static volatile LONG kaiozen_arm_requested = 0;
static volatile LONG kaiozen_fp16_attempted = 0;
static volatile LONG kaiozen_thread_started = 0;


static DWORD WINAPI KaiozenHDRTriggerThread(LPVOID) {
  reshade::log::message(
      reshade::log::level::info,
      "[Kaiozen] EXTERNAL_TRIGGER_THREAD_READY");

  constexpr const wchar_t* trigger_path =
      L"C:\\KAIOZEN_HSR_HDR_ARM.flag";

  while (true) {
    const DWORD attrs =
        GetFileAttributesW(trigger_path);

    if (attrs != INVALID_FILE_ATTRIBUTES
        && (attrs & FILE_ATTRIBUTE_DIRECTORY) == 0) {

      DeleteFileW(trigger_path);

      InterlockedExchange(
          &kaiozen_arm_requested,
          1);

      reshade::log::message(
          reshade::log::level::info,
          "[Kaiozen] EXTERNAL_HDR_ARM_RECEIVED");

      return 0;
    }

    Sleep(100);
  }
}


static void KaiozenStartTriggerThread(
    reshade::api::device* device) {

  (void)device;

  if (InterlockedCompareExchange(
          &kaiozen_thread_started,
          1,
          0) != 0) {
    return;
  }

  HANDLE thread = CreateThread(
      nullptr,
      0,
      KaiozenHDRTriggerThread,
      nullptr,
      0,
      nullptr);

  if (thread == nullptr) {
    InterlockedExchange(
        &kaiozen_thread_started,
        0);

    reshade::log::message(
        reshade::log::level::error,
        "[Kaiozen] EXTERNAL_TRIGGER_THREAD_FAILED");

    return;
  }

  CloseHandle(thread);
}


static void KaiozenExternalHDRPresent(
    reshade::api::command_queue* queue,
    reshade::api::swapchain* swapchain,
    const reshade::api::rect* source_rect,
    const reshade::api::rect* dest_rect,
    uint32_t dirty_rect_count,
    const reshade::api::rect* dirty_rects) {

  (void)queue;
  (void)source_rect;
  (void)dest_rect;
  (void)dirty_rect_count;
  (void)dirty_rects;

  // During normal play this is the ONLY operation performed:
  // one atomic read and return.
  //
  // NO GetAsyncKeyState.
  // NO filesystem access.
  // NO timer.
  // NO swapchain modification.
  if (InterlockedCompareExchange(
          &kaiozen_arm_requested,
          0,
          0) == 0) {
    return;
  }

  if (InterlockedCompareExchange(
          &kaiozen_fp16_attempted,
          1,
          0) != 0) {
    return;
  }

  reshade::log::message(
      reshade::log::level::info,
      "[Kaiozen] EXTERNAL_NATIVE_FP16_BEGIN");

  auto* native_swapchain =
      reinterpret_cast<IDXGISwapChain*>(
          swapchain->get_native());

  if (native_swapchain == nullptr) {
    reshade::log::message(
        reshade::log::level::error,
        "[Kaiozen] EXTERNAL_NATIVE_FP16_NO_SWAPCHAIN");
    return;
  }

  IDXGISwapChain4* swapchain4 = nullptr;

  HRESULT hr =
      native_swapchain->QueryInterface(
          IID_PPV_ARGS(&swapchain4));

  if (FAILED(hr) || swapchain4 == nullptr) {
    reshade::log::message(
        reshade::log::level::error,
        "[Kaiozen] EXTERNAL_NATIVE_FP16_QUERY_FAILED");
    return;
  }

  DXGI_SWAP_CHAIN_DESC1 desc = {};

  hr = swapchain4->GetDesc1(&desc);

  if (FAILED(hr)) {
    reshade::log::message(
        reshade::log::level::error,
        "[Kaiozen] EXTERNAL_NATIVE_FP16_GETDESC_FAILED");

    swapchain4->Release();
    return;
  }

  if (desc.Format != DXGI_FORMAT_R8G8B8A8_UNORM
      || desc.Width < 800
      || desc.Height < 600) {

    reshade::log::message(
        reshade::log::level::warning,
        "[Kaiozen] EXTERNAL_NATIVE_FP16_WRONG_SWAPCHAIN");

    InterlockedExchange(
        &kaiozen_fp16_attempted,
        0);

    swapchain4->Release();
    return;
  }

  reshade::log::message(
      reshade::log::level::info,
      "[Kaiozen] EXTERNAL_NATIVE_FP16_RESIZE_BEGIN");

  hr = swapchain4->ResizeBuffers(
      0,
      desc.Width,
      desc.Height,
      DXGI_FORMAT_R16G16B16A16_FLOAT,
      desc.Flags);

  if (FAILED(hr)) {
    reshade::log::message(
        reshade::log::level::error,
        "[Kaiozen] EXTERNAL_NATIVE_FP16_RESIZE_FAILED");

    swapchain4->Release();
    return;
  }

  reshade::log::message(
      reshade::log::level::info,
      "[Kaiozen] EXTERNAL_NATIVE_FP16_RESIZE_OK");

  hr = swapchain4->SetColorSpace1(
      DXGI_COLOR_SPACE_RGB_FULL_G10_NONE_P709);

  if (FAILED(hr)) {
    reshade::log::message(
        reshade::log::level::error,
        "[Kaiozen] EXTERNAL_NATIVE_FP16_COLORSPACE_FAILED");

    swapchain4->Release();
    return;
  }

  reshade::log::message(
      reshade::log::level::info,
      "[Kaiozen] EXTERNAL_NATIVE_FP16_COLORSPACE_OK");

  swapchain4->Release();

  reshade::log::message(
      reshade::log::level::info,
      "[Kaiozen] EXTERNAL_NATIVE_FP16_RETURNED");
}


BOOL APIENTRY DllMain(
    HMODULE h_module,
    DWORD fdw_reason,
    LPVOID) {

  switch (fdw_reason) {
    case DLL_PROCESS_ATTACH:
      if (!reshade::register_addon(h_module))
        return FALSE;

      // Proven-good HSR renderer.
      renodx::mods::shader::force_pipeline_cloning = true;

      // Start the trigger waiter after D3D device initialization.
      reshade::register_event<
          reshade::addon_event::init_device>(
              KaiozenStartTriggerThread);

      // Present contains only an atomic check until explicitly armed.
      reshade::register_event<
          reshade::addon_event::present>(
              KaiozenExternalHDRPresent);

      break;

    case DLL_PROCESS_DETACH:
      reshade::unregister_event<
          reshade::addon_event::present>(
              KaiozenExternalHDRPresent);

      reshade::unregister_event<
          reshade::addon_event::init_device>(
              KaiozenStartTriggerThread);

      reshade::unregister_addon(h_module);
      break;
  }

  renodx::utils::settings::Use(
      fdw_reason,
      &settings,
      &OnPresetOff);

  renodx::mods::shader::Use(
      fdw_reason,
      custom_shaders,
      &shader_injection);

  // INTENTIONALLY NEVER USED:
  //
  // renodx::utils::resource::Use(...)
  // renodx::mods::swapchain::Use(...)
  // GetAsyncKeyState(...)
  //
  // Unity startup/presentation remains shader-only until armed.

  return TRUE;
}
'''



DIRECT_RGBA8_PQ = r"""
#include <dxgi1_6.h>

extern "C" __declspec(dllexport) const char*
KAIOZEN_HSR_LAB_VARIANT =
    "KAIOZEN_HSR_44_RGBA8_PQ_HOTFIX_L";

static void KaiozenApplyPQHDR(
    reshade::api::swapchain* swapchain,
    bool resize) {

  if (swapchain == nullptr)
    return;

  auto* native_swapchain =
      reinterpret_cast<IDXGISwapChain*>(
          swapchain->get_native());

  if (native_swapchain == nullptr)
    return;

  IDXGISwapChain3* swapchain3 = nullptr;

  HRESULT hr =
      native_swapchain->QueryInterface(
          IID_PPV_ARGS(&swapchain3));

  if (FAILED(hr) || swapchain3 == nullptr)
    return;

  DXGI_SWAP_CHAIN_DESC1 desc = {};

  hr = swapchain3->GetDesc1(&desc);

  if (FAILED(hr)) {
    swapchain3->Release();
    return;
  }

  if (desc.Format != DXGI_FORMAT_R8G8B8A8_UNORM
      || desc.Width < 800
      || desc.Height < 600) {
    swapchain3->Release();
    return;
  }

  reshade::log::message(
      reshade::log::level::info,
      resize
          ? "[Kaiozen] J_PQ_REAPPLY_AFTER_RESIZE"
          : "[Kaiozen] J_PQ_INITIAL_SWAPCHAIN");

  reshade::log::message(
      reshade::log::level::info,
      "[Kaiozen] J_FORMAT_28_CONFIRMED");

  constexpr DXGI_COLOR_SPACE_TYPE color_space =
      DXGI_COLOR_SPACE_RGB_FULL_G2084_NONE_P2020;

  UINT support = 0;

  hr = swapchain3->CheckColorSpaceSupport(
      color_space,
      &support);

  if (FAILED(hr)
      || (support
          & DXGI_SWAP_CHAIN_COLOR_SPACE_SUPPORT_FLAG_PRESENT)
             == 0) {

    reshade::log::message(
        reshade::log::level::error,
        "[Kaiozen] J_PQ_COLORSPACE_UNSUPPORTED");

    swapchain3->Release();
    return;
  }

  reshade::log::message(
      reshade::log::level::info,
      "[Kaiozen] J_PQ_COLORSPACE_SUPPORTED");

  hr = swapchain3->SetColorSpace1(
      color_space);

  if (FAILED(hr)) {
    reshade::log::message(
        reshade::log::level::error,
        "[Kaiozen] J_SETCOLORSPACE_FAILED");

    swapchain3->Release();
    return;
  }

  reshade::log::message(
      reshade::log::level::info,
      "[Kaiozen] J_SETCOLORSPACE_OK");

  IDXGISwapChain4* swapchain4 = nullptr;

  hr = native_swapchain->QueryInterface(
      IID_PPV_ARGS(&swapchain4));

  if (SUCCEEDED(hr) && swapchain4 != nullptr) {

    DXGI_HDR_METADATA_HDR10 metadata = {};

    metadata.RedPrimary[0] = 34000;
    metadata.RedPrimary[1] = 16000;

    metadata.GreenPrimary[0] = 13250;
    metadata.GreenPrimary[1] = 34500;

    metadata.BluePrimary[0] = 7500;
    metadata.BluePrimary[1] = 3000;

    metadata.WhitePoint[0] = 15635;
    metadata.WhitePoint[1] = 16450;

    metadata.MaxMasteringLuminance =
        1000u * 10000u;

    metadata.MinMasteringLuminance = 0;

    metadata.MaxContentLightLevel = 1000;
    metadata.MaxFrameAverageLightLevel = 400;

    hr = swapchain4->SetHDRMetaData(
        DXGI_HDR_METADATA_TYPE_HDR10,
        sizeof(metadata),
        &metadata);

    reshade::log::message(
        SUCCEEDED(hr)
            ? reshade::log::level::info
            : reshade::log::level::warning,
        SUCCEEDED(hr)
            ? "[Kaiozen] J_HDR_METADATA_OK"
            : "[Kaiozen] J_HDR_METADATA_FAILED");

    swapchain4->Release();
  }

  swapchain3->Release();

  reshade::log::message(
      reshade::log::level::info,
      "[Kaiozen] J_RGBA8_PQ_READY");
}


BOOL APIENTRY DllMain(
    HMODULE h_module,
    DWORD fdw_reason,
    LPVOID) {

  switch (fdw_reason) {

    case DLL_PROCESS_ATTACH:

      if (!reshade::register_addon(h_module))
        return FALSE;

      renodx::mods::shader::force_pipeline_cloning =
          true;

      reshade::register_event<
          reshade::addon_event::init_swapchain>(
              KaiozenApplyPQHDR);

      break;


    case DLL_PROCESS_DETACH:

      reshade::unregister_event<
          reshade::addon_event::init_swapchain>(
              KaiozenApplyPQHDR);

      reshade::unregister_addon(h_module);

      break;
  }

  renodx::utils::settings::Use(
      fdw_reason,
      &settings,
      &OnPresetOff);

  renodx::mods::shader::Use(
      fdw_reason,
      custom_shaders,
      &shader_injection);

  return TRUE;
}
"""


def patch_pq_transport(game_dir: Path) -> None:
    common_path = game_dir / "common.hlsl"
    common = common_path.read_text(encoding="utf-8")

    if "FinalizeOutputPQ8" not in common:
        _, end = find_function_span(
            common,
            "float3 FinalizeOutput(float3 color)"
        )

        helper = r"""
float3 FinalizeOutputPQ8(float3 color) {
  //
  // KAIOZEN HOTFIX L
  //
  // Goals:
  // 1. Preserve RenoDX diffuse/reference white.
  // 2. Preserve RenoDX UI brightness.
  // 3. Expand only genuine scene highlights into HDR headroom.
  // 4. Correct excessive chroma without changing luminance.
  // 5. Deliver BT.2020 + ST.2084 PQ.
  //

  color = max(color, 0.f);
  color = min(color, 16.f);

  // HSR RenoDX output is gamma-domain at this point.
  float3 linear709 =
      renodx::color::gamma::DecodeSafe(
          color,
          2.2f);

  //
  // PostToneMapScale already applies:
  //
  // GameNits / UINits
  //
  // Therefore multiplying by UI nits restores
  // absolute RenoDX scene luminance.
  //
  float3 nits709 =
      linear709
      * injectedData.toneMapUINits;

  float referenceWhite =
      max(
          injectedData.toneMapGameNits,
          1.f);

  float peakNits =
      max(
          injectedData.toneMapPeakNits,
          referenceWhite);

  nits709 =
      max(
          nits709,
          0.f);

  //
  // Linear-light BT.709 luminance.
  //
  float sceneY =
      dot(
          nits709,
          float3(
              0.2126729f,
              0.7151522f,
              0.0721750f));

  float targetY = sceneY;

  //
  // HDR HIGHLIGHT EXPANSION
  //
  // <= reference white:
  //     completely untouched.
  //
  // > reference white:
  //     expand progressively into the available
  //     203 -> 1000 nit headroom.
  //
  // This preserves normal scene brightness while
  // making lights/reflections/effects genuinely HDR.
  //
  if (sceneY > referenceWhite) {
    float sourceSpan =
        max(
            peakNits - referenceWhite,
            1.f);

    float normalizedHighlight =
        saturate(
            (sceneY - referenceWhite)
            / sourceSpan);

    //
    // Square-root shoulder is intentionally expansive:
    // small HDR excursions become visibly separated
    // from diffuse white, while remaining monotonic
    // and bounded at peak.
    //
    float expandedHighlight =
        sqrt(normalizedHighlight);

    targetY =
        referenceWhite
        + expandedHighlight
        * (peakNits - referenceWhite);

    targetY =
        min(
            targetY,
            peakNits);
  }

  //
  // Scale RGB by ONE scalar.
  //
  // This changes luminance without changing hue/chromaticity.
  //
  float luminanceScale =
      targetY
      / max(sceneY, 0.0001f);

  float3 hdr709 =
      nits709
      * luminanceScale;


  // ----------------------------------------------------------
  // LUMA-PRESERVING CHROMA COMPRESSION
  // ----------------------------------------------------------
  //
  // The previous fixed 90% saturation reduction was too weak.
  //
  // This version adapts:
  //   low-chroma pixels -> almost unchanged
  //   highly saturated pixels -> stronger correction
  //
  // Both endpoints have the SAME luminance targetY,
  // so this does not dim the HDR image.
  //

  float3 neutral =
      float3(
          targetY,
          targetY,
          targetY);

  float3 chromaVector =
      hdr709 - neutral;

  float chromaMagnitude =
      max(
          max(
              abs(chromaVector.r),
              abs(chromaVector.g)),
          abs(chromaVector.b));

  float normalizedChroma =
      saturate(
          chromaMagnitude
          / max(targetY, 1.f));

  //
  // Neutral/natural colors: 94%
  // Very saturated colors:    76%
  //
  float chromaScale =
      lerp(
          0.94f,
          0.76f,
          normalizedChroma);

  hdr709 =
      neutral
      + chromaVector
      * chromaScale;

  hdr709 =
      max(
          hdr709,
          0.f);


  // ----------------------------------------------------------
  // BT.709 -> BT.2020
  // ----------------------------------------------------------

  float3 hdr2020 =
      renodx::color::bt2020::from::BT709(
          hdr709);

  hdr2020 =
      max(
          hdr2020,
          0.f);

  //
  // Bound all channels to RenoDX peak.
  //
  hdr2020 =
      min(
          hdr2020,
          peakNits);


  // ----------------------------------------------------------
  // ABSOLUTE NITS -> ST.2084 PQ
  // ----------------------------------------------------------

  float3 pq =
      renodx::color::pq::EncodeSafe(
          hdr2020,
          1.f);

  return saturate(pq);
}
"""

        common = (
            common[:end]
            + "\n\n"
            + helper.strip()
            + "\n"
            + common[end:]
        )

        common_path.write_text(
            common,
            encoding="utf-8"
        )

    shader_files = [
        "uberpost0_0x93121324.ps_4_0.hlsl",
        "uberpost1_0x318A9DF6.ps_4_0.hlsl",
        "uberpost2_0xB2079998.ps_4_0.hlsl",
        "uberpost3_0x1AC9F8BC.ps_4_0.hlsl",
    ]

    anchor = "  o0.xyz = PostToneMapScale(o0.xyz);"

    replacement = (
        anchor
        + "\n\n"
        + "  // HOTFIX J: upstream RenoDX final output -> BT.2020 PQ.\n"
        + "  o0.rgb = saturate(FinalizeOutputPQ8(o0.rgb));"
    )

    for name in shader_files:
        path = game_dir / name
        text = path.read_text(encoding="utf-8")

        if "FinalizeOutputPQ8(o0.rgb)" in text:
            print(f"PQ_SHADER_ALREADY_PATCHED={name}")
            continue

        count = text.count(anchor)

        if count != 1:
            raise SystemExit(
                f"FAIL: {name}: PostToneMapScale anchor count={count}"
            )

        text = text.replace(
            anchor,
            replacement,
            1
        )

        path.write_text(
            text,
            encoding="utf-8"
        )

        print(f"PQ_SHADER_PATCHED={name}")

def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--file",
        required=True)

    parser.add_argument(
        "--variant",
        required=True,
        choices=[
            "register-only",
            "shader-only",
            "external-trigger-fp16",
            "direct-rgba8-pq",
        ])

    args = parser.parse_args()

    path = Path(args.file)
    text = path.read_text(encoding="utf-8")

    start, end = find_function_span(
        text,
        "BOOL APIENTRY DllMain")

    if args.variant == "register-only":
        replacement = REGISTER_ONLY

    elif args.variant == "shader-only":
        replacement = SHADER_ONLY

    elif args.variant == "external-trigger-fp16":
        replacement = EXTERNAL_TRIGGER_FP16

    else:
        replacement = DIRECT_RGBA8_PQ

    text = text[:start] + replacement + text[end:]

    path.write_text(
        text,
        encoding="utf-8")

    if args.variant == "direct-rgba8-pq":
        patch_pq_transport(path.parent)

    print(f"PATCHED_VARIANT={args.variant}")
    print(f"FILE={path}")


if __name__ == "__main__":
    main()
