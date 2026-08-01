from __future__ import annotations

from pathlib import Path

SOURCE = Path("source/d3d12/d3d12.cpp")
REPORT = Path("v64-patch-report.txt")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one anchor, found {count}")
    return text.replace(old, new, 1)


text = SOURCE.read_text(encoding="utf-8")
if "D3DMetal RTX temporal ray-hit snapshots v64" in text:
    raise RuntimeError("V64 patch appears to be applied already")
if "D3DMetal RTX strict FP32 uint24 division v63" not in text:
    raise RuntimeError("V63 baseline marker is missing")
if "D3DMetal RTX AddToStateObject lineage bridge v61" not in text:
    raise RuntimeError("V61 strict-lineage marker is missing")

# Re-enable only the Map/Unmap observation needed to recover the persistent
# raygen local-root record. Copy and GPU-VA global tracing remain disabled.
text = replace_once(
    text,
    "static std::atomic<bool> s_v59_high_frequency_tracking_enabled = false;",
    "static std::atomic<bool> s_v59_high_frequency_tracking_enabled = true;",
    "temporarily enable minimal V59 mapping observation",
)

text = replace_once(
    text,
    '''        // V63 visual mode: the V62 Map/Unmap lineage probe is dormant.\n        // V59 and V62 already established the exact local-root u1 contract.\n''',
    '''        // V64 temporal mode: observe Map and Unmap only long enough to\n        // recover the persistent 64-byte raygen record and exact local-root u1.\n        v57_install_resource_map_hook(resource);\n        v59_install_resource_unmap_hook(resource);\n''',
    "restore minimal Map/Unmap lineage hooks",
)

# Add an earlier rewritten-pipeline candidate used only for diagnostics. The
# strict V61 execution proof remains unchanged at 512 pipeline rays.
v61_helper = '''\tbool v61_rewritten_steady_state_candidate(\n\t\tID3D12GraphicsCommandList4 *command_list,\n\t\tuint64_t &pipeline_id,\n\t\tuint64_t &pipeline_ray_index,\n\t\tuint64_t &rewritten_state_call)\n\t{\n\t\tpipeline_id = v54_lookup_bound_pipeline(command_list);\n\t\tpipeline_ray_index = 0;\n\t\trewritten_state_call = 0;\n\t\tif (pipeline_id == 0)\n\t\t\treturn false;\n\n\t\tstd::lock_guard<std::mutex> lock(s_v54_pipeline_mutex);\n\t\tconst auto found = s_v54_pipeline_infos.find(pipeline_id);\n\t\tif (found == s_v54_pipeline_infos.end())\n\t\t\treturn false;\n\n\t\tconst v54_pipeline_info &info = found->second;\n\t\tpipeline_ray_index = info.indirect_ray_count;\n\t\trewritten_state_call = info.rewritten_state_call;\n\t\treturn info.rewritten && rewritten_state_call != 0 &&\n\t\t\tpipeline_ray_index >= 512;\n\t}\n'''

v64_helper = v61_helper + '''\n\tbool v64_rewritten_capture_candidate(\n\t\tID3D12GraphicsCommandList4 *command_list,\n\t\tuint64_t minimum_pipeline_rays,\n\t\tuint64_t &pipeline_id,\n\t\tuint64_t &pipeline_ray_index,\n\t\tuint64_t &rewritten_state_call)\n\t{\n\t\tpipeline_id = v54_lookup_bound_pipeline(command_list);\n\t\tpipeline_ray_index = 0;\n\t\trewritten_state_call = 0;\n\t\tif (pipeline_id == 0)\n\t\t\treturn false;\n\n\t\tstd::lock_guard<std::mutex> lock(s_v54_pipeline_mutex);\n\t\tconst auto found = s_v54_pipeline_infos.find(pipeline_id);\n\t\tif (found == s_v54_pipeline_infos.end())\n\t\t\treturn false;\n\n\t\tconst v54_pipeline_info &info = found->second;\n\t\tpipeline_ray_index = info.indirect_ray_count;\n\t\trewritten_state_call = info.rewritten_state_call;\n\t\treturn info.rewritten && rewritten_state_call != 0 &&\n\t\t\tpipeline_ray_index >= minimum_pipeline_rays;\n\t}\n'''
text = replace_once(text, v61_helper, v64_helper, "add V64 early capture candidate")

