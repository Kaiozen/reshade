from __future__ import annotations

from pathlib import Path

SOURCE = Path("source/d3d12/d3d12.cpp")
REPORT = Path("v59-patch-report.txt")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one anchor, found {count}")
    return text.replace(old, new, 1)


text = SOURCE.read_text(encoding="utf-8")
if "D3DMetal RTX steady-state shader-table lineage v59" in text:
    raise RuntimeError("V59 patch appears to be applied already")
if "D3DMetal RTX live GPU-VA relocation tracking v58" not in text:
    raise RuntimeError("V58 baseline marker is missing")

text = replace_once(
    text,
    """\tusing v57_resource_map_fn = HRESULT (STDMETHODCALLTYPE *)(\n\t\tID3D12Resource *,\n\t\tUINT,\n\t\tconst D3D12_RANGE *,\n\t\tvoid **);\n\n\tusing v58_get_gpu_virtual_address_fn =\n""",
    """\tusing v57_resource_map_fn = HRESULT (STDMETHODCALLTYPE *)(\n\t\tID3D12Resource *,\n\t\tUINT,\n\t\tconst D3D12_RANGE *,\n\t\tvoid **);\n\n\tusing v59_resource_unmap_fn = void (STDMETHODCALLTYPE *)(\n\t\tID3D12Resource *,\n\t\tUINT,\n\t\tconst D3D12_RANGE *);\n\n\tusing v58_get_gpu_virtual_address_fn =\n""",
    "add Unmap function type",
)

text = replace_once(
    text,
    """\tconstexpr size_t v57_copy_buffer_region_slot = 15;\n\tconstexpr size_t v57_resource_map_slot = 8;\n\tconstexpr UINT64 v57_max_recovery_buffer_bytes = 16ull * 1024ull * 1024ull;\n""",
    """\tconstexpr size_t v57_copy_buffer_region_slot = 15;\n\tconstexpr size_t v57_resource_map_slot = 8;\n\tconstexpr size_t v59_resource_unmap_slot = 9;\n\tconstexpr UINT64 v57_max_recovery_buffer_bytes = 16ull * 1024ull * 1024ull;\n""",
    "add Unmap slot",
)

text = replace_once(
    text,
    """\tvoid v58_install_gpu_va_hook(ID3D12Resource *resource);\n\tvoid v57_install_resource_map_hook(ID3D12Resource *resource);\n\tvoid v39_track_resource(void *created);\n""",
    """\tvoid v58_install_gpu_va_hook(ID3D12Resource *resource);\n\tvoid v57_install_resource_map_hook(ID3D12Resource *resource);\n\tvoid v59_install_resource_unmap_hook(ID3D12Resource *resource);\n\tvoid v39_track_resource(void *created);\n""",
    "add V59 forward declaration",
)

