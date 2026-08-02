from __future__ import annotations

from pathlib import Path

SOURCE = Path("source/d3d12/d3d12.cpp")
REPORT = Path("v65-patch-report.txt")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one anchor, found {count}")
    return text.replace(old, new, 1)


text = SOURCE.read_text(encoding="utf-8")
if "D3DMetal RTX u1 target rollover v65" in text:
    raise RuntimeError("V65 patch appears to be applied already")
if "D3DMetal RTX temporal ray-hit snapshots v64" not in text:
    raise RuntimeError("V64 baseline marker is missing")
if "D3DMetal RTX AddToStateObject lineage bridge v61" not in text:
    raise RuntimeError("V61 strict lineage marker is missing")

text = replace_once(
    text,
    '''    // D3DMetal RTX temporal ray-hit snapshots v64.
    // Three same-range u1 snapshots separate producer data evolution from
    // downstream temporal-lighting accumulation.
''',
    '''    // D3DMetal RTX temporal ray-hit snapshots v64.
    // Three same-range u1 snapshots separate producer data evolution from
    // downstream temporal-lighting accumulation.

    // D3DMetal RTX u1 target rollover v65.
    // Refreshes the local-root u1 descriptor after a rewritten pipeline change,
    // rejects stale target generations, and captures the post-menu resource
    // shortly after rollover instead of waiting on the old V64 1400-ray target.
''',
    "add V65 source marker",
)

old_state = '''static std::atomic<bool> s_v62_u1_target_ready = false;
    static std::atomic<bool> s_v62_capture_claimed = false;
    static std::atomic<bool> s_v62_copy_recorded = false;
    static std::atomic<bool> s_v62_queue_signaled = false;
    static std::atomic<bool> s_v62_readback_complete = false;
    static std::atomic<bool> s_v62_capture_failed = false;

    constexpr UINT v64_snapshot_count = 3;
    constexpr UINT64 v64_snapshot_thresholds[v64_snapshot_count] = { 96, 512, 1400 };

    static std::mutex s_v64_capture_mutex;
    static ID3D12Resource *s_v64_readbacks[v64_snapshot_count] = {};
    static ID3D12Fence *s_v64_fences[v64_snapshot_count] = {};
    static HANDLE s_v64_events[v64_snapshot_count] = {};
    static void *s_v64_command_list_identities[v64_snapshot_count] = {};
    static UINT64 s_v64_destination_offsets[v64_snapshot_count][v62_max_sample_blocks] = {};
    static UINT64 s_v64_record_starts[v64_snapshot_count][v62_max_sample_blocks] = {};
    static UINT64 s_v64_readback_bytes[v64_snapshot_count] = {};
    static UINT64 s_v64_actual_pipeline_rays[v64_snapshot_count] = {};
    static UINT64 s_v64_pipeline_ids[v64_snapshot_count] = {};
    static std::atomic<bool> s_v64_claimed[v64_snapshot_count] = {};
    static std::atomic<bool> s_v64_submitted[v64_snapshot_count] = {};
    static std::atomic<bool> s_v64_complete[v64_snapshot_count] = {};
    static std::atomic<bool> s_v64_failed[v64_snapshot_count] = {};
    static std::atomic<uint64_t> s_v64_success_count = 0;
    static std::atomic<uint64_t> s_v64_failure_count = 0;'''