# Resolve the local-root contract from the rewritten descendant at 64 rays,
# rather than waiting for the 512-ray strict-proof threshold.
text = text.replace(
    '''!v61_rewritten_steady_state_candidate(\n                reinterpret_cast<ID3D12GraphicsCommandList4 *>(command_list),\n                v62_pipeline_id,\n                v62_pipeline_ray_index,\n                v62_state_call))''',
    '''!v64_rewritten_capture_candidate(\n                reinterpret_cast<ID3D12GraphicsCommandList4 *>(command_list),\n                64,\n                v62_pipeline_id,\n                v62_pipeline_ray_index,\n                v62_state_call))''',
)
text = text.replace(
    '''!v61_rewritten_steady_state_candidate(\n\t\t\t\treinterpret_cast<ID3D12GraphicsCommandList4 *>(command_list),\n\t\t\t\tv62_pipeline_id,\n\t\t\t\tv62_pipeline_ray_index,\n\t\t\t\tv62_state_call))''',
    '''!v64_rewritten_capture_candidate(\n\t\t\t\treinterpret_cast<ID3D12GraphicsCommandList4 *>(command_list),\n\t\t\t\t64,\n\t\t\t\tv62_pipeline_id,\n\t\t\t\tv62_pipeline_ray_index,\n\t\t\t\tv62_state_call))''',
)
if text.count("v64_rewritten_capture_candidate(") < 3:
    raise RuntimeError("V64 did not retarget both dispatch/shader-table capture gates")

# Add independent three-snapshot state after the existing V62 state. V62's
# single-shot implementation is retained as reference but is not invoked.
v62_state = '''    static std::atomic<bool> s_v62_u1_target_ready = false;\n    static std::atomic<bool> s_v62_capture_claimed = false;\n    static std::atomic<bool> s_v62_copy_recorded = false;\n    static std::atomic<bool> s_v62_queue_signaled = false;\n    static std::atomic<bool> s_v62_readback_complete = false;\n    static std::atomic<bool> s_v62_capture_failed = false;\n'''

v64_state = v62_state + '''\n    constexpr UINT v64_snapshot_count = 3;\n    constexpr UINT64 v64_snapshot_thresholds[v64_snapshot_count] = { 96, 512, 1400 };\n\n    static std::mutex s_v64_capture_mutex;\n    static ID3D12Resource *s_v64_readbacks[v64_snapshot_count] = {};\n    static ID3D12Fence *s_v64_fences[v64_snapshot_count] = {};\n    static HANDLE s_v64_events[v64_snapshot_count] = {};\n    static void *s_v64_command_list_identities[v64_snapshot_count] = {};\n    static UINT64 s_v64_destination_offsets[v64_snapshot_count][v62_max_sample_blocks] = {};\n    static UINT64 s_v64_record_starts[v64_snapshot_count][v62_max_sample_blocks] = {};\n    static UINT64 s_v64_readback_bytes[v64_snapshot_count] = {};\n    static UINT64 s_v64_actual_pipeline_rays[v64_snapshot_count] = {};\n    static UINT64 s_v64_pipeline_ids[v64_snapshot_count] = {};\n    static std::atomic<bool> s_v64_claimed[v64_snapshot_count] = {};\n    static std::atomic<bool> s_v64_submitted[v64_snapshot_count] = {};\n    static std::atomic<bool> s_v64_complete[v64_snapshot_count] = {};\n    static std::atomic<bool> s_v64_failed[v64_snapshot_count] = {};\n    static std::atomic<uint64_t> s_v64_success_count = 0;\n    static std::atomic<uint64_t> s_v64_failure_count = 0;\n'''
text = replace_once(text, v62_state, v64_state, "add V64 three-snapshot state")

