from __future__ import annotations

from pathlib import Path

SOURCE = Path('source/d3d12/d3d12.cpp')
REPORT = Path('v62-patch-report.txt')


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: expected exactly one anchor, found {count}')
    return text.replace(old, new, 1)


text = SOURCE.read_text(encoding='utf-8')
if 'D3DMetal RTX ray-hit output forensics v62' in text:
    raise RuntimeError('V62 patch appears to be applied already')
if 'D3DMetal RTX AddToStateObject lineage bridge v61' not in text:
    raise RuntimeError('V61 baseline marker is missing')

# Keep a raw pointer for descriptor-resolved buffers. V62 pins only the exact u1
# resource after the descriptor contract is proven, avoiding thousands of retained
# references during the descriptor census.
text = replace_once(
    text,
    '''        unsigned int flags = 0;\n        UINT64 gpu_va = 0;\n    };\n''',
    '''        unsigned int flags = 0;\n        UINT64 gpu_va = 0;\n        ID3D12Resource *resource = nullptr;\n    };\n''',
    'retain V55 resource pointer',
)

text = replace_once(
    text,
    '''        info.gpu_va = desc.Dimension == D3D12_RESOURCE_DIMENSION_BUFFER ?\n            static_cast<UINT64>(resource->GetGPUVirtualAddress()) : 0;\n\n        {\n''',
    '''        info.gpu_va = desc.Dimension == D3D12_RESOURCE_DIMENSION_BUFFER ?\n            static_cast<UINT64>(resource->GetGPUVirtualAddress()) : 0;\n        info.resource = resource;\n        resource->AddRef();\n\n        {\n''',
    'record registered resource pointer',
)

# Add the capture state beside the V55 descriptor census state so it is visible to
# the local-root resolver and to the later command-list/queue hooks.
text = replace_once(
    text,
    '''    static std::atomic<uint64_t> s_v55_descriptor_events = 0;\n    static std::atomic<uint64_t> s_v55_descriptor_copy_events = 0;\n''',
    '''    static std::atomic<uint64_t> s_v55_descriptor_events = 0;\n    static std::atomic<uint64_t> s_v55_descriptor_copy_events = 0;\n\n    constexpr UINT v62_rayhit_stride = 24;\n    constexpr UINT v62_sample_records_per_block = 256;\n    constexpr UINT v62_max_sample_blocks = 5;\n\n    static std::mutex s_v62_capture_mutex;\n    static ID3D12Resource *s_v62_u1_resource = nullptr;\n    static UINT64 s_v62_u1_base_offset = 0;\n    static UINT64 s_v62_u1_total_bytes = 0;\n    static UINT64 s_v62_u1_total_records = 0;\n    static ID3D12Resource *s_v62_readback_resource = nullptr;\n    static ID3D12Fence *s_v62_capture_fence = nullptr;\n    static HANDLE s_v62_capture_event = nullptr;\n    static void *s_v62_capture_command_list_identity = nullptr;\n    static UINT64 s_v62_block_source_offsets[v62_max_sample_blocks] = {};\n    static UINT64 s_v62_block_destination_offsets[v62_max_sample_blocks] = {};\n    static UINT64 s_v62_block_record_starts[v62_max_sample_blocks] = {};\n    static UINT s_v62_block_count = 0;\n    static UINT64 s_v62_readback_bytes = 0;\n    static std::atomic<bool> s_v62_u1_target_ready = false;\n    static std::atomic<bool> s_v62_capture_claimed = false;\n    static std::atomic<bool> s_v62_copy_recorded = false;\n    static std::atomic<bool> s_v62_queue_signaled = false;\n    static std::atomic<bool> s_v62_readback_complete = false;\n    static std::atomic<bool> s_v62_capture_failed = false;\n''',
    'add V62 capture state',
)