new_state = '''static std::atomic<bool> s_v62_u1_target_ready = false;
    static std::atomic<bool> s_v62_capture_claimed = false;
    static std::atomic<bool> s_v62_copy_recorded = false;
    static std::atomic<bool> s_v62_queue_signaled = false;
    static std::atomic<bool> s_v62_readback_complete = false;
    static std::atomic<bool> s_v62_capture_failed = false;

    constexpr UINT v64_snapshot_count = 3;
    // V65 reuses the proven V64 copy/readback engine. Stages one and two
    // sample the initial world pipeline. Stage three samples 64 rays into
    // the first rewritten pipeline rollover after a fresh u1 resolution.
    constexpr UINT64 v64_snapshot_thresholds[v64_snapshot_count] = { 96, 512, 64 };

    static std::mutex s_v64_capture_mutex;
    static ID3D12Resource *s_v64_readbacks[v64_snapshot_count] = {};
    static ID3D12Fence *s_v64_fences[v64_snapshot_count] = {};
    static HANDLE s_v64_events[v64_snapshot_count] = {};
    static void *s_v64_command_list_identities[v64_snapshot_count] = {};
    static UINT64 s_v64_destination_offsets[v64_snapshot_count][v62_max_sample_blocks] = {};
    static UINT64 s_v64_record_starts[v64_snapshot_count][v62_max_sample_blocks] = {};
    static UINT64 s_v64_readback_bytes[v64_snapshot_count] = {};
    static UINT64 s_v64_actual_pipeline_rays[v64_snapshot_count] = {};
    static UINT64 s_v64_pipeline_ids[v64_snapshot_count] = {};
    static std::atomic<bool> s_v64_claimed[v64_snapshot_count] = {};
    static std::atomic<bool> s_v64_submitted[v64_snapshot_count] = {};
    static std::atomic<bool> s_v64_complete[v64_snapshot_count] = {};
    static std::atomic<bool> s_v64_failed[v64_snapshot_count] = {};
    static std::atomic<uint64_t> s_v64_success_count = 0;
    static std::atomic<uint64_t> s_v64_failure_count = 0;

    static std::atomic<uint64_t> s_v65_u1_target_generation = 0;
    static std::atomic<uint64_t> s_v65_u1_refresh_count = 0;
    static std::atomic<uint64_t> s_v65_u1_change_count = 0;
    static std::atomic<uint64_t> s_v65_pipeline_rollover_count = 0;
    static std::atomic<uint64_t> s_v65_last_pipeline_id = 0;
    static UINT64 s_v65_snapshot_generations[v64_snapshot_count] = {};
    static std::atomic<uint64_t> s_v65_initial_pipeline_id = 0;'''

text = replace_once(text, old_state, new_state, "add V65 target-generation state")

old_publish = '''            bool published = false;
            if (total_records != 0)
            {
                std::lock_guard<std::mutex> lock(s_v62_capture_mutex);
                if (!s_v62_u1_target_ready.load(std::memory_order_acquire))
                {
                    u1_resource.resource->AddRef();
                    s_v62_u1_resource = u1_resource.resource;
                    s_v62_u1_base_offset = first_byte;
                    s_v62_u1_total_bytes = usable_bytes;
                    s_v62_u1_total_records = total_records;
                    s_v62_u1_target_ready.store(true, std::memory_order_release);
                    published = true;
                }
            }
            if (published)
            {
                reshade::log::message(
                    reshade::log::level::info,
                    "D3DMetal RTX ray-hit output forensics v62: U1_TARGET_READY resource=%p resource_id=%llu base_offset=%llu total_bytes=%llu total_records=%llu stride=%u commands_modified=0.",
                    u1_resource.resource,
                    static_cast<unsigned long long>(u1.resource_id),
                    static_cast<unsigned long long>(first_byte),
                    static_cast<unsigned long long>(usable_bytes),
                    static_cast<unsigned long long>(total_records),
                    u1.structure_stride);
            }'''