v59_block = r'''

    // V59 closes the V58 resource-lookup gap without changing shader-table
    // addresses or command bytes. It retains a rolling window of small buffers
    // observed through Map and CopyBufferRegion, refreshes their live GPU virtual
    // addresses at the selected steady-state dispatch, and follows a 64-byte
    // ExecuteTrace raygen record through Unmap and copy lineage. High-frequency
    // tracking is disabled immediately after the one decisive lookup attempt.
    constexpr UINT64 v59_max_candidate_resource_bytes =
        4ull * 1024ull * 1024ull;
    constexpr UINT64 v59_max_retained_total_bytes =
        384ull * 1024ull * 1024ull;
    constexpr size_t v59_max_retained_resources = 4096;
    constexpr size_t v59_max_record_candidates = 512;
    constexpr SIZE_T v59_max_map_scan_bytes =
        1024ull * 1024ull;

    struct v59_retained_resource
    {
        ID3D12Resource *resource = nullptr;
        UINT64 width = 0;
        D3D12_HEAP_TYPE heap_type = D3D12_HEAP_TYPE_DEFAULT;
        uint64_t sequence = 0;
    };

    struct v59_retention_ticket
    {
        ID3D12Resource *resource = nullptr;
        uint64_t sequence = 0;
    };

    struct v59_map_state
    {
        ID3D12Resource *resource = nullptr;
        void *data = nullptr;
        UINT subresource = 0;
        UINT64 width = 0;
        uint64_t sequence = 0;
    };

    struct v59_shader_record_candidate
    {
        ID3D12Resource *resource = nullptr;
        UINT64 offset = 0;
        unsigned char bytes[64] = {};
        uint64_t sequence = 0;
        uint32_t lineage_depth = 0;
        const char *source = nullptr;
    };

    static std::atomic<bool> s_v59_high_frequency_tracking_enabled = true;
    static std::atomic<bool> s_v59_unmap_hook_installed = false;
    static std::atomic<bool> s_v59_rescan_complete = false;
    static std::atomic<bool> s_v59_lineage_resolution_invoked = false;
    static std::atomic<bool> s_v59_lineage_exact_address_match = false;
    static std::atomic<uint64_t> s_v59_resource_activity_sequence = 0;
    static std::atomic<uint64_t> s_v59_candidate_sequence = 0;
    static std::atomic<uint64_t> s_v59_map_capture_count = 0;
    static std::atomic<uint64_t> s_v59_unmap_capture_count = 0;
    static std::atomic<uint64_t> s_v59_copy_lineage_count = 0;
    static std::atomic<uint64_t> s_v59_rescan_resource_count = 0;
    static std::atomic<uint64_t> s_v59_rescan_target_match_count = 0;

    static std::mutex s_v59_retained_mutex;
    static std::unordered_map<ID3D12Resource *, v59_retained_resource>
        s_v59_retained_resources;
    static std::deque<v59_retention_ticket> s_v59_retention_order;
    static UINT64 s_v59_retained_total_bytes = 0;

    static std::mutex s_v59_map_mutex;
    static std::unordered_map<ID3D12Resource *, v59_map_state>
        s_v59_map_states;

    static std::mutex s_v59_candidate_mutex;
    static std::vector<v59_shader_record_candidate>
        s_v59_record_candidates;

    static std::mutex s_v59_unmap_hook_mutex;
    static std::unordered_map<void **, v59_resource_unmap_fn>
        s_v59_original_unmap_by_vtable;

    static std::mutex s_v59_activity_mutex;
    static std::unordered_map<ID3D12Resource *, uint32_t>
        s_v59_resource_activity_counts;

    bool v59_parse_hex_identifier(
        const char *hex,
        unsigned char (&identifier)[D3D12_SHADER_IDENTIFIER_SIZE_IN_BYTES])
    {
        if (hex == nullptr)
            return false;
        auto hex_value = [](char value) -> int
        {
            if (value >= '0' && value <= '9') return value - '0';
            if (value >= 'a' && value <= 'f') return value - 'a' + 10;
            if (value >= 'A' && value <= 'F') return value - 'A' + 10;
            return -1;
        };
        for (size_t index = 0;
             index < D3D12_SHADER_IDENTIFIER_SIZE_IN_BYTES;
             ++index)
        {
            const int high = hex_value(hex[index * 2]);
            const int low = hex_value(hex[index * 2 + 1]);
            if (high < 0 || low < 0)
                return false;
            identifier[index] = static_cast<unsigned char>((high << 4) | low);
        }
        return hex[D3D12_SHADER_IDENTIFIER_SIZE_IN_BYTES * 2] == '\0';
    }

    bool v59_get_execute_identifier(
        unsigned char (&identifier)[D3D12_SHADER_IDENTIFIER_SIZE_IN_BYTES])
    {
        std::lock_guard<std::mutex> lock(s_v54_baseline_mutex);
        return s_v54_baseline_ready &&
            v59_parse_hex_identifier(s_v54_baseline_execute_hex, identifier);
    }

    bool v59_should_refresh_resource(ID3D12Resource *resource)
    {
        if (resource == nullptr ||
            !s_v59_high_frequency_tracking_enabled.load(
                std::memory_order_acquire))
            return false;
        std::lock_guard<std::mutex> lock(s_v59_activity_mutex);
        uint32_t &count = s_v59_resource_activity_counts[resource];
        ++count;
        return count <= 2 || (count % 1024u) == 0;
    }

    void v59_retain_candidate_resource(ID3D12Resource *resource)
    {
        if (resource == nullptr ||
            !s_v59_high_frequency_tracking_enabled.load(
                std::memory_order_acquire))
            return;

        const D3D12_RESOURCE_DESC desc = resource->GetDesc();
        if (desc.Dimension != D3D12_RESOURCE_DIMENSION_BUFFER ||
            desc.Width == 0 ||
            desc.Width > v59_max_candidate_resource_bytes)
            return;

        D3D12_HEAP_PROPERTIES properties = {};
        D3D12_HEAP_FLAGS flags = D3D12_HEAP_FLAG_NONE;
        const HRESULT heap_hr = resource->GetHeapProperties(&properties, &flags);
        const D3D12_HEAP_TYPE heap_type = SUCCEEDED(heap_hr) ?
            properties.Type : D3D12_HEAP_TYPE_DEFAULT;
        const uint64_t sequence = ++s_v59_resource_activity_sequence;

        std::lock_guard<std::mutex> lock(s_v59_retained_mutex);
        auto found = s_v59_retained_resources.find(resource);
        if (found != s_v59_retained_resources.end())
        {
            found->second.sequence = sequence;
            found->second.width = desc.Width;
            found->second.heap_type = heap_type;
            s_v59_retention_order.push_back({ resource, sequence });
            return;
        }

        resource->AddRef();
        v59_retained_resource retained = {};
        retained.resource = resource;
        retained.width = desc.Width;
        retained.heap_type = heap_type;
        retained.sequence = sequence;
        s_v59_retained_resources[resource] = retained;
        s_v59_retention_order.push_back({ resource, sequence });
        s_v59_retained_total_bytes += desc.Width;

        while ((!s_v59_retention_order.empty()) &&
               (s_v59_retained_resources.size() > v59_max_retained_resources ||
                s_v59_retained_total_bytes > v59_max_retained_total_bytes))
        {
            const v59_retention_ticket ticket = s_v59_retention_order.front();
            s_v59_retention_order.pop_front();
            auto candidate = s_v59_retained_resources.find(ticket.resource);
            if (candidate == s_v59_retained_resources.end() ||
                candidate->second.sequence != ticket.sequence)
                continue;
            ID3D12Resource *const released = candidate->second.resource;
            s_v59_retained_total_bytes -= candidate->second.width;
            s_v59_retained_resources.erase(candidate);
            released->Release();
        }
    }

    void v59_note_resource_map(
        ID3D12Resource *resource,
        UINT subresource,
        void *data)
    {
        if (resource == nullptr || data == nullptr ||
            !s_v59_high_frequency_tracking_enabled.load(
                std::memory_order_acquire))
            return;
        const D3D12_RESOURCE_DESC desc = resource->GetDesc();
        if (desc.Dimension != D3D12_RESOURCE_DIMENSION_BUFFER ||
            desc.Width < 64 ||
            desc.Width > v59_max_candidate_resource_bytes)
            return;
        v59_retain_candidate_resource(resource);
        v59_map_state state = {};
        state.resource = resource;
        state.data = data;
        state.subresource = subresource;
        state.width = desc.Width;
        state.sequence = ++s_v59_resource_activity_sequence;
        {
            std::lock_guard<std::mutex> lock(s_v59_map_mutex);
            const auto found = s_v59_map_states.find(resource);
            if (found == s_v59_map_states.end())
                resource->AddRef();
            s_v59_map_states[resource] = state;
        }
        ++s_v59_map_capture_count;
    }

    bool v59_record_shader_candidate(
        ID3D12Resource *resource,
        UINT64 offset,
        const unsigned char (&record)[64],
        const char *source,
        uint32_t lineage_depth)
    {
        if (resource == nullptr || lineage_depth > 8)
            return false;
        unsigned char execute_identifier[D3D12_SHADER_IDENTIFIER_SIZE_IN_BYTES] = {};
        if (!v59_get_execute_identifier(execute_identifier) ||
            memcmp(record, execute_identifier, sizeof(execute_identifier)) != 0)
            return false;

        std::lock_guard<std::mutex> lock(s_v59_candidate_mutex);
        for (auto &candidate : s_v59_record_candidates)
        {
            if (candidate.resource == resource &&
                candidate.offset == offset &&
                memcmp(candidate.bytes, record, sizeof(candidate.bytes)) == 0)
                return false;
        }
        if (s_v59_record_candidates.size() >= v59_max_record_candidates)
            return false;

        resource->AddRef();
        v59_shader_record_candidate candidate = {};
        candidate.resource = resource;
        candidate.offset = offset;
        memcpy(candidate.bytes, record, sizeof(candidate.bytes));
        candidate.sequence = ++s_v59_candidate_sequence;
        candidate.lineage_depth = lineage_depth;
        candidate.source = source;
        s_v59_record_candidates.push_back(candidate);

        UINT64 srv_handle = 0, cbv_handle = 0, uav_handle = 0;
        memcpy(&srv_handle, record + 32, sizeof(srv_handle));
        memcpy(&cbv_handle, record + 40, sizeof(cbv_handle));
        memcpy(&uav_handle, record + 48, sizeof(uav_handle));
        reshade::log::message(
            reshade::log::level::info,
            "D3DMetal RTX steady-state shader-table lineage v59: RAYGEN_RECORD_CANDIDATE sequence=%llu source=%s resource=%p offset=%llu depth=%u srv=0x%llX cbv=0x%llX uav=0x%llX.",
            static_cast<unsigned long long>(candidate.sequence),
            source != nullptr ? source : "unknown",
            resource,
            static_cast<unsigned long long>(offset),
            lineage_depth,
            static_cast<unsigned long long>(srv_handle),
            static_cast<unsigned long long>(cbv_handle),
            static_cast<unsigned long long>(uav_handle));
        return true;
    }

    bool v59_scan_mapped_range(
        const v59_map_state &state,
        SIZE_T begin,
        SIZE_T end,
        const char *source)
    {
        if (state.resource == nullptr || state.data == nullptr || state.width < 64)
            return false;
        if (begin > state.width) begin = static_cast<SIZE_T>(state.width);
        if (end == 0 || end > state.width) end = static_cast<SIZE_T>(state.width);
        if (end <= begin || end - begin < 64)
            return false;
        if (end - begin > v59_max_map_scan_bytes)
            end = begin + v59_max_map_scan_bytes;
        SIZE_T offset = (begin + 31u) & ~static_cast<SIZE_T>(31u);
        for (; offset + 64 <= end; offset += 32)
        {
            unsigned char record[64] = {};
            const unsigned char *const address =
                static_cast<const unsigned char *>(state.data) + offset;
            if (!safe_copy_from_process(address, record, sizeof(record)))
                continue;
            if (v59_record_shader_candidate(
                    state.resource,
                    static_cast<UINT64>(offset),
                    record,
                    source,
                    0))
                return true;
        }
        return false;
    }

    void v59_note_resource_unmap(
        ID3D12Resource *resource,
        UINT subresource,
        const D3D12_RANGE *written_range)
    {
        if (resource == nullptr ||
            !s_v59_high_frequency_tracking_enabled.load(
                std::memory_order_acquire))
            return;
        v59_map_state state = {};
        {
            std::lock_guard<std::mutex> lock(s_v59_map_mutex);
            const auto found = s_v59_map_states.find(resource);
            if (found == s_v59_map_states.end())
                return;
            state = found->second;
            s_v59_map_states.erase(found);
        }
        if (state.subresource != subresource)
        {
            state.resource->Release();
            return;
        }
        SIZE_T begin = 0;
        SIZE_T end = static_cast<SIZE_T>(state.width);
        if (written_range != nullptr)
        {
            D3D12_RANGE range = {};
            if (safe_copy_from_process(written_range, &range, sizeof(range)))
            {
                begin = range.Begin;
                end = range.End;
            }
        }
        if (v59_scan_mapped_range(state, begin, end, "resource-unmap"))
            ++s_v59_unmap_capture_count;
        state.resource->Release();
    }

    void STDMETHODCALLTYPE v59_trace_resource_unmap(
        ID3D12Resource *resource,
        UINT subresource,
        const D3D12_RANGE *written_range)
    {
        v59_resource_unmap_fn original = nullptr;
        if (resource != nullptr)
        {
            void **const vtable = *reinterpret_cast<void ***>(resource);
            std::lock_guard<std::mutex> lock(s_v59_unmap_hook_mutex);
            const auto found = s_v59_original_unmap_by_vtable.find(vtable);
            if (found != s_v59_original_unmap_by_vtable.end())
                original = found->second;
        }
        v59_note_resource_unmap(resource, subresource, written_range);
        if (original != nullptr)
            original(resource, subresource, written_range);
    }

    void v59_install_resource_unmap_hook(ID3D12Resource *resource)
    {
        if (resource == nullptr)
            return;
        void **const vtable = *reinterpret_cast<void ***>(resource);
        {
            std::lock_guard<std::mutex> lock(s_v59_unmap_hook_mutex);
            if (s_v59_original_unmap_by_vtable.find(vtable) !=
                s_v59_original_unmap_by_vtable.end())
                return;
        }
        void *const current = vtable[v59_resource_unmap_slot];
        if (current == reinterpret_cast<void *>(&v59_trace_resource_unmap))
            return;
        DWORD old_protect = 0;
        if (!VirtualProtect(
                &vtable[v59_resource_unmap_slot],
                sizeof(void *),
                PAGE_EXECUTE_READWRITE,
                &old_protect))
            return;
        {
            std::lock_guard<std::mutex> lock(s_v59_unmap_hook_mutex);
            s_v59_original_unmap_by_vtable[vtable] =
                reinterpret_cast<v59_resource_unmap_fn>(current);
        }
        InterlockedExchangePointer(
            reinterpret_cast<PVOID volatile *>(
                &vtable[v59_resource_unmap_slot]),
            reinterpret_cast<PVOID>(&v59_trace_resource_unmap));
        DWORD ignored = 0;
        VirtualProtect(
            &vtable[v59_resource_unmap_slot],
            sizeof(void *),
            old_protect,
            &ignored);
        FlushInstructionCache(
            GetCurrentProcess(),
            &vtable[v59_resource_unmap_slot],
            sizeof(void *));
        const bool installed =
            vtable[v59_resource_unmap_slot] ==
                reinterpret_cast<void *>(&v59_trace_resource_unmap);
        if (installed)
            s_v59_unmap_hook_installed.store(true, std::memory_order_release);
        reshade::log::message(
            installed ? reshade::log::level::info : reshade::log::level::warning,
            "D3DMetal RTX steady-state shader-table lineage v59: RESOURCE_UNMAP_HOOK installed=%u vtable=%p slot=%zu original=%p replacement=%p.",
            installed ? 1u : 0u,
            vtable,
            v59_resource_unmap_slot,
            current,
            reinterpret_cast<void *>(&v59_trace_resource_unmap));
    }

    void v59_propagate_copy_lineage(
        ID3D12Resource *destination_buffer,
        UINT64 destination_offset,
        ID3D12Resource *source_buffer,
        UINT64 source_offset,
        UINT64 bytes)
    {
        if (destination_buffer == nullptr || source_buffer == nullptr || bytes < 64 ||
            !s_v59_high_frequency_tracking_enabled.load(
                std::memory_order_acquire))
            return;
        std::vector<v59_shader_record_candidate> candidates;
        {
            std::lock_guard<std::mutex> lock(s_v59_candidate_mutex);
            candidates = s_v59_record_candidates;
        }
        if (source_offset + bytes < source_offset)
            return;
        for (const auto &candidate : candidates)
        {
            if (candidate.resource != source_buffer ||
                candidate.offset < source_offset ||
                candidate.offset + 64 < candidate.offset ||
                candidate.offset + 64 > source_offset + bytes)
                continue;
            const UINT64 propagated_offset =
                destination_offset + (candidate.offset - source_offset);
            if (v59_record_shader_candidate(
                    destination_buffer,
                    propagated_offset,
                    candidate.bytes,
                    "copy-lineage",
                    candidate.lineage_depth + 1))
            {
                v59_retain_candidate_resource(destination_buffer);
                ++s_v59_copy_lineage_count;
            }
        }
    }

    void v59_scan_persistent_mappings()
    {
        std::vector<v59_map_state> states;
        {
            std::lock_guard<std::mutex> lock(s_v59_map_mutex);
            states.reserve(s_v59_map_states.size());
            for (const auto &entry : s_v59_map_states)
            {
                entry.second.resource->AddRef();
                states.push_back(entry.second);
            }
        }
        for (const auto &state : states)
        {
            v59_scan_mapped_range(
                state,
                0,
                static_cast<SIZE_T>(state.width),
                "steady-state-persistent-map");
            state.resource->Release();
        }
    }

    bool v59_range_contains(
        D3D12_GPU_VIRTUAL_ADDRESS base,
        UINT64 width,
        D3D12_GPU_VIRTUAL_ADDRESS address,
        UINT64 bytes)
    {
        if (base == 0 || width == 0 || address == 0 || bytes == 0 ||
            address < base || address + bytes < address)
            return false;
        const UINT64 offset = address - base;
        return offset <= width && bytes <= width - offset;
    }

    void v59_refresh_live_candidate_addresses(
        const D3D12_DISPATCH_RAYS_DESC &desc)
    {
        std::vector<ID3D12Resource *> resources;
        {
            std::lock_guard<std::mutex> lock(s_v59_retained_mutex);
            resources.reserve(s_v59_retained_resources.size());
            for (const auto &entry : s_v59_retained_resources)
            {
                entry.first->AddRef();
                resources.push_back(entry.first);
            }
        }

        std::vector<v39_buffer_record> fresh_records;
        fresh_records.reserve(resources.size());
        uint64_t raygen_matches = 0, miss_matches = 0;
        uint64_t hit_matches = 0, callable_matches = 0;
        for (ID3D12Resource *resource : resources)
        {
            const D3D12_RESOURCE_DESC resource_desc = resource->GetDesc();
            const D3D12_GPU_VIRTUAL_ADDRESS base =
                resource->GetGPUVirtualAddress();
            if (resource_desc.Dimension == D3D12_RESOURCE_DIMENSION_BUFFER &&
                resource_desc.Width != 0 && base != 0)
            {
                D3D12_HEAP_PROPERTIES properties = {};
                D3D12_HEAP_FLAGS flags = D3D12_HEAP_FLAG_NONE;
                const HRESULT heap_hr =
                    resource->GetHeapProperties(&properties, &flags);
                v39_buffer_record record = {};
                record.resource = resource;
                record.base = base;
                record.width = resource_desc.Width;
                record.heap_type = SUCCEEDED(heap_hr) ?
                    properties.Type : D3D12_HEAP_TYPE_DEFAULT;
                record.sequence = ++s_v39_resource_sequence;
                fresh_records.push_back(record);
                if (v59_range_contains(
                        base, resource_desc.Width,
                        desc.RayGenerationShaderRecord.StartAddress,
                        desc.RayGenerationShaderRecord.SizeInBytes))
                    ++raygen_matches;
                if (v59_range_contains(
                        base, resource_desc.Width,
                        desc.MissShaderTable.StartAddress,
                        desc.MissShaderTable.SizeInBytes))
                    ++miss_matches;
                if (v59_range_contains(
                        base, resource_desc.Width,
                        desc.HitGroupTable.StartAddress,
                        desc.HitGroupTable.SizeInBytes))
                    ++hit_matches;
                if (desc.CallableShaderTable.SizeInBytes != 0 &&
                    v59_range_contains(
                        base, resource_desc.Width,
                        desc.CallableShaderTable.StartAddress,
                        desc.CallableShaderTable.SizeInBytes))
                    ++callable_matches;
            }
            resource->Release();
        }

        {
            std::lock_guard<std::mutex> lock(s_v39_resource_mutex);
            s_v39_buffer_records.insert(
                s_v39_buffer_records.end(),
                fresh_records.begin(),
                fresh_records.end());
            if (s_v39_buffer_records.size() > 16384)
                s_v39_buffer_records.erase(
                    s_v39_buffer_records.begin(),
                    s_v39_buffer_records.begin() +
                        (s_v39_buffer_records.size() - 16384));
        }

        UINT64 retained_total_bytes = 0;
        {
            std::lock_guard<std::mutex> lock(s_v59_retained_mutex);
            retained_total_bytes = s_v59_retained_total_bytes;
        }
        s_v59_rescan_resource_count.store(
            fresh_records.size(), std::memory_order_release);
        const uint64_t target_matches =
            raygen_matches + miss_matches + hit_matches + callable_matches;
        s_v59_rescan_target_match_count.store(
            target_matches, std::memory_order_release);
        s_v59_rescan_complete.store(true, std::memory_order_release);
        reshade::log::message(
            target_matches != 0 ? reshade::log::level::info :
                                  reshade::log::level::warning,
            "D3DMetal RTX steady-state shader-table lineage v59: STEADY_RESCAN_RESULT scanned=%zu inserted=%zu raygen_matches=%llu miss_matches=%llu hit_matches=%llu callable_matches=%llu retained_total_bytes=%llu.",
            resources.size(),
            fresh_records.size(),
            static_cast<unsigned long long>(raygen_matches),
            static_cast<unsigned long long>(miss_matches),
            static_cast<unsigned long long>(hit_matches),
            static_cast<unsigned long long>(callable_matches),
            static_cast<unsigned long long>(retained_total_bytes));
    }

    bool v59_try_resolve_raygen_record_lineage(
        const D3D12_DISPATCH_RAYS_DESC &desc)
    {
        v59_scan_persistent_mappings();
        std::vector<v59_shader_record_candidate> candidates;
        {
            std::lock_guard<std::mutex> lock(s_v59_candidate_mutex);
            candidates = s_v59_record_candidates;
        }
        if (candidates.empty())
        {
            reshade::log::message(
                reshade::log::level::warning,
                "D3DMetal RTX steady-state shader-table lineage v59: RAYGEN_RECORD_LINEAGE_RESULT success=0 reason=no-execute-record-candidates.");
            return false;
        }

        const v59_shader_record_candidate *best = nullptr;
        int best_score = -1;
        D3D12_GPU_VIRTUAL_ADDRESS best_base = 0;
        for (const auto &candidate : candidates)
        {
            const D3D12_RESOURCE_DESC resource_desc =
                candidate.resource->GetDesc();
            const D3D12_GPU_VIRTUAL_ADDRESS base =
                candidate.resource->GetGPUVirtualAddress();
            int score = 1;
            if (base != 0 &&
                base + candidate.offset ==
                    desc.RayGenerationShaderRecord.StartAddress)
                score = 3;
            else if (v59_range_contains(
                        base,
                        resource_desc.Width,
                        desc.RayGenerationShaderRecord.StartAddress,
                        desc.RayGenerationShaderRecord.SizeInBytes))
                score = 2;
            if (best == nullptr || score > best_score ||
                (score == best_score && candidate.sequence > best->sequence))
            {
                best = &candidate;
                best_score = score;
                best_base = base;
            }
        }
        if (best == nullptr)
            return false;

        UINT64 srv_handle = 0, cbv_handle = 0, uav_handle = 0;
        memcpy(&srv_handle, best->bytes + 32, sizeof(srv_handle));
        memcpy(&cbv_handle, best->bytes + 40, sizeof(cbv_handle));
        memcpy(&uav_handle, best->bytes + 48, sizeof(uav_handle));
        const bool exact = best_score == 3;
        s_v59_lineage_exact_address_match.store(
            exact, std::memory_order_release);
        s_v59_lineage_resolution_invoked.store(
            true, std::memory_order_release);
        reshade::log::message(
            reshade::log::level::info,
            "D3DMetal RTX steady-state shader-table lineage v59: RAYGEN_RECORD_LINEAGE_RESULT success=1 confidence=%s sequence=%llu source=%s resource=%p resource_gpu_va=0x%llX record_offset=%llu target_raygen=0x%llX depth=%u srv=0x%llX cbv=0x%llX uav=0x%llX.",
            exact ? "exact-address" :
                (best_score == 2 ? "resource-range" : "latest-identifier"),
            static_cast<unsigned long long>(best->sequence),
            best->source != nullptr ? best->source : "unknown",
            best->resource,
            static_cast<unsigned long long>(best_base),
            static_cast<unsigned long long>(best->offset),
            static_cast<unsigned long long>(
                desc.RayGenerationShaderRecord.StartAddress),
            best->lineage_depth,
            static_cast<unsigned long long>(srv_handle),
            static_cast<unsigned long long>(cbv_handle),
            static_cast<unsigned long long>(uav_handle));
        v55_resolve_raygen_local_root(best->bytes, sizeof(best->bytes));
        return true;
    }

    void v59_disable_high_frequency_tracking(const char *reason)
    {
        const bool was_enabled =
            s_v59_high_frequency_tracking_enabled.exchange(
                false, std::memory_order_acq_rel);
        if (!was_enabled)
            return;
        size_t retained_count = 0;
        size_t candidate_count = 0;
        {
            std::lock_guard<std::mutex> lock(s_v59_retained_mutex);
            retained_count = s_v59_retained_resources.size();
        }
        {
            std::lock_guard<std::mutex> lock(s_v59_candidate_mutex);
            candidate_count = s_v59_record_candidates.size();
        }
        reshade::log::message(
            reshade::log::level::info,
            "D3DMetal RTX steady-state shader-table lineage v59: HIGH_FREQUENCY_TRACKING_DISABLED reason=%s gpu_va_calls=%llu copy_calls=%llu map_calls=%llu retained=%zu candidates=%zu.",
            reason != nullptr ? reason : "unknown",
            static_cast<unsigned long long>(
                s_v58_gpu_va_calls.load(std::memory_order_acquire)),
            static_cast<unsigned long long>(
                s_v57_copy_buffer_calls.load(std::memory_order_acquire)),
            static_cast<unsigned long long>(
                s_v57_map_calls.load(std::memory_order_acquire)),
            retained_count,
            candidate_count);
    }
'''