# Add a forward declaration before the queue hook calls it.
forward_anchor = '''\tvoid v62_on_execute_command_lists(\n\t\tID3D12CommandQueue *queue,\n\t\tUINT count,\n\t\tID3D12CommandList *const *command_lists);\n'''
forward_new = forward_anchor + '''\n\tvoid v64_on_execute_command_lists(\n\t\tID3D12CommandQueue *queue,\n\t\tUINT count,\n\t\tID3D12CommandList *const *command_lists);\n'''
text = replace_once(text, forward_anchor, forward_new, "declare V64 queue callback")

text = replace_once(
    text,
    '''\t\tv39_on_execute_command_lists(queue, count, command_lists);\n\t\tv62_on_execute_command_lists(queue, count, command_lists);\n''',
    '''\t\tv39_on_execute_command_lists(queue, count, command_lists);\n\t\tv62_on_execute_command_lists(queue, count, command_lists);\n\t\tv64_on_execute_command_lists(queue, count, command_lists);\n''',
    "invoke V64 queue callback",
)

# Insert the V64 capture implementation immediately after the legacy V62 queue
# callback, before the command-signature declarations.
insert_anchor = '''    }\n\n\n\tusing v34_create_command_signature_fn = HRESULT (STDMETHODCALLTYPE *)(\n'''