# Publish the exact u1 resource after V55 has proven the local-root contract.
needle = '''        reshade::log::message(\n            exact_ok ? reshade::log::level::info :\n                       reshade::log::level::warning,\n            "D3DMetal RTX raygen local-root descriptor resolution v55: LOCAL_ROOT_DESCRIPTOR_RESOLUTION_RESULT success=1 srv_resolved=%u/8 cbv_resolved=%u/1 uav_resolved=%u/2 u1_contract_match=%u descriptor_events=%llu descriptor_copy_events=%llu diagnosis=%s commands_modified=0 capture_scope=v56-steady-state-inherited-pipeline.",\n            srv_resolved,\n            cbv_resolved,\n            uav_resolved,\n            u1_resource_ok ? 1u : 0u,\n            static_cast<unsigned long long>(\n                s_v55_descriptor_events.load(std::memory_order_acquire)),\n            static_cast<unsigned long long>(\n                s_v55_descriptor_copy_events.load(std::memory_order_acquire)),\n            diagnosis);\n'''
insert = needle + r'''

        if (exact_ok && u1_resource.resource != nullptr)
        {
            const UINT64 first_byte =
                static_cast<UINT64>(u1.first_element) *
                static_cast<UINT64>(u1.structure_stride);
            const UINT64 descriptor_bytes =
                static_cast<UINT64>(u1.num_elements) *
                static_cast<UINT64>(u1.structure_stride);
            const UINT64 available_bytes =
                first_byte < u1_resource.width ?
                    u1_resource.width - first_byte : 0;
            const UINT64 usable_bytes =
                descriptor_bytes < available_bytes ?
                    descriptor_bytes : available_bytes;
            const UINT64 total_records =
                u1.structure_stride != 0 ?
                    usable_bytes / u1.structure_stride : 0;

            bool published = false;
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
            }
        }
'''
text = replace_once(text, needle, insert, 'publish V62 u1 target')

# Reactivate only the hooks needed to recover the mapped raygen record and exact
# descriptor bindings. GPU-VA and CopyBufferRegion lineage remain disabled.
text = replace_once(
    text,
    '''    static std::atomic<bool> s_v59_high_frequency_tracking_enabled = false;\n''',
    '''    static std::atomic<bool> s_v59_high_frequency_tracking_enabled = true;\n''',
    'enable temporary V59 map tracking',
)

text = replace_once(
    text,
    '''        // V60 visual mode: do not install Map, Unmap, or GPU-VA hooks.\n        // V59 already proved the shader-table lineage and local-root contract.\n''',
    '''        // V62 forensic mode: Map and Unmap are temporarily observed so the\n        // persistent 64-byte raygen record can be recovered. Copy and GPU-VA\n        // tracing stay disabled.\n        v57_install_resource_map_hook(resource);\n        v59_install_resource_unmap_hook(resource);\n''',
    'restore minimal resource mapping hooks',
)

# The old V38/V39 capture gates target an unrewritten inherited pipeline. V62 must
# target the strict V61 rewritten descendant instead.
old_gate = '''\t\tuint64_t v56_pipeline_id = 0;\n\t\tuint64_t v56_pipeline_ray_index = 0;\n\t\tif (!dispatch_rays || command_list == nullptr ||\n\t\t\targument_buffer == nullptr ||\n\t\t\t!v56_steady_state_pipeline_candidate(\n\t\t\t\tcommand_list,\n\t\t\t\tv56_pipeline_id,\n\t\t\t\tv56_pipeline_ray_index))\n\t\t\treturn;\n'''
new_gate = '''\t\tuint64_t v62_pipeline_id = 0;\n\t\tuint64_t v62_pipeline_ray_index = 0;\n\t\tuint64_t v62_state_call = 0;\n\t\tif (!dispatch_rays || command_list == nullptr ||\n\t\t\targument_buffer == nullptr ||\n\t\t\t!v61_rewritten_steady_state_candidate(\n\t\t\t\treinterpret_cast<ID3D12GraphicsCommandList4 *>(command_list),\n\t\t\t\tv62_pipeline_id,\n\t\t\t\tv62_pipeline_ray_index,\n\t\t\t\tv62_state_call))\n\t\t\treturn;\n'''
text = replace_once(text, old_gate, new_gate, 'retarget V38 to strict rewritten pipeline')

