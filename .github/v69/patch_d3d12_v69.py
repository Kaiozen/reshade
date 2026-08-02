from pathlib import Path

source = Path("source/d3d12/d3d12.cpp")
if not source.is_file():
    raise SystemExit("ERROR: source/d3d12/d3d12.cpp is missing")

text = source.read_text(encoding="utf-8")

active_v68 = '''\
\t\t\t\treshade::log::message(
\t\t\t\t\treshade::log::level::info,
                    "D3DMetal RTX persistent-map candidate bootstrap v68: ACTIVE persistent-map-rescan=bounded max-scans=3 candidate-source=steady-state-persistent-map consumer-observation=v66 readback=disabled resource-barriers=disabled commands_modified=0.");
'''
active_v69 = active_v68 + '''\
\t\t\t\treshade::log::message(
\t\t\t\t\treshade::log::level::info,
                    "D3DMetal RTX manual normal-menu history transition v69: ACTIVE trigger=explicit-signal signal-file=C:/kaiozen-v69-menu-closed.signal automatic-gap-detection=disabled consumer-observation=v66 persistent-output-comparison=enabled readback=disabled resource-barriers=disabled commands_modified=0.");
'''

old_v66_active = '''\
\t\t\t\treshade::log::message(
\t\t\t\t\treshade::log::level::info,
                    "D3DMetal RTX ray-hit consumer and lighting-history discovery v66: ACTIVE strict-lineage=v61 normalization=v63-fdiv descriptor-binding-observation=enabled normal-menu-gap-threshold-ms=3000 descriptor-scan-limit=96 resource-readback=disabled resource-barriers=disabled commands_modified=0.");
'''
new_v66_active = '''\
\t\t\t\treshade::log::message(
\t\t\t\t\treshade::log::level::info,
                    "D3DMetal RTX ray-hit consumer and lighting-history discovery v66: ACTIVE strict-lineage=v61 normalization=v63-fdiv descriptor-binding-observation=enabled normal-menu-gap-detection=disabled-by-v69 descriptor-scan-limit=96 resource-readback=disabled resource-barriers=disabled commands_modified=0.");
'''

state_anchor = '''\
    static std::atomic<bool> s_v66_post_menu_consumer_found = false;
'''
state_replacement = state_anchor + '''\
    static std::atomic<bool> s_v69_manual_signal_accepted = false;
    static std::atomic<uint64_t> s_v69_manual_signal_checks = 0;
    static std::atomic<uint64_t> s_v69_last_signal_check_tick_ms = 0;
'''

gap_block = '''\
        if (s_v66_world_consumer_found.load(std::memory_order_acquire) &&
            !s_v66_post_menu_phase.load(std::memory_order_acquire) &&
            previous_tick != 0 && now > previous_tick &&
            now - previous_tick >= 3000)
        {
            bool expected = false;
            if (s_v66_post_menu_phase.compare_exchange_strong(
                    expected, true, std::memory_order_acq_rel))
            {
                const uint64_t gap_index = s_v66_menu_gap_count.fetch_add(
                    1, std::memory_order_acq_rel) + 1;
                reshade::log::message(
                    reshade::log::level::info,
                    "D3DMetal RTX ray-hit consumer and lighting-history discovery v66: MENU_TRANSITION_RESUME gap_index=%llu gap_ms=%llu ray_epoch=%llu dispatch_kind=%s state_call=%llu ray_index=%llu.",
                    static_cast<unsigned long long>(gap_index),
                    static_cast<unsigned long long>(now - previous_tick),
                    static_cast<unsigned long long>(epoch),
                    kind != nullptr ? kind : "unknown",
                    static_cast<unsigned long long>(state_call),
                    static_cast<unsigned long long>(ray_index));
            }
        }
'''
manual_block = '''\
        // V69 removes V66's unreliable timing-gap guess. The Mac runner
        // creates this signal only after the user has opened the normal 3D
        // character menu, closed it, returned to the world, and pressed Enter.
        if (s_v66_world_consumer_found.load(std::memory_order_acquire) &&
            !s_v66_post_menu_phase.load(std::memory_order_acquire) &&
            !s_v69_manual_signal_accepted.load(std::memory_order_acquire))
        {
            uint64_t last_check = s_v69_last_signal_check_tick_ms.load(
                std::memory_order_acquire);
            if (now >= last_check + 100 &&
                s_v69_last_signal_check_tick_ms.compare_exchange_strong(
                    last_check, now, std::memory_order_acq_rel))
            {
                const uint64_t check_index =
                    s_v69_manual_signal_checks.fetch_add(
                        1, std::memory_order_acq_rel) + 1;
                const DWORD attributes = GetFileAttributesW(
                    L"C:\\\\kaiozen-v69-menu-closed.signal");
                if (attributes != INVALID_FILE_ATTRIBUTES &&
                    (attributes & FILE_ATTRIBUTE_DIRECTORY) == 0)
                {
                    bool expected = false;
                    if (s_v69_manual_signal_accepted.compare_exchange_strong(
                            expected, true, std::memory_order_acq_rel))
                    {
                        s_v66_post_menu_phase.store(
                            true, std::memory_order_release);
                        reshade::log::message(
                            reshade::log::level::info,
                            "D3DMetal RTX manual normal-menu history transition v69: MANUAL_MENU_CONFIRMATION accepted=1 check_index=%llu ray_epoch=%llu dispatch_kind=%s state_call=%llu ray_index=%llu signal_file=C:/kaiozen-v69-menu-closed.signal commands_modified=0.",
                            static_cast<unsigned long long>(check_index),
                            static_cast<unsigned long long>(epoch),
                            kind != nullptr ? kind : "unknown",
                            static_cast<unsigned long long>(state_call),
                            static_cast<unsigned long long>(ray_index));
                    }
                }
            }
        }
'''

