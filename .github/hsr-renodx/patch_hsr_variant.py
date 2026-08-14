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
        raise SystemExit("FAIL: DllMain opening brace not found")

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

    raise SystemExit("FAIL: DllMain closing brace not found")


REGISTER_ONLY = r'''extern "C" __declspec(dllexport) const char* KAIOZEN_HSR_LAB_VARIANT = "KAIOZEN_HSR_44_REGISTER_ONLY";

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
}'''


SHADER_ONLY = r'''extern "C" __declspec(dllexport) const char* KAIOZEN_HSR_LAB_VARIANT = "KAIOZEN_HSR_44_SHADER_ONLY";

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

  renodx::utils::settings::Use(fdw_reason, &settings, &OnPresetOff);
  renodx::mods::shader::Use(fdw_reason, custom_shaders, &shader_injection);

  return TRUE;
}'''


R10_HDR10 = r'''extern "C" __declspec(dllexport) const char* KAIOZEN_HSR_LAB_VARIANT = "KAIOZEN_HSR_44_R10_HDR10_LATE";

BOOL APIENTRY DllMain(HMODULE h_module, DWORD fdw_reason, LPVOID) {
  switch (fdw_reason) {
    case DLL_PROCESS_ATTACH:
      if (!reshade::register_addon(h_module)) return FALSE;

      // Keep the shader replacement path already proven stable on HSR 4.4.
      renodx::mods::shader::force_pipeline_cloning = true;

      // ==========================================================
      // KAIOZEN HSR MAC R10/HDR10 DIAGNOSTIC
      //
      // Inspired by the working Kaiozen ZZZ D3DMetal HDR path.
      //
      // Primary output:
      //   R10G10B10A2_UNORM
      //   HDR10 / ST2084
      //
      // Explicitly avoid the failing HSR upstream FP16/scRGB path.
      // ==========================================================

      renodx::mods::swapchain::SetUseHDR10(true);

      // HOTFIX D:
      // Do NOT replace Unity's swapchain format during creation.
      //
      // Let HSR create and initialize its native RGBA8 swapchain first.
      // After the game reaches its first Present, ask RenoDX to resize
      // that already-initialized swapchain to R10 HDR10.
      renodx::mods::swapchain::use_resize_buffer = true;
      renodx::mods::swapchain::use_resize_buffer_on_present = true;
      renodx::mods::swapchain::use_resize_buffer_on_demand = false;
      renodx::mods::swapchain::use_resize_buffer_on_set_full_screen = false;

      // Remove unrelated variables from this experiment.
      renodx::mods::swapchain::use_resource_cloning = false;
      renodx::mods::swapchain::prevent_full_screen = false;
      renodx::mods::swapchain::force_borderless = false;
      renodx::mods::swapchain::force_screen_tearing = false;

      // Keep color-space switching ON because this is specifically
      // testing the HDR10/ST2084 presentation path.
      renodx::mods::swapchain::set_color_space = true;

      // No proxy shaders.
      // No HSR internal FP16 upgrade targets.
      // No extra resource upgrades.

      break;

    case DLL_PROCESS_DETACH:
      reshade::unregister_addon(h_module);
      break;
  }

  renodx::utils::settings::Use(fdw_reason, &settings, &OnPresetOff);
  renodx::mods::swapchain::Use(fdw_reason, &shader_injection);
  renodx::mods::shader::Use(fdw_reason, custom_shaders, &shader_injection);

  return TRUE;
}'''


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument(
        "--variant",
        required=True,
        choices=[
            "register-only",
            "shader-only",
            "r10-hdr10",
        ],
    )
    args = ap.parse_args()

    path = Path(args.file)
    text = path.read_text(encoding="utf-8")

    start, end = find_function_span(text, "BOOL APIENTRY DllMain")

    if args.variant == "register-only":
        replacement = REGISTER_ONLY
    elif args.variant == "shader-only":
        replacement = SHADER_ONLY
    else:
        replacement = R10_HDR10

    text = text[:start] + replacement + text[end:]
    path.write_text(text, encoding="utf-8")

    print(f"PATCHED_VARIANT={args.variant}")
    print(f"FILE={path}")


if __name__ == "__main__":
    main()
