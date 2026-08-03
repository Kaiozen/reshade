from pathlib import Path

source = Path('source/d3d12/d3d12.cpp')
if not source.is_file():
    raise SystemExit('ERROR: source/d3d12/d3d12.cpp is missing')
text = source.read_text(encoding='utf-8')


def replace_once(old: str, new: str, label: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'ERROR: {label} anchor count was {count}, expected 1')
    text = text.replace(old, new, 1)


# Keep the V77 strings in the PE image even with link-time string folding.
manifest_anchor = '''    return manifest;\n}\n\nnamespace\n'''
manifest_block = r'''    return manifest;
}

extern "C" __declspec(dllexport) const char *kaiozen_v77_binary_marker_manifest()
{
    static const char manifest[] =
        "V77_BINARY_MARKER_MANIFEST_R1_SETTINGS_RESUME_DIFFERENTIAL\n"
        "D3DMetal RTX settings-resume resource differential v77: ACTIVE\n"
        "KAIOZEN_V77_ACTIVE\n"
        "V77_BASELINE_READY\n"
        "SETTINGS_SIGNAL_ACCEPTED\n"
        "DIFFERENTIAL_CANDIDATE\n"
        "DIFFERENTIAL_RESULT\n"
        "signal-file=C:/kaiozen-v77-settings-returned.signal\n"
        "trigger=radial-settings-return-to-world\n"
        "commands_modified=0\n";
    return manifest;
}

namespace
'''
replace_once(manifest_anchor, manifest_block, 'V77 exported binary marker manifest')

state_anchor = '''    static constexpr UINT v76_row_pitch = 256;\n'''
state_block = state_anchor + r'''

    struct v77_slot_record
    {
        uintptr_t pipeline = 0;
        bool graphics = false;
        unsigned int event_class = 0;
        unsigned int descriptor_kind = 0; // 2=SRV, 3=UAV
        unsigned int binding_kind = 1; // 1=table
        UINT root_parameter = 0;
        UINT descriptor_offset = 0;
        unsigned int format = 0;
        unsigned int dimension = 0;
        UINT64 width = 0;
        UINT height = 0;
        unsigned int flags = 0;
        uint64_t uses = 0;
        std::vector<uint64_t> resource_ids;
    };

    struct v77_phase_state
    {
        uint64_t events = 0;
        std::unordered_map<std::string, v77_slot_record> slots;
    };

    static std::once_flag s_v77_active_once;
    static std::atomic<bool> s_v77_active = false;
    static std::atomic<bool> s_v77_baseline_ready = false;
    static std::atomic<bool> s_v77_manual_signal_accepted = false;
    static std::atomic<bool> s_v77_post_phase = false;
    static std::atomic<bool> s_v77_result_ready = false;
    static std::atomic<bool> s_v77_compare_claimed = false;
    static std::atomic<uint64_t> s_v77_signal_checks = 0;
    static std::atomic<uint64_t> s_v77_last_signal_check_tick_ms = 0;
    static std::atomic<uint64_t> s_v77_observed_event_count = 0;
    static std::mutex s_v77_mutex;
    static v77_phase_state s_v77_baseline;
    static v77_phase_state s_v77_post;
    static constexpr uint64_t v77_events_per_phase = 120;
    static constexpr size_t v77_max_slots_per_phase = 4096;
'''
replace_once(state_anchor, state_block, 'V77 state')

proto_anchor = '''    bool v76_is_active();\n    bool v76_apply_canary_after_dispatch(\n        ID3D12GraphicsCommandList *command_list,\n        UINT max_command_count);\n    void v76_on_execute_command_lists(\n        ID3D12CommandQueue *queue,\n        UINT count,\n        ID3D12CommandList *const *command_lists);\n\n\t// V33 and V36 define these helpers later in the same namespace. V54 is\n'''
proto_block = '''    bool v76_is_active();\n    bool v76_apply_canary_after_dispatch(\n        ID3D12GraphicsCommandList *command_list,\n        UINT max_command_count);\n    void v76_on_execute_command_lists(\n        ID3D12CommandQueue *queue,\n        UINT count,\n        ID3D12CommandList *const *command_lists);\n    bool v77_is_active();\n    void v77_observe_event(\n        ID3D12GraphicsCommandList *command_list,\n        const char *kind,\n        bool graphics);\n\n\t// V33 and V36 define these helpers later in the same namespace. V54 is\n'''
replace_once(proto_anchor, proto_block, 'V77 prototypes')