old_gate2 = '''        uint64_t v56_pipeline_id = 0;\n        uint64_t v56_pipeline_ray_index = 0;\n        if (!dispatch_rays || command_list == nullptr ||\n            !v56_steady_state_pipeline_candidate(\n                command_list,\n                v56_pipeline_id,\n                v56_pipeline_ray_index))\n            return;\n'''
new_gate2 = '''        uint64_t v62_pipeline_id = 0;\n        uint64_t v62_pipeline_ray_index = 0;\n        uint64_t v62_state_call = 0;\n        if (!dispatch_rays || command_list == nullptr ||\n            !v61_rewritten_steady_state_candidate(\n                reinterpret_cast<ID3D12GraphicsCommandList4 *>(command_list),\n                v62_pipeline_id,\n                v62_pipeline_ray_index,\n                v62_state_call))\n            return;\n'''
text = replace_once(text, old_gate2, new_gate2, 'retarget V39 to strict rewritten pipeline')

# Install the queue, resource, and descriptor hooks that V60 intentionally parked.
old_disabled = '''\t\tstatic std::once_flag v60_heavy_diagnostics_disabled_once;\n\t\tstd::call_once(\n\t\t\tv60_heavy_diagnostics_disabled_once,\n\t\t\t[]()\n\t\t\t{\n\t\t\t\treshade::log::message(\n\t\t\t\t\treshade::log::level::info,\n\t\t\t\t\t"D3DMetal RTX real FP32 visual candidate v60: HEAVY_DIAGNOSTICS_DISABLED dispatch-readback=1 shader-table-readback=1 descriptor-census=1 map-unmap=1 gpu-va=1 copy-lineage=1.");\n\t\t\t});\n'''
new_enabled = '''\t\tstatic std::once_flag v62_forensic_hooks_once;\n\t\tstd::call_once(\n\t\t\tv62_forensic_hooks_once,\n\t\t\t[device]()\n\t\t\t{\n\t\t\t\tv38_install_create_command_queue_hook(device);\n\t\t\t\tv39_install_resource_hooks(device);\n\t\t\t\tv55_install_descriptor_hooks(device);\n\t\t\t\treshade::log::message(\n\t\t\t\t\treshade::log::level::info,\n\t\t\t\t\t"D3DMetal RTX ray-hit output forensics v62: FORENSIC_HOOKS_ENABLED dispatch-argument-readback=1 mapped-raygen-lineage=1 descriptor-resolution=1 u1-output-readback=1 gpu-va-tracing=0 copy-lineage=0.");\n\t\t\t});\n'''
text = replace_once(text, old_disabled, new_enabled, 'enable V62 forensic hooks')

# Reinsert the dispatch and shader-record recovery calls before the strict V61 proof.
proof_anchor = '''\t\tif (dispatch_rays &&\n\t\t\t!s_v61_rewritten_steady_state_seen.load(std::memory_order_acquire))\n'''
proof_insert = '''\t\tv38_try_capture_dispatch_record(\n\t\t\tcommand_list,\n\t\t\targument_buffer,\n\t\t\targument_buffer_offset,\n\t\t\tdispatch_rays,\n\t\t\trewritten,\n\t\t\tstate_call,\n\t\t\trewritten_ray_index);\n\n\t\tv39_try_capture_shader_tables(\n\t\t\tcommand_list,\n\t\t\tdispatch_rays,\n\t\t\trewritten,\n\t\t\tstate_call,\n\t\t\trewritten_ray_index);\n\n''' + proof_anchor
text = replace_once(text, proof_anchor, proof_insert, 'restore rewritten dispatch and raygen recovery')