v64_impl = r'''    }

    void v64_release_snapshot_objects(UINT snapshot)
    {
        ID3D12Resource *readback = nullptr;
        ID3D12Fence *fence = nullptr;
        HANDLE event_handle = nullptr;
        {
            std::lock_guard<std::mutex> lock(s_v64_capture_mutex);
            readback = s_v64_readbacks[snapshot];
            fence = s_v64_fences[snapshot];
            event_handle = s_v64_events[snapshot];
            s_v64_readbacks[snapshot] = nullptr;
            s_v64_fences[snapshot] = nullptr;
            s_v64_events[snapshot] = nullptr;
            s_v64_command_list_identities[snapshot] = nullptr;
        }
        if (readback != nullptr) readback->Release();
        if (fence != nullptr) fence->Release();
        if (event_handle != nullptr) CloseHandle(event_handle);
    }

    DWORD WINAPI v64_readback_worker(LPVOID parameter)
    {
        const UINT snapshot = static_cast<UINT>(reinterpret_cast<uintptr_t>(parameter));
        if (snapshot >= v64_snapshot_count)
            return 0;

        ID3D12Resource *readback = nullptr;
        ID3D12Fence *fence = nullptr;
        HANDLE event_handle = nullptr;
        UINT64 total_bytes = 0;
        UINT64 destination_offsets[v62_max_sample_blocks] = {};
        UINT64 record_starts[v62_max_sample_blocks] = {};
        UINT64 actual_ray = 0;
        UINT64 pipeline_id = 0;
        {
            std::lock_guard<std::mutex> lock(s_v64_capture_mutex);
            readback = s_v64_readbacks[snapshot];
            fence = s_v64_fences[snapshot];
            event_handle = s_v64_events[snapshot];
            total_bytes = s_v64_readback_bytes[snapshot];
            actual_ray = s_v64_actual_pipeline_rays[snapshot];
            pipeline_id = s_v64_pipeline_ids[snapshot];
            memcpy(destination_offsets, s_v64_destination_offsets[snapshot], sizeof(destination_offsets));
            memcpy(record_starts, s_v64_record_starts[snapshot], sizeof(record_starts));
            if (readback != nullptr) readback->AddRef();
            if (fence != nullptr) fence->AddRef();
        }

        auto fail = [&](const char *reason)
        {
            s_v64_failed[snapshot].store(true, std::memory_order_release);
            ++s_v64_failure_count;
            reshade::log::message(
                reshade::log::level::warning,
                "D3DMetal RTX temporal ray-hit snapshots v64: TEMPORAL_SNAPSHOT_RESULT stage=%u success=0 threshold=%llu actual_pipeline_ray=%llu pipeline_id=%llu reason=%s.",
                snapshot + 1,
                static_cast<unsigned long long>(v64_snapshot_thresholds[snapshot]),
                static_cast<unsigned long long>(actual_ray),
                static_cast<unsigned long long>(pipeline_id),
                reason);
        };

        if (readback == nullptr || fence == nullptr || event_handle == nullptr || total_bytes == 0)
        {
            fail("missing-capture-objects");
            if (readback != nullptr) readback->Release();
            if (fence != nullptr) fence->Release();
            v64_release_snapshot_objects(snapshot);
            return 0;
        }

        const DWORD wait_result = WaitForSingleObject(event_handle, 20000);
        if (wait_result != WAIT_OBJECT_0)
        {
            fail("fence-wait");
            readback->Release();
            fence->Release();
            v64_release_snapshot_objects(snapshot);
            return 0;
        }

        void *mapped = nullptr;
        const D3D12_RANGE read_range = { 0, static_cast<SIZE_T>(total_bytes) };
        const HRESULT map_hr = readback->Map(0, &read_range, &mapped);
        if (FAILED(map_hr) || mapped == nullptr)
        {
            fail("map-failed");
            readback->Release();
            fence->Release();
            v64_release_snapshot_objects(snapshot);
            return 0;
        }

        const unsigned char *bytes = static_cast<const unsigned char *>(mapped);
        const UINT64 block_bytes = static_cast<UINT64>(v62_sample_records_per_block) * v62_rayhit_stride;
        uint64_t sampled = 0;
        uint64_t misses = 0;
        uint64_t hits = 0;
        uint64_t invalid_distance = 0;
        uint64_t all_zero = 0;
        uint64_t word3_zero = 0;
        uint64_t word4_expected = 0;
        uint64_t word5_zero = 0;
        std::vector<uint64_t> unique_hashes;

        for (UINT block = 0; block < v62_max_sample_blocks; ++block)
        {
            uint64_t block_misses = 0, block_hits = 0, block_invalid = 0, block_zero = 0;
            std::vector<uint64_t> block_hashes;
            const UINT64 destination = destination_offsets[block];
            if (destination + block_bytes > total_bytes)
                continue;

            for (UINT record_index = 0; record_index < v62_sample_records_per_block; ++record_index)
            {
                const unsigned char *record = bytes + destination + static_cast<UINT64>(record_index) * v62_rayhit_stride;
                uint32_t words[6] = {};
                float distance = 0.0f;
                memcpy(words, record, sizeof(words));
                memcpy(&distance, record, sizeof(distance));

                bool record_zero = true;
                for (size_t byte_index = 0; byte_index < v62_rayhit_stride; ++byte_index)
                    record_zero = record_zero && record[byte_index] == 0;
                if (record_zero) { ++all_zero; ++block_zero; }

                const bool finite_distance = (words[0] & 0x7F800000u) != 0x7F800000u;
                if (words[0] == 0x42800000u && words[2] == 1u)
                {
                    ++misses;
                    ++block_misses;
                }
                else if (finite_distance && distance >= 0.0f && distance < 64.0f)
                {
                    ++hits;
                    ++block_hits;
                }
                else
                {
                    ++invalid_distance;
                    ++block_invalid;
                }

                if (words[3] == 0) ++word3_zero;
                if (words[4] == 0x0032FFF8u) ++word4_expected;
                if (words[5] == 0) ++word5_zero;

                const uint64_t hash = v39_fnv1a64(record, v62_rayhit_stride);
                if (std::find(block_hashes.begin(), block_hashes.end(), hash) == block_hashes.end())
                    block_hashes.push_back(hash);
                if (std::find(unique_hashes.begin(), unique_hashes.end(), hash) == unique_hashes.end())
                    unique_hashes.push_back(hash);

                if (record_index < 4)
                {
                    char record_hex[v62_rayhit_stride * 2 + 1] = {};
                    v39_bytes_to_hex(record, v62_rayhit_stride, record_hex, sizeof(record_hex));
                    reshade::log::message(
                        reshade::log::level::info,
                        "D3DMetal RTX temporal ray-hit snapshots v64: TEMPORAL_RECORD stage=%u block=%u sample_index=%u global_record=%llu distance=%.9g u32=%08X,%08X,%08X,%08X,%08X,%08X hex=%s.",
                        snapshot + 1,
                        block,
                        record_index,
                        static_cast<unsigned long long>(record_starts[block] + record_index),
                        distance,
                        words[0], words[1], words[2], words[3], words[4], words[5],
                        record_hex);
                }
                ++sampled;
            }

            reshade::log::message(
                reshade::log::level::info,
                "D3DMetal RTX temporal ray-hit snapshots v64: TEMPORAL_BLOCK_SUMMARY stage=%u block=%u start_record=%llu records=%u misses=%llu hits=%llu invalid_distance=%llu all_zero=%llu unique_record_hashes=%zu.",
                snapshot + 1,
                block,
                static_cast<unsigned long long>(record_starts[block]),
                v62_sample_records_per_block,
                static_cast<unsigned long long>(block_misses),
                static_cast<unsigned long long>(block_hits),
                static_cast<unsigned long long>(block_invalid),
                static_cast<unsigned long long>(block_zero),
                block_hashes.size());
        }

        const D3D12_RANGE written_range = { 0, 0 };
        readback->Unmap(0, &written_range);
        s_v64_complete[snapshot].store(true, std::memory_order_release);
        ++s_v64_success_count;
        reshade::log::message(
            reshade::log::level::info,
            "D3DMetal RTX temporal ray-hit snapshots v64: TEMPORAL_SNAPSHOT_RESULT stage=%u success=1 threshold=%llu actual_pipeline_ray=%llu pipeline_id=%llu sampled_records=%llu misses=%llu hits=%llu invalid_distance=%llu all_zero=%llu word3_zero=%llu word4_expected=%llu word5_zero=%llu unique_record_hashes=%zu commands_modified=copy-after-dispatch-restored-uav-state.",
            snapshot + 1,
            static_cast<unsigned long long>(v64_snapshot_thresholds[snapshot]),
            static_cast<unsigned long long>(actual_ray),
            static_cast<unsigned long long>(pipeline_id),
            static_cast<unsigned long long>(sampled),
            static_cast<unsigned long long>(misses),
            static_cast<unsigned long long>(hits),
            static_cast<unsigned long long>(invalid_distance),
            static_cast<unsigned long long>(all_zero),
            static_cast<unsigned long long>(word3_zero),
            static_cast<unsigned long long>(word4_expected),
            static_cast<unsigned long long>(word5_zero),
            unique_hashes.size());

        readback->Release();
        fence->Release();
        v64_release_snapshot_objects(snapshot);
        return 0;
    }

    void v64_record_snapshot(
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
        {
            std::lock_guard<std::mutex> lock(s_v62_capture_mutex);
            resource = s_v62_u1_resource;
            base_offset = s_v62_u1_base_offset;
            total_records = s_v62_u1_total_records;
            if (resource != nullptr) resource->AddRef();
        }
        if (resource == nullptr || total_records < v62_sample_records_per_block)
        {
            s_v64_failed[snapshot].store(true, std::memory_order_release);
            ++s_v64_failure_count;
            if (resource != nullptr) resource->Release();
            return;
        }

        UINT64 starts[v62_max_sample_blocks] = {
            0,
            total_records / 8,
            total_records / 4,
            (total_records * 3) / 8,
            total_records / 2,
        };
        for (UINT index = 0; index < v62_max_sample_blocks; ++index)
            if (starts[index] + v62_sample_records_per_block > total_records)
                starts[index] = total_records - v62_sample_records_per_block;

        ID3D12Device *device = nullptr;
        HRESULT hr = resource->GetDevice(__uuidof(ID3D12Device), reinterpret_cast<void **>(&device));
        if (FAILED(hr) || device == nullptr)
        {
            s_v64_failed[snapshot].store(true, std::memory_order_release);
            ++s_v64_failure_count;
            resource->Release();
            return;
        }

        const UINT64 block_bytes = static_cast<UINT64>(v62_sample_records_per_block) * v62_rayhit_stride;
        const UINT64 readback_bytes = block_bytes * v62_max_sample_blocks;
        D3D12_HEAP_PROPERTIES heap_properties = {};
        heap_properties.Type = D3D12_HEAP_TYPE_READBACK;
        heap_properties.CreationNodeMask = 1;
        heap_properties.VisibleNodeMask = 1;
        D3D12_RESOURCE_DESC readback_desc = {};
        readback_desc.Dimension = D3D12_RESOURCE_DIMENSION_BUFFER;
        readback_desc.Width = readback_bytes;
        readback_desc.Height = 1;
        readback_desc.DepthOrArraySize = 1;
        readback_desc.MipLevels = 1;
        readback_desc.Format = DXGI_FORMAT_UNKNOWN;
        readback_desc.SampleDesc.Count = 1;
        readback_desc.Layout = D3D12_TEXTURE_LAYOUT_ROW_MAJOR;

        ID3D12Resource *readback = nullptr;
        hr = device->CreateCommittedResource(
            &heap_properties, D3D12_HEAP_FLAG_NONE, &readback_desc,
            D3D12_RESOURCE_STATE_COPY_DEST, nullptr, __uuidof(ID3D12Resource),
            reinterpret_cast<void **>(&readback));
        ID3D12Fence *fence = nullptr;
        const HRESULT fence_hr = device->CreateFence(
            0, D3D12_FENCE_FLAG_NONE, __uuidof(ID3D12Fence), reinterpret_cast<void **>(&fence));
        HANDLE event_handle = CreateEventW(nullptr, FALSE, FALSE, nullptr);
        device->Release();
        if (FAILED(hr) || readback == nullptr || FAILED(fence_hr) || fence == nullptr || event_handle == nullptr)
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
        uav_barrier.UAV.pResource = resource;
        command_list->ResourceBarrier(1, &uav_barrier);
        D3D12_RESOURCE_BARRIER to_copy = {};
        to_copy.Type = D3D12_RESOURCE_BARRIER_TYPE_TRANSITION;
        to_copy.Transition.pResource = resource;
        to_copy.Transition.Subresource = D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES;
        to_copy.Transition.StateBefore = D3D12_RESOURCE_STATE_UNORDERED_ACCESS;
        to_copy.Transition.StateAfter = D3D12_RESOURCE_STATE_COPY_SOURCE;
        D3D12_RESOURCE_BARRIER to_uav = to_copy;
        to_uav.Transition.StateBefore = D3D12_RESOURCE_STATE_COPY_SOURCE;
        to_uav.Transition.StateAfter = D3D12_RESOURCE_STATE_UNORDERED_ACCESS;

        command_list->ResourceBarrier(1, &to_copy);
        for (UINT block = 0; block < v62_max_sample_blocks; ++block)
        {
            const UINT64 source_offset = base_offset + starts[block] * v62_rayhit_stride;
            const UINT64 destination_offset = block * block_bytes;
            command_list->CopyBufferRegion(readback, destination_offset, resource, source_offset, block_bytes);
            s_v64_destination_offsets[snapshot][block] = destination_offset;
            s_v64_record_starts[snapshot][block] = starts[block];
        }
        command_list->ResourceBarrier(1, &to_uav);

        void *const identity = v33_identity_pointer(reinterpret_cast<IUnknown *>(command_list));
        {
            std::lock_guard<std::mutex> lock(s_v64_capture_mutex);
            s_v64_readbacks[snapshot] = readback;
            s_v64_fences[snapshot] = fence;
            s_v64_events[snapshot] = event_handle;
            s_v64_command_list_identities[snapshot] = identity;
            s_v64_readback_bytes[snapshot] = readback_bytes;
            s_v64_actual_pipeline_rays[snapshot] = pipeline_ray_index;
            s_v64_pipeline_ids[snapshot] = pipeline_id;
        }
        reshade::log::message(
            reshade::log::level::info,
            "D3DMetal RTX temporal ray-hit snapshots v64: TEMPORAL_CAPTURE_RECORDED stage=%u threshold=%llu actual_pipeline_ray=%llu pipeline_id=%llu command_list=%p identity=%p total_records=%llu sampled_records=%u commands_modified=copy-after-dispatch-restored-uav-state.",
            snapshot + 1,
            static_cast<unsigned long long>(v64_snapshot_thresholds[snapshot]),
            static_cast<unsigned long long>(pipeline_ray_index),
            static_cast<unsigned long long>(pipeline_id),
            command_list,
            identity,
            static_cast<unsigned long long>(total_records),
            v62_sample_records_per_block * v62_max_sample_blocks);
        resource->Release();
    }

    void v64_try_capture_timeline(ID3D12GraphicsCommandList *command_list)
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

    void v64_on_execute_command_lists(
        ID3D12CommandQueue *queue,
        UINT count,
        ID3D12CommandList *const *command_lists)
    {
        if (queue == nullptr || command_lists == nullptr)
            return;

        for (UINT snapshot = 0; snapshot < v64_snapshot_count; ++snapshot)
        {
            void *identity = nullptr;
            ID3D12Fence *fence = nullptr;
            HANDLE event_handle = nullptr;
            {
                std::lock_guard<std::mutex> lock(s_v64_capture_mutex);
                identity = s_v64_command_list_identities[snapshot];
                fence = s_v64_fences[snapshot];
                event_handle = s_v64_events[snapshot];
            }
            if (identity == nullptr || fence == nullptr || event_handle == nullptr)
                continue;

            bool contains = false;
            for (UINT index = 0; index < count; ++index)
            {
                ID3D12CommandList *list = nullptr;
                if (!safe_copy_from_process(command_lists + index, &list, sizeof(list)) || list == nullptr)
                    continue;
                if (v33_identity_pointer(reinterpret_cast<IUnknown *>(list)) == identity)
                {
                    contains = true;
                    break;
                }
            }
            bool expected = false;
            if (!contains || !s_v64_submitted[snapshot].compare_exchange_strong(expected, true, std::memory_order_acq_rel))
                continue;

            const HRESULT signal_hr = queue->Signal(fence, 1);
            const HRESULT event_hr = SUCCEEDED(signal_hr) ? fence->SetEventOnCompletion(1, event_handle) : E_FAIL;
            reshade::log::message(
                SUCCEEDED(signal_hr) && SUCCEEDED(event_hr) ? reshade::log::level::info : reshade::log::level::warning,
                "D3DMetal RTX temporal ray-hit snapshots v64: TEMPORAL_QUEUE_SUBMITTED stage=%u count=%u signal_hr=%s event_hr=%s.",
                snapshot + 1,
                count,
                reshade::log::hr_to_string(signal_hr).c_str(),
                reshade::log::hr_to_string(event_hr).c_str());

            if (SUCCEEDED(signal_hr) && SUCCEEDED(event_hr))
            {
                HANDLE thread_handle = CreateThread(
                    nullptr, 0, &v64_readback_worker,
                    reinterpret_cast<LPVOID>(static_cast<uintptr_t>(snapshot)), 0, nullptr);
                if (thread_handle != nullptr)
                    CloseHandle(thread_handle);
                else
                {
                    s_v64_failed[snapshot].store(true, std::memory_order_release);
                    ++s_v64_failure_count;
                }
            }
            else
            {
                s_v64_failed[snapshot].store(true, std::memory_order_release);
                ++s_v64_failure_count;
            }
        }
    }


\tusing v34_create_command_signature_fn = HRESULT (STDMETHODCALLTYPE *)(
'''
text = replace_once(text, insert_anchor, v64_impl, "insert V64 temporal capture implementation")

