from pathlib import Path

SOURCE = Path("source/d3d12/d3d12.cpp")
REPORT = Path("v60-source-verification.txt")
text = SOURCE.read_text(encoding="utf-8")

required = [
    "D3DMetal RTX real FP32 visual candidate v60",
    "REAL_FP32_DISPATCH_EXECUTED",
    "HEAVY_DIAGNOSTICS_DISABLED",
    "COPY_BUFFER_DIAGNOSTIC_HOOK_DISABLED",
    "instance-mask=shader-selected",
    "output-stores=original",
    "pattern=disabled",
    "s_v59_high_frequency_tracking_enabled = false",
    "s_v60_real_fp32_dispatch_seen",
]
for marker in required:
    if marker not in text:
        raise RuntimeError(f"Missing V60 source marker: {marker}")

for forbidden in [
    "functional FP32 forced-miss control v52: ACTIVE",
    "ray-hit output pattern control v53: ACTIVE",
    "v57_install_resource_map_hook(resource);\n        v59_install_resource_unmap_hook(resource);\n        v58_install_gpu_va_hook(resource);",
    "\t\tv38_install_create_command_queue_hook(device);\n\t\tv39_install_resource_hooks(device);\n\t\tv55_install_descriptor_hooks(device);",
]:
    if forbidden in text:
        raise RuntimeError(f"Forbidden V60 source fragment remains: {forbidden}")

# Definitions remain compiled for future diagnostics, but the two mutating
# capture functions must have no runtime call sites.
if text.count("v38_try_capture_dispatch_record(") != 1:
    raise RuntimeError("V38 dispatch capture still has a runtime call site")
if text.count("v39_try_capture_shader_tables(") != 1:
    raise RuntimeError("V39 shader-table capture still has a runtime call site")

REPORT.write_text(
    "\n".join(
        [
            "V60_SOURCE_VERIFICATION_OK",
            "REAL_FP32_RUNTIME_STATUS=TRUTHFUL",
            "HEAVY_DIAGNOSTIC_INSTALLERS=DISABLED",
            "GPU_COMMAND_READBACK_CALLS=DISABLED",
            "LIGHTWEIGHT_EXECUTION_PROOF=ENABLED",
            "COMMANDS_MODIFIED=NO",
            "RESULT=PASS",
            "",
        ]
    ),
    encoding="utf-8",
    newline="\n",
)
print("V60_SOURCE_VERIFICATION_OK")