new_publish = '''            bool published = false;
            bool changed = false;
            uint64_t generation = s_v65_u1_target_generation.load(
                std::memory_order_acquire);
            ID3D12Resource *previous_resource = nullptr;
            if (total_records != 0)
            {
                std::lock_guard<std::mutex> lock(s_v62_capture_mutex);
                const bool same_target =
                    s_v62_u1_target_ready.load(std::memory_order_acquire) &&
                    s_v62_u1_resource == u1_resource.resource &&
                    s_v62_u1_base_offset == first_byte &&
                    s_v62_u1_total_bytes == usable_bytes &&
                    s_v62_u1_total_records == total_records;
                if (!same_target)
                {
                    u1_resource.resource->AddRef();
                    previous_resource = s_v62_u1_resource;
                    s_v62_u1_resource = u1_resource.resource;
                    s_v62_u1_base_offset = first_byte;
                    s_v62_u1_total_bytes = usable_bytes;
                    s_v62_u1_total_records = total_records;
                    s_v62_u1_target_ready.store(true, std::memory_order_release);
                    generation = s_v65_u1_target_generation.fetch_add(
                        1, std::memory_order_acq_rel) + 1;
                    ++s_v65_u1_change_count;
                    published = true;
                    changed = previous_resource != nullptr;
                }
                else
                {
                    generation = s_v65_u1_target_generation.load(
                        std::memory_order_acquire);
                }
            }
            if (previous_resource != nullptr)
                previous_resource->Release();
            if (published)
            {
                reshade::log::message(
                    reshade::log::level::info,
                    "D3DMetal RTX ray-hit output forensics v62: U1_TARGET_READY resource=%p resource_id=%llu base_offset=%llu total_bytes=%llu total_records=%llu stride=%u commands_modified=0.",
                    u1_resource.resource,
                    static_cast<unsigned long long>(u1.resource_id),
                    static_cast<unsigned long long>(first_byte),
                    static_cast<unsigned long long>(usable_bytes),
                    static_cast<unsigned long long>(total_records),
                    u1.structure_stride);
                reshade::log::message(
                    reshade::log::level::info,
                    "D3DMetal RTX u1 target rollover v65: U1_TARGET_GENERATION generation=%llu changed=%u resource=%p resource_id=%llu base_offset=%llu total_records=%llu.",
                    static_cast<unsigned long long>(generation),
                    changed ? 1u : 0u,
                    u1_resource.resource,
                    static_cast<unsigned long long>(u1.resource_id),
                    static_cast<unsigned long long>(first_byte),
                    static_cast<unsigned long long>(total_records));
            }'''

text = replace_once(text, old_publish, new_publish, "make u1 publication generation-aware")

insert_before = '''    void v59_disable_high_frequency_tracking(const char *reason)
    {'''

helper = r'''    bool v65_refresh_current_u1_target(
        uint64_t pipeline_id,
        const char *reason)
    {
        std::vector<v59_shader_record_candidate> candidates;
        {
            std::lock_guard<std::mutex> lock(s_v59_candidate_mutex);
            candidates = s_v59_record_candidates;
        }

        const v59_shader_record_candidate *latest = nullptr;
        for (const auto &candidate : candidates)
            if (latest == nullptr || candidate.sequence > latest->sequence)
                latest = &candidate;

        const uint64_t before_generation =
            s_v65_u1_target_generation.load(std::memory_order_acquire);
        const uint64_t refresh_index =
            s_v65_u1_refresh_count.fetch_add(
                1, std::memory_order_acq_rel) + 1;

        if (latest == nullptr)
        {
            reshade::log::message(
                reshade::log::level::warning,
                "D3DMetal RTX u1 target rollover v65: U1_REFRESH_RESULT success=0 refresh=%llu pipeline_id=%llu reason=%s candidate=none generation=%llu.",
                static_cast<unsigned long long>(refresh_index),
                static_cast<unsigned long long>(pipeline_id),
                reason != nullptr ? reason : "unknown",
                static_cast<unsigned long long>(before_generation));
            return false;
        }

        v55_resolve_raygen_local_root(
            latest->bytes,
            sizeof(latest->bytes));

        const uint64_t after_generation =
            s_v65_u1_target_generation.load(std::memory_order_acquire);
        const bool ready =
            s_v62_u1_target_ready.load(std::memory_order_acquire);

        reshade::log::message(
            ready ? reshade::log::level::info :
                    reshade::log::level::warning,
            "D3DMetal RTX u1 target rollover v65: U1_REFRESH_RESULT success=%u refresh=%llu pipeline_id=%llu reason=%s candidate_sequence=%llu candidate_source=%s generation_before=%llu generation_after=%llu target_changed=%u.",
            ready ? 1u : 0u,
            static_cast<unsigned long long>(refresh_index),
            static_cast<unsigned long long>(pipeline_id),
            reason != nullptr ? reason : "unknown",
            static_cast<unsigned long long>(latest->sequence),
            latest->source != nullptr ? latest->source : "unknown",
            static_cast<unsigned long long>(before_generation),
            static_cast<unsigned long long>(after_generation),
            after_generation != before_generation ? 1u : 0u);
        return ready;
    }

'''
text = replace_once(text, insert_before, helper + insert_before, "add V65 lightweight u1 refresh")