active_anchor = '''                (void)v76_is_active();\n\t\t\t\treshade::log::message(\n\t\t\t\t\treshade::log::level::info,\n                    "D3DMetal RTX canary mutation verification v76: ACTIVE runtime-gate=KAIOZEN_V76_ACTIVE v75-runtime-disabled=1 exact-consumer-signature=u1-root0-offset17-srv outputs=root0-offsets35,36 patterns=magenta|cyan persistent-canary-clears=enabled one-shot-before-after-readback=enabled sample_points=64,64|1380,888 samples=8 readback_bytes=4096 row_pitch=256 placement_stride=512 queue-fence=enabled visual-timer-requires-readback-match=1 commands_modified=1.");\n'''
active_block = active_anchor + r'''                (void)v77_is_active();
                reshade::log::message(
                    reshade::log::level::info,
                    "D3DMetal RTX settings-resume resource differential v77: ACTIVE runtime-gate=KAIOZEN_V77_ACTIVE trigger=radial-settings-return-to-world signal-file=C:/kaiozen-v77-settings-returned.signal phases=world-baseline,post-settings-resume events-per-phase=120 descriptor-scan-limit=96 textures-only=1 physical-resource-differential=1 feedback-ranking=1 readback=disabled resource-copies=disabled resource-barriers=disabled commands_modified=0.");
'''
replace_once(active_anchor, active_block, 'V77 active marker')

execute_anchor = '''            v76_apply_canary_after_dispatch(\n                command_list,\n                max_command_count);\n'''
execute_block = execute_anchor + '''            v77_observe_event(\n                command_list,\n                "execute-indirect-compute",\n                false);\n'''
replace_once(execute_anchor, execute_block, 'V77 execute-indirect observation')

dispatch_anchor = '''        v66_observe_consumer_dispatch(\n            command_list, "direct-compute", group_x, group_y, group_z);\n'''
dispatch_block = dispatch_anchor + '''        v77_observe_event(\n            command_list, "direct-compute", false);\n'''
replace_once(dispatch_anchor, dispatch_block, 'V77 direct dispatch observation')

draw_anchor = '''        v66_observe_graphics_draw(command_list, "draw-instanced");\n'''
draw_block = draw_anchor + '''        v77_observe_event(\n            command_list, "draw-instanced", true);\n'''
replace_once(draw_anchor, draw_block, 'V77 draw-instanced observation')

draw_indexed_anchor = '''        v66_observe_graphics_draw(command_list, "draw-indexed-instanced");\n'''
draw_indexed_block = draw_indexed_anchor + '''        v77_observe_event(\n            command_list, "draw-indexed-instanced", true);\n'''
replace_once(draw_indexed_anchor, draw_indexed_block, 'V77 draw-indexed observation')

