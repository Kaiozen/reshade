from pathlib import Path

source = Path("source/d3d12/d3d12.cpp")
if not source.is_file():
    raise SystemExit("ERROR: source/d3d12/d3d12.cpp is missing")

text = source.read_text(encoding="utf-8")

active_anchor = '\t\t\t\treshade::log::message(\n\t\t\t\t\treshade::log::level::info,\n                    "D3DMetal RTX ray-hit consumer bootstrap repair v67: ACTIVE resource-map-bootstrap=enabled bounded-refresh=enabled actual-pipeline-id=enabled consumer-observation=v66 readback=disabled resource-barriers=disabled commands_modified=0.");\n'
active_replacement = active_anchor + '\t\t\t\treshade::log::message(\n\t\t\t\t\treshade::log::level::info,\n                    "D3DMetal RTX persistent-map candidate bootstrap v68: ACTIVE persistent-map-rescan=bounded max-scans=3 candidate-source=steady-state-persistent-map consumer-observation=v66 readback=disabled resource-barriers=disabled commands_modified=0.");\n'

candidate_anchor = '        std::vector<v59_shader_record_candidate> candidates;\n        {\n            std::lock_guard<std::mutex> lock(s_v59_candidate_mutex);\n            candidates = s_v59_record_candidates;\n        }\n\n        const v59_shader_record_candidate *latest = nullptr;\n'

candidate_replacement = '        std::vector<v59_shader_record_candidate> candidates;\n        {\n            std::lock_guard<std::mutex> lock(s_v59_candidate_mutex);\n            candidates = s_v59_record_candidates;\n        }\n\n        // V68 repair: Map hooks only remember persistently mapped buffers.\n        // V59 found the raygen record by explicitly scanning those live\n        // mappings at steady state. V67 refreshed the candidate list without\n        // ever invoking that scan, so every attempt reported candidate=none.\n        static std::atomic<uint64_t> s_v68_persistent_scan_attempts = 0;\n        if (candidates.empty() &&\n            s_v59_high_frequency_tracking_enabled.load(\n                std::memory_order_acquire))\n        {\n            const uint64_t scan_attempt =\n                s_v68_persistent_scan_attempts.fetch_add(\n                    1, std::memory_order_acq_rel) + 1;\n            if (scan_attempt <= 3)\n            {\n                size_t mapped_before = 0;\n                {\n                    std::lock_guard<std::mutex> lock(s_v59_map_mutex);\n                    mapped_before = s_v59_map_states.size();\n                }\n\n                const uint64_t started_ms = GetTickCount64();\n                v59_scan_persistent_mappings();\n                const uint64_t duration_ms =\n                    GetTickCount64() - started_ms;\n\n                {\n                    std::lock_guard<std::mutex> lock(s_v59_candidate_mutex);\n                    candidates = s_v59_record_candidates;\n                }\n\n                reshade::log::message(\n                    candidates.empty() ?\n                        reshade::log::level::warning :\n                        reshade::log::level::info,\n                    "D3DMetal RTX persistent-map candidate bootstrap v68: PERSISTENT_MAP_SCAN_RESULT success=%u attempt=%llu pipeline_id=%llu reason=%s mapped_states=%zu candidates=%zu duration_ms=%llu commands_modified=0.",\n                    candidates.empty() ? 0u : 1u,\n                    static_cast<unsigned long long>(scan_attempt),\n                    static_cast<unsigned long long>(pipeline_id),\n                    reason != nullptr ? reason : "unknown",\n                    mapped_before,\n                    candidates.size(),\n                    static_cast<unsigned long long>(duration_ms));\n            }\n        }\n\n        const v59_shader_record_candidate *latest = nullptr;\n'

ready_anchor = '        const bool ready =\n            s_v62_u1_target_ready.load(std::memory_order_acquire);\n\n        reshade::log::message(\n'
ready_replacement = '        const bool ready =\n            s_v62_u1_target_ready.load(std::memory_order_acquire);\n\n        if (ready)\n        {\n            const bool tracking_was_enabled =\n                s_v59_high_frequency_tracking_enabled.exchange(\n                    false, std::memory_order_acq_rel);\n            reshade::log::message(\n                reshade::log::level::info,\n                "D3DMetal RTX persistent-map candidate bootstrap v68: BOOTSTRAP_TRACKING_DISABLED ready=1 was_enabled=%u candidate_sequence=%llu commands_modified=0.",\n                tracking_was_enabled ? 1u : 0u,\n                static_cast<unsigned long long>(latest->sequence));\n        }\n\n        reshade::log::message(\n'

if "D3DMetal RTX persistent-map candidate bootstrap v68: ACTIVE" in text:
    print("V68_PATCH_ALREADY_APPLIED=YES")
else:
    for label, anchor in [
        ("active log", active_anchor),
        ("candidate list", candidate_anchor),
        ("ready state", ready_anchor),
    ]:
        if anchor not in text:
            raise SystemExit(f"ERROR: V68 {label} anchor was not found")
    text = text.replace(active_anchor, active_replacement, 1)
    text = text.replace(candidate_anchor, candidate_replacement, 1)
    text = text.replace(ready_anchor, ready_replacement, 1)
    source.write_text(text, encoding="utf-8")

required = [
    "D3DMetal RTX persistent-map candidate bootstrap v68: ACTIVE",
    "persistent-map-rescan=bounded",
    "max-scans=3",
    "s_v68_persistent_scan_attempts",
    "v59_scan_persistent_mappings();",
    "PERSISTENT_MAP_SCAN_RESULT success=%u",
    "BOOTSTRAP_TRACKING_DISABLED ready=1",
    "candidate-source=steady-state-persistent-map",
    "consumer-observation=v66",
    "readback=disabled",
    "resource-barriers=disabled",
    "commands_modified=0",
]
for marker in required:
    if marker not in text:
        raise SystemExit(f"ERROR: V68 required marker missing after patch: {marker}")

Path("v68-patch-report.txt").write_text(
    "\n".join([
        "V68_PERSISTENT_MAP_CANDIDATE_BOOTSTRAP_PATCH_OK",
        "BASELINE=V67_RAYHIT_CONSUMER_BOOTSTRAP",
        "ROOT_CAUSE=V67_STORED_PERSISTENT_MAPS_BUT_NEVER_SCANNED_THEM",
        "PERSISTENT_MAP_RESCAN=ENABLED",
        "MAX_PERSISTENT_MAP_SCANS=3",
        "U1_REFRESH_AFTER_SCAN=ENABLED",
        "TRACKING_DISABLED_AFTER_U1_READY=YES",
        "CONSUMER_OBSERVATION=V66",
        "RAYHIT_READBACK=DISABLED",
        "RESOURCE_COPIES=DISABLED",
        "RESOURCE_BARRIERS=DISABLED",
        "COMMANDS_MODIFIED=NO",
        "RESULT=PASS",
        "",
    ]),
    encoding="ascii",
)
print("V68_PERSISTENT_MAP_CANDIDATE_BOOTSTRAP_PATCH_OK")