# Invoke the timeline after each real dispatch has executed.
text = replace_once(
    text,
    '''\t\t// V63 visual mode keeps the strict V61 proof but does not inject the\n\t\t// V62 diagnostic copy/readback commands.\n''',
    '''\t\t// V64 captures the same genuine u1 records at early, middle, and late\n\t\t// rewritten-pipeline milestones to test temporal accumulation.\n\t\tif (dispatch_rays && rewritten)\n\t\t\tv64_try_capture_timeline(command_list);\n''',
    "invoke V64 temporal snapshots",
)

# Re-enable the minimal queue/resource/descriptor hooks and publish a durable
# active marker. The broad V58 GPU-VA and CopyBufferRegion tracing stays off.
v63_activation = '''\t\tstatic std::once_flag v63_visual_mode_once;\n\t\tstd::call_once(\n\t\t\tv63_visual_mode_once,\n\t\t\t[]()\n\t\t\t{\n\t\t\t\treshade::log::message(\n\t\t\t\t\treshade::log::level::info,\n\t\t\t\t\t"D3DMetal RTX strict FP32 uint24 division v63: ACTIVE normalization=fdiv-fp32-by-16777215 fast-math=disabled strict-lineage=v61 v62-forensics=disabled commands_modified=0.");\n\t\t\t});\n'''