impl_anchor = '''    void STDMETHODCALLTYPE v66_trace_dispatch(\n'''
impl = r'''    bool v77_is_active()
    {
        std::call_once(
            s_v77_active_once,
            []()
            {
                char value[16] = {};
                const DWORD length = GetEnvironmentVariableA(
                    "KAIOZEN_V77_ACTIVE", value,
                    static_cast<DWORD>(sizeof(value)));
                const bool active = length != 0 && length < sizeof(value) &&
                    (value[0] == '1' || value[0] == 'Y' || value[0] == 'y' ||
                     value[0] == 'T' || value[0] == 't');
                s_v77_active.store(active, std::memory_order_release);
                reshade::log::message(
                    reshade::log::level::info,
                    "D3DMetal RTX settings-resume resource differential v77: RUNTIME_GATE active=%u environment=%s selection_timing=dll-startup commands_modified=0.",
                    active ? 1u : 0u,
                    length != 0 ? value : "unset");
            });
        return s_v77_active.load(std::memory_order_acquire);
    }

    unsigned int v77_event_class(const char *kind)
    {
        if (kind == nullptr)
            return 0;
        if (std::strcmp(kind, "execute-indirect-compute") == 0)
            return 1;
        if (std::strcmp(kind, "direct-compute") == 0)
            return 2;
        if (std::strcmp(kind, "draw-instanced") == 0)
            return 3;
        if (std::strcmp(kind, "draw-indexed-instanced") == 0)
            return 4;
        return 5;
    }

    const char *v77_event_class_name(unsigned int value)
    {
        switch (value)
        {
        case 1: return "execute-indirect-compute";
        case 2: return "direct-compute";
        case 3: return "draw-instanced";
        case 4: return "draw-indexed-instanced";
        default: return "other";
        }
    }

    std::string v77_make_slot_key(
        const v77_slot_record &slot)
    {
        std::ostringstream stream;
        stream << std::hex << slot.pipeline << std::dec
            << '|' << (slot.graphics ? 1 : 0)
            << '|' << slot.event_class
            << '|' << slot.descriptor_kind
            << '|' << slot.binding_kind
            << '|' << slot.root_parameter
            << '|' << slot.descriptor_offset
            << '|' << slot.format
            << '|' << slot.dimension
            << '|' << slot.width
            << '|' << slot.height
            << '|' << slot.flags;
        return stream.str();
    }

    void v77_add_resource_id(
        std::vector<uint64_t> &ids,
        uint64_t resource_id)
    {
        if (resource_id == 0 ||
            std::find(ids.begin(), ids.end(), resource_id) != ids.end())
            return;
        if (ids.size() < 16)
            ids.push_back(resource_id);
    }

    bool v77_has_overlap(
        const std::vector<uint64_t> &left,
        const std::vector<uint64_t> &right)
    {
        for (const uint64_t value : left)
            if (std::find(right.begin(), right.end(), value) != right.end())
                return true;
        return false;
    }

    std::string v77_ids_to_string(
        const std::vector<uint64_t> &ids)
    {
        std::ostringstream stream;
        for (size_t index = 0; index < ids.size(); ++index)
        {
            if (index != 0)
                stream << ',';
            stream << ids[index];
        }
        return stream.str();
    }

    void v77_record_slot(
        v77_phase_state &phase,
        const v77_slot_record &candidate,
        uint64_t resource_id)
    {
        if (phase.slots.size() >= v77_max_slots_per_phase)
            return;
        const std::string key = v77_make_slot_key(candidate);
        auto found = phase.slots.find(key);
        if (found == phase.slots.end())
        {
            v77_slot_record stored = candidate;
            stored.uses = 1;
            v77_add_resource_id(stored.resource_ids, resource_id);
            phase.slots.emplace(key, std::move(stored));
        }
        else
        {
            ++found->second.uses;
            v77_add_resource_id(found->second.resource_ids, resource_id);
        }
    }

    bool v77_phase_resource_feedback(
        const v77_phase_state &phase,
        const std::vector<uint64_t> &ids)
    {
        bool read = false;
        bool write = false;
        for (const auto &entry : phase.slots)
        {
            const auto &slot = entry.second;
            bool intersects = false;
            for (const uint64_t id : ids)
            {
                if (std::find(
                        slot.resource_ids.begin(),
                        slot.resource_ids.end(), id) !=
                    slot.resource_ids.end())
                {
                    intersects = true;
                    break;
                }
            }
            if (!intersects)
                continue;
            read = read || slot.descriptor_kind == 2;
            write = write || slot.descriptor_kind == 3;
            if (read && write)
                return true;
        }
        return false;
    }

    struct v77_ranked_candidate
    {
        int score = 0;
        bool overlap = false;
        bool feedback_baseline = false;
        bool feedback_post = false;
        v77_slot_record baseline;
        v77_slot_record post;
    };

    void v77_compare_and_log()
    {
        v77_phase_state baseline;
        v77_phase_state post;
        {
            std::lock_guard<std::mutex> lock(s_v77_mutex);
            baseline = s_v77_baseline;
            post = s_v77_post;
        }

        std::vector<v77_ranked_candidate> ranked;
        uint64_t matched = 0;
        uint64_t recreated = 0;
        uint64_t persistent = 0;
        uint64_t post_only = 0;

        for (const auto &entry : baseline.slots)
        {
            const auto found = post.slots.find(entry.first);
            if (found == post.slots.end())
                continue;
            ++matched;
            v77_ranked_candidate candidate = {};
            candidate.baseline = entry.second;
            candidate.post = found->second;
            candidate.overlap = v77_has_overlap(
                candidate.baseline.resource_ids,
                candidate.post.resource_ids);
            candidate.feedback_baseline = v77_phase_resource_feedback(
                baseline, candidate.baseline.resource_ids);
            candidate.feedback_post = v77_phase_resource_feedback(
                post, candidate.post.resource_ids);

            if (candidate.overlap)
            {
                ++persistent;
                continue;
            }

            ++recreated;
            candidate.score = 100;
            if (candidate.post.descriptor_kind == 3)
                candidate.score += 35;
            if (candidate.feedback_baseline || candidate.feedback_post)
                candidate.score += 45;
            if (candidate.post.width >= 2000 && candidate.post.height >= 1000)
                candidate.score += 25;
            if (candidate.post.width <= 1024 && candidate.post.height <= 1024)
                candidate.score += 15;
            if (candidate.post.format == 10 || candidate.post.format == 2)
                candidate.score += 10;
            if (candidate.post.uses >= 8 && candidate.baseline.uses >= 8)
                candidate.score += 10;
            ranked.push_back(std::move(candidate));
        }

        for (const auto &entry : post.slots)
            if (baseline.slots.find(entry.first) == baseline.slots.end())
                ++post_only;

        std::sort(
            ranked.begin(), ranked.end(),
            [](const v77_ranked_candidate &left,
               const v77_ranked_candidate &right)
            {
                if (left.score != right.score)
                    return left.score > right.score;
                return left.post.uses > right.post.uses;
            });

        const size_t report_count = ranked.size() < 24 ? ranked.size() : 24;
        for (size_t index = 0; index < report_count; ++index)
        {
            const auto &candidate = ranked[index];
            const char *classification =
                candidate.post.descriptor_kind == 3 ?
                    ((candidate.feedback_baseline || candidate.feedback_post) ?
                        "recreated-feedback-uav" : "recreated-uav") :
                    ((candidate.feedback_baseline || candidate.feedback_post) ?
                        "recreated-feedback-srv" : "recreated-srv");
            reshade::log::message(
                reshade::log::level::info,
                "D3DMetal RTX settings-resume resource differential v77: DIFFERENTIAL_CANDIDATE rank=%zu score=%d pipeline_state=%p event_class=%s graphics=%u descriptor_kind=%s binding_kind=table root_parameter=%u descriptor_offset=%u format=%u dimension=%u width=%llu height=%u flags=0x%X baseline_uses=%llu post_uses=%llu baseline_ids=%s post_ids=%s physical_overlap=0 feedback_baseline=%u feedback_post=%u classification=%s commands_modified=0.",
                index + 1,
                candidate.score,
                reinterpret_cast<void *>(candidate.post.pipeline),
                v77_event_class_name(candidate.post.event_class),
                candidate.post.graphics ? 1u : 0u,
                candidate.post.descriptor_kind == 3 ? "uav" : "srv",
                candidate.post.root_parameter,
                candidate.post.descriptor_offset,
                candidate.post.format,
                candidate.post.dimension,
                static_cast<unsigned long long>(candidate.post.width),
                candidate.post.height,
                candidate.post.flags,
                static_cast<unsigned long long>(candidate.baseline.uses),
                static_cast<unsigned long long>(candidate.post.uses),
                v77_ids_to_string(candidate.baseline.resource_ids).c_str(),
                v77_ids_to_string(candidate.post.resource_ids).c_str(),
                candidate.feedback_baseline ? 1u : 0u,
                candidate.feedback_post ? 1u : 0u,
                classification);
        }

        reshade::log::message(
            reshade::log::level::info,
            "D3DMetal RTX settings-resume resource differential v77: DIFFERENTIAL_RESULT success=%u baseline_events=%llu post_events=%llu baseline_slots=%zu post_slots=%zu matched_slots=%llu recreated_slots=%llu persistent_slots=%llu post_only_slots=%llu ranked_candidates=%zu strict_rewritten_proof=%u trigger=radial-settings-return-to-world commands_modified=0.",
            matched != 0 && recreated != 0 ? 1u : 0u,
            static_cast<unsigned long long>(baseline.events),
            static_cast<unsigned long long>(post.events),
            baseline.slots.size(),
            post.slots.size(),
            static_cast<unsigned long long>(matched),
            static_cast<unsigned long long>(recreated),
            static_cast<unsigned long long>(persistent),
            static_cast<unsigned long long>(post_only),
            report_count,
            s_v61_rewritten_steady_state_seen.load(
                std::memory_order_acquire) ? 1u : 0u);
        s_v77_result_ready.store(true, std::memory_order_release);
    }

    void v77_check_manual_signal()
    {
        if (!s_v77_baseline_ready.load(std::memory_order_acquire) ||
            s_v77_manual_signal_accepted.load(std::memory_order_acquire))
            return;
        const uint64_t now = GetTickCount64();
        uint64_t previous = s_v77_last_signal_check_tick_ms.load(
            std::memory_order_acquire);
        if (now < previous + 100 ||
            !s_v77_last_signal_check_tick_ms.compare_exchange_strong(
                previous, now, std::memory_order_acq_rel))
            return;
        const uint64_t check_index = s_v77_signal_checks.fetch_add(
            1, std::memory_order_acq_rel) + 1;
        const DWORD attributes = GetFileAttributesW(
            L"C:\\kaiozen-v77-settings-returned.signal");
        if (attributes == INVALID_FILE_ATTRIBUTES ||
            (attributes & FILE_ATTRIBUTE_DIRECTORY) != 0)
            return;
        bool expected = false;
        if (!s_v77_manual_signal_accepted.compare_exchange_strong(
                expected, true, std::memory_order_acq_rel))
            return;
        s_v77_post_phase.store(true, std::memory_order_release);
        reshade::log::message(
            reshade::log::level::info,
            "D3DMetal RTX settings-resume resource differential v77: SETTINGS_SIGNAL_ACCEPTED accepted=1 check_index=%llu signal_file=C:/kaiozen-v77-settings-returned.signal phase=post-settings-resume commands_modified=0.",
            static_cast<unsigned long long>(check_index));
    }

    void v77_observe_event(
        ID3D12GraphicsCommandList *command_list,
        const char *kind,
        bool graphics)
    {
        if (!v77_is_active() || command_list == nullptr ||
            s_v77_result_ready.load(std::memory_order_acquire) ||
            !s_v66_world_consumer_found.load(std::memory_order_acquire))
            return;

        v77_check_manual_signal();
        const bool post_phase = s_v77_post_phase.load(
            std::memory_order_acquire);
        if (!post_phase && s_v77_baseline_ready.load(
                std::memory_order_acquire))
            return;

        v66_command_binding_state state = {};
        {
            std::lock_guard<std::mutex> lock(s_v66_binding_state_mutex);
            const auto found = s_v66_binding_states.find(command_list);
            if (found == s_v66_binding_states.end())
                return;
            state = found->second;
        }
        if (state.pipeline_state == nullptr)
            return;

        std::vector<v77_slot_record> observed;
        const auto &tables = graphics ?
            state.graphics_tables : state.compute_tables;
        for (const auto &table : tables)
        {
            v55_heap_info heap = {};
            UINT base_index = 0;
            if (!v55_find_heap_by_gpu(table.second, heap, base_index))
                continue;
            const UINT remaining = heap.count > base_index ?
                heap.count - base_index : 0;
            const UINT inspect = remaining < 96u ? remaining : 96u;
            for (UINT offset = 0; offset < inspect; ++offset)
            {
                const UINT64 handle = heap.gpu_start +
                    static_cast<UINT64>(base_index + offset) * heap.increment;
                v55_heap_info resolved_heap = {};
                UINT descriptor_index = 0;
                v55_descriptor_info descriptor = {};
                v55_resource_info resource = {};
                if (!v55_resolve_gpu_descriptor(
                        handle, resolved_heap, descriptor_index,
                        descriptor, resource))
                    continue;
                if ((descriptor.kind != 2 && descriptor.kind != 3) ||
                    resource.resource_id == 0 || resource.dimension <= 1)
                    continue;
                v77_slot_record slot = {};
                slot.pipeline = reinterpret_cast<uintptr_t>(state.pipeline_state);
                slot.graphics = graphics;
                slot.event_class = v77_event_class(kind);
                slot.descriptor_kind = descriptor.kind;
                slot.binding_kind = 1;
                slot.root_parameter = table.first;
                slot.descriptor_offset = offset;
                slot.format = descriptor.format != 0 ?
                    descriptor.format : resource.format;
                slot.dimension = resource.dimension;
                slot.width = resource.width;
                slot.height = resource.height;
                slot.flags = resource.flags;
                observed.push_back(slot);

                std::lock_guard<std::mutex> lock(s_v77_mutex);
                v77_phase_state &phase = post_phase ?
                    s_v77_post : s_v77_baseline;
                v77_record_slot(phase, slot, resource.resource_id);
            }
        }

        if (observed.empty())
            return;

        uint64_t phase_events = 0;
        size_t phase_slots = 0;
        {
            std::lock_guard<std::mutex> lock(s_v77_mutex);
            v77_phase_state &phase = post_phase ?
                s_v77_post : s_v77_baseline;
            ++phase.events;
            phase_events = phase.events;
            phase_slots = phase.slots.size();
        }
        s_v77_observed_event_count.fetch_add(1, std::memory_order_acq_rel);

        if (!post_phase && phase_events >= v77_events_per_phase)
        {
            bool expected = false;
            if (s_v77_baseline_ready.compare_exchange_strong(
                    expected, true, std::memory_order_acq_rel))
            {
                reshade::log::message(
                    reshade::log::level::info,
                    "D3DMetal RTX settings-resume resource differential v77: V77_BASELINE_READY ready=1 baseline_events=%llu baseline_slots=%zu strict_rewritten_proof=%u now_open_settings_from_radial_menu=1 commands_modified=0.",
                    static_cast<unsigned long long>(phase_events),
                    phase_slots,
                    s_v61_rewritten_steady_state_seen.load(
                        std::memory_order_acquire) ? 1u : 0u);
            }
        }
        else if (post_phase && phase_events >= v77_events_per_phase &&
                 !s_v77_result_ready.load(std::memory_order_acquire))
        {
            bool expected = false;
            if (s_v77_compare_claimed.compare_exchange_strong(
                    expected, true, std::memory_order_acq_rel))
                v77_compare_and_log();
        }
    }

'''
replace_once(impl_anchor, impl + impl_anchor, 'V77 implementation')

source.write_text(text, encoding='utf-8', newline='\n')
Path('v77-patch-report.txt').write_text(
    '\n'.join([
        'V77_SETTINGS_RESUME_DIFFERENTIAL_PATCH_OK',
        'RUNTIME_GATE=KAIOZEN_V77_ACTIVE',
        'TRIGGER=RADIAL_SETTINGS_RETURN_TO_WORLD',
        'SIGNAL_FILE=C:/kaiozen-v77-settings-returned.signal',
        'BASELINE_EVENTS=120',
        'POST_EVENTS=120',
        'DESCRIPTOR_SCAN_LIMIT=96',
        'TEXTURES_ONLY=YES',
        'PHYSICAL_RESOURCE_DIFFERENTIAL=YES',
        'FEEDBACK_RANKING=YES',
        'GPU_READBACK=DISABLED',
        'RESOURCE_COPIES=DISABLED',
        'RESOURCE_BARRIERS=DISABLED',
        'COMMANDS_MODIFIED=NO',
        'RESULT=PASS',
    ]) + '\n',
    encoding='ascii')
print('V77_SETTINGS_RESUME_DIFFERENTIAL_PATCH_OK')
