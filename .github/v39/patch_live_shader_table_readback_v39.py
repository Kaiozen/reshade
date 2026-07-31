from pathlib import Path

SOURCE = Path("source/d3d12/d3d12.cpp")
if not SOURCE.is_file():
    raise RuntimeError(f"Missing source file: {SOURCE}")

text = SOURCE.read_text(encoding="utf-8-sig")
if "D3DMetal RTX live dispatch readback v38:" not in text:
    raise RuntimeError("V38 must be applied before V39")
if "D3DMetal RTX live shader-table readback v39:" in text:
    raise RuntimeError("V39 is already present")


def replace_once(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 occurrence, found {count}")
    return source.replace(old, new, 1)

# Correct V38's logging-only terminator typo. The capture bytes and decoded fields were unaffected.
text = replace_once(text, "hex[0] = '\\\\0';", "hex[0] = '\\0';", "V38 initial hex terminator")
text = replace_once(text, "hex[count * 2] = '\\\\0';", "hex[count * 2] = '\\0';", "V38 final hex terminator")

anchor = "\tusing v38_create_command_queue_fn = HRESULT (STDMETHODCALLTYPE *)(\n"
if text.count(anchor) != 1:
    raise RuntimeError(f"V39 helper anchor mismatch: {text.count(anchor)}")

helper = r'''
    using v39_create_committed_resource_fn = HRESULT (STDMETHODCALLTYPE *)(
        ID3D12Device *,
        const D3D12_HEAP_PROPERTIES *,
        D3D12_HEAP_FLAGS,
        const D3D12_RESOURCE_DESC *,
        D3D12_RESOURCE_STATES,
        const D3D12_CLEAR_VALUE *,
        REFIID,
        void **);

    using v39_create_placed_resource_fn = HRESULT (STDMETHODCALLTYPE *)(
        ID3D12Device *,
        ID3D12Heap *,
        UINT64,
        const D3D12_RESOURCE_DESC *,
        D3D12_RESOURCE_STATES,
        const D3D12_CLEAR_VALUE *,
        REFIID,
        void **);

    using v39_create_reserved_resource_fn = HRESULT (STDMETHODCALLTYPE *)(
        ID3D12Device *,
        const D3D12_RESOURCE_DESC *,
        D3D12_RESOURCE_STATES,
        const D3D12_CLEAR_VALUE *,
        REFIID,
        void **);

    constexpr size_t v39_create_committed_resource_slot = 27;
    constexpr size_t v39_create_placed_resource_slot = 29;
    constexpr size_t v39_create_reserved_resource_slot = 30;
    constexpr UINT64 v39_max_shader_table_bytes = 4ull * 1024ull * 1024ull;

    static v39_create_committed_resource_fn s_v39_original_create_committed_resource = nullptr;
    static v39_create_placed_resource_fn s_v39_original_create_placed_resource = nullptr;
    static v39_create_reserved_resource_fn s_v39_original_create_reserved_resource = nullptr;
    static std::once_flag s_v39_resource_hook_once;
    static std::atomic<bool> s_v39_resource_hooks_installed = false;
    static std::atomic<uint64_t> s_v39_resource_sequence = 0;

    struct v39_buffer_record
    {
        ID3D12Resource *resource = nullptr;
        D3D12_GPU_VIRTUAL_ADDRESS base = 0;
        UINT64 width = 0;
        D3D12_HEAP_TYPE heap_type = D3D12_HEAP_TYPE_DEFAULT;
        uint64_t sequence = 0;
    };

    static std::mutex s_v39_resource_mutex;
    static std::vector<v39_buffer_record> s_v39_buffer_records;

    struct v39_dispatch_snapshot
    {
        D3D12_DISPATCH_RAYS_DESC desc = {};
        bool ready = false;
    };

    static std::mutex s_v39_desc_mutex;
    static v39_dispatch_snapshot s_v39_dispatch_snapshot;

    static std::atomic<bool> s_v39_capture_claimed = false;
    static std::atomic<bool> s_v39_copy_recorded = false;
    static std::atomic<bool> s_v39_queue_signaled = false;
    static std::atomic<bool> s_v39_readback_complete = false;
    static std::atomic<bool> s_v39_capture_failed = false;
    static std::mutex s_v39_capture_mutex;
    static ID3D12Resource *s_v39_readback_resource = nullptr;
    static ID3D12Fence *s_v39_capture_fence = nullptr;
    static HANDLE s_v39_capture_event = nullptr;
    static void *s_v39_capture_command_list_identity = nullptr;
    static UINT64 s_v39_total_readback_bytes = 0;
    static UINT64 s_v39_raygen_offset = 0;
    static UINT64 s_v39_raygen_bytes = 0;
    static UINT64 s_v39_miss_offset = 0;
    static UINT64 s_v39_miss_bytes = 0;
    static UINT64 s_v39_hit_offset = 0;
    static UINT64 s_v39_hit_bytes = 0;
    static UINT64 s_v39_callable_offset = 0;
    static UINT64 s_v39_callable_bytes = 0;
    static UINT64 s_v39_hit_stride = 0;
    static uint64_t s_v39_state_call = 0;
    static uint64_t s_v39_ray_index = 0;

    void v39_bytes_to_hex(
        const unsigned char *bytes,
        size_t count,
        char *hex,
        size_t hex_size)
    {
        if (hex == nullptr || hex_size == 0)
            return;
        hex[0] = '\0';
        if (bytes == nullptr || hex_size < count * 2 + 1)
            return;
        static const char digits[] = "0123456789abcdef";
        for (size_t index = 0; index < count; ++index)
        {
            hex[index * 2] = digits[bytes[index] >> 4];
            hex[index * 2 + 1] = digits[bytes[index] & 0x0F];
        }
        hex[count * 2] = '\0';
    }

    uint64_t v39_fnv1a64(const unsigned char *bytes, size_t count)
    {
        uint64_t hash = 1469598103934665603ull;
        for (size_t index = 0; index < count; ++index)
        {
            hash ^= bytes[index];
            hash *= 1099511628211ull;
        }
        return hash;
    }

    void v39_track_resource(void *created)
    {
        if (created == nullptr)
            return;
        ID3D12Resource *resource = nullptr;
        const HRESULT qi_hr = reinterpret_cast<IUnknown *>(created)->QueryInterface(
            __uuidof(ID3D12Resource), reinterpret_cast<void **>(&resource));
        if (FAILED(qi_hr) || resource == nullptr)
            return;

        const D3D12_RESOURCE_DESC desc = resource->GetDesc();
        const D3D12_GPU_VIRTUAL_ADDRESS base = resource->GetGPUVirtualAddress();
        D3D12_HEAP_PROPERTIES properties = {};
        D3D12_HEAP_FLAGS flags = D3D12_HEAP_FLAG_NONE;
        const HRESULT heap_hr = resource->GetHeapProperties(&properties, &flags);
        if (desc.Dimension == D3D12_RESOURCE_DIMENSION_BUFFER && base != 0 && desc.Width != 0)
        {
            v39_buffer_record record = {};
            record.resource = resource;
            record.base = base;
            record.width = desc.Width;
            record.heap_type = SUCCEEDED(heap_hr) ? properties.Type : D3D12_HEAP_TYPE_DEFAULT;
            record.sequence = ++s_v39_resource_sequence;
            std::lock_guard<std::mutex> lock(s_v39_resource_mutex);
            s_v39_buffer_records.push_back(record);
            if (s_v39_buffer_records.size() > 16384)
                s_v39_buffer_records.erase(s_v39_buffer_records.begin(), s_v39_buffer_records.begin() + 4096);
        }
        resource->Release();
    }

    bool v39_find_buffer(
        D3D12_GPU_VIRTUAL_ADDRESS address,
        UINT64 bytes,
        v39_buffer_record &result,
        UINT64 &offset)
    {
        result = {};
        offset = 0;
        if (address == 0 || bytes == 0 || address + bytes < address)
            return false;
        std::lock_guard<std::mutex> lock(s_v39_resource_mutex);
        for (auto it = s_v39_buffer_records.rbegin(); it != s_v39_buffer_records.rend(); ++it)
        {
            if (address < it->base)
                continue;
            const UINT64 candidate_offset = address - it->base;
            if (candidate_offset <= it->width && bytes <= it->width - candidate_offset)
            {
                result = *it;
                offset = candidate_offset;
                return true;
            }
        }
        return false;
    }

    HRESULT STDMETHODCALLTYPE v39_trace_create_committed_resource(
        ID3D12Device *device,
        const D3D12_HEAP_PROPERTIES *heap_properties,
        D3D12_HEAP_FLAGS heap_flags,
        const D3D12_RESOURCE_DESC *desc,
        D3D12_RESOURCE_STATES initial_state,
        const D3D12_CLEAR_VALUE *clear_value,
        REFIID riid,
        void **resource)
    {
        if (s_v39_original_create_committed_resource == nullptr)
            return E_FAIL;
        const HRESULT hr = s_v39_original_create_committed_resource(
            device, heap_properties, heap_flags, desc, initial_state, clear_value, riid, resource);
        void *created = nullptr;
        if (resource != nullptr)
            safe_copy_from_process(resource, &created, sizeof(created));
        if (SUCCEEDED(hr))
            v39_track_resource(created);
        return hr;
    }

    HRESULT STDMETHODCALLTYPE v39_trace_create_placed_resource(
        ID3D12Device *device,
        ID3D12Heap *heap,
        UINT64 heap_offset,
        const D3D12_RESOURCE_DESC *desc,
        D3D12_RESOURCE_STATES initial_state,
        const D3D12_CLEAR_VALUE *clear_value,
        REFIID riid,
        void **resource)
    {
        if (s_v39_original_create_placed_resource == nullptr)
            return E_FAIL;
        const HRESULT hr = s_v39_original_create_placed_resource(
            device, heap, heap_offset, desc, initial_state, clear_value, riid, resource);
        void *created = nullptr;
        if (resource != nullptr)
            safe_copy_from_process(resource, &created, sizeof(created));
        if (SUCCEEDED(hr))
            v39_track_resource(created);
        return hr;
    }

    HRESULT STDMETHODCALLTYPE v39_trace_create_reserved_resource(
        ID3D12Device *device,
        const D3D12_RESOURCE_DESC *desc,
        D3D12_RESOURCE_STATES initial_state,
        const D3D12_CLEAR_VALUE *clear_value,
        REFIID riid,
        void **resource)
    {
        if (s_v39_original_create_reserved_resource == nullptr)
            return E_FAIL;
        const HRESULT hr = s_v39_original_create_reserved_resource(
            device, desc, initial_state, clear_value, riid, resource);
        void *created = nullptr;
        if (resource != nullptr)
            safe_copy_from_process(resource, &created, sizeof(created));
        if (SUCCEEDED(hr))
            v39_track_resource(created);
        return hr;
    }

    void v39_install_resource_hooks(ID3D12Device *device)
    {
        if (device == nullptr)
            return;
        std::call_once(s_v39_resource_hook_once, [device]()
        {
            void **const vtable = *reinterpret_cast<void ***>(device);
            s_v39_original_create_committed_resource = reinterpret_cast<v39_create_committed_resource_fn>(vtable[v39_create_committed_resource_slot]);
            s_v39_original_create_placed_resource = reinterpret_cast<v39_create_placed_resource_fn>(vtable[v39_create_placed_resource_slot]);
            s_v39_original_create_reserved_resource = reinterpret_cast<v39_create_reserved_resource_fn>(vtable[v39_create_reserved_resource_slot]);

            DWORD old_committed = 0, old_placed = 0, old_reserved = 0;
            const bool protect_committed = VirtualProtect(&vtable[v39_create_committed_resource_slot], sizeof(void *), PAGE_EXECUTE_READWRITE, &old_committed) != FALSE;
            const bool protect_placed = VirtualProtect(&vtable[v39_create_placed_resource_slot], sizeof(void *), PAGE_EXECUTE_READWRITE, &old_placed) != FALSE;
            const bool protect_reserved = VirtualProtect(&vtable[v39_create_reserved_resource_slot], sizeof(void *), PAGE_EXECUTE_READWRITE, &old_reserved) != FALSE;
            if (protect_committed)
                InterlockedExchangePointer(reinterpret_cast<PVOID volatile *>(&vtable[v39_create_committed_resource_slot]), reinterpret_cast<PVOID>(&v39_trace_create_committed_resource));
            if (protect_placed)
                InterlockedExchangePointer(reinterpret_cast<PVOID volatile *>(&vtable[v39_create_placed_resource_slot]), reinterpret_cast<PVOID>(&v39_trace_create_placed_resource));
            if (protect_reserved)
                InterlockedExchangePointer(reinterpret_cast<PVOID volatile *>(&vtable[v39_create_reserved_resource_slot]), reinterpret_cast<PVOID>(&v39_trace_create_reserved_resource));
            DWORD ignored = 0;
            if (protect_committed) VirtualProtect(&vtable[v39_create_committed_resource_slot], sizeof(void *), old_committed, &ignored);
            if (protect_placed) VirtualProtect(&vtable[v39_create_placed_resource_slot], sizeof(void *), old_placed, &ignored);
            if (protect_reserved) VirtualProtect(&vtable[v39_create_reserved_resource_slot], sizeof(void *), old_reserved, &ignored);
            FlushInstructionCache(GetCurrentProcess(), &vtable[v39_create_committed_resource_slot], sizeof(void *));
            FlushInstructionCache(GetCurrentProcess(), &vtable[v39_create_placed_resource_slot], sizeof(void *));
            FlushInstructionCache(GetCurrentProcess(), &vtable[v39_create_reserved_resource_slot], sizeof(void *));
            const bool installed =
                vtable[v39_create_committed_resource_slot] == reinterpret_cast<void *>(&v39_trace_create_committed_resource) &&
                vtable[v39_create_placed_resource_slot] == reinterpret_cast<void *>(&v39_trace_create_placed_resource) &&
                vtable[v39_create_reserved_resource_slot] == reinterpret_cast<void *>(&v39_trace_create_reserved_resource);
            s_v39_resource_hooks_installed.store(installed, std::memory_order_release);
            reshade::log::message(installed ? reshade::log::level::info : reshade::log::level::warning,
                "D3DMetal RTX live shader-table readback v39: RESOURCE_HOOKS installed=%u committed_slot=%zu placed_slot=%zu reserved_slot=%zu.",
                installed ? 1u : 0u,
                v39_create_committed_resource_slot,
                v39_create_placed_resource_slot,
                v39_create_reserved_resource_slot);
        });
    }

    void v39_store_dispatch_desc(const D3D12_DISPATCH_RAYS_DESC &desc)
    {
        std::lock_guard<std::mutex> lock(s_v39_desc_mutex);
        s_v39_dispatch_snapshot.desc = desc;
        s_v39_dispatch_snapshot.ready = true;
        reshade::log::message(
            reshade::log::level::info,
            "D3DMetal RTX live shader-table readback v39: DISPATCH_DESC_READY raygen=0x%llX miss=0x%llX hit=0x%llX callable=0x%llX width=%u height=%u depth=%u.",
            static_cast<unsigned long long>(desc.RayGenerationShaderRecord.StartAddress),
            static_cast<unsigned long long>(desc.MissShaderTable.StartAddress),
            static_cast<unsigned long long>(desc.HitGroupTable.StartAddress),
            static_cast<unsigned long long>(desc.CallableShaderTable.StartAddress),
            desc.Width, desc.Height, desc.Depth);
    }

    struct v39_unique_identifier
    {
        unsigned char identifier[D3D12_SHADER_IDENTIFIER_SIZE_IN_BYTES] = {};
        uint64_t count = 0;
        uint64_t first_record = 0;
    };

    DWORD WINAPI v39_readback_worker(LPVOID)
    {
        HANDLE event_handle = nullptr;
        ID3D12Resource *readback = nullptr;
        ID3D12Fence *fence = nullptr;
        UINT64 total_bytes = 0, raygen_offset = 0, raygen_bytes = 0, miss_offset = 0, miss_bytes = 0;
        UINT64 hit_offset = 0, hit_bytes = 0, callable_offset = 0, callable_bytes = 0, hit_stride = 0;
        uint64_t state_call = 0, ray_index = 0;
        {
            std::lock_guard<std::mutex> lock(s_v39_capture_mutex);
            event_handle = s_v39_capture_event;
            readback = s_v39_readback_resource;
            fence = s_v39_capture_fence;
            total_bytes = s_v39_total_readback_bytes;
            raygen_offset = s_v39_raygen_offset;
            raygen_bytes = s_v39_raygen_bytes;
            miss_offset = s_v39_miss_offset;
            miss_bytes = s_v39_miss_bytes;
            hit_offset = s_v39_hit_offset;
            hit_bytes = s_v39_hit_bytes;
            callable_offset = s_v39_callable_offset;
            callable_bytes = s_v39_callable_bytes;
            hit_stride = s_v39_hit_stride;
            state_call = s_v39_state_call;
            ray_index = s_v39_ray_index;
            if (readback != nullptr) readback->AddRef();
            if (fence != nullptr) fence->AddRef();
        }
        if (event_handle == nullptr || readback == nullptr || fence == nullptr || total_bytes == 0)
        {
            s_v39_capture_failed.store(true, std::memory_order_release);
            reshade::log::message(reshade::log::level::warning,
                "D3DMetal RTX live shader-table readback v39: SHADER_TABLE_READBACK_RESULT success=0 reason=missing_capture_objects.");
            if (readback != nullptr) readback->Release();
            if (fence != nullptr) fence->Release();
            return 0;
        }
        const DWORD wait_result = WaitForSingleObject(event_handle, 15000);
        if (wait_result != WAIT_OBJECT_0)
        {
            s_v39_capture_failed.store(true, std::memory_order_release);
            reshade::log::message(reshade::log::level::warning,
                "D3DMetal RTX live shader-table readback v39: SHADER_TABLE_READBACK_RESULT success=0 reason=fence_wait wait_result=%lu completed=%llu.",
                wait_result, static_cast<unsigned long long>(fence->GetCompletedValue()));
            readback->Release(); fence->Release(); return 0;
        }
        void *mapped = nullptr;
        const D3D12_RANGE read_range = { 0, static_cast<SIZE_T>(total_bytes) };
        const HRESULT map_hr = readback->Map(0, &read_range, &mapped);
        if (FAILED(map_hr) || mapped == nullptr)
        {
            s_v39_capture_failed.store(true, std::memory_order_release);
            reshade::log::message(reshade::log::level::warning,
                "D3DMetal RTX live shader-table readback v39: SHADER_TABLE_READBACK_RESULT success=0 reason=map hr=%s raw=0x%08X.",
                reshade::log::hr_to_string(map_hr).c_str(), static_cast<uint32_t>(map_hr));
            readback->Release(); fence->Release(); return 0;
        }
        const unsigned char *bytes = static_cast<const unsigned char *>(mapped);

        auto log_single_record = [&](const char *kind, UINT64 offset, UINT64 size)
        {
            if (size < 32 || offset + size > total_bytes)
                return;
            const size_t record_bytes = static_cast<size_t>(size < 64 ? size : 64);
            char identifier_hex[65] = {};
            char local_root_hex[65] = {};
            char record_hex[129] = {};
            v39_bytes_to_hex(bytes + offset, 32, identifier_hex, sizeof(identifier_hex));
            if (record_bytes >= 64)
                v39_bytes_to_hex(bytes + offset + 32, 32, local_root_hex, sizeof(local_root_hex));
            else
                memcpy(local_root_hex, "NONE", 5);
            v39_bytes_to_hex(bytes + offset, record_bytes, record_hex, sizeof(record_hex));
            reshade::log::message(reshade::log::level::info,
                "D3DMetal RTX live shader-table readback v39: TABLE_RECORD kind=%s index=0 identifier=%s local_root=%s record_hex=%s.",
                kind, identifier_hex, local_root_hex, record_hex);
        };

        log_single_record("RAYGEN", raygen_offset, raygen_bytes);
        log_single_record("MISS", miss_offset, miss_bytes);
        log_single_record("CALLABLE", callable_offset, callable_bytes);

        const UINT64 effective_stride = hit_stride >= 32 ? hit_stride : 64;
        const UINT64 hit_record_count = effective_stride != 0 ? hit_bytes / effective_stride : 0;
        std::vector<v39_unique_identifier> unique_identifiers;
        std::vector<uint64_t> unique_local_hashes;
        uint64_t zero_local_root_count = 0;
        for (UINT64 record_index = 0; record_index < hit_record_count; ++record_index)
        {
            const UINT64 record_offset = hit_offset + record_index * effective_stride;
            if (record_offset + 32 > total_bytes)
                break;
            const unsigned char *identifier = bytes + record_offset;
            size_t unique_index = unique_identifiers.size();
            for (size_t index = 0; index < unique_identifiers.size(); ++index)
            {
                if (memcmp(unique_identifiers[index].identifier, identifier, 32) == 0)
                {
                    unique_index = index;
                    break;
                }
            }
            if (unique_index == unique_identifiers.size())
            {
                v39_unique_identifier entry = {};
                memcpy(entry.identifier, identifier, 32);
                entry.count = 1;
                entry.first_record = record_index;
                unique_identifiers.push_back(entry);
            }
            else
            {
                unique_identifiers[unique_index].count++;
            }

            if (effective_stride >= 64 && record_offset + 64 <= total_bytes)
            {
                const unsigned char *local_root = bytes + record_offset + 32;
                bool all_zero = true;
                for (size_t index = 0; index < 32; ++index)
                    all_zero = all_zero && local_root[index] == 0;
                if (all_zero)
                    zero_local_root_count++;
                const uint64_t local_hash = v39_fnv1a64(local_root, 32);
                if (std::find(unique_local_hashes.begin(), unique_local_hashes.end(), local_hash) == unique_local_hashes.end())
                    unique_local_hashes.push_back(local_hash);
            }

            if (record_index < 16 && record_offset + effective_stride <= total_bytes)
            {
                const size_t sample_bytes = static_cast<size_t>(effective_stride < 64 ? effective_stride : 64);
                char record_hex[129] = {};
                v39_bytes_to_hex(bytes + record_offset, sample_bytes, record_hex, sizeof(record_hex));
                reshade::log::message(reshade::log::level::info,
                    "D3DMetal RTX live shader-table readback v39: HIT_RECORD index=%llu record_hex=%s.",
                    static_cast<unsigned long long>(record_index), record_hex);
            }
        }

        for (size_t index = 0; index < unique_identifiers.size(); ++index)
        {
            char identifier_hex[65] = {};
            v39_bytes_to_hex(unique_identifiers[index].identifier, 32, identifier_hex, sizeof(identifier_hex));
            reshade::log::message(reshade::log::level::info,
                "D3DMetal RTX live shader-table readback v39: HIT_IDENTIFIER unique_index=%zu count=%llu first_record=%llu identifier=%s.",
                index + 1,
                static_cast<unsigned long long>(unique_identifiers[index].count),
                static_cast<unsigned long long>(unique_identifiers[index].first_record),
                identifier_hex);
        }

        const D3D12_RANGE written_range = { 0, 0 };
        readback->Unmap(0, &written_range);
        reshade::log::message(reshade::log::level::info,
            "D3DMetal RTX live shader-table readback v39: SHADER_TABLE_READBACK_RESULT success=1 state_call=%llu ray_index=%llu total_bytes=%llu raygen_bytes=%llu miss_bytes=%llu hit_bytes=%llu hit_stride=%llu hit_records=%llu hit_unique_identifiers=%zu hit_zero_local_roots=%llu hit_unique_local_hashes=%zu callable_bytes=%llu.",
            static_cast<unsigned long long>(state_call),
            static_cast<unsigned long long>(ray_index),
            static_cast<unsigned long long>(total_bytes),
            static_cast<unsigned long long>(raygen_bytes),
            static_cast<unsigned long long>(miss_bytes),
            static_cast<unsigned long long>(hit_bytes),
            static_cast<unsigned long long>(hit_stride),
            static_cast<unsigned long long>(hit_record_count),
            unique_identifiers.size(),
            static_cast<unsigned long long>(zero_local_root_count),
            unique_local_hashes.size(),
            static_cast<unsigned long long>(callable_bytes));

        s_v39_readback_complete.store(true, std::memory_order_release);
        readback->Release(); fence->Release();
        return 0;
    }

    void v39_on_execute_command_lists(
        ID3D12CommandQueue *queue,
        UINT count,
        ID3D12CommandList *const *command_lists)
    {
        void *capture_identity = nullptr;
        {
            std::lock_guard<std::mutex> lock(s_v39_capture_mutex);
            capture_identity = s_v39_capture_command_list_identity;
        }
        if (capture_identity == nullptr || command_lists == nullptr)
            return;
        bool contains_capture = false;
        for (UINT index = 0; index < count; ++index)
        {
            ID3D12CommandList *list = nullptr;
            if (!safe_copy_from_process(command_lists + index, &list, sizeof(list)) || list == nullptr)
                continue;
            if (v33_identity_pointer(reinterpret_cast<IUnknown *>(list)) == capture_identity)
            {
                contains_capture = true;
                break;
            }
        }
        bool expected = false;
        if (!contains_capture || !s_v39_queue_signaled.compare_exchange_strong(expected, true, std::memory_order_acq_rel))
            return;

        ID3D12Fence *fence = nullptr;
        HANDLE event_handle = nullptr;
        {
            std::lock_guard<std::mutex> lock(s_v39_capture_mutex);
            fence = s_v39_capture_fence;
            event_handle = s_v39_capture_event;
        }
        HRESULT signal_hr = E_FAIL, event_hr = E_FAIL;
        if (queue != nullptr && fence != nullptr && event_handle != nullptr)
        {
            signal_hr = queue->Signal(fence, 1);
            if (SUCCEEDED(signal_hr))
                event_hr = fence->SetEventOnCompletion(1, event_handle);
        }
        reshade::log::message(SUCCEEDED(signal_hr) && SUCCEEDED(event_hr) ? reshade::log::level::info : reshade::log::level::warning,
            "D3DMetal RTX live shader-table readback v39: QUEUE_CAPTURE_SUBMITTED count=%u signal_hr=%s signal_raw=0x%08X event_hr=%s event_raw=0x%08X.",
            count,
            reshade::log::hr_to_string(signal_hr).c_str(), static_cast<uint32_t>(signal_hr),
            reshade::log::hr_to_string(event_hr).c_str(), static_cast<uint32_t>(event_hr));
        if (SUCCEEDED(signal_hr) && SUCCEEDED(event_hr))
        {
            HANDLE thread_handle = CreateThread(nullptr, 0, &v39_readback_worker, nullptr, 0, nullptr);
            if (thread_handle != nullptr) CloseHandle(thread_handle);
            else s_v39_capture_failed.store(true, std::memory_order_release);
        }
        else
        {
            s_v39_capture_failed.store(true, std::memory_order_release);
        }
    }

    void v39_try_capture_shader_tables(
        ID3D12GraphicsCommandList *command_list,
        bool dispatch_rays,
        bool rewritten,
        uint64_t state_call,
        uint64_t rewritten_ray_index)
    {
        if (!dispatch_rays || !rewritten || command_list == nullptr || rewritten_ray_index < 2 ||
            !s_v38_readback_complete.load(std::memory_order_acquire))
            return;
        bool expected = false;
        if (!s_v39_capture_claimed.compare_exchange_strong(expected, true, std::memory_order_acq_rel))
            return;

        D3D12_DISPATCH_RAYS_DESC desc = {};
        {
            std::lock_guard<std::mutex> lock(s_v39_desc_mutex);
            if (!s_v39_dispatch_snapshot.ready)
            {
                s_v39_capture_claimed.store(false, std::memory_order_release);
                return;
            }
            desc = s_v39_dispatch_snapshot.desc;
        }

        const UINT64 raygen_bytes = desc.RayGenerationShaderRecord.SizeInBytes;
        const UINT64 miss_bytes = desc.MissShaderTable.SizeInBytes;
        const UINT64 hit_bytes = desc.HitGroupTable.SizeInBytes;
        const UINT64 callable_bytes = desc.CallableShaderTable.SizeInBytes;
        const UINT64 total_bytes = raygen_bytes + miss_bytes + hit_bytes + callable_bytes;
        if (raygen_bytes == 0 || miss_bytes == 0 || hit_bytes == 0 || total_bytes == 0 || total_bytes > v39_max_shader_table_bytes)
        {
            s_v39_capture_failed.store(true, std::memory_order_release);
            reshade::log::message(reshade::log::level::warning,
                "D3DMetal RTX live shader-table readback v39: SHADER_TABLE_CAPTURE recorded=0 reason=table_sizes raygen=%llu miss=%llu hit=%llu callable=%llu total=%llu.",
                static_cast<unsigned long long>(raygen_bytes), static_cast<unsigned long long>(miss_bytes),
                static_cast<unsigned long long>(hit_bytes), static_cast<unsigned long long>(callable_bytes),
                static_cast<unsigned long long>(total_bytes));
            return;
        }

        v39_buffer_record raygen_resource = {}, miss_resource = {}, hit_resource = {}, callable_resource = {};
        UINT64 raygen_source_offset = 0, miss_source_offset = 0, hit_source_offset = 0, callable_source_offset = 0;
        const bool raygen_found = v39_find_buffer(desc.RayGenerationShaderRecord.StartAddress, raygen_bytes, raygen_resource, raygen_source_offset);
        const bool miss_found = v39_find_buffer(desc.MissShaderTable.StartAddress, miss_bytes, miss_resource, miss_source_offset);
        const bool hit_found = v39_find_buffer(desc.HitGroupTable.StartAddress, hit_bytes, hit_resource, hit_source_offset);
        const bool callable_found = callable_bytes == 0 || v39_find_buffer(desc.CallableShaderTable.StartAddress, callable_bytes, callable_resource, callable_source_offset);
        if (!raygen_found || !miss_found || !hit_found || !callable_found)
        {
            s_v39_capture_failed.store(true, std::memory_order_release);
            reshade::log::message(reshade::log::level::warning,
                "D3DMetal RTX live shader-table readback v39: SHADER_TABLE_CAPTURE recorded=0 reason=resource_lookup raygen=%u miss=%u hit=%u callable=%u tracked=%zu.",
                raygen_found ? 1u : 0u, miss_found ? 1u : 0u, hit_found ? 1u : 0u, callable_found ? 1u : 0u,
                s_v39_buffer_records.size());
            return;
        }

        ID3D12Device *device = nullptr;
        HRESULT hr = raygen_resource.resource->GetDevice(__uuidof(ID3D12Device), reinterpret_cast<void **>(&device));
        if (FAILED(hr) || device == nullptr)
        {
            s_v39_capture_failed.store(true, std::memory_order_release);
            return;
        }

        D3D12_HEAP_PROPERTIES heap_properties = {};
        heap_properties.Type = D3D12_HEAP_TYPE_READBACK;
        heap_properties.CPUPageProperty = D3D12_CPU_PAGE_PROPERTY_UNKNOWN;
        heap_properties.MemoryPoolPreference = D3D12_MEMORY_POOL_UNKNOWN;
        heap_properties.CreationNodeMask = 1;
        heap_properties.VisibleNodeMask = 1;
        D3D12_RESOURCE_DESC readback_desc = {};
        readback_desc.Dimension = D3D12_RESOURCE_DIMENSION_BUFFER;
        readback_desc.Width = total_bytes;
        readback_desc.Height = 1;
        readback_desc.DepthOrArraySize = 1;
        readback_desc.MipLevels = 1;
        readback_desc.Format = DXGI_FORMAT_UNKNOWN;
        readback_desc.SampleDesc.Count = 1;
        readback_desc.Layout = D3D12_TEXTURE_LAYOUT_ROW_MAJOR;
        readback_desc.Flags = D3D12_RESOURCE_FLAG_NONE;
        ID3D12Resource *readback = nullptr;
        hr = device->CreateCommittedResource(&heap_properties, D3D12_HEAP_FLAG_NONE, &readback_desc,
            D3D12_RESOURCE_STATE_COPY_DEST, nullptr, __uuidof(ID3D12Resource), reinterpret_cast<void **>(&readback));
        if (FAILED(hr) || readback == nullptr)
        {
            device->Release();
            s_v39_capture_failed.store(true, std::memory_order_release);
            reshade::log::message(reshade::log::level::warning,
                "D3DMetal RTX live shader-table readback v39: SHADER_TABLE_CAPTURE recorded=0 reason=create_readback hr=%s raw=0x%08X.",
                reshade::log::hr_to_string(hr).c_str(), static_cast<uint32_t>(hr));
            return;
        }

        ID3D12Fence *fence = nullptr;
        hr = device->CreateFence(0, D3D12_FENCE_FLAG_NONE, __uuidof(ID3D12Fence), reinterpret_cast<void **>(&fence));
        HANDLE event_handle = CreateEventW(nullptr, FALSE, FALSE, nullptr);
        device->Release();
        if (FAILED(hr) || fence == nullptr || event_handle == nullptr)
        {
            if (readback != nullptr) readback->Release();
            if (fence != nullptr) fence->Release();
            if (event_handle != nullptr) CloseHandle(event_handle);
            s_v39_capture_failed.store(true, std::memory_order_release);
            return;
        }

        ID3D12Resource *unique_resources[4] = {};
        UINT unique_count = 0;
        auto add_unique = [&](ID3D12Resource *resource)
        {
            if (resource == nullptr) return;
            for (UINT index = 0; index < unique_count; ++index)
                if (unique_resources[index] == resource) return;
            unique_resources[unique_count++] = resource;
        };
        add_unique(raygen_resource.resource);
        add_unique(miss_resource.resource);
        add_unique(hit_resource.resource);
        if (callable_bytes != 0) add_unique(callable_resource.resource);

        D3D12_RESOURCE_BARRIER to_copy[4] = {};
        D3D12_RESOURCE_BARRIER from_copy[4] = {};
        for (UINT index = 0; index < unique_count; ++index)
        {
            to_copy[index].Type = D3D12_RESOURCE_BARRIER_TYPE_TRANSITION;
            to_copy[index].Flags = D3D12_RESOURCE_BARRIER_FLAG_NONE;
            to_copy[index].Transition.pResource = unique_resources[index];
            to_copy[index].Transition.Subresource = D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES;
            to_copy[index].Transition.StateBefore = D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE;
            to_copy[index].Transition.StateAfter = D3D12_RESOURCE_STATE_COPY_SOURCE;
            from_copy[index] = to_copy[index];
            from_copy[index].Transition.StateBefore = D3D12_RESOURCE_STATE_COPY_SOURCE;
            from_copy[index].Transition.StateAfter = D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE;
        }

        command_list->ResourceBarrier(unique_count, to_copy);
        UINT64 destination_offset = 0;
        const UINT64 raygen_destination_offset = destination_offset;
        command_list->CopyBufferRegion(readback, destination_offset, raygen_resource.resource, raygen_source_offset, raygen_bytes);
        destination_offset += raygen_bytes;
        const UINT64 miss_destination_offset = destination_offset;
        command_list->CopyBufferRegion(readback, destination_offset, miss_resource.resource, miss_source_offset, miss_bytes);
        destination_offset += miss_bytes;
        const UINT64 hit_destination_offset = destination_offset;
        command_list->CopyBufferRegion(readback, destination_offset, hit_resource.resource, hit_source_offset, hit_bytes);
        destination_offset += hit_bytes;
        const UINT64 callable_destination_offset = destination_offset;
        if (callable_bytes != 0)
            command_list->CopyBufferRegion(readback, destination_offset, callable_resource.resource, callable_source_offset, callable_bytes);
        command_list->ResourceBarrier(unique_count, from_copy);

        void *const identity = v33_identity_pointer(reinterpret_cast<IUnknown *>(command_list));
        {
            std::lock_guard<std::mutex> lock(s_v39_capture_mutex);
            s_v39_readback_resource = readback;
            s_v39_capture_fence = fence;
            s_v39_capture_event = event_handle;
            s_v39_capture_command_list_identity = identity;
            s_v39_total_readback_bytes = total_bytes;
            s_v39_raygen_offset = raygen_destination_offset;
            s_v39_raygen_bytes = raygen_bytes;
            s_v39_miss_offset = miss_destination_offset;
            s_v39_miss_bytes = miss_bytes;
            s_v39_hit_offset = hit_destination_offset;
            s_v39_hit_bytes = hit_bytes;
            s_v39_callable_offset = callable_destination_offset;
            s_v39_callable_bytes = callable_bytes;
            s_v39_hit_stride = desc.HitGroupTable.StrideInBytes;
            s_v39_state_call = state_call;
            s_v39_ray_index = rewritten_ray_index;
        }
        s_v39_copy_recorded.store(true, std::memory_order_release);
        reshade::log::message(reshade::log::level::info,
            "D3DMetal RTX live shader-table readback v39: SHADER_TABLE_CAPTURE recorded=1 state_call=%llu ray_index=%llu command_list=%p identity=%p total_bytes=%llu unique_resources=%u raygen_resource=%p miss_resource=%p hit_resource=%p callable_resource=%p.",
            static_cast<unsigned long long>(state_call), static_cast<unsigned long long>(rewritten_ray_index),
            command_list, identity, static_cast<unsigned long long>(total_bytes), unique_count,
            raygen_resource.resource, miss_resource.resource, hit_resource.resource,
            callable_bytes != 0 ? callable_resource.resource : nullptr);
    }

'''
text = text.replace(anchor, helper + anchor, 1)

# Store the real descriptor after V38 decodes it.
desc_anchor = "\t\tmemcpy(&desc, bytes, sizeof(desc));\n"
text = replace_once(text, desc_anchor, desc_anchor + "\t\tv39_store_dispatch_desc(desc);\n", "V39 descriptor storage")

# Install resource hooks alongside V38's queue hook.
install_anchor = "\t\tv38_install_create_command_queue_hook(device);\n"
text = replace_once(text, install_anchor, install_anchor + "\t\tv39_install_resource_hooks(device);\n", "V39 resource hook install")

# Signal V39 after the game command lists have been submitted.
queue_anchor = "\t\tif (s_v38_original_execute_command_lists != nullptr)\n\t\t\ts_v38_original_execute_command_lists(\n\t\t\t\tqueue, count, command_lists);\n\n"
text = replace_once(text, queue_anchor, queue_anchor + "\t\tv39_on_execute_command_lists(queue, count, command_lists);\n\n", "V39 queue submission correlation")

# Capture shader tables on a subsequent rewritten indirect ray launch.
execute_anchor = "\t\tv38_try_capture_dispatch_record(\n\t\t\tcommand_list,\n\t\t\targument_buffer,\n\t\t\targument_buffer_offset,\n\t\t\tdispatch_rays,\n\t\t\trewritten,\n\t\t\tstate_call,\n\t\t\trewritten_ray_index);\n\n"
execute_add = execute_anchor + "\t\tv39_try_capture_shader_tables(\n\t\t\tcommand_list,\n\t\t\tdispatch_rays,\n\t\t\trewritten,\n\t\t\tstate_call,\n\t\t\trewritten_ray_index);\n\n"
text = replace_once(text, execute_anchor, execute_add, "V39 shader-table capture call")

required = [
    "D3DMetal RTX live shader-table readback v39:",
    "RESOURCE_HOOKS installed=",
    "DISPATCH_DESC_READY raygen=",
    "SHADER_TABLE_CAPTURE recorded=",
    "QUEUE_CAPTURE_SUBMITTED count=",
    "SHADER_TABLE_READBACK_RESULT success=",
    "TABLE_RECORD kind=",
    "HIT_IDENTIFIER unique_index=",
    "v39_try_capture_shader_tables(",
    "v39_install_resource_hooks(device);",
    "v39_store_dispatch_desc(desc);",
    "v39_on_execute_command_lists(queue, count, command_lists);",
]
for marker in required:
    if marker not in text:
        raise RuntimeError(f"Missing V39 source marker: {marker}")

if "hex[0] = '\\\\0';" in text or "hex[count * 2] = '\\\\0';" in text:
    raise RuntimeError("V38 logging terminator typo remains")

SOURCE.write_text(text, encoding="utf-8", newline="\n")

report = Path("v39-patch-report.txt")
report.write_text("\n".join([
    "V39_LIVE_SHADER_TABLE_READBACK_PATCH_OK",
    "V38_LIVE_DISPATCH_READBACK_PRESERVED=YES",
    "V38_HEX_TERMINATOR_CORRECTED=YES",
    "CREATE_COMMITTED_RESOURCE_SLOT=27",
    "CREATE_PLACED_RESOURCE_SLOT=29",
    "CREATE_RESERVED_RESOURCE_SLOT=30",
    "LIVE_SHADER_TABLE_RESOURCE_TRACKING=ENABLED",
    "RAYGEN_TABLE_READBACK=ENABLED",
    "MISS_TABLE_READBACK=ENABLED",
    "FULL_HIT_TABLE_READBACK=ENABLED",
    "CALLABLE_TABLE_READBACK=ENABLED",
    "IDENTIFIER_AND_LOCAL_ROOT_DECODING=ENABLED",
    "TABLE_BYTES_UNMODIFIED=YES",
    "DISPATCH_ARGUMENTS_UNMODIFIED=YES",
    "STATE_OBJECT_UNMODIFIED_BY_V39=YES",
    "RESULT=PASS",
    "",
]), encoding="utf-8", newline="\n")
print(report.read_text(encoding="utf-8"))