text = replace_once(
    text,
    """    bool v39_find_buffer(\n""",
    v59_block + "\n\n    bool v39_find_buffer(\n",
    "insert V59 implementation",
)

text = replace_once(
    text,
    """        v57_install_resource_map_hook(resource);\n        v58_install_gpu_va_hook(resource);\n""",
    """        v57_install_resource_map_hook(resource);\n        v59_install_resource_unmap_hook(resource);\n        v58_install_gpu_va_hook(resource);\n""",
    "install Unmap hook on tracked resources",
)

text = replace_once(
    text,
    """        const bool raygen_found = v39_find_buffer(desc.RayGenerationShaderRecord.StartAddress, raygen_bytes, raygen_resource, raygen_source_offset);\n        const bool miss_found = v39_find_buffer(desc.MissShaderTable.StartAddress, miss_bytes, miss_resource, miss_source_offset);\n        const bool hit_found = v39_find_buffer(desc.HitGroupTable.StartAddress, hit_bytes, hit_resource, hit_source_offset);\n        const bool callable_found = callable_bytes == 0 || v39_find_buffer(desc.CallableShaderTable.StartAddress, callable_bytes, callable_resource, callable_source_offset);\n""",
    """        v59_refresh_live_candidate_addresses(desc);\n        const bool v59_lineage_record =\n            v59_try_resolve_raygen_record_lineage(desc);\n\n        const bool raygen_found = v39_find_buffer(desc.RayGenerationShaderRecord.StartAddress, raygen_bytes, raygen_resource, raygen_source_offset);\n        const bool miss_found = v39_find_buffer(desc.MissShaderTable.StartAddress, miss_bytes, miss_resource, miss_source_offset);\n        const bool hit_found = v39_find_buffer(desc.HitGroupTable.StartAddress, hit_bytes, hit_resource, hit_source_offset);\n        const bool callable_found = callable_bytes == 0 || v39_find_buffer(desc.CallableShaderTable.StartAddress, callable_bytes, callable_resource, callable_source_offset);\n""",
    "run steady-state rescan and lineage recovery",
)

