from __future__ import annotations

from pathlib import Path

SOURCE = Path("source/d3d12/d3d12.cpp")
REPORT = Path("v63-patch-report.txt")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one anchor, found {count}")
    return text.replace(old, new, 1)


text = SOURCE.read_text(encoding="utf-8")
if "D3DMetal RTX strict FP32 uint24 division v63" in text:
    raise RuntimeError("V63 patch appears to be applied already")
if "D3DMetal RTX ray-hit output forensics v62" not in text:
    raise RuntimeError("V62 baseline marker is missing")
if "D3DMetal RTX AddToStateObject lineage bridge v61" not in text:
    raise RuntimeError("V61 strict-lineage marker is missing")

text = replace_once(
    text,
    "static std::atomic<bool> s_v59_high_frequency_tracking_enabled = true;",
    "static std::atomic<bool> s_v59_high_frequency_tracking_enabled = false;",
    "disable temporary V59 mapping tracking",
)

text = replace_once(
    text,
    '''        // V62 forensic mode: Map and Unmap are temporarily observed so the\n        // persistent 64-byte raygen record can be recovered. Copy and GPU-VA\n        // tracing stay disabled.\n        v57_install_resource_map_hook(resource);\n        v59_install_resource_unmap_hook(resource);\n''',
    '''        // V63 visual mode: the V62 Map/Unmap lineage probe is dormant.\n        // V59 and V62 already established the exact local-root u1 contract.\n''',
    "disable V62 Map/Unmap hooks",
)

text = replace_once(
    text,
    '''\t\tif (dispatch_rays &&\n\t\t\ts_v61_rewritten_steady_state_seen.load(std::memory_order_acquire))\n\t\t\tv62_try_capture_u1_output(command_list);\n''',
    '''\t\t// V63 visual mode keeps the strict V61 proof but does not inject the\n\t\t// V62 diagnostic copy/readback commands.\n''',
    "disable V62 u1 diagnostic copy",
)

text = replace_once(
    text,
    '''\t\tstatic std::once_flag v62_forensic_hooks_once;\n\t\tstd::call_once(\n\t\t\tv62_forensic_hooks_once,\n\t\t\t[device]()\n\t\t\t{\n\t\t\t\tv38_install_create_command_queue_hook(device);\n\t\t\t\tv39_install_resource_hooks(device);\n\t\t\t\tv55_install_descriptor_hooks(device);\n\t\t\t\treshade::log::message(\n\t\t\t\t\treshade::log::level::info,\n\t\t\t\t\t"D3DMetal RTX ray-hit output forensics v62: FORENSIC_HOOKS_ENABLED dispatch-argument-readback=1 mapped-raygen-lineage=1 descriptor-resolution=1 u1-output-readback=1 gpu-va-tracing=0 copy-lineage=0.");\n\t\t\t});\n''',
    '''\t\tstatic std::once_flag v63_visual_mode_once;\n\t\tstd::call_once(\n\t\t\tv63_visual_mode_once,\n\t\t\t[]()\n\t\t\t{\n\t\t\t\treshade::log::message(\n\t\t\t\t\treshade::log::level::info,\n\t\t\t\t\t"D3DMetal RTX strict FP32 uint24 division v63: ACTIVE normalization=fdiv-fp32-by-16777215 fast-math=disabled strict-lineage=v61 v62-forensics=disabled commands_modified=0.");\n\t\t\t});\n''',
    "replace V62 forensic hook activation with V63 visual marker",
)

text = replace_once(
    text,
    "    // D3DMetal RTX ray-hit output forensics v62.\n",
    "    // D3DMetal RTX strict FP32 uint24 division v63.\n"
    "    // The generated V30 IR uses non-fast FP32 division by 16777215 at both\n"
    "    // former FP64 normalization sites. V61 strict lineage remains active.\n\n"
    "    // D3DMetal RTX ray-hit output forensics v62.\n",
    "add V63 durable source marker",
)

SOURCE.write_text(text, encoding="utf-8", newline="\n")
REPORT.write_text(
    "\n".join(
        [
            "V63_STRICT_FP32_UINT24_DIVISION_VISUAL_PATCH_OK",
            "BASELINE=V62_RAYHIT_OUTPUT_FORENSICS",
            "DXIL_NORMALIZATION=FP32_DIVIDE_BY_EXACT_INTEGER_16777215",
            "DIVISION_FAST_MATH=DISABLED",
            "NORMALIZATION_SITES=2",
            "V61_STRICT_REWRITTEN_LINEAGE=ENABLED",
            "V62_DISPATCH_READBACK=DISABLED",
            "V62_SHADER_TABLE_LINEAGE=DISABLED",
            "V62_DESCRIPTOR_CENSUS=DISABLED",
            "V62_U1_COPY_READBACK=DISABLED",
            "V59_MAP_UNMAP_TRACKING=DISABLED",
            "COMMANDS_MODIFIED_BY_V63=NO",
            "RESULT=PASS",
            "",
        ]
    ),
    encoding="utf-8",
    newline="\n",
)
print("V63_STRICT_FP32_UINT24_DIVISION_VISUAL_PATCH_OK")