v64_activation = '''\t\tstatic std::once_flag v64_temporal_mode_once;\n\t\tstd::call_once(\n\t\t\tv64_temporal_mode_once,\n\t\t\t[device]()\n\t\t\t{\n\t\t\t\tv38_install_create_command_queue_hook(device);\n\t\t\t\tv39_install_resource_hooks(device);\n\t\t\t\tv55_install_descriptor_hooks(device);\n\t\t\t\treshade::log::message(\n\t\t\t\t\treshade::log::level::info,\n\t\t\t\t\t"D3DMetal RTX temporal ray-hit snapshots v64: ACTIVE stages=3 thresholds=96,512,1400 records-per-stage=1280 strict-lineage=v61 normalization=v63-fdiv broad-gpu-va-tracing=disabled commands_modified=diagnostic-copy-only.");\n\t\t\t});\n'''
text = replace_once(text, v63_activation, v64_activation, "activate V64 minimal forensic hooks")

text = replace_once(
    text,
    "    // D3DMetal RTX strict FP32 uint24 division v63.\n",
    "    // D3DMetal RTX temporal ray-hit snapshots v64.\n"
    "    // Three same-range u1 snapshots separate producer data evolution from\n"
    "    // downstream temporal-lighting accumulation.\n\n"
    "    // D3DMetal RTX strict FP32 uint24 division v63.\n",
    "add V64 durable source marker",
)

