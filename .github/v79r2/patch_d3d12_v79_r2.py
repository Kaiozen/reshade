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


manifest_anchor = r'''extern "C" __declspec(dllexport) const char *kaiozen_v79_binary_marker_manifest()
{
    static const char manifest[] =
        "V79_BINARY_MARKER_MANIFEST_R1_PRESENT_BACKBUFFER_CHAIN\n"
        "D3DMetal RTX presented-frame producer chain v79: ACTIVE\n"
        "KAIOZEN_V79_ACTIVE\n"
        "BACKBUFFER_BEGIN_CANDIDATE\n"
        "PRESENT_BACKBUFFER_CAPTURE\n"
        "PRESENT_CANDIDATE_REJECTED\n"
        "PRESENT_WRITER\n"
        "PRESENT_CHAIN_NODE\n"
        "V79_BASELINE_READY\n"
        "SETTINGS_RETURN_SIGNAL_ACCEPTED\n"
        "PRESENT_CHAIN_COMPARISON_RESULT\n"
        "signal-file=C:/kaiozen-v79-settings-returned.signal\n"
        "trigger=radial-settings-return-to-world\n"
        "commands_modified=0\n";
    return manifest;
}

namespace
'''
manifest_block = manifest_anchor[:-len("namespace\n")] + r'''extern "C" __declspec(dllexport) const char *kaiozen_v79_r2_binary_marker_manifest()
{
    static const char manifest[] =
        "V79_R2_BINARY_MARKER_MANIFEST_R2_RTV_CYCLE_FRAME_BOUNDARY\n"
        "D3DMetal RTX presented-frame producer chain v79 R2: ACTIVE\n"
        "SWAPCHAIN_GROUP_SELECTED\n"
        "RTV_CYCLE_BIND\n"
        "RTV_CYCLE_FRAME\n"
        "baseline-capture-freeze=enabled\n"
        "reverse-present-barrier=not-required\n"
        "commands_modified=0\n";
    return manifest;
}

namespace
'''
replace_once(manifest_anchor, manifest_block, "V79 R2 exported manifest")

state_anchor = r'''    static constexpr size_t v79_max_chain_depth = 6;
'''
state_block = state_anchor + r'''
    struct v79_r2_begin_candidate
    {
        uint64_t resource_id = 0;
        unsigned int format = 0;
        UINT64 width = 0;
        UINT height = 0;
    };

    static std::vector<v79_r2_begin_candidate> s_v79_r2_begin_candidates;
    static std::unordered_map<uint64_t, bool> s_v79_r2_selected_resources;
    static unsigned int s_v79_r2_selected_format = 0;
    static UINT64 s_v79_r2_selected_width = 0;
    static UINT s_v79_r2_selected_height = 0;
    static uint64_t s_v79_r2_last_bound_resource = 0;
    static std::atomic<uint64_t> s_v79_r2_group_selected_count = 0;
    static std::atomic<uint64_t> s_v79_r2_cycle_bind_count = 0;
    static std::atomic<uint64_t> s_v79_r2_cycle_frame_count = 0;
'''
replace_once(state_anchor, state_block, "V79 R2 state")

forward_anchor = r'''    void STDMETHODCALLTYPE v79_trace_create_rtv(
'''
forward_block = r'''    void v79_process_present(ID3D12Resource *resource);

''' + forward_anchor
replace_once(forward_anchor, forward_block, "V79 R2 process-present declaration")