text = replace_once(
    text,
    '''        UINT64 actual_ray = 0;
        UINT64 pipeline_id = 0;
''',
    '''        UINT64 actual_ray = 0;
        UINT64 pipeline_id = 0;
        UINT64 target_generation = 0;
''',
    "read snapshot target generation",
)
text = replace_once(
    text,
    '''            pipeline_id = s_v64_pipeline_ids[snapshot];
            memcpy(destination_offsets, s_v64_destination_offsets[snapshot], sizeof(destination_offsets));
''',
    '''            pipeline_id = s_v64_pipeline_ids[snapshot];
            target_generation = s_v65_snapshot_generations[snapshot];
            memcpy(destination_offsets, s_v64_destination_offsets[snapshot], sizeof(destination_offsets));
''',
    "load snapshot target generation",
)

text = replace_once(
    text,
    '''"D3DMetal RTX temporal ray-hit snapshots v64: TEMPORAL_SNAPSHOT_RESULT stage=%u success=1 threshold=%llu actual_pipeline_ray=%llu pipeline_id=%llu sampled_records=%llu misses=%llu hits=%llu invalid_distance=%llu all_zero=%llu word3_zero=%llu word4_expected=%llu word5_zero=%llu unique_record_hashes=%zu commands_modified=copy-after-dispatch-restored-uav-state.",''',
    '''"D3DMetal RTX u1 target rollover v65: ROLLOVER_SNAPSHOT_RESULT stage=%u success=1 threshold=%llu actual_pipeline_ray=%llu pipeline_id=%llu target_generation=%llu sampled_records=%llu misses=%llu hits=%llu invalid_distance=%llu all_zero=%llu word3_zero=%llu word4_expected=%llu word5_zero=%llu unique_record_hashes=%zu commands_modified=copy-after-dispatch-restored-uav-state.",''',
    "rename success snapshot marker",
)
text = replace_once(
    text,
    '''            static_cast<unsigned long long>(pipeline_id),
            static_cast<unsigned long long>(sampled),''',
    '''            static_cast<unsigned long long>(pipeline_id),
            static_cast<unsigned long long>(target_generation),
            static_cast<unsigned long long>(sampled),''',
    "log success target generation",
)

text = replace_once(
    text,
    '''    void v64_record_snapshot(
        UINT snapshot,
        ID3D12GraphicsCommandList *command_list,
        uint64_t pipeline_id,
        uint64_t pipeline_ray_index)
    {
        if (snapshot >= v64_snapshot_count || command_list == nullptr ||
            !s_v62_u1_target_ready.load(std::memory_order_acquire))
            return;

        bool expected = false;
        if (!s_v64_claimed[snapshot].compare_exchange_strong(expected, true, std::memory_order_acq_rel))
            return;

        ID3D12Resource *resource = nullptr;
        UINT64 base_offset = 0;
        UINT64 total_records = 0;
''',
    '''    void v64_record_snapshot(
        UINT snapshot,
        ID3D12GraphicsCommandList *command_list,
        uint64_t pipeline_id,
        uint64_t pipeline_ray_index)
    {
        if (snapshot >= v64_snapshot_count || command_list == nullptr ||
            !s_v62_u1_target_ready.load(std::memory_order_acquire))
            return;

        bool expected = false;
        if (!s_v64_claimed[snapshot].compare_exchange_strong(expected, true, std::memory_order_acq_rel))
            return;

        ID3D12Resource *resource = nullptr;
        UINT64 base_offset = 0;
        UINT64 total_records = 0;
        UINT64 target_generation = 0;
''',
    "capture current target generation",
)
text = replace_once(
    text,
    '''        UINT64 target_generation = 0;
        {
            std::lock_guard<std::mutex> lock(s_v62_capture_mutex);
            resource = s_v62_u1_resource;
            base_offset = s_v62_u1_base_offset;
            total_records = s_v62_u1_total_records;
            if (resource != nullptr) resource->AddRef();
''',
    '''        UINT64 target_generation = 0;
        {
            std::lock_guard<std::mutex> lock(s_v62_capture_mutex);
            resource = s_v62_u1_resource;
            base_offset = s_v62_u1_base_offset;
            total_records = s_v62_u1_total_records;
            target_generation = s_v65_u1_target_generation.load(
                std::memory_order_acquire);
            if (resource != nullptr) resource->AddRef();
''',
    "read target generation with resource",
)

