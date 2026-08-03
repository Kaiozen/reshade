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

manifest_anchor = r'''extern "C" __declspec(dllexport) const char *kaiozen_v79_r2_binary_marker_manifest()
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
manifest_block = manifest_anchor[:-len("namespace\n")] + r'''extern "C" __declspec(dllexport) const char *kaiozen_v79_r3_binary_marker_manifest()
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
replace_once(manifest_anchor, manifest_block, "V79 R3 exported manifest")

state_anchor = r'''    static std::atomic<uint64_t> s_v79_r2_cycle_frame_count = 0;
'''
state_block = state_anchor + r'''

    struct v79_r3_signature_sequence
    {
        unsigned int format = 0;
        UINT64 width = 0;
        UINT height = 0;
        std::vector<uint64_t> recent_switches;
    };

    static std::vector<v79_r3_signature_sequence> s_v79_r3_sequences;
    static std::unordered_map<uint64_t, bool> s_v79_r3_locked_resources;
    static unsigned int s_v79_r3_locked_format = 0;
    static UINT64 s_v79_r3_locked_width = 0;
    static UINT s_v79_r3_locked_height = 0;
    static uint64_t s_v79_r3_last_bound_resource = 0;
    static std::atomic<bool> s_v79_r3_triplet_locked = false;
    static std::atomic<uint64_t> s_v79_r3_triplet_lock_count = 0;
    static std::atomic<uint64_t> s_v79_r3_ring_bind_count = 0;
    static std::atomic<uint64_t> s_v79_r3_ring_frame_count = 0;
'''
replace_once(state_anchor, state_block, "V79 R3 state")

