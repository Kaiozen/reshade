#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_reshade_minimal_reset_symmetry.py <runtime.cpp>")

p = Path(sys.argv[1])
s = p.read_text(encoding="utf-8")

top_anchor = (
    "void reshade::runtime::on_reset()\n"
    "{\n"
    "\tif (_device->get_api() == api::device_api::d3d11)\n"
)

if s.count(top_anchor) != 1:
    raise SystemExit(
        f"FAIL: V on_reset top anchor count={s.count(top_anchor)}"
    )

top_replacement = (
    "void reshade::runtime::on_reset()\n"
    "{\n"
    "\tconst bool kaiozen_hsr_minimal_reset =\n"
    "\t\t_device->get_api() == api::device_api::d3d11 &&\n"
    "\t\tapi::format_to_typeless(_back_buffer_format) ==\n"
    "\t\t\tapi::format::r8g8b8a8_typeless &&\n"
    "\t\t_width >= 1000 &&\n"
    "\t\t_height >= 700;\n"
    "\n"
    "\tif (kaiozen_hsr_minimal_reset)\n"
    "\t\tlog::message(\n"
    "\t\t\tlog::level::info,\n"
    "\t\t\t\"[Kaiozen] V_MINIMAL_RESET=ENTER \"\n"
    "\t\t\t\"SKIP_DESTROY_EFFECT_RUNTIME=YES\");\n"
    "\n"
    "\tif (_device->get_api() == api::device_api::d3d11)\n"
)

s = s.replace(top_anchor, top_replacement, 1)

destroy_anchor = (
    "#if RESHADE_ADDON\n"
    "\tinvoke_addon_event<addon_event::destroy_effect_runtime>(this);\n"
    "#endif\n"
    "\n"
    "\tlog::message(log::level::info, "
    "\"Destroyed runtime environment on runtime %p ('%s').\", "
    "this, _config_path.u8string().c_str());\n"
)

if s.count(destroy_anchor) != 1:
    raise SystemExit(
        f"FAIL: V destroy event anchor count={s.count(destroy_anchor)}"
    )

destroy_replacement = (
    "#if RESHADE_ADDON\n"
    "\t// HOTFIX V: HSR minimal on_init returns before init_effect_runtime.\n"
    "\t// Therefore runtime-private add-on state such as generic_depth_data\n"
    "\t// does not exist and its destroy callback must not run.\n"
    "\tif (!kaiozen_hsr_minimal_reset)\n"
    "\t{\n"
    "\t\tinvoke_addon_event<addon_event::destroy_effect_runtime>(this);\n"
    "\t}\n"
    "\telse\n"
    "\t{\n"
    "\t\tlog::message(\n"
    "\t\t\tlog::level::info,\n"
    "\t\t\t\"[Kaiozen] V_DESTROY_EFFECT_RUNTIME=SKIPPED \"\n"
    "\t\t\t\"INIT_EVENT_WAS_BYPASSED=YES\");\n"
    "\t}\n"
    "#endif\n"
    "\n"
    "\tif (kaiozen_hsr_minimal_reset)\n"
    "\t\tlog::message(\n"
    "\t\t\tlog::level::info,\n"
    "\t\t\t\"[Kaiozen] V_MINIMAL_RESET=COMPLETE \"\n"
    "\t\t\t\"RESIZE_REINIT_EXPECTED=YES\");\n"
    "\n"
    "\tlog::message(log::level::info, "
    "\"Destroyed runtime environment on runtime %p ('%s').\", "
    "this, _config_path.u8string().c_str());\n"
)

s = s.replace(destroy_anchor, destroy_replacement, 1)
p.write_text(s, encoding="utf-8", newline="\n")

print("HOTFIX=V")
print("MINIMAL_INIT_DESTROY_SYMMETRY=YES")
print("GENERIC_DEPTH_NULL_DEREF_GUARD=YES")
print("DESTROY_EFFECT_RUNTIME_SKIPPED_FOR_HSR_MINIMAL=YES")
print("DESTROY_SWAPCHAIN_UNCHANGED=YES")
