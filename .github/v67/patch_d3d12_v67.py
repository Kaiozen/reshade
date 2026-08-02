from pathlib import Path

source = Path("source/d3d12/d3d12.cpp")
if not source.is_file():
    raise SystemExit("ERROR: source/d3d12/d3d12.cpp is missing")

text = source.read_text(encoding="utf-8")

old_init = '\t\tstatic std::once_flag v66_consumer_mode_once;\n\t\tstd::call_once(\n\t\t\tv66_consumer_mode_once,\n\t\t\t[device]()\n\t\t\t{\n\t\t\t\tv55_install_descriptor_hooks(device);\n\t\t\t\treshade::log::message(\n\t\t\t\t\treshade::log::level::info,\n                    "D3DMetal RTX ray-hit consumer and lighting-history discovery v66: ACTIVE strict-lineage=v61 normalization=v63-fdiv descriptor-binding-observation=enabled normal-menu-gap-threshold-ms=3000 descriptor-scan-limit=96 resource-readback=disabled resource-barriers=disabled commands_modified=0.");\n\t\t\t});\n'
new_init = '\t\tstatic std::once_flag v66_consumer_mode_once;\n\t\tstd::call_once(\n\t\t\tv66_consumer_mode_once,\n\t\t\t[device]()\n\t\t\t{\n                // V67 bootstrap repair: V66 attempted to resolve u1 without\n                // installing the resource creation, Map and Unmap observers\n                // that populate the verified 64-byte raygen-record candidates.\n                // These observers are disabled automatically after u1 resolves.\n                v39_install_resource_hooks(device);\n\t\t\t\tv55_install_descriptor_hooks(device);\n\t\t\t\treshade::log::message(\n\t\t\t\t\treshade::log::level::info,\n                    "D3DMetal RTX ray-hit consumer bootstrap repair v67: ACTIVE resource-map-bootstrap=enabled bounded-refresh=enabled actual-pipeline-id=enabled consumer-observation=v66 readback=disabled resource-barriers=disabled commands_modified=0.");\n\t\t\t\treshade::log::message(\n\t\t\t\t\treshade::log::level::info,\n                    "D3DMetal RTX ray-hit consumer and lighting-history discovery v66: ACTIVE strict-lineage=v61 normalization=v63-fdiv descriptor-binding-observation=enabled normal-menu-gap-threshold-ms=3000 descriptor-scan-limit=96 resource-readback=disabled resource-barriers=disabled commands_modified=0.");\n\t\t\t});\n'
old_refresh = '        if (!s_v62_u1_target_ready.load(std::memory_order_acquire) &&\n            ray_index >= 32)\n            v65_refresh_current_u1_target(0, "v66-world-ray-dispatch");\n'
new_refresh = '        // V67 bootstrap repair: derive the actual rewritten pipeline identity\n        // from the command list. V66 passed pipeline_id=0 on every ray launch\n        // and spammed thousands of refreshes without ever installing the Map\n        // observers needed to create a raygen-record candidate.\n        uint64_t bootstrap_pipeline_id = 0;\n        uint64_t bootstrap_pipeline_ray_index = 0;\n        uint64_t bootstrap_state_call = 0;\n        const bool bootstrap_candidate = v64_rewritten_capture_candidate(\n            reinterpret_cast<ID3D12GraphicsCommandList4 *>(command_list),\n            1,\n            bootstrap_pipeline_id,\n            bootstrap_pipeline_ray_index,\n            bootstrap_state_call);\n\n        static std::atomic<uint64_t> s_v67_last_refresh_pipeline = 0;\n        static std::atomic<uint64_t> s_v67_last_refresh_ray = 0;\n        static std::atomic<uint64_t> s_v67_refresh_attempts = 0;\n\n        if (!s_v62_u1_target_ready.load(std::memory_order_acquire) &&\n            bootstrap_candidate &&\n            bootstrap_pipeline_id != 0 &&\n            bootstrap_pipeline_ray_index >= 32)\n        {\n            const uint64_t previous_pipeline =\n                s_v67_last_refresh_pipeline.load(std::memory_order_acquire);\n            const uint64_t previous_ray =\n                s_v67_last_refresh_ray.load(std::memory_order_acquire);\n            const bool pipeline_changed =\n                previous_pipeline != bootstrap_pipeline_id;\n            const bool interval_reached =\n                bootstrap_pipeline_ray_index >= previous_ray + 64;\n\n            if (pipeline_changed || interval_reached)\n            {\n                s_v67_last_refresh_pipeline.store(\n                    bootstrap_pipeline_id, std::memory_order_release);\n                s_v67_last_refresh_ray.store(\n                    bootstrap_pipeline_ray_index, std::memory_order_release);\n                const uint64_t attempt =\n                    s_v67_refresh_attempts.fetch_add(\n                        1, std::memory_order_acq_rel) + 1;\n                const bool ready = v65_refresh_current_u1_target(\n                    bootstrap_pipeline_id,\n                    pipeline_changed ?\n                        "v67-rewritten-pipeline-bootstrap" :\n                        "v67-bounded-ray-bootstrap");\n                reshade::log::message(\n                    ready ? reshade::log::level::info :\n                            reshade::log::level::warning,\n                    "D3DMetal RTX ray-hit consumer bootstrap repair v67: U1_BOOTSTRAP_RESULT success=%u attempt=%llu pipeline_id=%llu pipeline_ray_index=%llu state_call=%llu callback_ray_index=%llu dispatch_kind=%s map_hooks=%u commands_modified=0.",\n                    ready ? 1u : 0u,\n                    static_cast<unsigned long long>(attempt),\n                    static_cast<unsigned long long>(bootstrap_pipeline_id),\n                    static_cast<unsigned long long>(bootstrap_pipeline_ray_index),\n                    static_cast<unsigned long long>(bootstrap_state_call),\n                    static_cast<unsigned long long>(ray_index),\n                    kind != nullptr ? kind : "unknown",\n                    s_v57_any_map_hook_installed.load(\n                        std::memory_order_acquire) ? 1u : 0u);\n            }\n        }\n'