text = replace_once(
    text,
    """                static_cast<unsigned long long>(\n                    s_v57_map_calls.load(std::memory_order_acquire)));\n            return;\n""",
    """                static_cast<unsigned long long>(\n                    s_v57_map_calls.load(std::memory_order_acquire)));\n            reshade::log::message(\n                v59_lineage_record ? reshade::log::level::info :\n                                     reshade::log::level::warning,\n                \"D3DMetal RTX steady-state shader-table lineage v59: V59_RESULT resource_lookup_complete=0 lineage_record=%u exact_address=%u rescan_resources=%llu rescan_target_matches=%llu commands_modified=0.\",\n                v59_lineage_record ? 1u : 0u,\n                s_v59_lineage_exact_address_match.load(\n                    std::memory_order_acquire) ? 1u : 0u,\n                static_cast<unsigned long long>(\n                    s_v59_rescan_resource_count.load(\n                        std::memory_order_acquire)),\n                static_cast<unsigned long long>(\n                    s_v59_rescan_target_match_count.load(\n                        std::memory_order_acquire)));\n            v59_disable_high_frequency_tracking(\"resource-lookup-finished\");\n            return;\n""",
    "log V59 lookup failure result",
)

text = replace_once(
    text,
    """        ID3D12Device *device = nullptr;\n""",
    """        reshade::log::message(\n            reshade::log::level::info,\n            \"D3DMetal RTX steady-state shader-table lineage v59: V59_RESULT resource_lookup_complete=1 lineage_record=%u exact_address=%u rescan_resources=%llu rescan_target_matches=%llu commands_modified=0.\",\n            v59_lineage_record ? 1u : 0u,\n            s_v59_lineage_exact_address_match.load(\n                std::memory_order_acquire) ? 1u : 0u,\n            static_cast<unsigned long long>(\n                s_v59_rescan_resource_count.load(\n                    std::memory_order_acquire)),\n            static_cast<unsigned long long>(\n                s_v59_rescan_target_match_count.load(\n                    std::memory_order_acquire)));\n        v59_disable_high_frequency_tracking(\"resource-lookup-finished\");\n\n        ID3D12Device *device = nullptr;\n""",
    "log V59 lookup success result",
)

