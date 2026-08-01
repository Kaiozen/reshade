from __future__ import annotations

import re
from pathlib import Path

SOURCE = Path("source/d3d12/d3d12.cpp")
REPORT = Path("v60-patch-report.txt")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one anchor, found {count}")
    return text.replace(old, new, 1)


def regex_once(text: str, pattern: str, replacement: str, label: str, flags: int = 0) -> str:
    updated, count = re.subn(pattern, replacement, text, count=1, flags=flags)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one regex match, found {count}")
    return updated


text = SOURCE.read_text(encoding="utf-8")
if "D3DMetal RTX real FP32 visual candidate v60" in text:
    raise RuntimeError("V60 patch appears to be applied already")
if "D3DMetal RTX steady-state shader-table lineage v59" not in text:
    raise RuntimeError("V59 baseline marker is missing")
if "D3DMetal RTX functional FP32 forced-miss control v52:" not in text:
    raise RuntimeError("V52 runtime marker baseline is missing")
if "D3DMetal RTX ray-hit output pattern control v53:" not in text:
    raise RuntimeError("V53 runtime marker baseline is missing")

# The V60 workflow deliberately does not run the V52 or V53 DXIL mutators.
# These runtime strings are therefore rewritten to describe the real V30 FP32
# shader that is embedded by the existing V30/V32 path.
text = replace_once(
    text,
    '"D3DMetal RTX functional FP32 forced-miss control v52: ACTIVE call=%llu state_object=%p module=real-v30-fp32 TraceRay=enabled instance-mask=0 output-stores=enabled hit-shaders=disabled ray-dispatch-suppression=disabled rt-bind-suppression=disabled."',
    '"D3DMetal RTX real FP32 visual candidate v60: ACTIVE call=%llu state_object=%p module=real-v30-fp32 TraceRay=enabled instance-mask=shader-selected output-stores=original hit-shaders=enabled diagnostic-pattern=disabled heavy-diagnostics=disabled."',
    "rewrite V52 runtime status",
)
text = replace_once(
    text,
    '"D3DMetal RTX ray-hit output pattern control v53: ACTIVE call=%llu state_object=%p output=_RWRayHitBuffer register=u1 stride=24 block=256 even=zero-record odd=far-miss-record TraceRay=enabled instance-mask=0 hit-shaders=disabled output-stores=patterned."',
    '"D3DMetal RTX real FP32 visual candidate v60: RAYHIT_OUTPUT call=%llu state_object=%p output=_RWRayHitBuffer register=u1 stride=24 output-stores=original pattern=disabled TraceRay=enabled instance-mask=shader-selected hit-shaders=enabled."',
    "rewrite V53 runtime status",
)

# V59 starts expensive tracking immediately. V60 keeps all old code available
# for later diagnostics, but leaves it dormant during the visual candidate run.
text = replace_once(
    text,
    "static std::atomic<bool> s_v59_high_frequency_tracking_enabled = true;",
    "static std::atomic<bool> s_v59_high_frequency_tracking_enabled = false;",
    "disable V59 high-frequency tracking by default",
)

text = replace_once(
    text,
    """        v57_install_resource_map_hook(resource);\n        v59_install_resource_unmap_hook(resource);\n        v58_install_gpu_va_hook(resource);\n""",
    """        // V60 visual mode: do not install Map, Unmap, or GPU-VA hooks.\n        // V59 already proved the shader-table lineage and local-root contract.\n""",
    "disable per-resource diagnostic hooks",
)

# Do not install the CopyBufferRegion diagnostic hook. SetPipelineState1 and
# DispatchRays remain hooked for lightweight execution proof.
text = regex_once(
    text,
    r"""\n\t\tbool v57_copy_verified = false;\n\t\tif \(verified\)\n\t\t\{.*?\n\t\t\}\n\n\t\treshade::log::message\(\n\t\t\tv57_copy_verified \?.*?\n\t\t\treinterpret_cast<void \*>\(\n\t\t\t\t&v57_trace_copy_buffer_region\)\);\n""",
    """
		static std::once_flag v60_copy_hook_disabled_once;
		std::call_once(
			v60_copy_hook_disabled_once,
			[]()
			{
				reshade::log::message(
					reshade::log::level::info,
					"D3DMetal RTX real FP32 visual candidate v60: COPY_BUFFER_DIAGNOSTIC_HOOK_DISABLED slot=%zu commands_modified=0. D3DMetal RTX shader-table resource recovery v57: COPY_BUFFER_REGION_HOOK installed=0 disabled-by-v60=1.",
					v57_copy_buffer_region_slot);
			});
""",
    "disable CopyBufferRegion hook installation",
    flags=re.DOTALL,
)

# Remove the three device-level readback/descriptor hook installers. The base
# command-signature and command-list hooks are retained.
text = replace_once(
    text,
    """\t\tv38_install_create_command_queue_hook(device);\n\t\tv39_install_resource_hooks(device);\n\t\tv55_install_descriptor_hooks(device);\n""",
    """\t\tstatic std::once_flag v60_heavy_diagnostics_disabled_once;\n\t\tstd::call_once(\n\t\t\tv60_heavy_diagnostics_disabled_once,\n\t\t\t[]()\n\t\t\t{\n\t\t\t\treshade::log::message(\n\t\t\t\t\treshade::log::level::info,\n\t\t\t\t\t\"D3DMetal RTX real FP32 visual candidate v60: HEAVY_DIAGNOSTICS_DISABLED dispatch-readback=1 shader-table-readback=1 descriptor-census=1 map-unmap=1 gpu-va=1 copy-lineage=1.\");\n\t\t\t});\n""",
    "disable device-level diagnostics",
)