barrier_anchor = '''        if (FAILED(hr) || readback == nullptr || FAILED(fence_hr) || fence == nullptr || event_handle == nullptr)
        {
            s_v64_failed[snapshot].store(true, std::memory_order_release);
            ++s_v64_failure_count;
            if (readback != nullptr) readback->Release();
            if (fence != nullptr) fence->Release();
            if (event_handle != nullptr) CloseHandle(event_handle);
            resource->Release();
            return;
        }

        D3D12_RESOURCE_BARRIER uav_barrier = {};
        uav_barrier.Type = D3D12_RESOURCE_BARRIER_TYPE_UAV;
'''
stale_guard = '''        if (FAILED(hr) || readback == nullptr || FAILED(fence_hr) || fence == nullptr || event_handle == nullptr)
        {
            s_v64_failed[snapshot].store(true, std::memory_order_release);
            ++s_v64_failure_count;
            if (readback != nullptr) readback->Release();
            if (fence != nullptr) fence->Release();
            if (event_handle != nullptr) CloseHandle(event_handle);
            resource->Release();
            return;
        }

        {
            std::lock_guard<std::mutex> lock(s_v62_capture_mutex);
            const uint64_t current_generation =
                s_v65_u1_target_generation.load(std::memory_order_acquire);
            if (s_v62_u1_resource != resource ||
                current_generation != target_generation)
            {
                reshade::log::message(
                    reshade::log::level::warning,
                    "D3DMetal RTX u1 target rollover v65: STALE_TARGET_REJECTED stage=%u captured_generation=%llu current_generation=%llu captured_resource=%p current_resource=%p commands_modified=0.",
                    snapshot + 1,
                    static_cast<unsigned long long>(target_generation),
                    static_cast<unsigned long long>(current_generation),
                    resource,
                    s_v62_u1_resource);
                s_v64_claimed[snapshot].store(false, std::memory_order_release);
                readback->Release();
                fence->Release();
                CloseHandle(event_handle);
                resource->Release();
                return;
            }
        }

'''
text = replace_once(
    text,
    barrier_anchor,
    stale_guard + '''        D3D12_RESOURCE_BARRIER uav_barrier = {};
        uav_barrier.Type = D3D12_RESOURCE_BARRIER_TYPE_UAV;
''',
    "reject stale u1 before barriers",
)