helper_anchor = r'''    void STDMETHODCALLTYPE v79_trace_om_set_render_targets(
'''
helper_block = r'''    void v79_r2_note_begin_candidate(const v55_resource_info &resource)
    {
        bool changed = false;
        size_t selected_count = 0;
        unsigned int selected_format = 0;
        UINT64 selected_width = 0;
        UINT selected_height = 0;
        {
            std::lock_guard<std::mutex> lock(s_v79_mutex);
            const auto existing = std::find_if(
                s_v79_r2_begin_candidates.begin(),
                s_v79_r2_begin_candidates.end(),
                [&resource](const v79_r2_begin_candidate &candidate)
                {
                    return candidate.resource_id == resource.resource_id;
                });
            if (existing == s_v79_r2_begin_candidates.end())
            {
                v79_r2_begin_candidate candidate = {};
                candidate.resource_id = resource.resource_id;
                candidate.format = resource.format;
                candidate.width = resource.width;
                candidate.height = resource.height;
                s_v79_r2_begin_candidates.push_back(candidate);
            }

            size_t best_count = 0;
            UINT64 best_area = 0;
            unsigned int best_format = 0;
            UINT64 best_width = 0;
            UINT best_height = 0;
            for (const auto &candidate : s_v79_r2_begin_candidates)
            {
                size_t count = 0;
                for (const auto &other : s_v79_r2_begin_candidates)
                {
                    if (candidate.format == other.format &&
                        candidate.width == other.width &&
                        candidate.height == other.height)
                        ++count;
                }
                const UINT64 area = candidate.width *
                    static_cast<UINT64>(candidate.height);
                if (count > best_count ||
                    (count == best_count && area > best_area))
                {
                    best_count = count;
                    best_area = area;
                    best_format = candidate.format;
                    best_width = candidate.width;
                    best_height = candidate.height;
                }
            }

            if (best_count >= 2)
            {
                changed =
                    s_v79_r2_selected_format != best_format ||
                    s_v79_r2_selected_width != best_width ||
                    s_v79_r2_selected_height != best_height ||
                    s_v79_r2_selected_resources.size() != best_count;
                s_v79_r2_selected_format = best_format;
                s_v79_r2_selected_width = best_width;
                s_v79_r2_selected_height = best_height;
                s_v79_r2_selected_resources.clear();
                for (const auto &candidate : s_v79_r2_begin_candidates)
                {
                    if (candidate.format == best_format &&
                        candidate.width == best_width &&
                        candidate.height == best_height)
                        s_v79_r2_selected_resources[candidate.resource_id] = true;
                }
                selected_count = s_v79_r2_selected_resources.size();
                selected_format = best_format;
                selected_width = best_width;
                selected_height = best_height;
            }
        }

        if (changed && selected_count >= 2)
        {
            const uint64_t count =
                s_v79_r2_group_selected_count.fetch_add(
                    1, std::memory_order_acq_rel) + 1;
            reshade::log::message(
                reshade::log::level::info,
                "D3DMetal RTX presented-frame producer chain v79 R2: SWAPCHAIN_GROUP_SELECTED count=%llu member_count=%zu format=%u dimensions=%llux%u selection=largest-repeated-begin-signature frame-boundary=rtv-resource-cycle reverse-present-barrier=not-required commands_modified=0.",
                static_cast<unsigned long long>(count),
                selected_count,
                selected_format,
                static_cast<unsigned long long>(selected_width),
                selected_height);
        }
    }

    void v79_r2_note_rtv_cycle(const std::vector<uint64_t> &resources)
    {
        if (!v79_is_active() || resources.empty() ||
            s_v79_result_ready.load(std::memory_order_acquire))
            return;

        uint64_t current = 0;
        uint64_t previous = 0;
        size_t group_size = 0;
        {
            std::lock_guard<std::mutex> lock(s_v79_mutex);
            group_size = s_v79_r2_selected_resources.size();
            if (group_size < 2)
                return;
            for (const uint64_t resource_id : resources)
            {
                const auto selected =
                    s_v79_r2_selected_resources.find(resource_id);
                if (selected != s_v79_r2_selected_resources.end() &&
                    selected->second)
                {
                    current = resource_id;
                    break;
                }
            }
            if (current == 0)
                return;

            previous = s_v79_r2_last_bound_resource;
            s_v79_r2_last_bound_resource = current;
            s_v79_active_backbuffers[current] = true;
            if (previous == 0)
                s_v79_frame_writers[current].clear();
            else if (previous != current)
            {
                s_v79_active_backbuffers[previous] = false;
                s_v79_frame_writers[current].clear();
            }
        }

        const uint64_t bind_count =
            s_v79_r2_cycle_bind_count.fetch_add(
                1, std::memory_order_acq_rel) + 1;
        if (bind_count <= 12)
            reshade::log::message(
                reshade::log::level::info,
                "D3DMetal RTX presented-frame producer chain v79 R2: RTV_CYCLE_BIND count=%llu resource_id=%llu previous_resource_id=%llu group_size=%zu switched=%u strict_rewritten_proof=%u commands_modified=0.",
                static_cast<unsigned long long>(bind_count),
                static_cast<unsigned long long>(current),
                static_cast<unsigned long long>(previous),
                group_size,
                previous != 0 && previous != current ? 1u : 0u,
                s_v61_rewritten_steady_state_seen.load(
                    std::memory_order_acquire) ? 1u : 0u);

        if (previous == 0 || previous == current ||
            !s_v61_rewritten_steady_state_seen.load(
                std::memory_order_acquire))
            return;

        v55_resource_info previous_info = {};
        if (!v55_get_resource(previous, previous_info) ||
            previous_info.resource == nullptr)
            return;

        const uint64_t frame =
            s_v79_r2_cycle_frame_count.fetch_add(
                1, std::memory_order_acq_rel) + 1;
        if (frame <= 16 || frame % 120 == 0)
            reshade::log::message(
                reshade::log::level::info,
                "D3DMetal RTX presented-frame producer chain v79 R2: RTV_CYCLE_FRAME frame=%llu completed_resource_id=%llu next_resource_id=%llu format=%u dimensions=%llux%u boundary=rtv-resource-switch reverse-present-barrier=not-required commands_modified=0.",
                static_cast<unsigned long long>(frame),
                static_cast<unsigned long long>(previous),
                static_cast<unsigned long long>(current),
                previous_info.format,
                static_cast<unsigned long long>(previous_info.width),
                previous_info.height);
        v79_process_present(previous_info.resource);
    }

''' + helper_anchor
replace_once(helper_anchor, helper_block, "V79 R2 cycle helpers")