text = replace_once(
    text,
    """\t\tconst D3D12_GPU_VIRTUAL_ADDRESS address =\n\t\t\toriginal(resource);\n\t\tif (address != 0)\n\t\t\tv58_record_current_gpu_va(\n""",
    """\t\tconst D3D12_GPU_VIRTUAL_ADDRESS address =\n\t\t\toriginal(resource);\n\t\tif (address != 0 &&\n\t\t\ts_v59_high_frequency_tracking_enabled.load(\n\t\t\t\tstd::memory_order_acquire))\n\t\t\tv58_record_current_gpu_va(\n""",
    "gate V58 high-frequency tracking",
)

text = replace_once(
    text,
    """\t\tconst HRESULT hr = original(resource, subresource, read_range, data);\n\t\tif (SUCCEEDED(hr))\n\t\t\tv57_track_candidate_buffer(resource, \"resource-map\");\n\t\treturn hr;\n""",
    """\t\tconst HRESULT hr = original(resource, subresource, read_range, data);\n\t\tif (SUCCEEDED(hr) &&\n\t\t\ts_v59_high_frequency_tracking_enabled.load(\n\t\t\t\tstd::memory_order_acquire))\n\t\t{\n\t\t\tif (v59_should_refresh_resource(resource))\n\t\t\t\tv57_track_candidate_buffer(resource, \"resource-map\");\n\t\t\tvoid *mapped_data = nullptr;\n\t\t\tif (data != nullptr)\n\t\t\t\tsafe_copy_from_process(\n\t\t\t\t\tdata, &mapped_data, sizeof(mapped_data));\n\t\t\tv59_note_resource_map(\n\t\t\t\tresource, subresource, mapped_data);\n\t\t}\n\t\treturn hr;\n""",
    "capture mapped buffers",
)

