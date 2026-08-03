from pathlib import Path

source = Path("source/d3d12/d3d12.cpp")
if not source.is_file():
    raise SystemExit("ERROR: source/d3d12/d3d12.cpp is missing")
text = source.read_text(encoding="utf-8")


def replace_once(old: str, new: str, label: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"ERROR: {label} anchor count was {count}, expected 1")
    text = text.replace(old, new, 1)


manifest_anchor = r'''extern "C" __declspec(dllexport) const char *kaiozen_v79_r3_binary_marker_manifest()
{
    static const char manifest[] =
        "V79_R3_BINARY_MARKER_MANIFEST_R3_STABLE_TRIPLET_RING\n"
        "D3DMetal RTX presented-frame producer chain v79 R3: ACTIVE\n"
        "SWAPCHAIN_TRIPLET_LOCKED\n"
        "RTV_RING_BIND\n"
        "RTV_RING_FRAME\n"
        "triplet-period-proof=4-cycles\n"
        "dynamic-largest-group-selection=disabled\n"
        "locked-present-resource-input-filter-bypass=enabled\n"
        "commands_modified=0\n";
    return manifest;
}

namespace
'''
manifest_block = manifest_anchor[:-len("namespace\n")] + r'''extern "C" __declspec(dllexport) const char *kaiozen_v79_r4_binary_marker_manifest()
{
    static const char manifest[] =
        "V79_R4_BINARY_MARKER_MANIFEST_R4_SUBMITTED_COMMAND_LIST_BOUNDARY\n"
        "D3DMetal RTX presented-frame producer chain v79 R4: ACTIVE\n"
        "SUBMITTED_RING_COMMAND_LIST\n"
        "SUBMITTED_RING_FRAME\n"
        "STATIC_COMMAND_LIST_WRITER_RECOVERY\n"
        "frame-boundary=submitted-command-list-replay\n"
        "recording-time-event-capture=enabled\n"
        "commands_modified=0\n";
    return manifest;
}

namespace
'''
replace_once(manifest_anchor, manifest_block, "V79 R4 exported manifest")


state_anchor = r'''    static std::atomic<uint64_t> s_v79_r3_ring_frame_count = 0;
'''
state_block = state_anchor + r'''

    static std::unordered_map<void *, std::vector<uint64_t>>
        s_v79_r4_command_list_rtvs_by_identity;
    static std::atomic<bool> s_v79_r4_writer_recovery_done = false;
    static std::atomic<uint64_t> s_v79_r4_writer_recovery_count = 0;
    static std::atomic<uint64_t> s_v79_r4_recovered_writer_count = 0;
    static std::atomic<uint64_t> s_v79_r4_submit_call_count = 0;
    static std::atomic<uint64_t> s_v79_r4_submit_hit_count = 0;
    static std::atomic<uint64_t> s_v79_r4_submit_miss_count = 0;
    static std::atomic<uint64_t> s_v79_r4_submit_ambiguous_count = 0;
    static std::atomic<uint64_t> s_v79_r4_submitted_ring_frame_count = 0;
    static uint64_t s_v79_r4_last_submitted_resource = 0;
    static constexpr uint64_t v79_r4_max_recorded_events = 12000;
'''
replace_once(state_anchor, state_block, "V79 R4 state")


forward_anchor = """    void v76_on_execute_command_lists(
        ID3D12CommandQueue *queue,
        UINT count,
        ID3D12CommandList *const *command_lists);

\tvoid v38_install_execute_command_lists_hook(ID3D12CommandQueue *queue);
"""
forward_block = """    void v76_on_execute_command_lists(
        ID3D12CommandQueue *queue,
        UINT count,
        ID3D12CommandList *const *command_lists);

    void v79_r4_on_execute_command_lists(
        ID3D12CommandQueue *queue,
        UINT count,
        ID3D12CommandList *const *command_lists);

\tvoid v38_install_execute_command_lists_hook(ID3D12CommandQueue *queue);
"""
replace_once(forward_anchor, forward_block, "V79 R4 execute-list forward declaration")