om_end_anchor = r'''        std::lock_guard<std::mutex> lock(s_v79_mutex);
        s_v79_current_rtvs[command_list] = std::move(resources);
    }

    bool v79_collect_bound_resources(
'''
om_end_block = r'''        {
            std::lock_guard<std::mutex> lock(s_v79_mutex);
            s_v79_current_rtvs[command_list] = resources;
        }
        v79_r2_note_rtv_cycle(resources);
    }

    bool v79_collect_bound_resources(
'''
replace_once(om_end_anchor, om_end_block, "V79 R2 OMSetRenderTargets cycle")

baseline_anchor = r'''        if (!post_phase)
        {
            const uint64_t frame = s_v79_baseline_present_count.fetch_add(
                1, std::memory_order_acq_rel) + 1;
            {
                std::lock_guard<std::mutex> lock(s_v79_mutex);
                s_v79_baseline_capture = capture;
            }
            if (frame >= 8)
            {
                bool expected = false;
                if (s_v79_baseline_ready.compare_exchange_strong(
                        expected, true, std::memory_order_acq_rel))
                {
                    v79_log_capture("baseline", capture);
                    reshade::log::message(
                        reshade::log::level::info,
                        "D3DMetal RTX presented-frame producer chain v79: V79_BASELINE_READY present_frames=%llu present_resource_id=%llu writer_count=%zu chain_depth=%zu candidate_filter=never-seen-as-input ready_for_radial_settings=1 commands_modified=0.",
                        static_cast<unsigned long long>(frame),
                        static_cast<unsigned long long>(capture.present_resource_id),
                        capture.writers.size(), capture.chain.size());
                }
            }
        }
'''
baseline_block = r'''        if (!post_phase)
        {
            if (s_v79_baseline_ready.load(std::memory_order_acquire))
                return;
            const uint64_t frame = s_v79_baseline_present_count.fetch_add(
                1, std::memory_order_acq_rel) + 1;
            {
                std::lock_guard<std::mutex> lock(s_v79_mutex);
                s_v79_baseline_capture = capture;
            }
            if (frame >= 8)
            {
                bool expected = false;
                if (s_v79_baseline_ready.compare_exchange_strong(
                        expected, true, std::memory_order_acq_rel))
                {
                    v79_log_capture("baseline", capture);
                    reshade::log::message(
                        reshade::log::level::info,
                        "D3DMetal RTX presented-frame producer chain v79: V79_BASELINE_READY present_frames=%llu present_resource_id=%llu writer_count=%zu chain_depth=%zu candidate_filter=never-seen-as-input baseline-capture-freeze=enabled ready_for_radial-settings=1 commands_modified=0.",
                        static_cast<unsigned long long>(frame),
                        static_cast<unsigned long long>(capture.present_resource_id),
                        capture.writers.size(), capture.chain.size());
                }
            }
        }
'''
replace_once(baseline_anchor, baseline_block, "V79 R2 baseline freeze")