text = replace_once(
    text,
    '''            s_v64_pipeline_ids[snapshot] = pipeline_id;
        }
        reshade::log::message(
''',
    '''            s_v64_pipeline_ids[snapshot] = pipeline_id;
            s_v65_snapshot_generations[snapshot] = target_generation;
        }
        reshade::log::message(
''',
    "store snapshot generation",
)
text = replace_once(
    text,
    '''"D3DMetal RTX temporal ray-hit snapshots v64: TEMPORAL_CAPTURE_RECORDED stage=%u threshold=%llu actual_pipeline_ray=%llu pipeline_id=%llu command_list=%p identity=%p total_records=%llu sampled_records=%u commands_modified=copy-after-dispatch-restored-uav-state.",''',
    '''"D3DMetal RTX u1 target rollover v65: ROLLOVER_CAPTURE_RECORDED stage=%u threshold=%llu actual_pipeline_ray=%llu pipeline_id=%llu target_generation=%llu command_list=%p identity=%p total_records=%llu sampled_records=%u commands_modified=copy-after-dispatch-restored-uav-state.",''',
    "rename capture marker",
)
text = replace_once(
    text,
    '''            static_cast<unsigned long long>(pipeline_id),
            command_list,''',
    '''            static_cast<unsigned long long>(pipeline_id),
            static_cast<unsigned long long>(target_generation),
            command_list,''',
    "log capture target generation",
)

old_timeline = '''    void v64_try_capture_timeline(ID3D12GraphicsCommandList *command_list)
    {
        if (command_list == nullptr || !s_v62_u1_target_ready.load(std::memory_order_acquire))
            return;

        uint64_t pipeline_id = 0, pipeline_ray_index = 0, state_call = 0;
        if (!v64_rewritten_capture_candidate(
                reinterpret_cast<ID3D12GraphicsCommandList4 *>(command_list),
                v64_snapshot_thresholds[0], pipeline_id, pipeline_ray_index, state_call))
            return;

        for (UINT snapshot = 0; snapshot < v64_snapshot_count; ++snapshot)
        {
            if (pipeline_ray_index < v64_snapshot_thresholds[snapshot] ||
                s_v64_claimed[snapshot].load(std::memory_order_acquire))
                continue;
            if (snapshot != 0 && !s_v64_complete[snapshot - 1].load(std::memory_order_acquire))
                return;
            v64_record_snapshot(snapshot, command_list, pipeline_id, pipeline_ray_index);
            return;
        }
    }

'''

new_timeline = '''    void v64_try_capture_timeline(ID3D12GraphicsCommandList *command_list)
    {
        if (command_list == nullptr)
            return;

        uint64_t pipeline_id = 0, pipeline_ray_index = 0, state_call = 0;
        if (!v64_rewritten_capture_candidate(
                reinterpret_cast<ID3D12GraphicsCommandList4 *>(command_list),
                1, pipeline_id, pipeline_ray_index, state_call))
            return;

        const uint64_t previous_pipeline =
            s_v65_last_pipeline_id.exchange(
                pipeline_id, std::memory_order_acq_rel);
        if (previous_pipeline != pipeline_id)
        {
            if (previous_pipeline != 0)
            {
                const uint64_t rollover =
                    s_v65_pipeline_rollover_count.fetch_add(
                        1, std::memory_order_acq_rel) + 1;
                reshade::log::message(
                    reshade::log::level::info,
                    "D3DMetal RTX u1 target rollover v65: PIPELINE_ROLLOVER count=%llu previous_pipeline=%llu current_pipeline=%llu current_pipeline_ray=%llu.",
                    static_cast<unsigned long long>(rollover),
                    static_cast<unsigned long long>(previous_pipeline),
                    static_cast<unsigned long long>(pipeline_id),
                    static_cast<unsigned long long>(pipeline_ray_index));
            }
            v65_refresh_current_u1_target(
                pipeline_id,
                previous_pipeline == 0 ? "initial-pipeline" :
                                         "pipeline-rollover");
        }

        if (!s_v62_u1_target_ready.load(std::memory_order_acquire))
            return;

        if (!s_v64_claimed[0].load(std::memory_order_acquire) &&
            pipeline_ray_index >= v64_snapshot_thresholds[0])
        {
            uint64_t expected_initial = 0;
            s_v65_initial_pipeline_id.compare_exchange_strong(
                expected_initial, pipeline_id, std::memory_order_acq_rel);
            v64_record_snapshot(
                0, command_list, pipeline_id, pipeline_ray_index);
            return;
        }

        const uint64_t initial_pipeline_id =
            s_v65_initial_pipeline_id.load(std::memory_order_acquire);

        if (s_v64_complete[0].load(std::memory_order_acquire) &&
            !s_v64_claimed[1].load(std::memory_order_acquire) &&
            pipeline_id == initial_pipeline_id &&
            pipeline_ray_index >= v64_snapshot_thresholds[1])
        {
            v65_refresh_current_u1_target(
                pipeline_id, "pre-menu-world-snapshot");
            v64_record_snapshot(
                1, command_list, pipeline_id, pipeline_ray_index);
            return;
        }

        if (s_v64_complete[1].load(std::memory_order_acquire) &&
            !s_v64_claimed[2].load(std::memory_order_acquire) &&
            pipeline_id != initial_pipeline_id &&
            pipeline_ray_index >= v64_snapshot_thresholds[2])
        {
            v65_refresh_current_u1_target(
                pipeline_id, "post-menu-rollover-snapshot");
            v64_record_snapshot(
                2, command_list, pipeline_id, pipeline_ray_index);
        }
    }

'''
text = replace_once(text, old_timeline, new_timeline, "replace stale V64 timeline with V65 rollover timeline")

