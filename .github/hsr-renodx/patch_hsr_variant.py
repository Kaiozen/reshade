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
        replacement = EXTERNAL_TRIGGER_FP16

    text = text[:start] + replacement + text[end:]

    path.write_text(
        text,
        encoding="utf-8")

    print(f"PATCHED_VARIANT={args.variant}")
    print(f"FILE={path}")


if __name__ == "__main__":
    main()