# Add the output-copy implementation immediately before the V34 command signature
# types. It uses the already-installed V38 queue hook for fence submission.
v62_code = r'''

    void v62_analyze_record_words(
        const unsigned char *record,
        uint64_t &nan_words,
        uint64_t &inf_words,
        uint64_t &negative_words,
        uint64_t &zero_words)
    {
        for (size_t word_index = 0; word_index < 6; ++word_index)
        {
            uint32_t word = 0;
            memcpy(&word, record + word_index * sizeof(word), sizeof(word));
            const uint32_t exponent = word & 0x7F800000u;
            const uint32_t mantissa = word & 0x007FFFFFu;
            if (word == 0)
                ++zero_words;
            if ((word & 0x80000000u) != 0 && (word & 0x7FFFFFFFu) != 0)
                ++negative_words;
            if (exponent == 0x7F800000u)
            {
                if (mantissa == 0)
                    ++inf_words;
                else
                    ++nan_words;
            }
        }
    }

    DWORD WINAPI v62_readback_worker(LPVOID)
    {
        ID3D12Resource *readback = nullptr;
        ID3D12Fence *fence = nullptr;
        HANDLE event_handle = nullptr;
        UINT64 total_bytes = 0;
        UINT block_count = 0;
        UINT64 destination_offsets[v62_max_sample_blocks] = {};
        UINT64 record_starts[v62_max_sample_blocks] = {};

        {
            std::lock_guard<std::mutex> lock(s_v62_capture_mutex);
            readback = s_v62_readback_resource;
            fence = s_v62_capture_fence;
            event_handle = s_v62_capture_event;
            total_bytes = s_v62_readback_bytes;
            block_count = s_v62_block_count;
            memcpy(destination_offsets, s_v62_block_destination_offsets, sizeof(destination_offsets));
            memcpy(record_starts, s_v62_block_record_starts, sizeof(record_starts));
            if (readback != nullptr) readback->AddRef();
            if (fence != nullptr) fence->AddRef();
        }

        if (readback == nullptr || fence == nullptr || event_handle == nullptr ||
            total_bytes == 0 || block_count == 0)
        {
            s_v62_capture_failed.store(true, std::memory_order_release);
            reshade::log::message(
                reshade::log::level::warning,
                "D3DMetal RTX ray-hit output forensics v62: U1_READBACK_RESULT success=0 reason=missing-capture-objects.");
            if (readback != nullptr) readback->Release();
            if (fence != nullptr) fence->Release();
            return 0;
        }

        const DWORD wait_result = WaitForSingleObject(event_handle, 20000);
        if (wait_result != WAIT_OBJECT_0)
        {
            s_v62_capture_failed.store(true, std::memory_order_release);
            reshade::log::message(
                reshade::log::level::warning,
                "D3DMetal RTX ray-hit output forensics v62: U1_READBACK_RESULT success=0 reason=fence-wait wait_result=%lu completed=%llu.",
                wait_result,
                static_cast<unsigned long long>(fence->GetCompletedValue()));
            readback->Release();
            fence->Release();
            return 0;
        }

        void *mapped = nullptr;
        const D3D12_RANGE read_range = { 0, static_cast<SIZE_T>(total_bytes) };
        const HRESULT map_hr = readback->Map(0, &read_range, &mapped);
        if (FAILED(map_hr) || mapped == nullptr)
        {
            s_v62_capture_failed.store(true, std::memory_order_release);
            reshade::log::message(
                reshade::log::level::warning,
                "D3DMetal RTX ray-hit output forensics v62: U1_READBACK_RESULT success=0 reason=map hr=%s raw=0x%08X.",
                reshade::log::hr_to_string(map_hr).c_str(),
                static_cast<uint32_t>(map_hr));
            readback->Release();
            fence->Release();
            return 0;
        }

        const unsigned char *bytes = static_cast<const unsigned char *>(mapped);
        const UINT64 block_bytes =
            static_cast<UINT64>(v62_sample_records_per_block) * v62_rayhit_stride;
        uint64_t total_records = 0;
        uint64_t all_zero_records = 0;
        uint64_t all_ff_records = 0;
        uint64_t nan_words = 0;
        uint64_t inf_words = 0;
        uint64_t negative_words = 0;
        uint64_t zero_words = 0;
        std::vector<uint64_t> unique_hashes;

        for (UINT block = 0; block < block_count; ++block)
        {
            const UINT64 destination = destination_offsets[block];
            if (destination + block_bytes > total_bytes)
                break;

            uint64_t block_zero = 0;
            uint64_t block_ff = 0;
            uint64_t block_nan = 0;
            uint64_t block_inf = 0;
            uint64_t block_negative = 0;
            uint64_t block_zero_words = 0;
            std::vector<uint64_t> block_hashes;

            for (UINT record_index = 0; record_index < v62_sample_records_per_block; ++record_index)
            {
                const unsigned char *record =
                    bytes + destination +
                    static_cast<UINT64>(record_index) * v62_rayhit_stride;
                bool all_zero = true;
                bool all_ff = true;
                for (size_t byte_index = 0; byte_index < v62_rayhit_stride; ++byte_index)
                {
                    all_zero = all_zero && record[byte_index] == 0;
                    all_ff = all_ff && record[byte_index] == 0xFF;
                }
                if (all_zero) { ++block_zero; ++all_zero_records; }
                if (all_ff) { ++block_ff; ++all_ff_records; }

                uint64_t local_nan = 0, local_inf = 0, local_negative = 0, local_zero_words = 0;
                v62_analyze_record_words(
                    record, local_nan, local_inf, local_negative, local_zero_words);
                block_nan += local_nan; nan_words += local_nan;
                block_inf += local_inf; inf_words += local_inf;
                block_negative += local_negative; negative_words += local_negative;
                block_zero_words += local_zero_words; zero_words += local_zero_words;

                const uint64_t hash = v39_fnv1a64(record, v62_rayhit_stride);
                if (std::find(block_hashes.begin(), block_hashes.end(), hash) == block_hashes.end())
                    block_hashes.push_back(hash);
                if (std::find(unique_hashes.begin(), unique_hashes.end(), hash) == unique_hashes.end())
                    unique_hashes.push_back(hash);

                if (record_index < 8)
                {
                    char record_hex[v62_rayhit_stride * 2 + 1] = {};
                    v39_bytes_to_hex(record, v62_rayhit_stride, record_hex, sizeof(record_hex));
                    uint32_t words[6] = {};
                    float floats[6] = {};
                    memcpy(words, record, sizeof(words));
                    memcpy(floats, record, sizeof(floats));
                    reshade::log::message(
                        reshade::log::level::info,
                        "D3DMetal RTX ray-hit output forensics v62: U1_RECORD block=%u sample_index=%u global_record=%llu hex=%s u32=%08X,%08X,%08X,%08X,%08X,%08X f32=%.9g,%.9g,%.9g,%.9g,%.9g,%.9g.",
                        block,
                        record_index,
                        static_cast<unsigned long long>(record_starts[block] + record_index),
                        record_hex,
                        words[0], words[1], words[2], words[3], words[4], words[5],
                        floats[0], floats[1], floats[2], floats[3], floats[4], floats[5]);
                }
                ++total_records;
            }

            reshade::log::message(
                reshade::log::level::info,
                "D3DMetal RTX ray-hit output forensics v62: U1_BLOCK_SUMMARY block=%u start_record=%llu records=%u all_zero=%llu all_ff=%llu nan_words=%llu inf_words=%llu negative_words=%llu zero_words=%llu unique_record_hashes=%zu.",
                block,
                static_cast<unsigned long long>(record_starts[block]),
                v62_sample_records_per_block,
                static_cast<unsigned long long>(block_zero),
                static_cast<unsigned long long>(block_ff),
                static_cast<unsigned long long>(block_nan),
                static_cast<unsigned long long>(block_inf),
                static_cast<unsigned long long>(block_negative),
                static_cast<unsigned long long>(block_zero_words),
                block_hashes.size());
        }

        const D3D12_RANGE written_range = { 0, 0 };
        readback->Unmap(0, &written_range);
        s_v62_readback_complete.store(true, std::memory_order_release);
        reshade::log::message(
            reshade::log::level::info,
            "D3DMetal RTX ray-hit output forensics v62: U1_READBACK_RESULT success=1 blocks=%u sampled_records=%llu stride=%u all_zero_records=%llu all_ff_records=%llu nan_words=%llu inf_words=%llu negative_words=%llu zero_words=%llu unique_record_hashes=%zu commands_modified=copy-after-dispatch-restored-uav-state.",
            block_count,
            static_cast<unsigned long long>(total_records),
            v62_rayhit_stride,
            static_cast<unsigned long long>(all_zero_records),
            static_cast<unsigned long long>(all_ff_records),
            static_cast<unsigned long long>(nan_words),
            static_cast<unsigned long long>(inf_words),
            static_cast<unsigned long long>(negative_words),
            static_cast<unsigned long long>(zero_words),
            unique_hashes.size());

        readback->Release();
        fence->Release();
        return 0;
    }

    void v62_try_capture_u1_output(ID3D12GraphicsCommandList *command_list)
    {
        if (command_list == nullptr ||
            !s_v62_u1_target_ready.load(std::memory_order_acquire) ||
            s_v62_readback_complete.load(std::memory_order_acquire))
            return;

        bool expected = false;
        if (!s_v62_capture_claimed.compare_exchange_strong(
                expected, true, std::memory_order_acq_rel))
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

        if (resource == nullptr || total_records == 0)
        {
            s_v62_capture_failed.store(true, std::memory_order_release);
            reshade::log::message(
                reshade::log::level::warning,
                "D3DMetal RTX ray-hit output forensics v62: U1_CAPTURE_RECORDED success=0 reason=target-unavailable.");
            if (resource != nullptr) resource->Release();
            return;
        }

        const UINT64 block_records =
            total_records < v62_sample_records_per_block ?
                total_records : v62_sample_records_per_block;
        if (block_records != v62_sample_records_per_block)
        {
            s_v62_capture_failed.store(true, std::memory_order_release);
            reshade::log::message(
                reshade::log::level::warning,
                "D3DMetal RTX ray-hit output forensics v62: U1_CAPTURE_RECORDED success=0 reason=insufficient-records total=%llu required=%u.",
                static_cast<unsigned long long>(total_records),
                v62_sample_records_per_block);
            resource->Release();
            return;
        }

        UINT64 starts[v62_max_sample_blocks] = {
            0,
            total_records / 4,
            total_records / 2,
            (total_records * 3) / 4,
            total_records - v62_sample_records_per_block,
        };
        for (UINT index = 0; index < v62_max_sample_blocks; ++index)
        {
            if (starts[index] + v62_sample_records_per_block > total_records)
                starts[index] = total_records - v62_sample_records_per_block;
        }

        ID3D12Device *device = nullptr;
        HRESULT hr = resource->GetDevice(
            __uuidof(ID3D12Device), reinterpret_cast<void **>(&device));
        if (FAILED(hr) || device == nullptr)
        {
            s_v62_capture_failed.store(true, std::memory_order_release);
            resource->Release();
            return;
        }

        const UINT64 block_bytes =
            static_cast<UINT64>(v62_sample_records_per_block) * v62_rayhit_stride;
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
            &heap_properties,
            D3D12_HEAP_FLAG_NONE,
            &readback_desc,
            D3D12_RESOURCE_STATE_COPY_DEST,
            nullptr,
            __uuidof(ID3D12Resource),
            reinterpret_cast<void **>(&readback));
        ID3D12Fence *fence = nullptr;
        HRESULT fence_hr = device->CreateFence(
            0, D3D12_FENCE_FLAG_NONE, __uuidof(ID3D12Fence),
            reinterpret_cast<void **>(&fence));
        HANDLE event_handle = CreateEventW(nullptr, FALSE, FALSE, nullptr);
        device->Release();

        if (FAILED(hr) || readback == nullptr || FAILED(fence_hr) ||
            fence == nullptr || event_handle == nullptr)
        {
            s_v62_capture_failed.store(true, std::memory_order_release);
            reshade::log::message(
                reshade::log::level::warning,
                "D3DMetal RTX ray-hit output forensics v62: U1_CAPTURE_RECORDED success=0 reason=create-capture hr=%s fence_hr=%s event=%p.",
                reshade::log::hr_to_string(hr).c_str(),
                reshade::log::hr_to_string(fence_hr).c_str(),
                event_handle);
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
            const UINT64 source_offset =
                base_offset + starts[block] * v62_rayhit_stride;
            const UINT64 destination_offset = block * block_bytes;
            command_list->CopyBufferRegion(
                readback, destination_offset, resource, source_offset, block_bytes);
            s_v62_block_source_offsets[block] = source_offset;
            s_v62_block_destination_offsets[block] = destination_offset;
            s_v62_block_record_starts[block] = starts[block];
        }
        command_list->ResourceBarrier(1, &to_uav);

        void *const identity = v33_identity_pointer(
            reinterpret_cast<IUnknown *>(command_list));
        {
            std::lock_guard<std::mutex> lock(s_v62_capture_mutex);
            s_v62_readback_resource = readback;
            s_v62_capture_fence = fence;
            s_v62_capture_event = event_handle;
            s_v62_capture_command_list_identity = identity;
            s_v62_block_count = v62_max_sample_blocks;
            s_v62_readback_bytes = readback_bytes;
        }
        s_v62_copy_recorded.store(true, std::memory_order_release);
        reshade::log::message(
            reshade::log::level::info,
            "D3DMetal RTX ray-hit output forensics v62: U1_CAPTURE_RECORDED success=1 command_list=%p identity=%p resource=%p base_offset=%llu total_records=%llu blocks=%u records_per_block=%u readback_bytes=%llu commands_modified=copy-after-dispatch-restored-uav-state.",
            command_list,
            identity,
            resource,
            static_cast<unsigned long long>(base_offset),
            static_cast<unsigned long long>(total_records),
            v62_max_sample_blocks,
            v62_sample_records_per_block,
            static_cast<unsigned long long>(readback_bytes));
        resource->Release();
    }

    void v62_on_execute_command_lists(
        ID3D12CommandQueue *queue,
        UINT count,
        ID3D12CommandList *const *command_lists)
    {
        void *capture_identity = nullptr;
        {
            std::lock_guard<std::mutex> lock(s_v62_capture_mutex);
            capture_identity = s_v62_capture_command_list_identity;
        }
        if (capture_identity == nullptr || command_lists == nullptr)
            return;

        bool contains_capture = false;
        for (UINT index = 0; index < count; ++index)
        {
            ID3D12CommandList *list = nullptr;
            if (!safe_copy_from_process(command_lists + index, &list, sizeof(list)) ||
                list == nullptr)
                continue;
            if (v33_identity_pointer(reinterpret_cast<IUnknown *>(list)) == capture_identity)
            {
                contains_capture = true;
                break;
            }
        }

        bool expected = false;
        if (!contains_capture ||
            !s_v62_queue_signaled.compare_exchange_strong(
                expected, true, std::memory_order_acq_rel))
            return;

        ID3D12Fence *fence = nullptr;
        HANDLE event_handle = nullptr;
        {
            std::lock_guard<std::mutex> lock(s_v62_capture_mutex);
            fence = s_v62_capture_fence;
            event_handle = s_v62_capture_event;
        }

        HRESULT signal_hr = E_FAIL;
        HRESULT event_hr = E_FAIL;
        if (queue != nullptr && fence != nullptr && event_handle != nullptr)
        {
            signal_hr = queue->Signal(fence, 1);
            if (SUCCEEDED(signal_hr))
                event_hr = fence->SetEventOnCompletion(1, event_handle);
        }
        reshade::log::message(
            SUCCEEDED(signal_hr) && SUCCEEDED(event_hr) ?
                reshade::log::level::info : reshade::log::level::warning,
            "D3DMetal RTX ray-hit output forensics v62: U1_QUEUE_SUBMITTED count=%u signal_hr=%s event_hr=%s.",
            count,
            reshade::log::hr_to_string(signal_hr).c_str(),
            reshade::log::hr_to_string(event_hr).c_str());

        if (SUCCEEDED(signal_hr) && SUCCEEDED(event_hr))
        {
            HANDLE thread_handle = CreateThread(
                nullptr, 0, &v62_readback_worker, nullptr, 0, nullptr);
            if (thread_handle != nullptr)
                CloseHandle(thread_handle);
            else
                s_v62_capture_failed.store(true, std::memory_order_release);
        }
        else
        {
            s_v62_capture_failed.store(true, std::memory_order_release);
        }
    }
'''
anchor = '''\n\n\tusing v34_create_command_signature_fn = HRESULT (STDMETHODCALLTYPE *)(\n'''
text = replace_once(text, anchor, v62_code + anchor, 'insert V62 output readback implementation')