helper_anchor = r'''    void v79_r2_note_begin_candidate(const v55_resource_info &resource)
'''
helper_block = r'''    bool v79_r3_resource_had_begin(uint64_t resource_id)
    {
        for (const auto &candidate : s_v79_r2_begin_candidates)
            if (candidate.resource_id == resource_id)
                return true;
        return false;
    }

    bool v79_r3_resource_seen_as_input(uint64_t resource_id)
    {
        const auto found = s_v79_seen_as_input.find(resource_id);
        return found != s_v79_seen_as_input.end() && found->second;
    }

    bool v79_r3_is_locked_resource(uint64_t resource_id)
    {
        std::lock_guard<std::mutex> lock(s_v79_mutex);
        const auto found = s_v79_r3_locked_resources.find(resource_id);
        return found != s_v79_r3_locked_resources.end() && found->second;
    }

    bool v79_r3_last_four_cycles_are_triplet(
        const std::vector<uint64_t> &sequence,
        std::vector<uint64_t> &triplet)
    {
        triplet.clear();
        if (sequence.size() < 12)
            return false;
        const size_t start = sequence.size() - 12;
        const uint64_t a = sequence[start + 0];
        const uint64_t b = sequence[start + 1];
        const uint64_t c = sequence[start + 2];
        if (a == 0 || b == 0 || c == 0 || a == b || a == c || b == c)
            return false;
        for (size_t index = 3; index < 12; ++index)
            if (sequence[start + index] != sequence[start + (index % 3)])
                return false;
        triplet = {a, b, c};
        return true;
    }

    void v79_r3_observe_rtv_sequence(const std::vector<uint64_t> &resources)
    {
        if (!v79_is_active() || resources.empty() ||
            s_v79_result_ready.load(std::memory_order_acquire))
            return;

        uint64_t current = 0;
        uint64_t previous = 0;
        bool locked_now = false;
        std::vector<uint64_t> locked_triplet;
        unsigned int locked_format = 0;
        UINT64 locked_width = 0;
        UINT locked_height = 0;

        {
            std::lock_guard<std::mutex> lock(s_v79_mutex);
            if (!s_v79_r3_triplet_locked.load(std::memory_order_acquire))
            {
                for (const uint64_t resource_id : resources)
                {
                    v55_resource_info info = {};
                    if (!v55_get_resource(resource_id, info) ||
                        !v79_is_large_texture(info) ||
                        (info.flags & D3D12_RESOURCE_FLAG_ALLOW_RENDER_TARGET) == 0 ||
                        !v79_r3_resource_had_begin(resource_id))
                        continue;

                    auto tracker = std::find_if(
                        s_v79_r3_sequences.begin(),
                        s_v79_r3_sequences.end(),
                        [&info](const v79_r3_signature_sequence &candidate)
                        {
                            return candidate.format == info.format &&
                                candidate.width == info.width &&
                                candidate.height == info.height;
                        });
                    if (tracker == s_v79_r3_sequences.end())
                    {
                        v79_r3_signature_sequence value = {};
                        value.format = info.format;
                        value.width = info.width;
                        value.height = info.height;
                        s_v79_r3_sequences.push_back(value);
                        tracker = s_v79_r3_sequences.end() - 1;
                    }
                    if (tracker->recent_switches.empty() ||
                        tracker->recent_switches.back() != resource_id)
                    {
                        tracker->recent_switches.push_back(resource_id);
                        if (tracker->recent_switches.size() > 18)
                            tracker->recent_switches.erase(
                                tracker->recent_switches.begin(),
                                tracker->recent_switches.begin() +
                                    (tracker->recent_switches.size() - 18));
                    }

                    std::vector<uint64_t> triplet;
                    if (!v79_r3_last_four_cycles_are_triplet(
                            tracker->recent_switches, triplet))
                        continue;
                    bool valid = true;
                    for (const uint64_t member : triplet)
                        if (!v79_r3_resource_had_begin(member) ||
                            v79_r3_resource_seen_as_input(member))
                        {
                            valid = false;
                            break;
                        }
                    if (!valid)
                        continue;

                    s_v79_r3_locked_resources.clear();
                    for (const uint64_t member : triplet)
                        s_v79_r3_locked_resources[member] = true;
                    s_v79_r3_locked_format = info.format;
                    s_v79_r3_locked_width = info.width;
                    s_v79_r3_locked_height = info.height;
                    s_v79_r3_last_bound_resource = resource_id;
                    s_v79_r3_triplet_locked.store(
                        true, std::memory_order_release);
                    locked_now = true;
                    locked_triplet = triplet;
                    locked_format = info.format;
                    locked_width = info.width;
                    locked_height = info.height;
                    current = resource_id;
                    s_v79_active_backbuffers[current] = true;
                    s_v79_frame_writers[current].clear();
                    break;
                }
            }

            if (s_v79_r3_triplet_locked.load(std::memory_order_acquire))
            {
                for (const uint64_t resource_id : resources)
                {
                    const auto found =
                        s_v79_r3_locked_resources.find(resource_id);
                    if (found != s_v79_r3_locked_resources.end() &&
                        found->second)
                    {
                        current = resource_id;
                        break;
                    }
                }
                if (current == 0)
                    return;
                previous = s_v79_r3_last_bound_resource;
                s_v79_r3_last_bound_resource = current;
                s_v79_active_backbuffers[current] = true;
                if (previous == 0)
                    s_v79_frame_writers[current].clear();
                else if (previous != current)
                {
                    s_v79_active_backbuffers[previous] = false;
                    s_v79_frame_writers[current].clear();
                }
            }
        }

        if (locked_now)
        {
            const uint64_t lock_count =
                s_v79_r3_triplet_lock_count.fetch_add(
                    1, std::memory_order_acq_rel) + 1;
            reshade::log::message(
                reshade::log::level::info,
                "D3DMetal RTX presented-frame producer chain v79 R3: SWAPCHAIN_TRIPLET_LOCKED count=%llu members=%llu,%llu,%llu format=%u dimensions=%llux%u proof=three-distinct-resources-four-exact-cycles begin-transition-required=1 never-seen-as-input-at-lock=1 dynamic-largest-group-selection=disabled commands_modified=0.",
                static_cast<unsigned long long>(lock_count),
                static_cast<unsigned long long>(locked_triplet[0]),
                static_cast<unsigned long long>(locked_triplet[1]),
                static_cast<unsigned long long>(locked_triplet[2]),
                locked_format,
                static_cast<unsigned long long>(locked_width),
                locked_height);
        }

        const uint64_t bind_count =
            s_v79_r3_ring_bind_count.fetch_add(
                1, std::memory_order_acq_rel) + 1;
        if (bind_count <= 12)
            reshade::log::message(
                reshade::log::level::info,
                "D3DMetal RTX presented-frame producer chain v79 R3: RTV_RING_BIND count=%llu resource_id=%llu previous_resource_id=%llu switched=%u strict_rewritten_proof=%u commands_modified=0.",
                static_cast<unsigned long long>(bind_count),
                static_cast<unsigned long long>(current),
                static_cast<unsigned long long>(previous),
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
            s_v79_r3_ring_frame_count.fetch_add(
                1, std::memory_order_acq_rel) + 1;
        if (frame <= 16 || frame % 120 == 0)
            reshade::log::message(
                reshade::log::level::info,
                "D3DMetal RTX presented-frame producer chain v79 R3: RTV_RING_FRAME frame=%llu completed_resource_id=%llu next_resource_id=%llu format=%u dimensions=%llux%u boundary=frozen-triplet-resource-switch commands_modified=0.",
                static_cast<unsigned long long>(frame),
                static_cast<unsigned long long>(previous),
                static_cast<unsigned long long>(current),
                previous_info.format,
                static_cast<unsigned long long>(previous_info.width),
                previous_info.height);
        v79_process_present(previous_info.resource);
    }

''' + helper_anchor
replace_once(helper_anchor, helper_block, "V79 R3 stable triplet helpers")