text = replace_once(
    text,
    """\t\tconst D3D12_RESOURCE_DESC desc = resource->GetDesc();\n\t\tconst D3D12_GPU_VIRTUAL_ADDRESS base = resource->GetGPUVirtualAddress();\n""",
    """\t\tconst D3D12_RESOURCE_DESC desc = resource->GetDesc();\n\t\tconst D3D12_GPU_VIRTUAL_ADDRESS base = resource->GetGPUVirtualAddress();\n""",
    "confirm V57 candidate anchor",
)

text = replace_once(
    text,
    """\t\tif (desc.Dimension != D3D12_RESOURCE_DIMENSION_BUFFER ||\n\t\t\tdesc.Width == 0 ||\n\t\t\tdesc.Width > v57_max_recovery_buffer_bytes ||\n\t\t\tbase == 0)\n\t\t\treturn false;\n\n\t\tbool inserted = false;\n""",
    """\t\tif (desc.Dimension != D3D12_RESOURCE_DIMENSION_BUFFER ||\n\t\t\tdesc.Width == 0 ||\n\t\t\tdesc.Width > v57_max_recovery_buffer_bytes ||\n\t\t\tbase == 0)\n\t\t\treturn false;\n\n\t\tv59_retain_candidate_resource(resource);\n\n\t\tbool inserted = false;\n""",
    "retain V57 candidate buffers",
)