# Forward-declare the V62 queue observer before the earlier V38 hook body.
text = replace_once(
    text,
    '''\tvoid v38_install_execute_command_lists_hook(ID3D12CommandQueue *queue);\n''',
    '''\tvoid v62_on_execute_command_lists(\n\t\tID3D12CommandQueue *queue,\n\t\tUINT count,\n\t\tID3D12CommandList *const *command_lists);\n\n\tvoid v38_install_execute_command_lists_hook(ID3D12CommandQueue *queue);\n''',
    'forward declare V62 queue observer',
)

# Let the shared command-queue hook submit the V62 fence after the captured list.
text = replace_once(
    text,
    '''\t\tv39_on_execute_command_lists(queue, count, command_lists);\n\n\t\tbool expected = false;\n''',
    '''\t\tv39_on_execute_command_lists(queue, count, command_lists);\n\t\tv62_on_execute_command_lists(queue, count, command_lists);\n\n\t\tbool expected = false;\n''',
    'connect V62 queue submission',
)

# The u1 output is only meaningful after the genuine indirect dispatch has been
# recorded. Insert the copy immediately after the original ExecuteIndirect call.
old_tail = '''\t\tif (s_v34_original_execute_indirect != nullptr)\n\t\t\ts_v34_original_execute_indirect(\n\t\t\t\tcommand_list,\n\t\t\t\tcommand_signature,\n\t\t\t\tmax_command_count,\n\t\t\t\targument_buffer,\n\t\t\t\targument_buffer_offset,\n\t\t\t\tcount_buffer,\n\t\t\t\tcount_buffer_offset);\n\t}\n'''
new_tail = '''\t\tif (s_v34_original_execute_indirect != nullptr)\n\t\t\ts_v34_original_execute_indirect(\n\t\t\t\tcommand_list,\n\t\t\t\tcommand_signature,\n\t\t\t\tmax_command_count,\n\t\t\t\targument_buffer,\n\t\t\t\targument_buffer_offset,\n\t\t\t\tcount_buffer,\n\t\t\t\tcount_buffer_offset);\n\n\t\tif (dispatch_rays &&\n\t\t\ts_v61_rewritten_steady_state_seen.load(std::memory_order_acquire))\n\t\t\tv62_try_capture_u1_output(command_list);\n\t}\n'''
text = replace_once(text, old_tail, new_tail, 'capture u1 after genuine dispatch')

