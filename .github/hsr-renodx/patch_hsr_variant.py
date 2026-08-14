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


MANUAL_NATIVE_FP16 = r'''
extern "C" __declspec(dllexport) const char*
KAIOZEN_HSR_LAB_VARIANT = "KAIOZEN_HSR_44_MANUAL_NATIVE_FP16";

static bool kaiozen_fp16_attempted = false;
static bool kaiozen_ready_logged = false;
static bool kaiozen_f10_was_down = false;


static void KaiozenManualFP16Present(
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

  if (!kaiozen_ready_logged) {
    kaiozen_ready_logged = true;

    reshade::log::message(
        reshade::log::level::info,
        "[Kaiozen] MANUAL_FP16_READY_PRESS_F10_IN_WORLD");
  }

  if (kaiozen_fp16_attempted)
    return;

  const bool f10_down =
      (GetAsyncKeyState(VK_F10) & 0x8000) != 0;

  // Edge-trigger the key.
  // Holding F10 cannot fire more than once.
  if (!f10_down) {
    kaiozen_f10_was_down = false;
    return;
  }

  if (kaiozen_f10_was_down)
    return;

  kaiozen_f10_was_down = true;

  reshade::log::message(
      reshade::log::level::info,
      "[Kaiozen] MANUAL_NATIVE_FP16_BEGIN");

  auto* native_swapchain =
      reinterpret_cast<IDXGISwapChain*>(
          swapchain->get_native());

  if (native_swapchain == nullptr) {
    reshade::log::message(
        reshade::log::level::error,
        "[Kaiozen] MANUAL_NATIVE_FP16_NO_NATIVE_SWAPCHAIN");
    return;
  }

  IDXGISwapChain4* swapchain4 = nullptr;

  HRESULT hr =
      native_swapchain->QueryInterface(
          IID_PPV_ARGS(&swapchain4));

  if (FAILED(hr) || swapchain4 == nullptr) {
    reshade::log::message(
        reshade::log::level::error,
        "[Kaiozen] MANUAL_NATIVE_FP16_QUERY_FAILED");
    return;
  }

  DXGI_SWAP_CHAIN_DESC1 desc = {};

  hr = swapchain4->GetDesc1(&desc);

  if (FAILED(hr)) {
    reshade::log::message(
        reshade::log::level::error,
        "[Kaiozen] MANUAL_NATIVE_FP16_GETDESC_FAILED");

    swapchain4->Release();
    return;
  }

  // We only want HSR's normal Unity RGBA8 swapchain.
  // Do not touch any unexpected secondary swapchain.
  if (desc.Format != DXGI_FORMAT_R8G8B8A8_UNORM) {
    reshade::log::message(
        reshade::log::level::warning,
        "[Kaiozen] MANUAL_NATIVE_FP16_UNEXPECTED_FORMAT");

    swapchain4->Release();
    return;
  }

  if (desc.Width < 800 || desc.Height < 600) {
    reshade::log::message(
        reshade::log::level::warning,
        "[Kaiozen] MANUAL_NATIVE_FP16_SECONDARY_SWAPCHAIN_IGNORED");

    swapchain4->Release();
    return;
  }

  // Set this before ResizeBuffers because ResizeBuffers can
  // synchronously generate additional ReShade callbacks.
  kaiozen_fp16_attempted = true;

  reshade::log::message(
      reshade::log::level::info,
      "[Kaiozen] MANUAL_NATIVE_FP16_RESIZE_BEGIN");

  // IMPORTANT:
  //
  // Direct native DXGI only.
  //
  // NO ResourceUtil.
  // NO mods::swapchain.
  // NO RenoDX ResizeBuffer helper.
  //
  // BufferCount=0 preserves the existing buffer count.
  hr = swapchain4->ResizeBuffers(
      0,
      desc.Width,
      desc.Height,
      DXGI_FORMAT_R16G16B16A16_FLOAT,
      desc.Flags);

  if (FAILED(hr)) {
    reshade::log::message(
        reshade::log::level::error,
        "[Kaiozen] MANUAL_NATIVE_FP16_RESIZE_FAILED");

    swapchain4->Release();
    return;
  }

  reshade::log::message(
      reshade::log::level::info,
      "[Kaiozen] MANUAL_NATIVE_FP16_RESIZE_OK");

  // scRGB / extended sRGB linear.
  hr = swapchain4->SetColorSpace1(
      DXGI_COLOR_SPACE_RGB_FULL_G10_NONE_P709);

  if (FAILED(hr)) {
    reshade::log::message(
        reshade::log::level::error,
        "[Kaiozen] MANUAL_NATIVE_FP16_COLORSPACE_FAILED");

    swapchain4->Release();
    return;
  }

  reshade::log::message(
      reshade::log::level::info,
      "[Kaiozen] MANUAL_NATIVE_FP16_COLORSPACE_OK");

  swapchain4->Release();

  reshade::log::message(
      reshade::log::level::info,
      "[Kaiozen] MANUAL_NATIVE_FP16_RETURNED");
}


BOOL APIENTRY DllMain(
    HMODULE h_module,
    DWORD fdw_reason,
    LPVOID) {

  switch (fdw_reason) {
    case DLL_PROCESS_ATTACH:
      if (!reshade::register_addon(h_module))
        return FALSE;

      // Exact proven-good shader-only renderer.
      renodx::mods::shader::force_pipeline_cloning = true;

      // Manual observation/activation only.
      // Nothing modifies Unity's swapchain during boot.
      reshade::register_event<
          reshade::addon_event::present>(
              KaiozenManualFP16Present);

      break;

    case DLL_PROCESS_DETACH:
      reshade::unregister_event<
          reshade::addon_event::present>(
              KaiozenManualFP16Present);

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

  // INTENTIONALLY ABSENT:
  //
  // renodx::utils::resource::Use(...)
  // renodx::mods::swapchain::Use(...)
  //
  // Startup must remain equivalent to shader-only.

  return TRUE;
}
'''


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
            "late-direct-fp16",
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
    else:
        replacement = MANUAL_NATIVE_FP16

    text = text[:start] + replacement + text[end:]

    path.write_text(
        text,
        encoding="utf-8")

    print(f"PATCHED_VARIANT={args.variant}")
    print(f"FILE={path}")


if __name__ == "__main__":
    main()