text = replace_once(
    text,
    """\t\t++s_v57_copy_buffer_calls;\n\t\tv57_track_candidate_buffer(destination_buffer, \"copy-destination\");\n\t\tv57_track_candidate_buffer(source_buffer, \"copy-source\");\n\n\t\tif (s_v57_original_copy_buffer_region != nullptr)\n""",
    """\t\tif (s_v59_high_frequency_tracking_enabled.load(\n\t\t\t\tstd::memory_order_acquire))\n\t\t{\n\t\t\t++s_v57_copy_buffer_calls;\n\t\t\tif (v59_should_refresh_resource(destination_buffer))\n\t\t\t\tv57_track_candidate_buffer(\n\t\t\t\t\tdestination_buffer, \"copy-destination\");\n\t\t\tif (v59_should_refresh_resource(source_buffer))\n\t\t\t\tv57_track_candidate_buffer(\n\t\t\t\t\tsource_buffer, \"copy-source\");\n\t\t\tv59_propagate_copy_lineage(\n\t\t\t\tdestination_buffer, destination_offset,\n\t\t\t\tsource_buffer, source_offset, bytes);\n\t\t}\n\n\t\tif (s_v57_original_copy_buffer_region != nullptr)\n""",
    "sample copy tracking and propagate lineage",
)