begin_anchor = r'''            if (begin)
            {
                const uint64_t count = s_v79_begin_candidate_count.fetch_add(
'''
begin_block = r'''            if (begin)
            {
                v79_r2_note_begin_candidate(resource);
                const uint64_t count = s_v79_begin_candidate_count.fetch_add(
'''
replace_once(begin_anchor, begin_block, "V79 R2 begin candidate grouping")

active_anchor = r'''"D3DMetal RTX presented-frame producer chain v79: ACTIVE runtime-gate=KAIOZEN_V79_ACTIVE backbuffer-detection=present-like-common-to-output+output-to-common rtv-tracking=enabled copy-resolve-tracking=enabled present-frame-writers=24 backward-depth=6 baseline-present-frames=8 post-settings-present-frames=4 signal-file=C:/kaiozen-v79-settings-returned.signal commands_modified=0.");'''
active_block = r'''"D3DMetal RTX presented-frame producer chain v79: ACTIVE runtime-gate=KAIOZEN_V79_ACTIVE backbuffer-detection=repeated-begin-signature+rtv-cycle-frame-boundary reverse-present-barrier=not-required rtv-tracking=enabled copy-resolve-tracking=enabled present-frame-writers=24 backward-depth=6 baseline-present-frames=8 baseline-capture-freeze=enabled post-settings-present-frames=4 signal-file=C:/kaiozen-v79-settings-returned.signal commands_modified=0.");'''
replace_once(active_anchor, active_block, "V79 R2 active marker")

source.write_text(text, encoding="utf-8", newline="\n")
Path("v79-r2-patch-report.txt").write_text(
    "\n".join([
        "V79_R2_RTV_CYCLE_FRAME_BOUNDARY_PATCH_OK",
        "BINARY_MANIFEST=V79_R2_BINARY_MARKER_MANIFEST_R2_RTV_CYCLE_FRAME_BOUNDARY",
        "PRESENT_BOUNDARY=RTV_RESOURCE_CYCLE",
        "SWAPCHAIN_SELECTION=LARGEST_REPEATED_BEGIN_SIGNATURE",
        "REVERSE_PRESENT_BARRIER_REQUIRED=NO",
        "BASELINE_CAPTURE_FREEZE=YES",
        "BASELINE_PRESENT_FRAMES=8",
        "POST_SETTINGS_PRESENT_FRAMES=4",
        "GPU_READBACK=DISABLED",
        "COMMANDS_MODIFIED=NO",
        "RESULT=PASS",
        "",
    ]),
    encoding="ascii",
)
print("V79_R2_RTV_CYCLE_FRAME_BOUNDARY_PATCH_OK")
