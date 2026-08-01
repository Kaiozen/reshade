from pathlib import Path

SOURCE = Path("source/d3d12/d3d12.cpp")
if not SOURCE.is_file():
    raise RuntimeError(f"Missing source file: {SOURCE}")

text = SOURCE.read_text(encoding="utf-8-sig")
for required in (
    "D3DMetal RTX ray-hit pattern inheritance census v54:",
    "D3DMetal RTX live dispatch readback v38:",
    "D3DMetal RTX live shader-table readback v39:",
):
    if required not in text:
        raise RuntimeError(f"V55 prerequisite is missing: {required}")
if "D3DMetal RTX raygen local-root descriptor resolution v55:" in text:
    raise RuntimeError("V55 is already present")


def replace_once(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 occurrence, found {count}")
    return source.replace(old, new, 1)


helper_anchor = "    using v39_create_committed_resource_fn = HRESULT (STDMETHODCALLTYPE *)(\n"
if text.count(helper_anchor) != 1:
    raise RuntimeError(f"V55 helper anchor mismatch: {text.count(helper_anchor)}")

helper = r'''
    // V55 resolves the three GPU descriptor-table handles stored in the
    // 64-byte raygen shader record local-root payload:
    //   +32: SRV table t0-t7
    //   +40: CBV table b0
    //   +48: UAV table u0-u1
    // The layout comes from the exact 188-byte local root signature captured
    // for ExecuteTrace (SHA256 b47efe3fe606db7f01f0e808c3c1dd5b58bc8c67f36078e52f379521bbc1125c).
    using v55_create_descriptor_heap_fn = HRESULT (STDMETHODCALLTYPE *)(
        ID3D12Device *, const D3D12_DESCRIPTOR_HEAP_DESC *, REFIID, void **);
    using v55_create_cbv_fn = void (STDMETHODCALLTYPE *)(
        ID3D12Device *, const D3D12_CONSTANT_BUFFER_VIEW_DESC *,
        D3D12_CPU_DESCRIPTOR_HANDLE);
    using v55_create_srv_fn = void (STDMETHODCALLTYPE *)(
        ID3D12Device *, ID3D12Resource *,
        const D3D12_SHADER_RESOURCE_VIEW_DESC *,
        D3D12_CPU_DESCRIPTOR_HANDLE);
    using v55_create_uav_fn = void (STDMETHODCALLTYPE *)(
        ID3D12Device *, ID3D12Resource *, ID3D12Resource *,
        const D3D12_UNORDERED_ACCESS_VIEW_DESC *,
        D3D12_CPU_DESCRIPTOR_HANDLE);
    using v55_copy_descriptors_fn = void (STDMETHODCALLTYPE *)(
        ID3D12Device *,
        UINT, const D3D12_CPU_DESCRIPTOR_HANDLE *, const UINT *,
        UINT, const D3D12_CPU_DESCRIPTOR_HANDLE *, const UINT *,
        D3D12_DESCRIPTOR_HEAP_TYPE);
    using v55_copy_descriptors_simple_fn = void (STDMETHODCALLTYPE *)(
        ID3D12Device *, UINT,
        D3D12_CPU_DESCRIPTOR_HANDLE,
        D3D12_CPU_DESCRIPTOR_HANDLE,
        D3D12_DESCRIPTOR_HEAP_TYPE);

    constexpr size_t v55_create_descriptor_heap_slot = 14;
    constexpr size_t v55_create_cbv_slot = 17;
    constexpr size_t v55_create_srv_slot = 18;
    constexpr size_t v55_create_uav_slot = 19;
    constexpr size_t v55_copy_descriptors_slot = 23;
    constexpr size_t v55_copy_descriptors_simple_slot = 24;

    static v55_create_descriptor_heap_fn s_v55_original_create_descriptor_heap = nullptr;
    static v55_create_cbv_fn s_v55_original_create_cbv = nullptr;
    static v55_create_srv_fn s_v55_original_create_srv = nullptr;
    static v55_create_uav_fn s_v55_original_create_uav = nullptr;
    static v55_copy_descriptors_fn s_v55_original_copy_descriptors = nullptr;
    static v55_copy_descriptors_simple_fn s_v55_original_copy_descriptors_simple = nullptr;

    struct v55_heap_info
    {
        uint64_t heap_id = 0;
        void *identity = nullptr;
        D3D12_DESCRIPTOR_HEAP_TYPE type = D3D12_DESCRIPTOR_HEAP_TYPE_CBV_SRV_UAV;
        UINT count = 0;
        UINT increment = 0;
        SIZE_T cpu_start = 0;
        UINT64 gpu_start = 0;
        bool shader_visible = false;
    };

    struct v55_resource_info
    {
        uint64_t resource_id = 0;
        void *identity = nullptr;
        unsigned int dimension = 0;
        UINT64 width = 0;
        UINT height = 0;
        UINT16 depth_or_array = 0;
        UINT16 mip_levels = 0;
        unsigned int format = 0;
        unsigned int layout = 0;
        unsigned int flags = 0;
        UINT64 gpu_va = 0;
    };

    struct v55_descriptor_info
    {
        unsigned int kind = 0; // 1=CBV, 2=SRV, 3=UAV
        uint64_t resource_id = 0;
        unsigned int format = 0;
        unsigned int view_dimension = 0;
        UINT64 first_element = 0;
        UINT num_elements = 0;
        UINT structure_stride = 0;
        UINT view_flags = 0;
        UINT64 buffer_location = 0;
        UINT size_in_bytes = 0;
        UINT64 acceleration_structure_location = 0;
    };

    static std::once_flag s_v55_device_hook_once;
    static std::once_flag s_v55_active_log_once;
    static std::atomic<bool> s_v55_device_hooks_installed = false;
    static std::atomic<bool> s_v55_resolution_claimed = false;
    static std::mutex s_v55_mutex;
    static std::vector<v55_heap_info> s_v55_heaps;
    static std::unordered_map<SIZE_T, v55_descriptor_info> s_v55_descriptors;
    static std::unordered_map<void *, uint64_t> s_v55_resource_ids_by_identity;
    static std::unordered_map<uint64_t, v55_resource_info> s_v55_resources;
    static std::atomic<uint64_t> s_v55_next_heap_id = 0;
    static std::atomic<uint64_t> s_v55_next_resource_id = 0;
    static std::atomic<uint64_t> s_v55_descriptor_events = 0;
    static std::atomic<uint64_t> s_v55_descriptor_copy_events = 0;

    const char *v55_descriptor_kind_name(unsigned int kind)
    {
        switch (kind)
        {
        case 1: return "cbv";
        case 2: return "srv";
        case 3: return "uav";
        default: return "unknown";
        }
    }

    void v55_log_active()
    {
        std::call_once(
            s_v55_active_log_once,
            []()
            {
                reshade::log::message(
                    reshade::log::level::info,
                    "D3DMetal RTX raygen local-root descriptor resolution v55: ACTIVE shader-record-bytes=64 local-root-offsets=srv32-cbv40-uav48 srv-range=t0-t7 cbv-range=b0 uav-range=u0-u1 exact-descriptor-resolution=1 commands-modified=0.");
            });
    }

    uint64_t v55_register_resource(ID3D12Resource *resource)
    {
        if (resource == nullptr)
            return 0;
        void *const identity = v33_identity_pointer(
            reinterpret_cast<IUnknown *>(resource));
        if (identity == nullptr)
            return 0;

        {
            std::lock_guard<std::mutex> lock(s_v55_mutex);
            const auto found = s_v55_resource_ids_by_identity.find(identity);
            if (found != s_v55_resource_ids_by_identity.end())
                return found->second;
        }

        const D3D12_RESOURCE_DESC desc = resource->GetDesc();
        v55_resource_info info = {};
        info.resource_id = ++s_v55_next_resource_id;
        info.identity = identity;
        info.dimension = static_cast<unsigned int>(desc.Dimension);
        info.width = desc.Width;
        info.height = desc.Height;
        info.depth_or_array = desc.DepthOrArraySize;
        info.mip_levels = desc.MipLevels;
        info.format = static_cast<unsigned int>(desc.Format);
        info.layout = static_cast<unsigned int>(desc.Layout);
        info.flags = static_cast<unsigned int>(desc.Flags);
        info.gpu_va = desc.Dimension == D3D12_RESOURCE_DIMENSION_BUFFER ?
            static_cast<UINT64>(resource->GetGPUVirtualAddress()) : 0;

        {
            std::lock_guard<std::mutex> lock(s_v55_mutex);
            const auto existing = s_v55_resource_ids_by_identity.find(identity);
            if (existing != s_v55_resource_ids_by_identity.end())
                return existing->second;
            s_v55_resource_ids_by_identity[identity] = info.resource_id;
            s_v55_resources[info.resource_id] = info;
        }
        return info.resource_id;
    }

    bool v55_get_resource(uint64_t resource_id, v55_resource_info &info)
    {
        info = {};
        if (resource_id == 0)
            return false;
        std::lock_guard<std::mutex> lock(s_v55_mutex);
        const auto found = s_v55_resources.find(resource_id);
        if (found == s_v55_resources.end())
            return false;
        info = found->second;
        return true;
    }

    void v55_set_descriptor(SIZE_T cpu_ptr, const v55_descriptor_info &info)
    {
        if (cpu_ptr == 0)
            return;
        std::lock_guard<std::mutex> lock(s_v55_mutex);
        s_v55_descriptors[cpu_ptr] = info;
        ++s_v55_descriptor_events;
    }

    bool v55_get_descriptor(SIZE_T cpu_ptr, v55_descriptor_info &info)
    {
        info = {};
        if (cpu_ptr == 0)
            return false;
        std::lock_guard<std::mutex> lock(s_v55_mutex);
        const auto found = s_v55_descriptors.find(cpu_ptr);
        if (found == s_v55_descriptors.end())
            return false;
        info = found->second;
        return true;
    }

    void v55_copy_one_descriptor(SIZE_T destination, SIZE_T source)
    {
        if (destination == 0 || source == 0)
            return;
        std::lock_guard<std::mutex> lock(s_v55_mutex);
        const auto found = s_v55_descriptors.find(source);
        if (found != s_v55_descriptors.end())
            s_v55_descriptors[destination] = found->second;
        else
            s_v55_descriptors.erase(destination);
        ++s_v55_descriptor_copy_events;
    }

    HRESULT STDMETHODCALLTYPE v55_trace_create_descriptor_heap(
        ID3D12Device *device,
        const D3D12_DESCRIPTOR_HEAP_DESC *desc,
        REFIID riid,
        void **heap)
    {
        if (s_v55_original_create_descriptor_heap == nullptr)
            return E_FAIL;
        const HRESULT hr =
            s_v55_original_create_descriptor_heap(device, desc, riid, heap);
        void *created = nullptr;
        if (heap != nullptr)
            safe_copy_from_process(heap, &created, sizeof(created));
        D3D12_DESCRIPTOR_HEAP_DESC snapshot = {};
        if (SUCCEEDED(hr) && created != nullptr && desc != nullptr &&
            safe_copy_from_process(desc, &snapshot, sizeof(snapshot)))
        {
            ID3D12DescriptorHeap *descriptor_heap = nullptr;
            if (SUCCEEDED(
                    reinterpret_cast<IUnknown *>(created)->QueryInterface(
                        __uuidof(ID3D12DescriptorHeap),
                        reinterpret_cast<void **>(&descriptor_heap))) &&
                descriptor_heap != nullptr)
            {
                v55_heap_info info = {};
                info.heap_id = ++s_v55_next_heap_id;
                info.identity = v33_identity_pointer(
                    reinterpret_cast<IUnknown *>(descriptor_heap));
                info.type = snapshot.Type;
                info.count = snapshot.NumDescriptors;
                info.increment =
                    device->GetDescriptorHandleIncrementSize(snapshot.Type);
                info.cpu_start =
                    descriptor_heap->GetCPUDescriptorHandleForHeapStart().ptr;
                info.shader_visible =
                    (snapshot.Flags &
                     D3D12_DESCRIPTOR_HEAP_FLAG_SHADER_VISIBLE) != 0;
                info.gpu_start = info.shader_visible ?
                    descriptor_heap->GetGPUDescriptorHandleForHeapStart().ptr : 0;
                {
                    std::lock_guard<std::mutex> lock(s_v55_mutex);
                    s_v55_heaps.push_back(info);
                }
                descriptor_heap->Release();
            }
        }
        return hr;
    }

    void STDMETHODCALLTYPE v55_trace_create_cbv(
        ID3D12Device *device,
        const D3D12_CONSTANT_BUFFER_VIEW_DESC *desc,
        D3D12_CPU_DESCRIPTOR_HANDLE destination)
    {
        if (s_v55_original_create_cbv != nullptr)
            s_v55_original_create_cbv(device, desc, destination);
        v55_descriptor_info info = {};
        info.kind = 1;
        D3D12_CONSTANT_BUFFER_VIEW_DESC snapshot = {};
        if (desc != nullptr &&
            safe_copy_from_process(desc, &snapshot, sizeof(snapshot)))
        {
            info.buffer_location = snapshot.BufferLocation;
            info.size_in_bytes = snapshot.SizeInBytes;
        }
        v55_set_descriptor(destination.ptr, info);
    }

    void STDMETHODCALLTYPE v55_trace_create_srv(
        ID3D12Device *device,
        ID3D12Resource *resource,
        const D3D12_SHADER_RESOURCE_VIEW_DESC *desc,
        D3D12_CPU_DESCRIPTOR_HANDLE destination)
    {
        if (s_v55_original_create_srv != nullptr)
            s_v55_original_create_srv(device, resource, desc, destination);
        v55_descriptor_info info = {};
        info.kind = 2;
        info.resource_id = v55_register_resource(resource);
        D3D12_SHADER_RESOURCE_VIEW_DESC snapshot = {};
        if (desc != nullptr &&
            safe_copy_from_process(desc, &snapshot, sizeof(snapshot)))
        {
            info.format = static_cast<unsigned int>(snapshot.Format);
            info.view_dimension =
                static_cast<unsigned int>(snapshot.ViewDimension);
            if (snapshot.ViewDimension == D3D12_SRV_DIMENSION_BUFFER)
            {
                info.first_element = snapshot.Buffer.FirstElement;
                info.num_elements = snapshot.Buffer.NumElements;
                info.structure_stride =
                    snapshot.Buffer.StructureByteStride;
                info.view_flags =
                    static_cast<UINT>(snapshot.Buffer.Flags);
            }
            else if (
                snapshot.ViewDimension ==
                D3D12_SRV_DIMENSION_RAYTRACING_ACCELERATION_STRUCTURE)
            {
                info.acceleration_structure_location =
                    snapshot.RaytracingAccelerationStructure.Location;
            }
        }
        v55_set_descriptor(destination.ptr, info);
    }

    void STDMETHODCALLTYPE v55_trace_create_uav(
        ID3D12Device *device,
        ID3D12Resource *resource,
        ID3D12Resource *counter_resource,
        const D3D12_UNORDERED_ACCESS_VIEW_DESC *desc,
        D3D12_CPU_DESCRIPTOR_HANDLE destination)
    {
        if (s_v55_original_create_uav != nullptr)
            s_v55_original_create_uav(
                device, resource, counter_resource, desc, destination);
        v55_descriptor_info info = {};
        info.kind = 3;
        info.resource_id = v55_register_resource(resource);
        D3D12_UNORDERED_ACCESS_VIEW_DESC snapshot = {};
        if (desc != nullptr &&
            safe_copy_from_process(desc, &snapshot, sizeof(snapshot)))
        {
            info.format = static_cast<unsigned int>(snapshot.Format);
            info.view_dimension =
                static_cast<unsigned int>(snapshot.ViewDimension);
            if (snapshot.ViewDimension == D3D12_UAV_DIMENSION_BUFFER)
            {
                info.first_element = snapshot.Buffer.FirstElement;
                info.num_elements = snapshot.Buffer.NumElements;
                info.structure_stride =
                    snapshot.Buffer.StructureByteStride;
                info.view_flags =
                    static_cast<UINT>(snapshot.Buffer.Flags);
            }
        }
        v55_set_descriptor(destination.ptr, info);
    }

    void STDMETHODCALLTYPE v55_trace_copy_descriptors_simple(
        ID3D12Device *device,
        UINT count,
        D3D12_CPU_DESCRIPTOR_HANDLE destination,
        D3D12_CPU_DESCRIPTOR_HANDLE source,
        D3D12_DESCRIPTOR_HEAP_TYPE type)
    {
        if (s_v55_original_copy_descriptors_simple != nullptr)
            s_v55_original_copy_descriptors_simple(
                device, count, destination, source, type);
        const UINT increment =
            device->GetDescriptorHandleIncrementSize(type);
        for (UINT index = 0; index < count && index < 16384u; ++index)
        {
            v55_copy_one_descriptor(
                destination.ptr + static_cast<SIZE_T>(index) * increment,
                source.ptr + static_cast<SIZE_T>(index) * increment);
        }
    }

    void STDMETHODCALLTYPE v55_trace_copy_descriptors(
        ID3D12Device *device,
        UINT destination_range_count,
        const D3D12_CPU_DESCRIPTOR_HANDLE *destination_starts,
        const UINT *destination_sizes,
        UINT source_range_count,
        const D3D12_CPU_DESCRIPTOR_HANDLE *source_starts,
        const UINT *source_sizes,
        D3D12_DESCRIPTOR_HEAP_TYPE type)
    {
        if (s_v55_original_copy_descriptors != nullptr)
            s_v55_original_copy_descriptors(
                device,
                destination_range_count,
                destination_starts,
                destination_sizes,
                source_range_count,
                source_starts,
                source_sizes,
                type);
        if (destination_starts == nullptr || source_starts == nullptr)
            return;
        const UINT increment =
            device->GetDescriptorHandleIncrementSize(type);
        UINT destination_range = 0;
        UINT source_range = 0;
        UINT destination_offset = 0;
        UINT source_offset = 0;
        UINT copied = 0;
        while (destination_range < destination_range_count &&
               source_range < source_range_count &&
               copied < 16384u)
        {
            D3D12_CPU_DESCRIPTOR_HANDLE destination_start = {};
            D3D12_CPU_DESCRIPTOR_HANDLE source_start = {};
            if (!safe_copy_from_process(
                    destination_starts + destination_range,
                    &destination_start,
                    sizeof(destination_start)) ||
                !safe_copy_from_process(
                    source_starts + source_range,
                    &source_start,
                    sizeof(source_start)))
                break;
            UINT destination_size = 1;
            UINT source_size = 1;
            if (destination_sizes != nullptr &&
                !safe_copy_from_process(
                    destination_sizes + destination_range,
                    &destination_size,
                    sizeof(destination_size)))
                break;
            if (source_sizes != nullptr &&
                !safe_copy_from_process(
                    source_sizes + source_range,
                    &source_size,
                    sizeof(source_size)))
                break;
            if (destination_offset >= destination_size)
            {
                ++destination_range;
                destination_offset = 0;
                continue;
            }
            if (source_offset >= source_size)
            {
                ++source_range;
                source_offset = 0;
                continue;
            }
            v55_copy_one_descriptor(
                destination_start.ptr +
                    static_cast<SIZE_T>(destination_offset) * increment,
                source_start.ptr +
                    static_cast<SIZE_T>(source_offset) * increment);
            ++destination_offset;
            ++source_offset;
            ++copied;
        }
    }

    bool v55_find_heap_by_gpu(
        UINT64 gpu_handle,
        v55_heap_info &heap,
        UINT &descriptor_index)
    {
        heap = {};
        descriptor_index = 0;
        if (gpu_handle == 0)
            return false;
        std::lock_guard<std::mutex> lock(s_v55_mutex);
        for (auto it = s_v55_heaps.rbegin(); it != s_v55_heaps.rend(); ++it)
        {
            if (!it->shader_visible || it->gpu_start == 0 ||
                it->increment == 0 || it->count == 0 ||
                gpu_handle < it->gpu_start)
                continue;
            const UINT64 delta = gpu_handle - it->gpu_start;
            if ((delta % it->increment) != 0)
                continue;
            const UINT64 index = delta / it->increment;
            if (index >= it->count)
                continue;
            heap = *it;
            descriptor_index = static_cast<UINT>(index);
            return true;
        }
        return false;
    }

    bool v55_resolve_gpu_descriptor(
        UINT64 gpu_handle,
        v55_heap_info &heap,
        UINT &descriptor_index,
        v55_descriptor_info &descriptor,
        v55_resource_info &resource)
    {
        descriptor = {};
        resource = {};
        if (!v55_find_heap_by_gpu(gpu_handle, heap, descriptor_index))
            return false;
        const SIZE_T cpu_ptr =
            heap.cpu_start +
            static_cast<SIZE_T>(descriptor_index) * heap.increment;
        if (!v55_get_descriptor(cpu_ptr, descriptor))
            return false;
        v55_get_resource(descriptor.resource_id, resource);
        return true;
    }

    unsigned int v55_log_table(
        const char *table_name,
        UINT64 base_handle,
        UINT descriptor_count)
    {
        v55_heap_info base_heap = {};
        UINT base_index = 0;
        if (!v55_find_heap_by_gpu(base_handle, base_heap, base_index))
        {
            reshade::log::message(
                reshade::log::level::warning,
                "D3DMetal RTX raygen local-root descriptor resolution v55: TABLE_UNRESOLVED table=%s base_gpu=0x%llX expected_count=%u.",
                table_name,
                static_cast<unsigned long long>(base_handle),
                descriptor_count);
            return 0;
        }

        unsigned int resolved = 0;
        for (UINT offset = 0; offset < descriptor_count; ++offset)
        {
            const UINT index = base_index + offset;
            if (index >= base_heap.count)
                break;
            const UINT64 gpu_handle =
                base_heap.gpu_start +
                static_cast<UINT64>(index) * base_heap.increment;
            v55_heap_info heap = {};
            UINT descriptor_index = 0;
            v55_descriptor_info descriptor = {};
            v55_resource_info resource = {};
            const bool found = v55_resolve_gpu_descriptor(
                gpu_handle, heap, descriptor_index, descriptor, resource);
            if (found)
                ++resolved;
            reshade::log::message(
                found ? reshade::log::level::info :
                        reshade::log::level::warning,
                "D3DMetal RTX raygen local-root descriptor resolution v55: TABLE_DESCRIPTOR table=%s offset=%u gpu_handle=0x%llX heap_id=%llu heap_index=%u heap_increment=%u found=%u kind=%s resource_id=%llu view_format=%u view_dimension=%u first_element=%llu num_elements=%u stride=%u view_flags=0x%X cbv_location=0x%llX cbv_size=%u as_location=0x%llX resource_dimension=%u resource_width=%llu resource_height=%u resource_format=%u resource_flags=0x%X resource_gpu_va=0x%llX.",
                table_name,
                offset,
                static_cast<unsigned long long>(gpu_handle),
                static_cast<unsigned long long>(heap.heap_id),
                descriptor_index,
                heap.increment,
                found ? 1u : 0u,
                v55_descriptor_kind_name(descriptor.kind),
                static_cast<unsigned long long>(descriptor.resource_id),
                descriptor.format,
                descriptor.view_dimension,
                static_cast<unsigned long long>(descriptor.first_element),
                descriptor.num_elements,
                descriptor.structure_stride,
                descriptor.view_flags,
                static_cast<unsigned long long>(descriptor.buffer_location),
                descriptor.size_in_bytes,
                static_cast<unsigned long long>(
                    descriptor.acceleration_structure_location),
                resource.dimension,
                static_cast<unsigned long long>(resource.width),
                resource.height,
                resource.format,
                resource.flags,
                static_cast<unsigned long long>(resource.gpu_va));
        }
        return resolved;
    }

    void v55_resolve_raygen_local_root(
        const unsigned char *record,
        UINT64 record_bytes)
    {
        bool expected = false;
        if (!s_v55_resolution_claimed.compare_exchange_strong(
                expected, true, std::memory_order_acq_rel))
            return;

        v55_log_active();
        if (record == nullptr || record_bytes < 56)
        {
            reshade::log::message(
                reshade::log::level::warning,
                "D3DMetal RTX raygen local-root descriptor resolution v55: LOCAL_ROOT_DESCRIPTOR_RESOLUTION_RESULT success=0 reason=raygen-record-too-small bytes=%llu.",
                static_cast<unsigned long long>(record_bytes));
            return;
        }

        UINT64 srv_handle = 0;
        UINT64 cbv_handle = 0;
        UINT64 uav_handle = 0;
        memcpy(&srv_handle, record + 32, sizeof(srv_handle));
        memcpy(&cbv_handle, record + 40, sizeof(cbv_handle));
        memcpy(&uav_handle, record + 48, sizeof(uav_handle));

        reshade::log::message(
            reshade::log::level::info,
            "D3DMetal RTX raygen local-root descriptor resolution v55: LOCAL_ROOT_HANDLES srv_t0_t7=0x%llX cbv_b0=0x%llX uav_u0_u1=0x%llX record_bytes=%llu local_root_signature_sha256=b47efe3fe606db7f01f0e808c3c1dd5b58bc8c67f36078e52f379521bbc1125c.",
            static_cast<unsigned long long>(srv_handle),
            static_cast<unsigned long long>(cbv_handle),
            static_cast<unsigned long long>(uav_handle),
            static_cast<unsigned long long>(record_bytes));

        const unsigned int srv_resolved =
            v55_log_table("srv_t0_t7", srv_handle, 8);
        const unsigned int cbv_resolved =
            v55_log_table("cbv_b0", cbv_handle, 1);
        const unsigned int uav_resolved =
            v55_log_table("uav_u0_u1", uav_handle, 2);

        v55_heap_info u1_heap = {};
        UINT u1_index = 0;
        v55_descriptor_info u1 = {};
        v55_resource_info u1_resource = {};
        UINT64 u1_gpu_handle = 0;
        bool u1_found = false;
        v55_heap_info uav_base_heap = {};
        UINT uav_base_index = 0;
        if (v55_find_heap_by_gpu(
                uav_handle, uav_base_heap, uav_base_index) &&
            uav_base_index + 1 < uav_base_heap.count)
        {
            u1_gpu_handle =
                uav_base_heap.gpu_start +
                static_cast<UINT64>(uav_base_index + 1) *
                    uav_base_heap.increment;
            u1_found = v55_resolve_gpu_descriptor(
                u1_gpu_handle,
                u1_heap,
                u1_index,
                u1,
                u1_resource);
        }

        const bool u1_kind_ok = u1_found && u1.kind == 3;
        const bool u1_view_ok =
            u1_kind_ok &&
            u1.view_dimension ==
                static_cast<unsigned int>(D3D12_UAV_DIMENSION_BUFFER);
        const bool u1_stride_ok = u1_view_ok && u1.structure_stride == 24;
        const bool u1_resource_ok =
            u1_stride_ok &&
            u1_resource.dimension ==
                static_cast<unsigned int>(D3D12_RESOURCE_DIMENSION_BUFFER) &&
            u1_resource.width >= 24;
        const bool exact_ok =
            srv_resolved == 8 &&
            cbv_resolved == 1 &&
            uav_resolved == 2 &&
            u1_resource_ok;

        const char *diagnosis =
            exact_ok ?
                "LOCAL_ROOT_AND_RAYHIT_U1_BINDING_MATCH_SHADER_CONTRACT" :
            !u1_found ?
                "RAYHIT_U1_DESCRIPTOR_NOT_RESOLVED" :
            !u1_kind_ok ?
                "RAYHIT_U1_DESCRIPTOR_KIND_MISMATCH" :
            !u1_view_ok ?
                "RAYHIT_U1_NOT_BUFFER_UAV" :
            !u1_stride_ok ?
                "RAYHIT_U1_STRUCTURE_STRIDE_MISMATCH" :
            !u1_resource_ok ?
                "RAYHIT_U1_RESOURCE_METADATA_MISMATCH" :
                "OTHER_LOCAL_ROOT_DESCRIPTOR_MISSING";

        reshade::log::message(
            exact_ok ? reshade::log::level::info :
                       reshade::log::level::warning,
            "D3DMetal RTX raygen local-root descriptor resolution v55: U1_RAYHIT_RESULT found=%u gpu_handle=0x%llX heap_id=%llu heap_index=%u kind=%s view_dimension=%u stride=%u num_elements=%u first_element=%llu resource_id=%llu resource_dimension=%u resource_width=%llu resource_flags=0x%X expected_kind=uav expected_dimension=buffer expected_stride=24 contract_match=%u.",
            u1_found ? 1u : 0u,
            static_cast<unsigned long long>(u1_gpu_handle),
            static_cast<unsigned long long>(u1_heap.heap_id),
            u1_index,
            v55_descriptor_kind_name(u1.kind),
            u1.view_dimension,
            u1.structure_stride,
            u1.num_elements,
            static_cast<unsigned long long>(u1.first_element),
            static_cast<unsigned long long>(u1.resource_id),
            u1_resource.dimension,
            static_cast<unsigned long long>(u1_resource.width),
            u1_resource.flags,
            u1_resource_ok ? 1u : 0u);

        reshade::log::message(
            exact_ok ? reshade::log::level::info :
                       reshade::log::level::warning,
            "D3DMetal RTX raygen local-root descriptor resolution v55: LOCAL_ROOT_DESCRIPTOR_RESOLUTION_RESULT success=1 srv_resolved=%u/8 cbv_resolved=%u/1 uav_resolved=%u/2 u1_contract_match=%u descriptor_events=%llu descriptor_copy_events=%llu diagnosis=%s commands_modified=0.",
            srv_resolved,
            cbv_resolved,
            uav_resolved,
            u1_resource_ok ? 1u : 0u,
            static_cast<unsigned long long>(
                s_v55_descriptor_events.load(std::memory_order_acquire)),
            static_cast<unsigned long long>(
                s_v55_descriptor_copy_events.load(std::memory_order_acquire)),
            diagnosis);
    }

    void v55_install_descriptor_hooks(ID3D12Device *device)
    {
        if (device == nullptr)
            return;
        std::call_once(
            s_v55_device_hook_once,
            [device]()
            {
                void **const vtable =
                    *reinterpret_cast<void ***>(device);
                s_v55_original_create_descriptor_heap =
                    reinterpret_cast<v55_create_descriptor_heap_fn>(
                        vtable[v55_create_descriptor_heap_slot]);
                s_v55_original_create_cbv =
                    reinterpret_cast<v55_create_cbv_fn>(
                        vtable[v55_create_cbv_slot]);
                s_v55_original_create_srv =
                    reinterpret_cast<v55_create_srv_fn>(
                        vtable[v55_create_srv_slot]);
                s_v55_original_create_uav =
                    reinterpret_cast<v55_create_uav_fn>(
                        vtable[v55_create_uav_slot]);
                s_v55_original_copy_descriptors =
                    reinterpret_cast<v55_copy_descriptors_fn>(
                        vtable[v55_copy_descriptors_slot]);
                s_v55_original_copy_descriptors_simple =
                    reinterpret_cast<v55_copy_descriptors_simple_fn>(
                        vtable[v55_copy_descriptors_simple_slot]);

                DWORD old_protect = 0;
                if (!VirtualProtect(
                        &vtable[v55_create_descriptor_heap_slot],
                        sizeof(void *) *
                            (v55_copy_descriptors_simple_slot -
                             v55_create_descriptor_heap_slot + 1),
                        PAGE_EXECUTE_READWRITE,
                        &old_protect))
                {
                    reshade::log::message(
                        reshade::log::level::warning,
                        "D3DMetal RTX raygen local-root descriptor resolution v55: DEVICE_HOOKS installed=0 error=%lu.",
                        GetLastError());
                    return;
                }

#define V55_INSTALL_DEVICE_SLOT(SLOT, FUNCTION) \
                InterlockedExchangePointer( \
                    reinterpret_cast<PVOID volatile *>( \
                        &vtable[SLOT]), \
                    reinterpret_cast<PVOID>(&FUNCTION))
                V55_INSTALL_DEVICE_SLOT(
                    v55_create_descriptor_heap_slot,
                    v55_trace_create_descriptor_heap);
                V55_INSTALL_DEVICE_SLOT(
                    v55_create_cbv_slot,
                    v55_trace_create_cbv);
                V55_INSTALL_DEVICE_SLOT(
                    v55_create_srv_slot,
                    v55_trace_create_srv);
                V55_INSTALL_DEVICE_SLOT(
                    v55_create_uav_slot,
                    v55_trace_create_uav);
                V55_INSTALL_DEVICE_SLOT(
                    v55_copy_descriptors_slot,
                    v55_trace_copy_descriptors);
                V55_INSTALL_DEVICE_SLOT(
                    v55_copy_descriptors_simple_slot,
                    v55_trace_copy_descriptors_simple);
#undef V55_INSTALL_DEVICE_SLOT

                DWORD ignored = 0;
                VirtualProtect(
                    &vtable[v55_create_descriptor_heap_slot],
                    sizeof(void *) *
                        (v55_copy_descriptors_simple_slot -
                         v55_create_descriptor_heap_slot + 1),
                    old_protect,
                    &ignored);
                FlushInstructionCache(
                    GetCurrentProcess(),
                    &vtable[v55_create_descriptor_heap_slot],
                    sizeof(void *) *
                        (v55_copy_descriptors_simple_slot -
                         v55_create_descriptor_heap_slot + 1));

                const bool verified =
                    vtable[v55_create_descriptor_heap_slot] ==
                        reinterpret_cast<void *>(
                            &v55_trace_create_descriptor_heap) &&
                    vtable[v55_create_cbv_slot] ==
                        reinterpret_cast<void *>(
                            &v55_trace_create_cbv) &&
                    vtable[v55_create_srv_slot] ==
                        reinterpret_cast<void *>(
                            &v55_trace_create_srv) &&
                    vtable[v55_create_uav_slot] ==
                        reinterpret_cast<void *>(
                            &v55_trace_create_uav) &&
                    vtable[v55_copy_descriptors_slot] ==
                        reinterpret_cast<void *>(
                            &v55_trace_copy_descriptors) &&
                    vtable[v55_copy_descriptors_simple_slot] ==
                        reinterpret_cast<void *>(
                            &v55_trace_copy_descriptors_simple);
                s_v55_device_hooks_installed.store(
                    verified, std::memory_order_release);
                reshade::log::message(
                    verified ? reshade::log::level::info :
                               reshade::log::level::warning,
                    "D3DMetal RTX raygen local-root descriptor resolution v55: DEVICE_HOOKS installed=%u heap_slot=%zu cbv_slot=%zu srv_slot=%zu uav_slot=%zu copy_slot=%zu copy_simple_slot=%zu.",
                    verified ? 1u : 0u,
                    v55_create_descriptor_heap_slot,
                    v55_create_cbv_slot,
                    v55_create_srv_slot,
                    v55_create_uav_slot,
                    v55_copy_descriptors_slot,
                    v55_copy_descriptors_simple_slot);
            });
    }

'''

text = text.replace(helper_anchor, helper + "\n" + helper_anchor, 1)

install_anchor = "\t\tv39_install_resource_hooks(device);\n"
text = replace_once(
    text,
    install_anchor,
    install_anchor + "\t\tv55_install_descriptor_hooks(device);\n",
    "V55 device-hook installation")

worker_anchor = '''        log_single_record("RAYGEN", raygen_offset, raygen_bytes);
        log_single_record("MISS", miss_offset, miss_bytes);
        log_single_record("CALLABLE", callable_offset, callable_bytes);
'''
worker_replacement = '''        log_single_record("RAYGEN", raygen_offset, raygen_bytes);
        v55_resolve_raygen_local_root(
            bytes + raygen_offset,
            raygen_bytes);
        log_single_record("MISS", miss_offset, miss_bytes);
        log_single_record("CALLABLE", callable_offset, callable_bytes);
'''
text = replace_once(
    text,
    worker_anchor,
    worker_replacement,
    "V55 raygen-record resolution call")

required_markers = (
    "D3DMetal RTX raygen local-root descriptor resolution v55: ACTIVE",
    "LOCAL_ROOT_HANDLES srv_t0_t7=",
    "TABLE_DESCRIPTOR table=",
    "U1_RAYHIT_RESULT found=",
    "LOCAL_ROOT_DESCRIPTOR_RESOLUTION_RESULT success=",
    "local-root-offsets=srv32-cbv40-uav48",
    "expected_stride=24",
    "commands_modified=0",
    "v55_install_descriptor_hooks(device);",
    "v55_resolve_raygen_local_root(",
)
for marker in required_markers:
    if marker not in text:
        raise RuntimeError(f"V55 generated source is missing marker: {marker}")

if text.count("v55_resolve_raygen_local_root(") != 2:
    raise RuntimeError("V55 expected one definition and one worker call")
if text.count("v55_install_descriptor_hooks(device);") != 1:
    raise RuntimeError("V55 device hook installation count mismatch")
if "\\t" in text:
    raise RuntimeError("V55 generated source contains literal tab escape text")
if text.count("{") != text.count("}"):
    raise RuntimeError(
        f"V55 generated source has unbalanced braces: "
        f"{text.count('{')} vs {text.count('}')}")

SOURCE.write_text(text, encoding="utf-8", newline="\n")

report = Path("v55-patch-report.txt")
report.write_text(
    "\n".join([
        "V55_RAYGEN_LOCAL_ROOT_DESCRIPTOR_RESOLUTION_PATCH_OK",
        "BASELINE=V54_PATTERNED_STEADY_STATE_PIPELINE",
        "LIVE_SHADER_TABLE_READBACK=V39",
        "LOCAL_ROOT_SIGNATURE_BYTES=188",
        "LOCAL_ROOT_SIGNATURE_SHA256=b47efe3fe606db7f01f0e808c3c1dd5b58bc8c67f36078e52f379521bbc1125c",
        "LOCAL_ROOT_PARAMETER_COUNT=3",
        "RAYGEN_RECORD_SIZE=64",
        "SRV_TABLE_RECORD_OFFSET=32",
        "SRV_TABLE_RANGE=t0-t7",
        "CBV_TABLE_RECORD_OFFSET=40",
        "CBV_TABLE_RANGE=b0",
        "UAV_TABLE_RECORD_OFFSET=48",
        "UAV_TABLE_RANGE=u0-u1",
        "RAYHIT_EXPECTED_REGISTER=u1",
        "RAYHIT_EXPECTED_UAV_DIMENSION=BUFFER",
        "RAYHIT_EXPECTED_STRUCTURE_STRIDE=24",
        "DESCRIPTOR_HEAP_TRACKING=ENABLED",
        "CBV_SRV_UAV_CREATION_TRACKING=ENABLED",
        "DESCRIPTOR_COPY_TRACKING=ENABLED",
        "RUNTIME_COMMANDS_MODIFIED=NO",
        "RESULT=PASS",
        "",
    ]),
    encoding="utf-8",
    newline="\n",
)
print(report.read_text(encoding="utf-8"))