execute_call_anchor = r'''        v76_on_execute_command_lists(queue, count, command_lists);

'''
execute_call_block = r'''        v76_on_execute_command_lists(queue, count, command_lists);
        v79_r4_on_execute_command_lists(queue, count, command_lists);

'''
replace_once(execute_call_anchor, execute_call_block, "V79 R4 execute-list callback")


helper_anchor = r'''    bool v79_r3_resource_had_begin(uint64_t resource_id)
'''
helper_block = r'''    void v79_r4_recover_locked_writer_metadata()
    {
        if (!v79_is_active() ||
            !s_v79_r3_triplet_locked.load(std::memory_order_acquire))
            return;

        bool expected = false;
        if (!s_v79_r4_writer_recovery_done.compare_exchange_strong(
                expected, true, std::memory_order_acq_rel))
            return;

        uint64_t recovered = 0;
        uint64_t members = 0;
        {
            std::lock_guard<std::mutex> lock(s_v79_mutex);
            for (const auto &entry : s_v79_r3_locked_resources)
            {
                if (!entry.second)
                    continue;
                ++members;
                const uint64_t resource_id = entry.first;
                s_v79_active_backbuffers[resource_id] = true;
                auto &writers = s_v79_frame_writers[resource_id];
                const auto last = s_v79_last_writer.find(resource_id);
                if (last != s_v79_last_writer.end())
                {
                    const bool duplicate = std::find_if(
                        writers.begin(), writers.end(),
                        [&last](const v79_event_record &event)
                        {
                            return event.index == last->second.index;
                        }) != writers.end();
                    if (!duplicate && writers.size() < v79_max_frame_writers)
                    {
                        writers.push_back(last->second);
                        ++recovered;
                    }
                }
            }
        }
        s_v79_r4_recovered_writer_count.store(
            recovered, std::memory_order_release);
        const uint64_t count =
            s_v79_r4_writer_recovery_count.fetch_add(
                1, std::memory_order_acq_rel) + 1;
        reshade::log::message(
            recovered != 0 ? reshade::log::level::info :
                             reshade::log::level::warning,
            "D3DMetal RTX presented-frame producer chain v79 R4: STATIC_COMMAND_LIST_WRITER_RECOVERY count=%llu locked_members=%llu recovered_direct_writers=%llu event_count=%llu recording-time-event-capture=enabled commands_modified=0.",
            static_cast<unsigned long long>(count),
            static_cast<unsigned long long>(members),
            static_cast<unsigned long long>(recovered),
            static_cast<unsigned long long>(
                s_v79_event_count.load(std::memory_order_acquire)));
    }

    void v79_r4_on_execute_command_lists(
        ID3D12CommandQueue *queue,
        UINT count,
        ID3D12CommandList *const *command_lists)
    {
        (void)queue;
        if (!v79_is_active() || command_lists == nullptr ||
            !s_v79_r3_triplet_locked.load(std::memory_order_acquire) ||
            s_v79_result_ready.load(std::memory_order_acquire))
            return;

        s_v79_r4_submit_call_count.fetch_add(
            1, std::memory_order_acq_rel);

        std::vector<uint64_t> submitted_resources;
        bool ambiguous = false;
        for (UINT index = 0; index < count; ++index)
        {
            ID3D12CommandList *list = nullptr;
            if (!safe_copy_from_process(
                    command_lists + index, &list, sizeof(list)) ||
                list == nullptr)
                continue;

            void *const identity = v33_identity_pointer(
                reinterpret_cast<IUnknown *>(list));
            std::vector<uint64_t> recorded;
            {
                std::lock_guard<std::mutex> lock(s_v79_mutex);
                if (identity != nullptr)
                {
                    const auto found =
                        s_v79_r4_command_list_rtvs_by_identity.find(identity);
                    if (found != s_v79_r4_command_list_rtvs_by_identity.end())
                        recorded = found->second;
                }
                if (recorded.empty())
                {
                    const auto found = s_v79_current_rtvs.find(
                        reinterpret_cast<ID3D12GraphicsCommandList *>(list));
                    if (found != s_v79_current_rtvs.end())
                        recorded = found->second;
                }
            }

            std::vector<uint64_t> locked_for_list;
            uint64_t selected = 0;
            {
                std::lock_guard<std::mutex> lock(s_v79_mutex);
                for (const uint64_t resource_id : recorded)
                {
                    const auto found =
                        s_v79_r3_locked_resources.find(resource_id);
                    if (found == s_v79_r3_locked_resources.end() ||
                        !found->second)
                        continue;
                    selected = resource_id;
                    if (std::find(
                            locked_for_list.begin(),
                            locked_for_list.end(),
                            resource_id) == locked_for_list.end())
                        locked_for_list.push_back(resource_id);
                }
            }
            if (selected == 0)
                continue;
            if (locked_for_list.size() > 1)
                ambiguous = true;

            if (submitted_resources.empty() ||
                submitted_resources.back() != selected)
                submitted_resources.push_back(selected);
        }

        if (submitted_resources.empty())
        {
            const uint64_t miss =
                s_v79_r4_submit_miss_count.fetch_add(
                    1, std::memory_order_acq_rel) + 1;
            if (miss <= 8)
                reshade::log::message(
                    reshade::log::level::info,
                    "D3DMetal RTX presented-frame producer chain v79 R4: SUBMITTED_RING_COMMAND_LIST hit=0 submit_call=%llu command_list_count=%u reason=no-submitted-command-list-mapped-to-frozen-triplet commands_modified=0.",
                    static_cast<unsigned long long>(
                        s_v79_r4_submit_call_count.load(
                            std::memory_order_acquire)),
                    count);
            return;
        }

        const uint64_t hit =
            s_v79_r4_submit_hit_count.fetch_add(
                1, std::memory_order_acq_rel) + 1;
        if (ambiguous)
            s_v79_r4_submit_ambiguous_count.fetch_add(
                1, std::memory_order_acq_rel);

        for (const uint64_t current : submitted_resources)
        {
            uint64_t previous = 0;
            {
                std::lock_guard<std::mutex> lock(s_v79_mutex);
                previous = s_v79_r4_last_submitted_resource;
                s_v79_r4_last_submitted_resource = current;
            }

            if (hit <= 16 || hit % 120 == 0)
                reshade::log::message(
                    reshade::log::level::info,
                    "D3DMetal RTX presented-frame producer chain v79 R4: SUBMITTED_RING_COMMAND_LIST hit=1 submit_hit=%llu command_list_count=%u selected_resource_id=%llu previous_resource_id=%llu switched=%u ambiguous_submission=%u strict_rewritten_proof=%u commands_modified=0.",
                    static_cast<unsigned long long>(hit),
                    count,
                    static_cast<unsigned long long>(current),
                    static_cast<unsigned long long>(previous),
                    previous != 0 && previous != current ? 1u : 0u,
                    ambiguous ? 1u : 0u,
                    s_v61_rewritten_steady_state_seen.load(
                        std::memory_order_acquire) ? 1u : 0u);

            if (previous == 0 || previous == current ||
                !s_v61_rewritten_steady_state_seen.load(
                    std::memory_order_acquire))
                continue;

            v55_resource_info previous_info = {};
            if (!v55_get_resource(previous, previous_info) ||
                previous_info.resource == nullptr)
                continue;

            const uint64_t frame =
                s_v79_r4_submitted_ring_frame_count.fetch_add(
                    1, std::memory_order_acq_rel) + 1;
            if (frame <= 16 || frame % 120 == 0)
                reshade::log::message(
                    reshade::log::level::info,
                    "D3DMetal RTX presented-frame producer chain v79 R4: SUBMITTED_RING_FRAME frame=%llu completed_resource_id=%llu next_resource_id=%llu format=%u dimensions=%llux%u boundary=submitted-command-list-replay ambiguous_submission=%u commands_modified=0.",
                    static_cast<unsigned long long>(frame),
                    static_cast<unsigned long long>(previous),
                    static_cast<unsigned long long>(current),
                    previous_info.format,
                    static_cast<unsigned long long>(previous_info.width),
                    previous_info.height,
                    ambiguous ? 1u : 0u);
            v79_process_present(previous_info.resource);
        }
    }

    bool v79_r3_resource_had_begin(uint64_t resource_id)
'''
replace_once(helper_anchor, helper_block, "V79 R4 helpers")