# Add one atomic used by the lightweight runtime marker.
text = replace_once(
    text,
    """\tstatic std::atomic<uint64_t> s_v34_rewritten_ray_indirect_total = 0;\n""",
    """\tstatic std::atomic<uint64_t> s_v34_rewritten_ray_indirect_total = 0;\n\tstatic std::atomic<bool> s_v60_real_fp32_dispatch_seen = false;\n""",
    "add V60 dispatch marker state",
)

# Replace V38/V39 command-list mutation/readback calls with a one-shot proof
# that the inherited pipeline carrying the real FP32 identifiers reached the
# steady-state indirect DispatchRays path. This adds no GPU commands.
text = replace_once(
    text,
    """\t\tv38_try_capture_dispatch_record(\n\t\t\tcommand_list,\n\t\t\targument_buffer,\n\t\t\targument_buffer_offset,\n\t\t\tdispatch_rays,\n\t\t\trewritten,\n\t\t\tstate_call,\n\t\t\tray_index);\n\n\t\tv39_try_capture_shader_tables(\n\t\t\tcommand_list,\n\t\t\tdispatch_rays,\n\t\t\trewritten,\n\t\t\tstate_call,\n\t\t\tray_index);\n""",
    """\t\tif (dispatch_rays &&\n\t\t\t!s_v60_real_fp32_dispatch_seen.load(std::memory_order_acquire))\n\t\t{\n\t\t\tuint64_t v60_pipeline_id = 0;\n\t\t\tuint64_t v60_pipeline_ray_index = 0;\n\t\t\tif (v56_steady_state_pipeline_candidate(\n\t\t\t\treinterpret_cast<ID3D12GraphicsCommandList *>(command_list),\n\t\t\t\tv60_pipeline_id,\n\t\t\t\tv60_pipeline_ray_index))\n\t\t\t{\n\t\t\t\tbool expected = false;\n\t\t\t\tif (s_v60_real_fp32_dispatch_seen.compare_exchange_strong(\n\t\t\t\t\texpected, true, std::memory_order_acq_rel))\n\t\t\t\t{\n\t\t\t\t\treshade::log::message(\n\t\t\t\t\t\treshade::log::level::info,\n\t\t\t\t\t\t\"D3DMetal RTX real FP32 visual candidate v60: REAL_FP32_DISPATCH_EXECUTED mode=indirect pipeline_id=%llu pipeline_ray_index=%llu global_ray_index=%llu state_call=%llu argument_gpu_va=0x%llX argument_offset=%llu commands_modified=0.\",\n\t\t\t\t\t\tstatic_cast<unsigned long long>(v60_pipeline_id),\n\t\t\t\t\t\tstatic_cast<unsigned long long>(v60_pipeline_ray_index),\n\t\t\t\t\t\tstatic_cast<unsigned long long>(ray_index),\n\t\t\t\t\t\tstatic_cast<unsigned long long>(state_call),\n\t\t\t\t\t\tstatic_cast<unsigned long long>(argument_gpu_va),\n\t\t\t\t\t\tstatic_cast<unsigned long long>(argument_buffer_offset));\n\t\t\t\t}\n\t\t\t}\n\t\t}\n""",
    "replace heavy captures with V60 execution proof",
)

# Add a durable source marker near the V59 implementation heading.
text = replace_once(
    text,
    """    // V59 closes the V58 resource-lookup gap without changing shader-table\n""",
    """    // D3DMetal RTX real FP32 visual candidate v60.\n    // The workflow embeds the original V30 FP32 TraceRay mask and output stores,\n    // while runtime diagnostics are reduced to one non-mutating execution marker.\n\n    // V59 closes the V58 resource-lookup gap without changing shader-table\n""",
    "add V60 source marker",
)

SOURCE.write_text(text, encoding="utf-8", newline="\n")
REPORT.write_text(
    "\n".join(
        [
            "V60_REAL_FP32_VISUAL_CANDIDATE_PATCH_OK",
            "BASELINE=V59_STEADY_STATE_SHADER_TABLE_LINEAGE",
            "DXIL_BASE=ORIGINAL_V30_FP32_EXECUTETRACE_PLUS_MISS",
            "V52_FORCED_ZERO_MASK_APPLIED=NO",
            "V53_PATTERNED_OUTPUT_APPLIED=NO",
            "TRACE_RAY_INSTANCE_MASK=SHADER_SELECTED",
            "RAYHIT_OUTPUT_STORES=ORIGINAL",
            "HIT_SHADER_EXECUTION=ENABLED",
            "V38_DISPATCH_READBACK=DISABLED",
            "V39_SHADER_TABLE_READBACK=DISABLED",
            "V55_DESCRIPTOR_CENSUS=DISABLED",
            "V57_COPY_MAP_TRACKING=DISABLED",
            "V58_GPU_VA_TRACKING=DISABLED",
            "V59_LINEAGE_TRACKING=DISABLED",
            "LIGHTWEIGHT_STEADY_STATE_EXECUTION_MARKER=ENABLED",
            "COMMANDS_MODIFIED_BY_V60=NO",
            "DESCRIPTORS_MODIFIED_BY_V60=NO",
            "RESOURCES_MODIFIED_BY_V60=NO",
            "RESULT=PASS",
            "",
        ]
    ),
    encoding="utf-8",
    newline="\n",
)
print("V60_REAL_FP32_VISUAL_CANDIDATE_PATCH_OK")