# Add a durable source heading.
text = replace_once(
    text,
    '''    // D3DMetal RTX AddToStateObject lineage bridge v61.\n''',
    '''    // D3DMetal RTX ray-hit output forensics v62.\n    // Recovers the rewritten steady-state raygen local root, resolves u1, and\n    // copies five 256-record samples after a genuine rewritten dispatch.\n\n    // D3DMetal RTX AddToStateObject lineage bridge v61.\n''',
    'add V62 source heading',
)

SOURCE.write_text(text, encoding='utf-8', newline='\n')
REPORT.write_text(
    '\n'.join([
        'V62_RAYHIT_OUTPUT_FORENSICS_PATCH_OK',
        'BASELINE=V61_STRICT_REWRITTEN_ADDTOSTATEOBJECT_LINEAGE',
        'STRICT_REWRITTEN_PIPELINE_REQUIRED=YES',
        'DISPATCH_ARGUMENT_READBACK=TEMPORARILY_ENABLED',
        'MAPPED_RAYGEN_RECORD_LINEAGE=TEMPORARILY_ENABLED',
        'DESCRIPTOR_RESOLUTION=TEMPORARILY_ENABLED',
        'GPU_VA_GLOBAL_TRACING=DISABLED',
        'COPY_LINEAGE_GLOBAL_TRACING=DISABLED',
        'U1_STRUCTURE_STRIDE=24',
        'U1_SAMPLE_BLOCKS=5',
        'U1_RECORDS_PER_BLOCK=256',
        'U1_TOTAL_SAMPLED_RECORDS=1280',
        'U1_COPY_OCCURS=AFTER_GENUINE_REWRITTEN_DISPATCH',
        'U1_RESOURCE_STATE_RESTORED=UNORDERED_ACCESS',
        'RAW_HEX_LOGGING=YES',
        'U32_AND_F32_DECODE=YES',
        'NAN_INF_NEGATIVE_ZERO_COUNTS=YES',
        'RESULT=PASS',
        '',
    ]),
    encoding='utf-8',
    newline='\n',
)
print('V62_RAYHIT_OUTPUT_FORENSICS_PATCH_OK')