r3_active_clear_anchor = r'''                s_v79_active_backbuffers[current] = true;
                if (previous == 0)
                    s_v79_frame_writers[current].clear();
                else if (previous != current)
                {
                    s_v79_active_backbuffers[previous] = false;
                    s_v79_frame_writers[current].clear();
                }
'''
r3_active_clear_block = r'''                for (const auto &entry : s_v79_r3_locked_resources)
                    if (entry.second)
                        s_v79_active_backbuffers[entry.first] = true;
'''
replace_once(
    r3_active_clear_anchor,
    r3_active_clear_block,
    "V79 R4 preserve static writer metadata")


r3_bind_anchor = r'''        const uint64_t bind_count =
            s_v79_r3_ring_bind_count.fetch_add(
'''
r3_bind_block = r'''        if (s_v79_r3_triplet_locked.load(std::memory_order_acquire))
        {
            v79_r4_recover_locked_writer_metadata();
            return;
        }

        const uint64_t bind_count =
            s_v79_r3_ring_bind_count.fetch_add(
'''
replace_once(r3_bind_anchor, r3_bind_block, "V79 R4 disable recording-time frame boundary")


om_map_anchor = r'''        {
            std::lock_guard<std::mutex> lock(s_v79_mutex);
            s_v79_current_rtvs[command_list] = resources;
        }
        v79_r3_observe_rtv_sequence(resources);
'''
om_map_block = r'''        void *const command_list_identity = v33_identity_pointer(
            reinterpret_cast<IUnknown *>(command_list));
        {
            std::lock_guard<std::mutex> lock(s_v79_mutex);
            s_v79_current_rtvs[command_list] = resources;
            if (command_list_identity != nullptr)
            {
                auto &recorded =
                    s_v79_r4_command_list_rtvs_by_identity[
                        command_list_identity];
                for (const uint64_t resource_id : resources)
                {
                    if (recorded.empty() ||
                        recorded.back() != resource_id)
                        recorded.push_back(resource_id);
                }
                if (recorded.size() > 64)
                    recorded.erase(
                        recorded.begin(),
                        recorded.begin() + (recorded.size() - 64));
            }
        }
        v79_r3_observe_rtv_sequence(resources);
        v79_r4_recover_locked_writer_metadata();
'''
replace_once(om_map_anchor, om_map_block, "V79 R4 command-list RTV identity map")


