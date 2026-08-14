#!/usr/bin/env python3
from pathlib import Path
import sys


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


path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")

include_anchor = "#include <include/reshade.hpp>"
if "#include <dxgi1_6.h>" not in text:
    if text.count(include_anchor) != 1:
        raise SystemExit("FAIL: ReShade include anchor invalid")
    text = text.replace(
        include_anchor,
        include_anchor + "\n#include <dxgi1_6.h>",
        1,
    )

replacement = r'''extern "C" __declspec(dllexport) const char*
KAIOZEN_HSR_LAB_VARIANT =
    "KAIOZEN_HSR_44_FINALFX_HDR_M";

static void KaiozenApplyFinalFXHDR10(
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

  HRESULT hr = native_swapchain->QueryInterface(
      IID_PPV_ARGS(&swapchain3));

  if (FAILED(hr) || swapchain3 == nullptr)
    return;

  DXGI_SWAP_CHAIN_DESC1 desc = {};
  hr = swapchain3->GetDesc1(&desc);

  if (FAILED(hr)) {
    swapchain3->Release();
    return;
  }

  // Only touch HSR's real primary Unity swap chain.
  if (desc.Format != DXGI_FORMAT_R8G8B8A8_UNORM
      || desc.Width < 800
      || desc.Height < 600) {
    swapchain3->Release();
    return;
  }

  constexpr DXGI_COLOR_SPACE_TYPE color_space =
      DXGI_COLOR_SPACE_RGB_FULL_G2084_NONE_P2020;

  UINT support = 0;
  hr = swapchain3->CheckColorSpaceSupport(
      color_space,
      &support);

  if (FAILED(hr)
      || (support & DXGI_SWAP_CHAIN_COLOR_SPACE_SUPPORT_FLAG_PRESENT) == 0) {
    reshade::log::message(
        reshade::log::level::error,
        "[Kaiozen] M_HDR10_COLORSPACE_UNSUPPORTED");
    swapchain3->Release();
    return;
  }

  hr = swapchain3->SetColorSpace1(color_space);

  if (FAILED(hr)) {
    reshade::log::message(
        reshade::log::level::error,
        "[Kaiozen] M_SETCOLORSPACE_FAILED");
    swapchain3->Release();
    return;
  }

  IDXGISwapChain4* swapchain4 = nullptr;
  hr = native_swapchain->QueryInterface(
      IID_PPV_ARGS(&swapchain4));

  if (SUCCEEDED(hr) && swapchain4 != nullptr) {
    DXGI_HDR_METADATA_HDR10 metadata = {};

    // Rec.2020 primaries and D65 white point in DXGI HDR10 units.
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

    const HRESULT metadata_hr = swapchain4->SetHDRMetaData(
        DXGI_HDR_METADATA_TYPE_HDR10,
        sizeof(metadata),
        &metadata);

    reshade::log::message(
        SUCCEEDED(metadata_hr)
            ? reshade::log::level::info
            : reshade::log::level::warning,
        SUCCEEDED(metadata_hr)
            ? "[Kaiozen] M_HDR_METADATA_OK"
            : "[Kaiozen] M_HDR_METADATA_FAILED");

    swapchain4->Release();
  }

  reshade::log::message(
      reshade::log::level::info,
      resize
          ? "[Kaiozen] M_FINALFX_HDR10_REAPPLIED"
          : "[Kaiozen] M_FINALFX_HDR10_READY");

  reshade::log::message(
      reshade::log::level::info,
      "[Kaiozen] M_EARLY_PQ=NO FINAL_FRAME_EFFECT=YES");

  swapchain3->Release();
}


BOOL APIENTRY DllMain(
    HMODULE h_module,
    DWORD fdw_reason,
    LPVOID) {

  switch (fdw_reason) {
    case DLL_PROCESS_ATTACH:
      if (!reshade::register_addon(h_module))
        return FALSE;

      // Keep the renderer on the repeatedly proven shader-only base.
      renodx::mods::shader::force_pipeline_cloning = true;

      // Lifecycle only. No per-frame callback and no swapchain mutation.
      reshade::register_event<
          reshade::addon_event::init_swapchain>(
              KaiozenApplyFinalFXHDR10);
      break;

    case DLL_PROCESS_DETACH:
      reshade::unregister_event<
          reshade::addon_event::init_swapchain>(
              KaiozenApplyFinalFXHDR10);

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
}'''

start, end = find_function_span(text, "BOOL APIENTRY DllMain")
text = text[:start] + replacement + text[end:]

path.write_text(text, encoding="utf-8")

print("PATCHED=HOTFIX_M_FINALFX")
print("EARLY_PQ=NO")
print("PRESENT_CALLBACK=NO")
print("THREAD=NO")
print("TIMER=NO")
print("MODS_SWAPCHAIN=NO")
print("RESOURCE_UTIL=NO")
