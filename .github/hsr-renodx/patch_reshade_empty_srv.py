#!/usr/bin/env python3

from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit(
        "usage: patch_reshade_empty_srv.py <runtime.cpp>"
    )

path = Path(sys.argv[1])

if not path.exists():
    raise SystemExit(f"FAIL: missing {path}")

text = path.read_text(encoding="utf-8")

start_marker = (
    "\t// Create an empty texture, which is bound to shader "
    "resource view slots"
)

end_marker = "\t// Create effect color and stencil resource"

start = text.find(start_marker)
end = text.find(end_marker, start)

if start < 0 or end < 0 or end <= start:
    raise SystemExit(
        "FAIL: ReShade empty-texture block not found"
    )

block = text[start:end]

CREATE_OLD = (
    "api::resource_desc("
    "1, 1, 1, 1, "
    "api::format::r16_float, "
    "1, "
    "api::memory_heap::default_, "
    "api::resource_usage::shader_resource)"
)

CREATE_NEW = (
    "api::resource_desc("
    "1, 1, 1, 1, "
    "empty_texture_format, "
    "1, "
    "api::memory_heap::default_, "
    "api::resource_usage::shader_resource)"
)

VIEW_OLD = (
    "api::resource_view_desc("
    "api::format::r16_float)"
)

VIEW_NEW = (
    "api::resource_view_desc("
    "empty_texture_format)"
)

if block.count(CREATE_OLD) != 1:
    raise SystemExit(
        "FAIL: expected one R16_FLOAT empty resource"
    )

if block.count(VIEW_OLD) != 1:
    raise SystemExit(
        "FAIL: expected one R16_FLOAT empty SRV"
    )

# Change ONLY the two existing resource/view uses first.
# This avoids accidentally editing the fallback declaration
# that is inserted below.
block = block.replace(
    CREATE_OLD,
    CREATE_NEW,
    1
)

block = block.replace(
    VIEW_OLD,
    VIEW_NEW,
    1
)

anchor = "\tif (_empty_tex == 0)\n\t{\n"

if block.count(anchor) != 1:
    raise SystemExit(
        "FAIL: empty-texture initialization anchor invalid"
    )

injection = (
    "\tif (_empty_tex == 0)\n"
    "\t{\n"
    "\t\t// Kaiozen HOTFIX N:\n"
    "\t\t// D3DMetal DX11 fails ReShade's R16_FLOAT "
    "dummy SRV.\n"
    "\t\t// Use RGBA8 only for D3D11. Preserve upstream "
    "R16_FLOAT elsewhere.\n"
    "\t\tconst api::format empty_texture_format =\n"
    "\t\t\t_device->get_api() == "
    "api::device_api::d3d11\n"
    "\t\t\t\t? api::format::r8g8b8a8_unorm\n"
    "\t\t\t\t: api::format::r16_float;\n"
    "\n"
    "\t\tif (_device->get_api() == "
    "api::device_api::d3d11)\n"
    "\t\t\tlog::message(\n"
    "\t\t\t\tlog::level::info,\n"
    "\t\t\t\t\"[Kaiozen] "
    "N_EMPTY_SRV_FORMAT=RGBA8_D3D11\");\n"
)

block = block.replace(
    anchor,
    injection,
    1
)

old_comment = (
    "\t\t// Use VK_FORMAT_R16_SFLOAT format, since it is "
    "mandatory according to the spec "
    "(see https://www.khronos.org/registry/vulkan/specs/"
    "1.1/html/vkspec.html#features-required-format-support)\n"
)

block = block.replace(
    old_comment,
    "",
    1
)

patched = text[:start] + block + text[end:]

if patched == text:
    raise SystemExit("FAIL: patch made no changes")

if patched.count(
    "N_EMPTY_SRV_FORMAT=RGBA8_D3D11"
) != 1:
    raise SystemExit(
        "FAIL: HOTFIX N marker verification failed"
    )

# After the patch there should still be one R16_FLOAT reference
# in this block: the non-D3D11 fallback.
patched_block = patched[start:
    patched.find(end_marker, start)
]

if patched_block.count(
    "api::format::r16_float"
) != 1:
    raise SystemExit(
        "FAIL: R16_FLOAT fallback count is not exactly one"
    )

if patched_block.count(
    "empty_texture_format"
) != 3:
    raise SystemExit(
        "FAIL: empty_texture_format wiring invalid"
    )

path.write_text(
    patched,
    encoding="utf-8",
    newline="\n"
)

print("RESHADER_EMPTY_SRV_PATCH=PASS")
print("D3D11_EMPTY_FORMAT=R8G8B8A8_UNORM")
print("NON_D3D11_EMPTY_FORMAT=R16_FLOAT")
print("HOTFIX=N_V2")
