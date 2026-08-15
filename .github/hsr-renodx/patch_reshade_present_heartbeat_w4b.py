#!/usr/bin/env python3
from pathlib import Path
import re
import sys

if len(sys.argv) != 3:
    raise SystemExit(
        "usage: patch_reshade_present_heartbeat_w4b.py <runtime.cpp> <dxgi_swapchain.cpp>"
    )

runtime_path = Path(sys.argv[1])
dxgi_path = Path(sys.argv[2])

runtime = runtime_path.read_text(encoding="utf-8")
dxgi = dxgi_path.read_text(encoding="utf-8")

runtime_pattern = re.compile(
    r'([ \t]*_frame_count\+\+;\n'
    r'[ \t]*if \(_frame_count == 1\)\n'
    r'[ \t]*log::message\(\n'
    r'[ \t]*log::level::info,\n'
    r'[ \t]*"\[Kaiozen\] R_COPY_DRAW_EXECUTED=YES "\n'
    r'[ \t]*"RAW_UNORM_SRV=YES RAW_UNORM_RTV=YES "\n'
    r'[ \t]*"T_INTERMEDIATE_RTV=NO"\);\n)'
)

runtime_matches = list(runtime_pattern.finditer(runtime))
if len(runtime_matches) != 1:
    raise SystemExit(
        f"FAIL: W4B exact post-T runtime heartbeat anchor count={len(runtime_matches)}"
    )

heartbeat_runtime = (
    "\n"
    "\t\tif ((_frame_count % 300) == 0)\n"
    "\t\t\tlog::message(\n"
    "\t\t\t\tlog::level::info,\n"
    "\t\t\t\t\"[Kaiozen] W4B_COPY_HEARTBEAT frame=%llu\",\n"
    "\t\t\t\tstatic_cast<unsigned long long>(_frame_count));\n"
)

runtime = runtime_pattern.sub(
    lambda m: m.group(1) + heartbeat_runtime,
    runtime,
    count=1,
)

dxgi_pattern = re.compile(
    r'([ \t]*static bool logged_success = false;\n'
    r'[ \t]*static bool logged_failure = false;\n)'
)

dxgi_matches = list(dxgi_pattern.finditer(dxgi))
if len(dxgi_matches) != 1:
    raise SystemExit(
        f"FAIL: W4B native heartbeat anchor count={len(dxgi_matches)}"
    )

heartbeat_dxgi = (
    "\tstatic unsigned long long kaiozen_w4b_native_present_count = 0;\n"
    "\t++kaiozen_w4b_native_present_count;\n"
    "\n"
    "\tif ((kaiozen_w4b_native_present_count % 300) == 0)\n"
    "\t{\n"
    "\t\treshade::log::message(\n"
    "\t\t\treshade::log::level::info,\n"
    "\t\t\t\"[Kaiozen] W4B_NATIVE_PRESENT_HEARTBEAT count=%llu color_hr=0x%08X metadata_hr=0x%08X\",\n"
    "\t\t\tkaiozen_w4b_native_present_count,\n"
    "\t\t\tstatic_cast<unsigned int>(color_hr),\n"
    "\t\t\tstatic_cast<unsigned int>(metadata_hr));\n"
    "\t}\n"
    "\n"
)

dxgi = dxgi_pattern.sub(
    lambda m: heartbeat_dxgi + m.group(1),
    dxgi,
    count=1,
)

runtime_path.write_text(runtime, encoding="utf-8", newline="\n")
dxgi_path.write_text(dxgi, encoding="utf-8", newline="\n")

print("HOTFIX=W4B")
print("COPY_HEARTBEAT_EVERY_FRAMES=300")
print("NATIVE_PRESENT_HEARTBEAT_EVERY_FRAMES=300")
print("HDR_MATH_CHANGED=NO")
print("W3_VISUAL_TUNING_CHANGED=NO")

