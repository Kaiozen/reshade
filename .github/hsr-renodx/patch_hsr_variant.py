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
      if (!reshade::register_addon(h_module)) return FALSE;
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
      if (!reshade::register_addon(h_module)) return FALSE;

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


LATE_DIRECT_FP16 = r'''
extern "C" __declspec(dllexport) const char*
KAIOZEN_HSR_LAB_VARIANT = "KAIOZEN_HSR_44_LATE_DIRECT_FP16_RESOURCE_SAFE";

static bool kaiozen_fp16_attempted = false;
static ULONGLONG kaiozen_first_present_ms = 0;

static void KaiozenLateFP16Present(
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

  if (kaiozen_fp16_attempted)
    return;

  const ULONGLONG now = GetTickCount64();

  if (kaiozen_first_present_ms == 0) {
    kaiozen_first_present_ms = now;

    reshade::log::message(
        reshade::log::level::info,
        "[Kaiozen] LATE_FP16_TIMER_STARTED");

    return;
  }

  // Give Unity plenty of time to complete its startup ResizeBuffers
  // sequence before touching the backbuffer.
  if ((now - kaiozen_first_present_ms) < 10000)
    return;

  // Set BEFORE ResizeBuffer because ResizeBuffers itself can generate
  // additional ReShade events.
  kaiozen_fp16_attempted = true;

  reshade::log::message(
      reshade::log::level::info,
      "[Kaiozen] LATE_DIRECT_FP16_BEGIN");

  // IMPORTANT:
  //
  // Do not call renodx::mods::swapchain::Use().
  //
  // Keep Unity's entire startup swapchain lifecycle untouched and
  // perform one direct upgrade only after stable presentation.
  renodx::utils::swapchain::ResizeBuffer(
      swapchain,
      reshade::api::format::r16g16b16a16_float,
      reshade::api::color_space::extended_srgb_linear);

  reshade::log::message(
      reshade::log::level::info,
      "[Kaiozen] LATE_DIRECT_FP16_RETURNED");
}


BOOL APIENTRY DllMain(
    HMODULE h_module,
    DWORD fdw_reason,
    LPVOID) {

  switch (fdw_reason) {
    case DLL_PROCESS_ATTACH:
      if (!reshade::register_addon(h_module))
        return FALSE;

      // Proven-good HSR 4.4 path.
      renodx::mods::shader::force_pipeline_cloning = true;

      // Lightweight observation only.
      // NO RenoDX swapchain module.
      reshade::register_event<reshade::addon_event::present>(
          KaiozenLateFP16Present);

      break;

    case DLL_PROCESS_DETACH:
      reshade::unregister_event<reshade::addon_event::present>(
          KaiozenLateFP16Present);

      reshade::unregister_addon(h_module);
      break;
  }

  // HOTFIX G:
  // ResizeBuffer() internally calls
  // utils::resource::RegisterSwapchainChange().
  // That API requires ResourceUtil's shared tracking state.
  //
  // IMPORTANT:
  // This is ONLY resource bookkeeping.
  // We still do NOT enable mods::swapchain.
  renodx::utils::resource::Use(fdw_reason);

  renodx::utils::settings::Use(
      fdw_reason,
      &settings,
      &OnPresetOff);

  renodx::mods::shader::Use(
      fdw_reason,
      custom_shaders,
      &shader_injection);

  // ABSOLUTELY NO:
  //
  // renodx::mods::swapchain::Use(...)
  //
  // That module is the proven HSR+D3DMetal startup failure boundary.

  return TRUE;
}
'''


def main() -> None:
    ap = argparse.ArgumentParser()

    ap.add_argument("--file", required=True)

    ap.add_argument(
        "--variant",
        required=True,
        choices=[
            "register-only",
            "shader-only",
            "late-direct-fp16",
        ],
    )

    args = ap.parse_args()

    path = Path(args.file)
    text = path.read_text(encoding="utf-8")

    start, end = find_function_span(
        text,
        "BOOL APIENTRY DllMain"
    )

    if args.variant == "register-only":
        replacement = REGISTER_ONLY
    elif args.variant == "shader-only":
        replacement = SHADER_ONLY
    else:
        replacement = LATE_DIRECT_FP16

    text = text[:start] + replacement + text[end:]

    path.write_text(text, encoding="utf-8")

    print(f"PATCHED_VARIANT={args.variant}")
    print(f"FILE={path}")


if __name__ == "__main__":
    main()
