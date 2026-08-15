#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_hsr_quarantine_318a9df6.py <shader.hpp>")

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")

marker = "[Kaiozen] W5_QUARANTINE_318A9DF6=ACTIVE"

if marker in text:
    print("W5_QUARANTINE_ALREADY_PRESENT=YES")
    raise SystemExit(0)

anchor = """  insert_shaders(internal::device_based_compile_time_replacements[device->get_api()], shared.data->compile_time_replacements, "API-based compile-time");
  insert_shaders(internal::device_based_initial_runtime_replacements[device->get_api()], shared.data->runtime_replacements, "API-based runtime");

  runtime_replacement_count = shared.data->runtime_replacements.size();
"""

if text.count(anchor) != 1:
    raise SystemExit(f"FAIL: W5 OnInitDevice anchor count={text.count(anchor)}")

replacement = """  insert_shaders(internal::device_based_compile_time_replacements[device->get_api()], shared.data->compile_time_replacements, "API-based compile-time");
  insert_shaders(internal::device_based_initial_runtime_replacements[device->get_api()], shared.data->runtime_replacements, "API-based runtime");

  // Kaiozen W5 diagnostic isolation:
  // 0x318A9DF6 is the final loading/title UberPost whose synchronous
  // replacement creation immediately preceded the captured freeze.
  // Remove it from BOTH replacement maps so neither OnCreatePipeline
  // nor runtime/bind replacement can substitute it.
  constexpr uint32_t kaiozen_w5_quarantined_shader = 0x318A9DF6u;
  shared.data->compile_time_replacements.erase(
      {device, kaiozen_w5_quarantined_shader});
  shared.data->runtime_replacements.erase(
      {device, kaiozen_w5_quarantined_shader});

  reshade::log::message(
      reshade::log::level::info,
      "[Kaiozen] W5_QUARANTINE_318A9DF6=ACTIVE "
      "COMPILE_TIME_REPLACEMENT=OFF RUNTIME_REPLACEMENT=OFF");

  runtime_replacement_count = shared.data->runtime_replacements.size();
"""

text = text.replace(anchor, replacement, 1)
path.write_text(text, encoding="utf-8", newline="\n")

print("HOTFIX=W5")
print("QUARANTINED_SHADER=0x318A9DF6")
print("COMPILE_TIME_REPLACEMENT=OFF")
print("RUNTIME_REPLACEMENT=OFF")
print("OTHER_SHADERS=UNCHANGED")