post_anchor = '''\
        reshade::log::message(
            reshade::log::level::info,
            "D3DMetal RTX ray-hit consumer and lighting-history discovery v66: POST_MENU_CONSUMER_RESULT success=1 dispatch_kind=%s dispatch_index=%llu ray_epoch=%llu pipeline_state=%p same_pipeline_state=%u u1_resource_id=%llu u1_binding=%s root_parameter=%u descriptor_offset=%u output_count=%zu persistent_output_count=%llu groups=%u,%u,%u commands_modified=0.",
'''
post_replacement = '''\
        for (const auto &output : outputs)
        {
            if (!v66_contains_id(s_v66_world_output_ids, output.resource_id))
                continue;
            reshade::log::message(
                reshade::log::level::info,
                "D3DMetal RTX manual normal-menu history transition v69: PERSISTENT_OUTPUT_CANDIDATE resource_id=%llu format=%u dimension=%u width=%llu height=%u flags=0x%X binding_kind=%s root_parameter=%u descriptor_offset=%u classification=lighting-history-candidate commands_modified=0.",
                static_cast<unsigned long long>(output.resource_id),
                output.format,
                output.dimension,
                static_cast<unsigned long long>(output.width),
                output.height,
                output.flags,
                output.binding_kind == 2 ? "direct-root-uav" : "table-uav",
                output.root_parameter,
                output.descriptor_offset);
        }

''' + post_anchor

if "D3DMetal RTX manual normal-menu history transition v69: ACTIVE" in text:
    print("V69_PATCH_ALREADY_APPLIED=YES")
else:
    anchors = [
        ("V68 active log", active_v68),
        ("V66 active log", old_v66_active),
        ("V66 state declarations", state_anchor),
        ("V66 automatic gap block", gap_block),
        ("V66 post-menu result", post_anchor),
    ]
    for label, anchor in anchors:
        count = text.count(anchor)
        if count != 1:
            raise SystemExit(f"ERROR: V69 {label} anchor count was {count}, expected 1")
    text = text.replace(active_v68, active_v69, 1)
    text = text.replace(old_v66_active, new_v66_active, 1)
    text = text.replace(state_anchor, state_replacement, 1)
    text = text.replace(gap_block, manual_block, 1)
    text = text.replace(post_anchor, post_replacement, 1)
    source.write_text(text, encoding="utf-8")

required = [
    "D3DMetal RTX manual normal-menu history transition v69: ACTIVE",
    "trigger=explicit-signal",
    "signal-file=C:/kaiozen-v69-menu-closed.signal",
    "automatic-gap-detection=disabled",
    "normal-menu-gap-detection=disabled-by-v69",
    "s_v69_manual_signal_accepted",
    "GetFileAttributesW(",
    "MANUAL_MENU_CONFIRMATION accepted=1",
    "PERSISTENT_OUTPUT_CANDIDATE resource_id=",
    "classification=lighting-history-candidate",
    "persistent-output-comparison=enabled",
    "readback=disabled",
    "resource-barriers=disabled",
    "commands_modified=0",
]
for marker in required:
    if marker not in text:
        raise SystemExit(f"ERROR: V69 required marker missing after patch: {marker}")

for forbidden in [
    "MENU_TRANSITION_RESUME gap_index=",
    "normal-menu-gap-threshold-ms=3000",
]:
    if forbidden in text:
        raise SystemExit(f"ERROR: V69 forbidden automatic-gap marker remains: {forbidden}")

Path("v69-patch-report.txt").write_text(
    "\n".join([
        "V69_MANUAL_MENU_HISTORY_TRANSITION_PATCH_OK",
        "BASELINE=V68_PERSISTENT_MAP_BOOTSTRAP",
        "ROOT_CAUSE=V68_USED_NORMAL_RENDERING_GAP_AS_FALSE_MENU_SIGNAL",
        "AUTOMATIC_GAP_DETECTION=DISABLED",
        "MANUAL_SIGNAL_FILE=C:/kaiozen-v69-menu-closed.signal",
        "MANUAL_CONFIRMATION_REQUIRED=YES",
        "POST_MENU_CAPTURE_ARMED_ONLY_AFTER_SIGNAL=YES",
        "PERSISTENT_OUTPUT_COMPARISON=ENABLED",
        "LIGHTING_HISTORY_CANDIDATE_LOGGING=ENABLED",
        "RAYHIT_READBACK=DISABLED",
        "RESOURCE_COPIES=DISABLED",
        "RESOURCE_BARRIERS=DISABLED",
        "COMMANDS_MODIFIED=NO",
        "RESULT=PASS",
        "",
    ]), encoding="ascii")
print("V69_MANUAL_MENU_HISTORY_TRANSITION_PATCH_OK")