text = replace_once(
    text,
    """\t\treshade::log::message(\n\t\t\treshade::log::level::info,\n\t\t\t\"D3DMetal RTX ray-hit pattern inheritance census v54: PIPELINE_BIND bind_total=%llu pipeline_id=%llu pipeline_bind_index=%llu command_list=%p state_object=%p.\",\n""",
    """\t\tif (bind_total <= 64 || pipeline_bind_index == 512 ||\n\t\t\t(bind_total % 120) == 0)\n\t\treshade::log::message(\n\t\t\treshade::log::level::info,\n\t\t\t\"D3DMetal RTX ray-hit pattern inheritance census v54: PIPELINE_BIND bind_total=%llu pipeline_id=%llu pipeline_bind_index=%llu command_list=%p state_object=%p.\",\n""",
    "sample V54 bind logs",
)

text = replace_once(
    text,
    """\t\treshade::log::message(\n\t\t\tpipeline_id != 0 ?\n\t\t\t\treshade::log::level::info :\n""",
    """\t\tif (global_ray_index <= 64 || pipeline_ray_index == 512 ||\n\t\t\t(global_ray_index % 120) == 0)\n\t\treshade::log::message(\n\t\t\tpipeline_id != 0 ?\n\t\t\t\treshade::log::level::info :\n""",
    "sample V54 ray logs",
)

SOURCE.write_text(text, encoding="utf-8", newline="\n")
REPORT.write_text(
    "\n".join(
        [
            "V59_STEADY_STATE_SHADER_TABLE_LINEAGE_PATCH_OK",
            "BASELINE=V58_LIVE_GPU_VA_RELOCATION",
            "STEADY_STATE_LIVE_GPU_VA_RESCAN=ENABLED",
            "RECENT_SMALL_RESOURCE_RETENTION=ENABLED",
            "RESOURCE_UNMAP_SLOT=9",
            "MAP_UNMAP_RAYGEN_RECORD_CAPTURE=ENABLED",
            "COPY_BUFFER_RECORD_LINEAGE=ENABLED",
            "PERSISTENT_MAP_STEADY_SCAN=ENABLED",
            "LOCAL_ROOT_FALLBACK_FROM_EXECUTETRACE_RECORD=ENABLED",
            "HIGH_FREQUENCY_TRACKING_AUTO_DISABLE=ENABLED",
            "V54_PIPELINE_LOG_SAMPLING=ENABLED",
            "MAX_SINGLE_RETAINED_BYTES=4194304",
            "MAX_TOTAL_RETAINED_BYTES=402653184",
            "MAX_RETAINED_RESOURCES=4096",
            "SHADERS_MODIFIED_BY_V59=NO",
            "DESCRIPTORS_MODIFIED_BY_V59=NO",
            "RESOURCES_CONTENTS_MODIFIED_BY_V59=NO",
            "GPU_VA_RESULTS_MODIFIED_BY_V59=NO",
            "COPY_COMMANDS_MODIFIED_BY_V59=NO",
            "DISPATCH_ARGUMENTS_MODIFIED_BY_V59=NO",
            "RESULT=PASS",
            "",
        ]
    ),
    encoding="utf-8",
    newline="\n",
)
print("V59_STEADY_STATE_SHADER_TABLE_LINEAGE_PATCH_OK")