SOURCE.write_text(text, encoding="utf-8", newline="\n")
REPORT.write_text(
    "\n".join(
        [
            "V64_TEMPORAL_RAYHIT_SNAPSHOTS_PATCH_OK",
            "BASELINE=V63_STRICT_FP32_DIVISION",
            "STRICT_V61_REWRITTEN_LINEAGE=ENABLED",
            "SNAPSHOT_COUNT=3",
            "SNAPSHOT_THRESHOLDS=96,512,1400",
            "SAMPLED_RECORDS_PER_SNAPSHOT=1280",
            "SAMPLE_STARTS=0,1/8,1/4,3/8,1/2",
            "EARLY_LOCAL_ROOT_CAPTURE_THRESHOLD=64",
            "V58_GPU_VA_GLOBAL_TRACING=DISABLED",
            "V57_COPY_LINEAGE_GLOBAL_TRACING=DISABLED",
            "MAP_UNMAP_LINEAGE=TEMPORARILY_ENABLED",
            "RENDER_COMMAND_MODIFICATION=DIAGNOSTIC_COPY_AND_RESTORE_UAV_STATE_ONLY",
            "RESULT=PASS",
            "",
        ]
    ),
    encoding="utf-8",
    newline="\n",
)
print("V64_TEMPORAL_RAYHIT_SNAPSHOTS_PATCH_OK")