cycle_call_anchor = r'''        v79_r2_note_rtv_cycle(resources);
'''
cycle_call_block = r'''        v79_r3_observe_rtv_sequence(resources);
'''
replace_once(cycle_call_anchor, cycle_call_block, "V79 R3 OMSetRenderTargets routing")

filter_anchor = r'''        if (seen_as_input)
        {
'''
filter_block = r'''        const bool locked_present_resource =
            v79_r3_is_locked_resource(info.resource_id);
        if (seen_as_input && !locked_present_resource)
        {
'''
replace_once(filter_anchor, filter_block, "V79 R3 locked-resource filter bypass")

active_anchor = r'''"D3DMetal RTX presented-frame producer chain v79: ACTIVE runtime-gate=KAIOZEN_V79_ACTIVE backbuffer-detection=repeated-begin-signature+rtv-cycle-frame-boundary reverse-present-barrier=not-required rtv-tracking=enabled copy-resolve-tracking=enabled present-frame-writers=24 backward-depth=6 baseline-present-frames=8 baseline-capture-freeze=enabled post-settings-present-frames=4 signal-file=C:/kaiozen-v79-settings-returned.signal commands_modified=0.");
'''
active_block = r'''"D3DMetal RTX presented-frame producer chain v79: ACTIVE runtime-gate=KAIOZEN_V79_ACTIVE backbuffer-detection=stable-three-resource-periodic-ring triplet-period-proof=4-cycles dynamic-largest-group-selection=disabled locked-present-resource-input-filter-bypass=enabled reverse-present-barrier=not-required rtv-tracking=enabled copy-resolve-tracking=enabled present-frame-writers=24 backward-depth=6 baseline-present-frames=8 baseline-capture-freeze=enabled post-settings-present-frames=4 signal-file=C:/kaiozen-v79-settings-returned.signal commands_modified=0.");
'''
replace_once(active_anchor, active_block, "V79 R3 active marker")

source.write_text(text, encoding="utf-8", newline="\n")
Path("v79-r3-patch-report.txt").write_text(
    "\n".join([
        "V79_R3_STABLE_TRIPLET_RING_PATCH_OK",
        "BINARY_MANIFEST=V79_R3_BINARY_MARKER_MANIFEST_R3_STABLE_TRIPLET_RING",
        "PRESENT_BOUNDARY=FROZEN_THREE_RESOURCE_PERIODIC_RING",
        "TRIPLET_PERIOD_PROOF=FOUR_EXACT_CYCLES",
        "BEGIN_TRANSITION_REQUIRED=YES",
        "INPUT_FILTER_AT_LOCK=NEVER_SEEN_AS_INPUT",
        "DYNAMIC_LARGEST_GROUP_SELECTION=DISABLED",
        "LOCKED_PRESENT_RESOURCE_INPUT_FILTER_BYPASS=YES",
        "BASELINE_CAPTURE_FREEZE=YES",
        "GPU_READBACK=DISABLED",
        "COMMANDS_MODIFIED=NO",
        "RESULT=PASS",
        "",
    ]),
    encoding="ascii",
)
print("V79_R3_STABLE_TRIPLET_RING_PATCH_OK")