if "D3DMetal RTX ray-hit consumer bootstrap repair v67: ACTIVE" in text:
    print("V67_PATCH_ALREADY_APPLIED=YES")
else:
    if old_init not in text:
        raise SystemExit("ERROR: V67 init anchor was not found")
    if old_refresh not in text:
        raise SystemExit("ERROR: V67 refresh anchor was not found")
    text = text.replace(old_init, new_init, 1)
    text = text.replace(old_refresh, new_refresh, 1)
    source.write_text(text, encoding="utf-8")

required = [
    "D3DMetal RTX ray-hit consumer bootstrap repair v67: ACTIVE",
    "v39_install_resource_hooks(device);",
    "v64_rewritten_capture_candidate(",
    "v67-rewritten-pipeline-bootstrap",
    "v67-bounded-ray-bootstrap",
    "U1_BOOTSTRAP_RESULT success=%u",
    "actual-pipeline-id=enabled",
    "bounded-refresh=enabled",
]
for marker in required:
    if marker not in text:
        raise SystemExit(f"ERROR: V67 required marker missing after patch: {marker}")

for forbidden in [
    'v65_refresh_current_u1_target(0, "v66-world-ray-dispatch")',
]:
    if forbidden in text:
        raise SystemExit(f"ERROR: V67 obsolete marker remains: {forbidden}")

Path("v67-patch-report.txt").write_text(
    "\n".join([
        "V67_RAYHIT_CONSUMER_BOOTSTRAP_REPAIR_PATCH_OK",
        "BASELINE=V66_RAYHIT_CONSUMER_HISTORY",
        "RESOURCE_CREATION_HOOKS=ENABLED",
        "RESOURCE_MAP_UNMAP_BOOTSTRAP=ENABLED",
        "ACTUAL_REWRITTEN_PIPELINE_ID=ENABLED",
        "REFRESH_INTERVAL_RAYS=64",
        "REFRESH_SPAM_REMOVED=YES",
        "RAYHIT_READBACK=DISABLED",
        "RESOURCE_COPIES=DISABLED",
        "RESOURCE_BARRIERS=DISABLED",
        "COMMANDS_MODIFIED=NO",
        "RESULT=PASS",
        "",
    ]),
    encoding="ascii",
)
print("V67_RAYHIT_CONSUMER_BOOTSTRAP_REPAIR_PATCH_OK")