record_event_anchor = r'''        if (!v79_is_active() || command_list == nullptr ||
            !s_v61_rewritten_steady_state_seen.load(std::memory_order_acquire) ||
            s_v79_result_ready.load(std::memory_order_acquire))
            return;
'''
record_event_block = r'''        if (!v79_is_active() || command_list == nullptr ||
            s_v79_result_ready.load(std::memory_order_acquire) ||
            s_v79_event_count.load(std::memory_order_acquire) >=
                v79_r4_max_recorded_events)
            return;
'''
replace_once(
    record_event_anchor,
    record_event_block,
    "V79 R4 recording-time bound-event capture")


copy_event_anchor = r'''        if (!v79_is_active() || destination == nullptr || source == nullptr ||
            !s_v61_rewritten_steady_state_seen.load(std::memory_order_acquire) ||
            s_v79_result_ready.load(std::memory_order_acquire))
            return;
'''
copy_event_block = r'''        if (!v79_is_active() || destination == nullptr || source == nullptr ||
            s_v79_result_ready.load(std::memory_order_acquire) ||
            s_v79_event_count.load(std::memory_order_acquire) >=
                v79_r4_max_recorded_events)
            return;
'''
replace_once(
    copy_event_anchor,
    copy_event_block,
    "V79 R4 recording-time copy-event capture")


