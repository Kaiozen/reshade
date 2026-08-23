#!/usr/bin/env python3
from pathlib import Path
import sys

addon = Path(sys.argv[1])
mods_shader = Path(sys.argv[2])

a = addon.read_text(encoding="utf-8")

old_marker = "KAIOZEN_HSR_44_SHADER_ONLY"
new_marker = "KAIOZEN_HSR_44_W10_COMPILE_ONLY_FULL_HDR"
force_true = "renodx::mods::shader::force_pipeline_cloning = true;"

if old_marker not in a:
    raise SystemExit("FAIL: base shader-only marker missing")
if a.count(force_true) != 1:
    raise SystemExit(f"FAIL: force true count={a.count(force_true)}")

a = a.replace(old_marker, new_marker, 1)
a = a.replace(
    force_true,
    '''renodx::mods::shader::force_pipeline_cloning = false;
      reshade::log::message(
          reshade::log::level::info,
          "[Kaiozen] W10_COMPILE_ONLY_FULL_HDR=ACTIVE FORCE_PIPELINE_CLONING=OFF RUNTIME_FALLBACK=OFF ALL_5_HSR_SHADERS=YES W5=OFF");''',
    1,
)
addon.write_text(a, encoding="utf-8")

s = mods_shader.read_text(encoding="utf-8")

old = '''            if (!shader.code.empty()) {
              if (compile_supported) {
                renodx::utils::shader::QueueCompileTimeReplacement(hash, shader.code);
              }
              // Use Runtime as fallback
              renodx::utils::shader::QueueRuntimeReplacement(hash, shader.code);
            }'''

new = '''            if (!shader.code.empty()) {
              if (compile_supported) {
                renodx::utils::shader::QueueCompileTimeReplacement(hash, shader.code);
              } else {
                renodx::utils::shader::QueueRuntimeReplacement(hash, shader.code);
              }
            }'''

if s.count(old) != 1:
    raise SystemExit(f"FAIL: fallback anchor count={s.count(old)}")

s = s.replace(old, new, 1)
mods_shader.write_text(s, encoding="utf-8")

a2 = addon.read_text(encoding="utf-8")
s2 = mods_shader.read_text(encoding="utf-8")

for token in [
    new_marker,
    "force_pipeline_cloning = false;",
    "RUNTIME_FALLBACK=OFF",
    "renodx::mods::shader::Use(",
    "custom_shaders",
    "shader_injection",
]:
    if token not in a2:
        raise SystemExit(f"FAIL: missing addon token {token}")

if "force_pipeline_cloning = true;" in a2:
    raise SystemExit("FAIL: forced cloning still on")
if "// Use Runtime as fallback" in s2:
    raise SystemExit("FAIL: unconditional runtime fallback remains")

print("W10_PATCH=PASS")
print("FULL_RENODX_HSR_HDR=YES")
print("ALL_5_HSR_SHADERS=YES")
print("COMPILE_TIME_REPLACEMENT=ON")
print("RUNTIME_FALLBACK_FOR_COMPILE_SUPPORTED=OFF")