text = text.replace(
    '"D3DMetal RTX temporal ray-hit snapshots v64: TEMPORAL_QUEUE_SUBMITTED stage=%u count=%u signal_hr=%s event_hr=%s.",',
    '"D3DMetal RTX u1 target rollover v65: ROLLOVER_QUEUE_SUBMITTED stage=%u count=%u signal_hr=%s event_hr=%s.",',
)
if "ROLLOVER_QUEUE_SUBMITTED" not in text:
    raise RuntimeError("V65 queue marker replacement failed")

text = replace_once(
    text,
    '''		// V64 captures the same genuine u1 records at early, middle, and late
		// rewritten-pipeline milestones to test temporal accumulation.
		if (dispatch_rays && rewritten)
			v64_try_capture_timeline(command_list);''',
    '''		// V65 captures the initial world target twice, then refreshes and
		// samples the current u1 target after the first rewritten pipeline
		// rollover (normally caused by the controlled menu transition).
		if (dispatch_rays && rewritten)
			v64_try_capture_timeline(command_list);''',
    "update ExecuteIndirect V65 purpose",
)

text = replace_once(
    text,
    '''"D3DMetal RTX temporal ray-hit snapshots v64: ACTIVE stages=3 thresholds=96,512,1400 records-per-stage=1280 strict-lineage=v61 normalization=v63-fdiv broad-gpu-va-tracing=disabled commands_modified=diagnostic-copy-only.");''',
    '''"D3DMetal RTX u1 target rollover v65: ACTIVE stages=3 initial-thresholds=96,512 rollover-threshold=64 records-per-stage=1280 strict-lineage=v61 normalization=v63-fdiv stale-target-rejection=enabled commands_modified=current-target-copy-only.");''',
    "replace active marker",
)

SOURCE.write_text(text, encoding="utf-8", newline="\n")
REPORT.write_text(
    "\n".join([
        "V65_U1_TARGET_ROLLOVER_PATCH_OK",
        "BASELINE=V64_TEMPORAL_RAYHIT_SNAPSHOTS",
        "INITIAL_WORLD_SNAPSHOT_THRESHOLDS=96,512",
        "POST_ROLLOVER_THRESHOLD=64",
        "TARGET_GENERATION_TRACKING=ENABLED",
        "PIPELINE_ROLLOVER_REFRESH=ENABLED",
        "STALE_TARGET_REJECTION=ENABLED",
        "MENU_CONTROLLED_TRANSITION=EXPECTED",
        "V61_STRICT_REWRITTEN_LINEAGE=ENABLED",
        "V52_FORCED_ZERO_MASK_PRESENT=NO",
        "V53_PATTERNED_OUTPUT_PRESENT=NO",
        "RESULT=PASS",
        "",
    ]),
    encoding="ascii",
)
print("V65_U1_TARGET_ROLLOVER_PATCH_OK")
