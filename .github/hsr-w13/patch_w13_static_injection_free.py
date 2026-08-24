#!/usr/bin/env python3
from pathlib import Path
import re
import sys

if len(sys.argv) != 4:
    raise SystemExit(
        "usage: patch_w13.py <addon.cpp> <mods/shader.hpp> <shared.h>"
    )

addon_path = Path(sys.argv[1])
mods_path = Path(sys.argv[2])
shared_path = Path(sys.argv[3])

addon = addon_path.read_text(encoding="utf-8")
mods = mods_path.read_text(encoding="utf-8")
shared = shared_path.read_text(encoding="utf-8")

for token in [
    "KAIOZEN_HSR_44_W10_COMPILE_ONLY_FULL_HDR",
    "force_pipeline_cloning = false;",
    "RUNTIME_FALLBACK=OFF",
]:
    if token not in addon:
        raise SystemExit(f"FAIL: W13 prerequisite missing: {token}")

if "// Use Runtime as fallback" in mods:
    raise SystemExit("FAIL: W10 compile-only fallback patch missing")

# Remove the entire dynamic settings/injection state from the HSR addon.
state_start = "ShaderInjectData shader_injection;\n"
namespace_end = "\n}  // namespace\n"

if addon.count(state_start) != 1:
    raise SystemExit(
        f"FAIL: shader_injection state anchor count={addon.count(state_start)}"
    )

start = addon.index(state_start)
end = addon.find(namespace_end, start)
if end < 0:
    raise SystemExit("FAIL: namespace end after shader injection not found")

addon = (
    addon[:start]
    + "// W13: all RenoDRT controls are compile-time constants in HLSL.\n"
      "// No settings objects and no runtime shader injection state.\n"
    + addon[end:]
)

settings_use_pattern = re.compile(
    r"\n  renodx::utils::settings::Use\(\n"
    r"      fdw_reason,\n"
    r"      &settings,\n"
    r"      &OnPresetOff\);\n"
)

addon, n_settings = settings_use_pattern.subn("\n", addon, count=1)
if n_settings != 1:
    raise SystemExit(f"FAIL: settings Use removal count={n_settings}")

old_shader_use = """  renodx::mods::shader::Use(
      fdw_reason,
      custom_shaders,
      &shader_injection);
"""

new_shader_use = """  renodx::mods::shader::Use(
      fdw_reason,
      custom_shaders);
"""

if addon.count(old_shader_use) != 1:
    raise SystemExit(
        f"FAIL: shader Use injection anchor count={addon.count(old_shader_use)}"
    )

addon = addon.replace(old_shader_use, new_shader_use, 1)

addon = addon.replace(
    "KAIOZEN_HSR_44_W10_COMPILE_ONLY_FULL_HDR",
    "KAIOZEN_HSR_44_W13_STATIC_INJECTION_FREE",
    1,
)

old_log = (
    '"[Kaiozen] W10_COMPILE_ONLY_FULL_HDR=ACTIVE '
    'FORCE_PIPELINE_CLONING=OFF RUNTIME_FALLBACK=OFF '
    'ALL_5_HSR_SHADERS=YES W5=OFF"'
)

new_log = (
    '"[Kaiozen] W13_STATIC_INJECTION_FREE=ACTIVE '
    'FORCE_PIPELINE_CLONING=OFF RUNTIME_FALLBACK=OFF '
    'ALL_5_HSR_SHADERS=YES SETTINGS_RUNTIME=OFF '
    'CBV13=OFF INJECTION_POINTER=NULL W5=OFF"'
)

if addon.count(old_log) != 1:
    raise SystemExit(f"FAIL: W10 log anchor count={addon.count(old_log)}")

addon = addon.replace(old_log, new_log, 1)

old_cb13 = """#ifndef __cplusplus
cbuffer cb13 : register(b13) {
  ShaderInjectData injectedData : packoffset(c0);
}
#endif
"""

new_static = """#ifndef __cplusplus
// W13 exact HSR RenoDX defaults, baked into shader bytecode.
// This removes b13 and all runtime constant-buffer injection/layout work.
static const ShaderInjectData injectedData = {
    3.0f,     // toneMapType = RenoDRT
    1000.0f,  // toneMapPeakNits
    203.0f,   // toneMapGameNits
    203.0f,   // toneMapUINits
    0.5f,     // toneMapHueCorrection (50% parsed)
    1.0f,     // colorGradeExposure
    1.0f,     // colorGradeHighlights (50 parsed)
    1.0f,     // colorGradeShadows (50 parsed)
    1.0f,     // colorGradeContrast (50 parsed)
    1.0f,     // colorGradeSaturation (50 parsed)
    0.0f,     // colorGradeBlowout
    1.0f      // colorGradeFlare (50 parsed)
};
#endif
"""

if shared.count(old_cb13) != 1:
    raise SystemExit(f"FAIL: cb13 anchor count={shared.count(old_cb13)}")

shared = shared.replace(old_cb13, new_static, 1)

# Strong postconditions.
for forbidden in [
    "ShaderInjectData shader_injection;",
    "renodx::utils::settings::Use(",
    "&shader_injection",
]:
    if forbidden in addon:
        raise SystemExit(f"FAIL: dynamic injection residue: {forbidden}")

if "cbuffer cb13" in shared or "register(b13)" in shared:
    raise SystemExit("FAIL: CBV13 still present")

for required in [
    "KAIOZEN_HSR_44_W13_STATIC_INJECTION_FREE",
    "W13_STATIC_INJECTION_FREE=ACTIVE",
    "force_pipeline_cloning = false;",
    "INJECTION_POINTER=NULL",
    "renodx::mods::shader::Use(",
]:
    if required not in addon:
        raise SystemExit(f"FAIL: W13 addon marker missing: {required}")

if "static const ShaderInjectData injectedData" not in shared:
    raise SystemExit("FAIL: static injectedData missing")

addon_path.write_text(addon, encoding="utf-8", newline="\n")
shared_path.write_text(shared, encoding="utf-8", newline="\n")

print("W13_PATCH=PASS")
print("STATIC_RENODRT_DEFAULTS=YES")
print("SETTINGS_RUNTIME=OFF")
print("CBV13=OFF")
print("INJECTION_POINTER=NULL")
print("PIPELINE_LAYOUT_INJECTION_TRIGGER=OFF")
print("COMPILE_TIME_REPLACEMENT=ON")
print("RUNTIME_FALLBACK_FOR_D3D11=OFF")
