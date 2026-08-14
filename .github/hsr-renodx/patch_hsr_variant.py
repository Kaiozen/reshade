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
  renodx::mods::shader::Use(
      fdw_reason,
      custom_shaders,
      &shader_injection);

  return TRUE;
}'''


PROXY_SCRGB = r'''extern "C" __declspec(dllexport) const char* KAIOZEN_HSR_LAB_VARIANT = "KAIOZEN_HSR_44_PROXY_SCRGB";

BOOL APIENTRY DllMain(HMODULE h_module, DWORD fdw_reason, LPVOID) {
  switch (fdw_reason) {
    case DLL_PROCESS_ATTACH:
      if (!reshade::register_addon(h_module)) return FALSE;

      // ==========================================================
      // KAIOZEN HSR MAC DISPLAY-PROXY HDR
      //
      // Keep HSR / Unity primary presentation untouched.
      //
      // PRIMARY:
      //   R8G8B8A8_UNORM
      //   normal Unity / D3DMetal path
      //
      // HDR OUTPUT:
      //   separate RenoDX display proxy
      //   R16G16B16A16_FLOAT
      //   extended_sRGB_linear / scRGB
      // ==========================================================

      // Already proven stable in shader-only.
      renodx::mods::shader::force_pipeline_cloning = true;

      // HSR's existing final proxy shader outputs linear scRGB.
      // Explicitly select FP16/scRGB, NOT HDR10/R10.
      renodx::mods::swapchain::SetUseHDR10(false);

      // This is the critical architectural change.
      //
      // Do not make HSR's own Unity swapchain the HDR swapchain.
      // Make RenoDX create/use a separate presentation device.
      renodx::mods::swapchain::use_device_proxy = true;

      // The proxy owns HDR color space.
      // Do not change color space on HSR's own swapchain.
      renodx::mods::swapchain::set_color_space = false;

      // Proxy/shared-resource transport.
      renodx::mods::swapchain::use_resource_cloning = true;

      // HSR's own upstream final-output proxy shaders.
      renodx::mods::swapchain::swap_chain_proxy_vertex_shader =
          __swap_chain_proxy_vertex_shader;

      renodx::mods::swapchain::swap_chain_proxy_pixel_shader =
          __swap_chain_proxy_pixel_shader;

      // HSR DX11 injection uses b13.
      renodx::mods::swapchain::expected_constant_buffer_index = 13;
      renodx::mods::swapchain::expected_constant_buffer_space = 0;

      // Start in maximum-synchronization mode.
      // We optimize this only AFTER it renders correctly.
      renodx::mods::swapchain::device_proxy_wait_idle_source = true;
      renodx::mods::swapchain::device_proxy_wait_idle_destination = true;

      // Absolutely no direct Unity swapchain resize path.
      renodx::mods::swapchain::use_resize_buffer = false;
      renodx::mods::swapchain::use_resize_buffer_on_present = false;
      renodx::mods::swapchain::use_resize_buffer_on_demand = false;
      renodx::mods::swapchain::use_resize_buffer_on_set_full_screen = false;

      // Don't alter Unity's window/presentation policy.
      renodx::mods::swapchain::prevent_full_screen = false;
      renodx::mods::swapchain::force_borderless = false;
      renodx::mods::swapchain::force_screen_tearing = false;

      break;

    case DLL_PROCESS_DETACH:
      reshade::unregister_addon(h_module);
      break;
  }

  renodx::utils::settings::Use(fdw_reason, &settings, &OnPresetOff);

  renodx::mods::swapchain::Use(
      fdw_reason,
      &shader_injection);

  renodx::mods::shader::Use(
      fdw_reason,
      custom_shaders,
      &shader_injection);

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
            "proxy-scrgb",
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
        replacement = PROXY_SCRGB

    text = text[:start] + replacement + text[end:]

    path.write_text(
        text,
        encoding="utf-8"
    )

    print(f"PATCHED_VARIANT={args.variant}")
    print(f"FILE={path}")


if __name__ == "__main__":
    main()