active_log_anchor = r'''"D3DMetal RTX presented-frame producer chain v79: ACTIVE runtime-gate=KAIOZEN_V79_ACTIVE backbuffer-detection=stable-three-resource-periodic-ring triplet-period-proof=4-cycles dynamic-largest-group-selection=disabled locked-present-resource-input-filter-bypass=enabled reverse-present-barrier=not-required rtv-tracking=enabled copy-resolve-tracking=enabled present-frame-writers=24 backward-depth=6 baseline-present-frames=8 baseline-capture-freeze=enabled post-settings-present-frames=4 signal-file=C:/kaiozen-v79-settings-returned.signal commands_modified=0.");'''
active_log_block = r'''"D3DMetal RTX presented-frame producer chain v79: ACTIVE runtime-gate=KAIOZEN_V79_ACTIVE backbuffer-detection=stable-three-resource-periodic-ring triplet-period-proof=4-cycles dynamic-largest-group-selection=disabled locked-present-resource-input-filter-bypass=enabled reverse-present-barrier=not-required frame-boundary=submitted-command-list-replay static-command-list-writer-recovery=enabled recording-time-event-capture=enabled rtv-tracking=enabled copy-resolve-tracking=enabled present-frame-writers=24 backward-depth=6 baseline-present-frames=8 baseline-capture-freeze=enabled post-settings-present-frames=4 signal-file=C:/kaiozen-v79-settings-returned.signal commands_modified=0.");
                reshade::log::message(
                    reshade::log::level::info,
                    "D3DMetal RTX presented-frame producer chain v79 R4: ACTIVE frozen-triplet-source=recording-time-OMSetRenderTargets frame-boundary=submitted-command-list-replay command-list-identity-map=enabled static-command-list-writer-recovery=enabled recording-time-event-capture=enabled strict-lineage-required-for-present-capture=1 GPU-readback=disabled injected-copies=disabled injected-barriers=disabled commands_modified=0.");'''
replace_once(active_log_anchor, active_log_block, "V79 R4 active log")


source.write_text(text, encoding="utf-8")

Path("v79-r4-patch-report.txt").write_text(
    "\n".join([
        "V79_R4_SUBMITTED_COMMAND_LIST_BOUNDARY_PATCH_OK",
        "BINARY_MANIFEST=V79_R4_BINARY_MARKER_MANIFEST_R4_SUBMITTED_COMMAND_LIST_BOUNDARY",
        "TRIPLET_SOURCE=RECORDING_TIME_OM_SET_RENDER_TARGETS",
        "FRAME_BOUNDARY=SUBMITTED_COMMAND_LIST_REPLAY",
        "COMMAND_LIST_IDENTITY_MAP=ENABLED",
        "STATIC_COMMAND_LIST_WRITER_RECOVERY=ENABLED",
        "RECORDING_TIME_EVENT_CAPTURE=ENABLED",
        "STRICT_LINEAGE_REQUIRED_FOR_PRESENT_CAPTURE=YES",
        "GPU_READBACK=DISABLED",
        "COMMANDS_MODIFIED=NO",
        "RESULT=PASS",
        "",
    ]),
    encoding="ascii",
)

print("V79_R4_SUBMITTED_COMMAND_LIST_BOUNDARY_PATCH_OK")
