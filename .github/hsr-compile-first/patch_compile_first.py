#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_compile_first.py <addon.cpp>")

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")

old_marker = "KAIOZEN_HSR_44_SHADER_ONLY"
new_marker = "KAIOZEN_HSR_44_COMPILE_FIRST_FULL_HDR"
force_true = "renodx::mods::shader::force_pipeline_cloning = true;"

if old_marker not in text:
    raise SystemExit("FAIL: shader-only source marker missing")
if text.count(force_true) != 1:
    raise SystemExit(
        f"FAIL: force_pipeline_cloning=true count={text.count(force_true)}"
    )

text = text.replace(old_marker, new_marker, 1)
text = text.replace(
    force_true,
    '''renodx::mods::shader::force_pipeline_cloning = false;
      reshade::log::message(
          reshade::log::level::info,
          "[Kaiozen] W7_COMPILE_FIRST_FULL_HDR=ACTIVE FORCE_PIPELINE_CLONING=OFF ALL_5_HSR_SHADERS=YES W5=OFF");''',
    1,
)

path.write_text(text, encoding="utf-8")

check = path.read_text(encoding="utf-8")

required = [
    new_marker,
    "force_pipeline_cloning = false;",
    "renodx::utils::settings::Use(",
    "renodx::mods::shader::Use(",
    "custom_shaders",
    "shader_injection",
    "ALL_5_HSR_SHADERS=YES",
    "W5=OFF",
]

for token in required:
    if token not in check:
        raise SystemExit(f"FAIL: required token missing: {token}")

if force_true in check:
    raise SystemExit("FAIL: force_pipeline_cloning=true still present")

print("W7_PATCH=PASS")
print("FULL_RENODX_HSR_HDR=YES")
print("ALL_5_HSR_SHADERS=YES")
print("FORCE_PIPELINE_CLONING=OFF")
print("W5_QUARANTINE=OFF")
