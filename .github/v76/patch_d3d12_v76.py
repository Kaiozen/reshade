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

# V75 must be impossible to reactivate through a stale launchctl environment.
v75_active_old = '''                const bool active = length != 0 && length < sizeof(value) &&
                    (value[0] == '1' || value[0] == 'Y' || value[0] == 'y' ||
                     value[0] == 'T' || value[0] == 't');
'''
v75_active_new = '''                const bool active = false; // V76 owns the mutation path.
'''
replace_once(v75_active_old, v75_active_new, 'V75 runtime disable')

state_old = '''    static std::atomic<uint64_t> s_v75_last_logged_pass = 0;\n'''
state_new = state_old + '''    static std::once_flag s_v76_active_once;
    static std::atomic<bool> s_v76_active = false;
    static std::atomic<bool> s_v76_capture_claimed = false;
    static std::atomic<bool> s_v76_capture_recorded = false;
    static std::atomic<bool> s_v76_queue_submitted = false;
    static std::atomic<bool> s_v76_readback_complete = false;
    static std::atomic<bool> s_v76_readback_match = false;
    static std::atomic<bool> s_v76_readback_failed = false;
    static std::atomic<uint64_t> s_v76_target_signature_count = 0;
    static std::atomic<uint64_t> s_v76_canary_clear_pass_count = 0;
    static std::atomic<uint64_t> s_v76_capture_failure_count = 0;
    static std::atomic<uint64_t> s_v76_clear_failure_count = 0;
    static std::atomic<uint64_t> s_v76_last_logged_pass = 0;
    static std::mutex s_v76_capture_mutex;
    static ID3D12Resource *s_v76_readback_resource = nullptr;
    static ID3D12Fence *s_v76_capture_fence = nullptr;
    static HANDLE s_v76_capture_event = nullptr;
    static void *s_v76_capture_command_list_identity = nullptr;
    static constexpr UINT64 v76_readback_bytes = 4096;
    static constexpr UINT64 v76_sample_stride = 512;
    static constexpr UINT v76_row_pitch = 256;
'''
replace_once(state_old, state_new, 'V76 state')

proto_old = '''    bool v75_clear_first_consumer_outputs_after_dispatch(
        ID3D12GraphicsCommandList *command_list,
        UINT max_command_count);
'''
proto_new = proto_old + '''    bool v76_is_active();
    bool v76_apply_canary_after_dispatch(
        ID3D12GraphicsCommandList *command_list,
        UINT max_command_count);
    void v76_on_execute_command_lists(
        ID3D12CommandQueue *queue,
        UINT count,
        ID3D12CommandList *const *command_lists);
'''
replace_once(proto_old, proto_new, 'V76 prototypes')

queue_decl_old = '''\tvoid v64_on_execute_command_lists(
\t\tID3D12CommandQueue *queue,
\t\tUINT count,
\t\tID3D12CommandList *const *command_lists);
'''
queue_decl_new = queue_decl_old + '''
    void v76_on_execute_command_lists(
        ID3D12CommandQueue *queue,
        UINT count,
        ID3D12CommandList *const *command_lists);
'''
replace_once(queue_decl_old, queue_decl_new, 'V76 queue declaration')

queue_call_old = '''\t\tv64_on_execute_command_lists(queue, count, command_lists);
'''
queue_call_new = queue_call_old + '''        v76_on_execute_command_lists(queue, count, command_lists);
'''
replace_once(queue_call_old, queue_call_new, 'V76 queue callback')

active_old = '''                (void)v75_is_active();
\t\t\t\treshade::log::message(
\t\t\t\t\treshade::log::level::info,
                    "D3DMetal RTX first ray-hit consumer output knockout v75: ACTIVE runtime-gate=KAIOZEN_V75_ACTIVE exact-consumer-signature=u1-root0-offset17-srv outputs=root0-offsets35,36 post-execute-indirect-clear=enabled output-pair-clear=enabled v74-default-selector=disabled uav-barriers-per-resource=2 visual-timer-requires-clear=1 commands_modified=1.");
'''
active_new = active_old + '''                (void)v76_is_active();
\t\t\t\treshade::log::message(
\t\t\t\t\treshade::log::level::info,
                    "D3DMetal RTX canary mutation verification v76: ACTIVE runtime-gate=KAIOZEN_V76_ACTIVE v75-runtime-disabled=1 exact-consumer-signature=u1-root0-offset17-srv outputs=root0-offsets35,36 patterns=magenta|cyan persistent-canary-clears=enabled one-shot-before-after-readback=enabled sample_points=64,64|1380,888 samples=8 readback_bytes=4096 row_pitch=256 placement_stride=512 queue-fence=enabled visual-timer-requires-readback-match=1 commands_modified=1.");
'''
replace_once(active_old, active_new, 'V76 active marker')

execute_old = '''            v75_clear_first_consumer_outputs_after_dispatch(
                command_list,
                max_command_count);
'''
execute_new = execute_old + '''            v76_apply_canary_after_dispatch(
                command_list,
                max_command_count);
'''
replace_once(execute_old, execute_new, 'V76 execute-indirect mutation')

impl_anchor = '''    void STDMETHODCALLTYPE v66_trace_dispatch(
'''
impl = r'''    bool v76_is_active()
    {
        std::call_once(
            s_v76_active_once,
            []()
            {
                char value[16] = {};
                const DWORD length = GetEnvironmentVariableA(
                    "KAIOZEN_V76_ACTIVE", value,
                    static_cast<DWORD>(sizeof(value)));
                const bool active = length != 0 && length < sizeof(value) &&
                    (value[0] == '1' || value[0] == 'Y' || value[0] == 'y' ||
                     value[0] == 'T' || value[0] == 't');
                s_v76_active.store(active, std::memory_order_release);
                reshade::log::message(
                    reshade::log::level::info,
                    "D3DMetal RTX canary mutation verification v76: RUNTIME_GATE active=%u environment=%s selection_timing=dll-startup v75-runtime-disabled=1 commands_modified=%u.",
                    active ? 1u : 0u,
                    length != 0 ? value : "unset",
                    active ? 1u : 0u);
            });
        return s_v76_active.load(std::memory_order_acquire);
    }

    bool v76_clear_with_pattern(
        ID3D12GraphicsCommandList *command_list,
        const v71_resolved_uav &resolved,
        const FLOAT (&values)[4])
    {
        if (command_list == nullptr || resolved.gpu.ptr == 0 ||
            resolved.cpu.ptr == 0 || resolved.resource.resource == nullptr)
            return false;

        D3D12_RESOURCE_BARRIER barrier = {};
        barrier.Type = D3D12_RESOURCE_BARRIER_TYPE_UAV;
        barrier.Flags = D3D12_RESOURCE_BARRIER_FLAG_NONE;
        barrier.UAV.pResource = resolved.resource.resource;
        command_list->ResourceBarrier(1, &barrier);
        command_list->ClearUnorderedAccessViewFloat(
            resolved.gpu,
            resolved.cpu,
            resolved.resource.resource,
            values,
            0,
            nullptr);
        command_list->ResourceBarrier(1, &barrier);
        return true;
    }

    void v76_copy_one_pixel(
        ID3D12GraphicsCommandList *command_list,
        ID3D12Resource *readback,
        ID3D12Resource *source_resource,
        UINT64 destination_offset,
        UINT x,
        UINT y)
    {
        D3D12_TEXTURE_COPY_LOCATION destination = {};
        destination.pResource = readback;
        destination.Type = D3D12_TEXTURE_COPY_TYPE_PLACED_FOOTPRINT;
        destination.PlacedFootprint.Offset = destination_offset;
        destination.PlacedFootprint.Footprint.Format =
            DXGI_FORMAT_R16G16B16A16_FLOAT;
        destination.PlacedFootprint.Footprint.Width = 1;
        destination.PlacedFootprint.Footprint.Height = 1;
        destination.PlacedFootprint.Footprint.Depth = 1;
        destination.PlacedFootprint.Footprint.RowPitch = v76_row_pitch;

        D3D12_TEXTURE_COPY_LOCATION source = {};
        source.pResource = source_resource;
        source.Type = D3D12_TEXTURE_COPY_TYPE_SUBRESOURCE_INDEX;
        source.SubresourceIndex = 0;

        D3D12_BOX box = {};
        box.left = x;
        box.top = y;
        box.front = 0;
        box.right = x + 1;
        box.bottom = y + 1;
        box.back = 1;
        command_list->CopyTextureRegion(
            &destination, 0, 0, 0, &source, &box);
    }

    bool v76_record_before_after_capture(
        ID3D12GraphicsCommandList *command_list,
        const v71_resolved_uav &output35,
        const v71_resolved_uav &output36,
        void *pipeline_state,
        uint64_t u1_resource_id)
    {
        if (command_list == nullptr || output35.resource.resource == nullptr ||
            output36.resource.resource == nullptr)
            return false;

        const D3D12_RESOURCE_DESC desc35 = output35.resource.resource->GetDesc();
        const D3D12_RESOURCE_DESC desc36 = output36.resource.resource->GetDesc();
        const bool descriptions_valid =
            desc35.Dimension == D3D12_RESOURCE_DIMENSION_TEXTURE2D &&
            desc36.Dimension == D3D12_RESOURCE_DIMENSION_TEXTURE2D &&
            desc35.Width == 2760 && desc35.Height == 1776 &&
            desc36.Width == 2760 && desc36.Height == 1776 &&
            desc35.SampleDesc.Count == 1 && desc36.SampleDesc.Count == 1 &&
            v74_resolved_format(output35) == 10 &&
            v74_resolved_format(output36) == 10;
        if (!descriptions_valid)
        {
            const uint64_t failure =
                s_v76_capture_failure_count.fetch_add(1, std::memory_order_acq_rel) + 1;
            reshade::log::message(
                reshade::log::level::warning,
                "D3DMetal RTX canary mutation verification v76: CANARY_CAPTURE_FAILURE failure_index=%llu stage=resource-description format35=%u format36=%u dimension35=%u dimension36=%u width35=%llu height35=%u width36=%llu height36=%u commands_modified=0.",
                static_cast<unsigned long long>(failure),
                v74_resolved_format(output35), v74_resolved_format(output36),
                static_cast<unsigned int>(desc35.Dimension),
                static_cast<unsigned int>(desc36.Dimension),
                static_cast<unsigned long long>(desc35.Width), desc35.Height,
                static_cast<unsigned long long>(desc36.Width), desc36.Height);
            return false;
        }

        ID3D12Device *device = nullptr;
        HRESULT hr = output35.resource.resource->GetDevice(
            __uuidof(ID3D12Device), reinterpret_cast<void **>(&device));
        if (FAILED(hr) || device == nullptr)
        {
            const uint64_t failure =
                s_v76_capture_failure_count.fetch_add(1, std::memory_order_acq_rel) + 1;
            reshade::log::message(
                reshade::log::level::warning,
                "D3DMetal RTX canary mutation verification v76: CANARY_CAPTURE_FAILURE failure_index=%llu stage=get-device hr=%s raw=0x%08X commands_modified=0.",
                static_cast<unsigned long long>(failure),
                reshade::log::hr_to_string(hr).c_str(), static_cast<uint32_t>(hr));
            return false;
        }

        D3D12_HEAP_PROPERTIES heap_properties = {};
        heap_properties.Type = D3D12_HEAP_TYPE_READBACK;
        heap_properties.CPUPageProperty = D3D12_CPU_PAGE_PROPERTY_UNKNOWN;
        heap_properties.MemoryPoolPreference = D3D12_MEMORY_POOL_UNKNOWN;
        heap_properties.CreationNodeMask = 1;
        heap_properties.VisibleNodeMask = 1;
        D3D12_RESOURCE_DESC readback_desc = {};
        readback_desc.Dimension = D3D12_RESOURCE_DIMENSION_BUFFER;
        readback_desc.Width = v76_readback_bytes;
        readback_desc.Height = 1;
        readback_desc.DepthOrArraySize = 1;
        readback_desc.MipLevels = 1;
        readback_desc.Format = DXGI_FORMAT_UNKNOWN;
        readback_desc.SampleDesc.Count = 1;
        readback_desc.Layout = D3D12_TEXTURE_LAYOUT_ROW_MAJOR;
        readback_desc.Flags = D3D12_RESOURCE_FLAG_NONE;

        ID3D12Resource *readback = nullptr;
        hr = device->CreateCommittedResource(
            &heap_properties, D3D12_HEAP_FLAG_NONE, &readback_desc,
            D3D12_RESOURCE_STATE_COPY_DEST, nullptr,
            __uuidof(ID3D12Resource), reinterpret_cast<void **>(&readback));
        ID3D12Fence *fence = nullptr;
        const HRESULT fence_hr = device->CreateFence(
            0, D3D12_FENCE_FLAG_NONE, __uuidof(ID3D12Fence),
            reinterpret_cast<void **>(&fence));
        HANDLE event_handle = CreateEventW(nullptr, FALSE, FALSE, nullptr);
        device->Release();
        if (FAILED(hr) || readback == nullptr || FAILED(fence_hr) ||
            fence == nullptr || event_handle == nullptr)
        {
            const uint64_t failure =
                s_v76_capture_failure_count.fetch_add(1, std::memory_order_acq_rel) + 1;
            reshade::log::message(
                reshade::log::level::warning,
                "D3DMetal RTX canary mutation verification v76: CANARY_CAPTURE_FAILURE failure_index=%llu stage=create-readback-or-fence readback_hr=%s fence_hr=%s event=%p commands_modified=0.",
                static_cast<unsigned long long>(failure),
                reshade::log::hr_to_string(hr).c_str(),
                reshade::log::hr_to_string(fence_hr).c_str(),
                event_handle);
            if (readback != nullptr) readback->Release();
            if (fence != nullptr) fence->Release();
            if (event_handle != nullptr) CloseHandle(event_handle);
            return false;
        }

        ID3D12Resource *resources[2] = {
            output35.resource.resource,
            output36.resource.resource,
        };
        D3D12_RESOURCE_BARRIER order[2] = {};
        D3D12_RESOURCE_BARRIER to_copy[2] = {};
        D3D12_RESOURCE_BARRIER to_uav[2] = {};
        for (UINT index = 0; index < 2; ++index)
        {
            order[index].Type = D3D12_RESOURCE_BARRIER_TYPE_UAV;
            order[index].UAV.pResource = resources[index];
            to_copy[index].Type = D3D12_RESOURCE_BARRIER_TYPE_TRANSITION;
            to_copy[index].Transition.pResource = resources[index];
            to_copy[index].Transition.Subresource = 0;
            to_copy[index].Transition.StateBefore = D3D12_RESOURCE_STATE_UNORDERED_ACCESS;
            to_copy[index].Transition.StateAfter = D3D12_RESOURCE_STATE_COPY_SOURCE;
            to_uav[index] = to_copy[index];
            to_uav[index].Transition.StateBefore = D3D12_RESOURCE_STATE_COPY_SOURCE;
            to_uav[index].Transition.StateAfter = D3D12_RESOURCE_STATE_UNORDERED_ACCESS;
        }

        // Before samples: two pixels from each output.
        command_list->ResourceBarrier(2, order);
        command_list->ResourceBarrier(2, to_copy);
        v76_copy_one_pixel(command_list, readback, resources[0], 0 * v76_sample_stride, 64, 64);
        v76_copy_one_pixel(command_list, readback, resources[0], 1 * v76_sample_stride, 1380, 888);
        v76_copy_one_pixel(command_list, readback, resources[1], 2 * v76_sample_stride, 64, 64);
        v76_copy_one_pixel(command_list, readback, resources[1], 3 * v76_sample_stride, 1380, 888);
        command_list->ResourceBarrier(2, to_uav);

        const FLOAT pattern35[4] = { 1.0f, 0.0f, 1.0f, 1.0f };
        const FLOAT pattern36[4] = { 0.0f, 1.0f, 1.0f, 1.0f };
        if (!v76_clear_with_pattern(command_list, output35, pattern35) ||
            !v76_clear_with_pattern(command_list, output36, pattern36))
        {
            const uint64_t failure =
                s_v76_clear_failure_count.fetch_add(1, std::memory_order_acq_rel) + 1;
            reshade::log::message(
                reshade::log::level::warning,
                "D3DMetal RTX canary mutation verification v76: CANARY_CLEAR_FAILURE failure_index=%llu stage=first-capture commands_modified=1.",
                static_cast<unsigned long long>(failure));
            readback->Release();
            fence->Release();
            CloseHandle(event_handle);
            return false;
        }

        // After samples: same two pixels from each output, immediately after clear.
        command_list->ResourceBarrier(2, to_copy);
        v76_copy_one_pixel(command_list, readback, resources[0], 4 * v76_sample_stride, 64, 64);
        v76_copy_one_pixel(command_list, readback, resources[0], 5 * v76_sample_stride, 1380, 888);
        v76_copy_one_pixel(command_list, readback, resources[1], 6 * v76_sample_stride, 64, 64);
        v76_copy_one_pixel(command_list, readback, resources[1], 7 * v76_sample_stride, 1380, 888);
        command_list->ResourceBarrier(2, to_uav);
        command_list->ResourceBarrier(2, order);

        void *const identity = v33_identity_pointer(
            reinterpret_cast<IUnknown *>(command_list));
        if (identity == nullptr)
        {
            const uint64_t failure =
                s_v76_capture_failure_count.fetch_add(1, std::memory_order_acq_rel) + 1;
            reshade::log::message(
                reshade::log::level::warning,
                "D3DMetal RTX canary mutation verification v76: CANARY_CAPTURE_FAILURE failure_index=%llu stage=command-list-identity commands_modified=1.",
                static_cast<unsigned long long>(failure));
            readback->Release();
            fence->Release();
            CloseHandle(event_handle);
            return false;
        }
        {
            std::lock_guard<std::mutex> lock(s_v76_capture_mutex);
            s_v76_readback_resource = readback;
            s_v76_capture_fence = fence;
            s_v76_capture_event = event_handle;
            s_v76_capture_command_list_identity = identity;
        }
        s_v76_capture_recorded.store(true, std::memory_order_release);
        reshade::log::message(
            reshade::log::level::info,
            "D3DMetal RTX canary mutation verification v76: CANARY_CAPTURE_RECORDED pipeline_state=%p u1_resource_id=%llu output35_resource_id=%llu output36_resource_id=%llu pattern35=1,0,1,1 pattern36=0,1,1,1 expected35_half_hex=003C0000003C003C expected36_half_hex=0000003C003C003C sample_points=64,64|1380,888 samples=8 before_samples=4 after_samples=4 readback_bytes=4096 row_pitch=256 placement_stride=512 copy_calls=8 transitions=uav-to-copy-source-to-uav command_list=%p identity=%p commands_modified=1.",
            pipeline_state,
            static_cast<unsigned long long>(u1_resource_id),
            static_cast<unsigned long long>(output35.resource.resource_id),
            static_cast<unsigned long long>(output36.resource.resource_id),
            command_list,
            identity);
        return true;
    }

    DWORD WINAPI v76_readback_worker(LPVOID)
    {
        ID3D12Resource *readback = nullptr;
        ID3D12Fence *fence = nullptr;
        HANDLE event_handle = nullptr;
        {
            std::lock_guard<std::mutex> lock(s_v76_capture_mutex);
            readback = s_v76_readback_resource;
            fence = s_v76_capture_fence;
            event_handle = s_v76_capture_event;
            s_v76_readback_resource = nullptr;
            s_v76_capture_fence = nullptr;
            s_v76_capture_event = nullptr;
        }
        if (readback == nullptr || fence == nullptr || event_handle == nullptr)
        {
            s_v76_readback_failed.store(true, std::memory_order_release);
            reshade::log::message(
                reshade::log::level::warning,
                "D3DMetal RTX canary mutation verification v76: CANARY_READBACK_RESULT success=0 decisive_match=0 reason=missing-capture-objects.");
            if (readback != nullptr) readback->Release();
            if (fence != nullptr) fence->Release();
            if (event_handle != nullptr) CloseHandle(event_handle);
            return 0;
        }

        const DWORD wait_result = WaitForSingleObject(event_handle, 15000);
        if (wait_result != WAIT_OBJECT_0)
        {
            s_v76_readback_failed.store(true, std::memory_order_release);
            reshade::log::message(
                reshade::log::level::warning,
                "D3DMetal RTX canary mutation verification v76: CANARY_READBACK_RESULT success=0 decisive_match=0 reason=fence-wait wait_result=%lu completed=%llu.",
                wait_result,
                static_cast<unsigned long long>(fence->GetCompletedValue()));
            readback->Release();
            fence->Release();
            CloseHandle(event_handle);
            return 0;
        }

        void *mapped = nullptr;
        const D3D12_RANGE read_range = {
            0, static_cast<SIZE_T>(v76_readback_bytes)
        };
        const HRESULT map_hr = readback->Map(0, &read_range, &mapped);
        if (FAILED(map_hr) || mapped == nullptr)
        {
            s_v76_readback_failed.store(true, std::memory_order_release);
            reshade::log::message(
                reshade::log::level::warning,
                "D3DMetal RTX canary mutation verification v76: CANARY_READBACK_RESULT success=0 decisive_match=0 reason=map hr=%s raw=0x%08X.",
                reshade::log::hr_to_string(map_hr).c_str(),
                static_cast<uint32_t>(map_hr));
            readback->Release();
            fence->Release();
            CloseHandle(event_handle);
            return 0;
        }

        const unsigned char *bytes = static_cast<const unsigned char *>(mapped);
        const unsigned char expected35[8] = {
            0x00, 0x3C, 0x00, 0x00, 0x00, 0x3C, 0x00, 0x3C
        };
        const unsigned char expected36[8] = {
            0x00, 0x00, 0x00, 0x3C, 0x00, 0x3C, 0x00, 0x3C
        };
        const unsigned char *before35a = bytes + 0 * v76_sample_stride;
        const unsigned char *before35b = bytes + 1 * v76_sample_stride;
        const unsigned char *before36a = bytes + 2 * v76_sample_stride;
        const unsigned char *before36b = bytes + 3 * v76_sample_stride;
        const unsigned char *after35a = bytes + 4 * v76_sample_stride;
        const unsigned char *after35b = bytes + 5 * v76_sample_stride;
        const unsigned char *after36a = bytes + 6 * v76_sample_stride;
        const unsigned char *after36b = bytes + 7 * v76_sample_stride;

        const bool match35 =
            memcmp(after35a, expected35, sizeof(expected35)) == 0 &&
            memcmp(after35b, expected35, sizeof(expected35)) == 0;
        const bool match36 =
            memcmp(after36a, expected36, sizeof(expected36)) == 0 &&
            memcmp(after36b, expected36, sizeof(expected36)) == 0;
        const bool changed35 =
            memcmp(before35a, expected35, sizeof(expected35)) != 0 ||
            memcmp(before35b, expected35, sizeof(expected35)) != 0;
        const bool changed36 =
            memcmp(before36a, expected36, sizeof(expected36)) != 0 ||
            memcmp(before36b, expected36, sizeof(expected36)) != 0;
        const bool decisive_match = match35 && match36 && changed35 && changed36;

        char before35a_hex[17] = {};
        char before35b_hex[17] = {};
        char before36a_hex[17] = {};
        char before36b_hex[17] = {};
        char after35a_hex[17] = {};
        char after35b_hex[17] = {};
        char after36a_hex[17] = {};
        char after36b_hex[17] = {};
        v39_bytes_to_hex(before35a, 8, before35a_hex, sizeof(before35a_hex));
        v39_bytes_to_hex(before35b, 8, before35b_hex, sizeof(before35b_hex));
        v39_bytes_to_hex(before36a, 8, before36a_hex, sizeof(before36a_hex));
        v39_bytes_to_hex(before36b, 8, before36b_hex, sizeof(before36b_hex));
        v39_bytes_to_hex(after35a, 8, after35a_hex, sizeof(after35a_hex));
        v39_bytes_to_hex(after35b, 8, after35b_hex, sizeof(after35b_hex));
        v39_bytes_to_hex(after36a, 8, after36a_hex, sizeof(after36a_hex));
        v39_bytes_to_hex(after36b, 8, after36b_hex, sizeof(after36b_hex));

        const D3D12_RANGE written_range = { 0, 0 };
        readback->Unmap(0, &written_range);
        s_v76_readback_complete.store(true, std::memory_order_release);
        s_v76_readback_match.store(decisive_match, std::memory_order_release);
        if (!decisive_match)
            s_v76_readback_failed.store(true, std::memory_order_release);
        reshade::log::message(
            decisive_match ? reshade::log::level::info : reshade::log::level::warning,
            "D3DMetal RTX canary mutation verification v76: CANARY_READBACK_RESULT success=1 decisive_match=%u match35=%u match36=%u changed35=%u changed36=%u expected35=003C0000003C003C expected36=0000003C003C003C before35_p0=%s before35_p1=%s before36_p0=%s before36_p1=%s after35_p0=%s after35_p1=%s after36_p0=%s after36_p1=%s sample_points=64,64|1380,888 samples=8 readback_bytes=4096 commands_modified=1.",
            decisive_match ? 1u : 0u,
            match35 ? 1u : 0u,
            match36 ? 1u : 0u,
            changed35 ? 1u : 0u,
            changed36 ? 1u : 0u,
            before35a_hex, before35b_hex,
            before36a_hex, before36b_hex,
            after35a_hex, after35b_hex,
            after36a_hex, after36b_hex);

        readback->Release();
        fence->Release();
        CloseHandle(event_handle);
        return 0;
    }

    void v76_on_execute_command_lists(
        ID3D12CommandQueue *queue,
        UINT count,
        ID3D12CommandList *const *command_lists)
    {
        if (!v76_is_active() || queue == nullptr || command_lists == nullptr ||
            !s_v76_capture_recorded.load(std::memory_order_acquire))
            return;

        void *identity = nullptr;
        ID3D12Fence *fence = nullptr;
        HANDLE event_handle = nullptr;
        {
            std::lock_guard<std::mutex> lock(s_v76_capture_mutex);
            identity = s_v76_capture_command_list_identity;
            fence = s_v76_capture_fence;
            event_handle = s_v76_capture_event;
        }
        if (identity == nullptr || fence == nullptr || event_handle == nullptr)
            return;

        bool contains = false;
        for (UINT index = 0; index < count; ++index)
        {
            ID3D12CommandList *list = nullptr;
            if (!safe_copy_from_process(command_lists + index, &list, sizeof(list)) ||
                list == nullptr)
                continue;
            if (v33_identity_pointer(reinterpret_cast<IUnknown *>(list)) == identity)
            {
                contains = true;
                break;
            }
        }
        bool expected = false;
        if (!contains || !s_v76_queue_submitted.compare_exchange_strong(
                expected, true, std::memory_order_acq_rel))
            return;

        const HRESULT signal_hr = queue->Signal(fence, 1);
        const HRESULT event_hr = SUCCEEDED(signal_hr) ?
            fence->SetEventOnCompletion(1, event_handle) : E_FAIL;
        reshade::log::message(
            SUCCEEDED(signal_hr) && SUCCEEDED(event_hr) ?
                reshade::log::level::info : reshade::log::level::warning,
            "D3DMetal RTX canary mutation verification v76: CANARY_QUEUE_SUBMITTED success=%u count=%u signal_hr=%s signal_raw=0x%08X event_hr=%s event_raw=0x%08X queue_fence=1.",
            SUCCEEDED(signal_hr) && SUCCEEDED(event_hr) ? 1u : 0u,
            count,
            reshade::log::hr_to_string(signal_hr).c_str(),
            static_cast<uint32_t>(signal_hr),
            reshade::log::hr_to_string(event_hr).c_str(),
            static_cast<uint32_t>(event_hr));
        if (SUCCEEDED(signal_hr) && SUCCEEDED(event_hr))
        {
            HANDLE thread_handle = CreateThread(
                nullptr, 0, &v76_readback_worker, nullptr, 0, nullptr);
            if (thread_handle != nullptr)
                CloseHandle(thread_handle);
            else
            {
                s_v76_readback_failed.store(true, std::memory_order_release);
                reshade::log::message(
                    reshade::log::level::warning,
                    "D3DMetal RTX canary mutation verification v76: CANARY_READBACK_RESULT success=0 decisive_match=0 reason=create-worker-thread.");
            }
        }
        else
        {
            s_v76_readback_failed.store(true, std::memory_order_release);
        }
    }

    bool v76_apply_canary_after_dispatch(
        ID3D12GraphicsCommandList *command_list,
        UINT max_command_count)
    {
        if (!v76_is_active() || command_list == nullptr || max_command_count == 0 ||
            !s_v62_u1_target_ready.load(std::memory_order_acquire) ||
            !s_v66_world_consumer_found.load(std::memory_order_acquire))
            return false;

        v66_command_binding_state state = {};
        if (!v74_get_binding_state(command_list, state))
            return false;

        ID3D12Resource *u1_resource = nullptr;
        {
            std::lock_guard<std::mutex> lock(s_v62_capture_mutex);
            u1_resource = s_v62_u1_resource;
        }
        if (u1_resource == nullptr)
            return false;

        v71_resolved_uav u1_srv = {};
        v71_resolved_uav output35 = {};
        v71_resolved_uav output36 = {};
        const bool signature =
            v74_resolve_compute_table_descriptor(state, 0, 17, 2, u1_srv) &&
            v74_resolve_compute_table_descriptor(state, 0, 35, 3, output35) &&
            v74_resolve_compute_table_descriptor(state, 0, 36, 3, output36) &&
            v75_same_resource_info(u1_srv, u1_resource) &&
            v74_resolved_format(output35) == 10 &&
            v74_resolved_format(output36) == 10 &&
            output35.resource.dimension == 3 &&
            output36.resource.dimension == 3 &&
            output35.resource.width == 2760 && output35.resource.height == 1776 &&
            output36.resource.width == 2760 && output36.resource.height == 1776 &&
            !v74_same_resource(output35, output36);
        if (!signature)
            return false;

        const uint64_t target_index =
            s_v76_target_signature_count.fetch_add(1, std::memory_order_acq_rel) + 1;
        if (target_index == 1)
        {
            reshade::log::message(
                reshade::log::level::info,
                "D3DMetal RTX canary mutation verification v76: FIRST_CONSUMER_SIGNATURE_MATCH target_index=1 pipeline_state=%p u1_resource_id=%llu output35_resource_id=%llu output36_resource_id=%llu output_format=10 dimensions=2760x1776 timing=after-execute-indirect-compute v75-runtime-disabled=1 commands_modified=0.",
                state.pipeline_state,
                static_cast<unsigned long long>(u1_srv.resource.resource_id),
                static_cast<unsigned long long>(output35.resource.resource_id),
                static_cast<unsigned long long>(output36.resource.resource_id));
        }

        bool applied = false;
        bool expected_capture = false;
        if (s_v76_capture_claimed.compare_exchange_strong(
                expected_capture, true, std::memory_order_acq_rel))
        {
            applied = v76_record_before_after_capture(
                command_list, output35, output36,
                state.pipeline_state, u1_srv.resource.resource_id);
            if (!applied)
                s_v76_capture_claimed.store(false, std::memory_order_release);
        }
        else if (!s_v76_readback_failed.load(std::memory_order_acquire))
        {
            const FLOAT pattern35[4] = { 1.0f, 0.0f, 1.0f, 1.0f };
            const FLOAT pattern36[4] = { 0.0f, 1.0f, 1.0f, 1.0f };
            applied =
                v76_clear_with_pattern(command_list, output35, pattern35) &&
                v76_clear_with_pattern(command_list, output36, pattern36);
        }

        if (!applied)
        {
            const uint64_t failure =
                s_v76_clear_failure_count.fetch_add(1, std::memory_order_acq_rel) + 1;
            reshade::log::message(
                reshade::log::level::warning,
                "D3DMetal RTX canary mutation verification v76: CANARY_CLEAR_FAILURE failure_index=%llu stage=apply-or-capture output35_resource_id=%llu output36_resource_id=%llu commands_modified=1.",
                static_cast<unsigned long long>(failure),
                static_cast<unsigned long long>(output35.resource.resource_id),
                static_cast<unsigned long long>(output36.resource.resource_id));
            return false;
        }

        const uint64_t pass_index =
            s_v76_canary_clear_pass_count.fetch_add(1, std::memory_order_acq_rel) + 1;
        const uint64_t last = s_v76_last_logged_pass.load(std::memory_order_acquire);
        if (pass_index == 1 || pass_index == 8 || pass_index == 64 ||
            pass_index >= last + 300)
        {
            s_v76_last_logged_pass.store(pass_index, std::memory_order_release);
            reshade::log::message(
                reshade::log::level::info,
                "D3DMetal RTX canary mutation verification v76: CANARY_CLEAR_PASS pass_index=%llu pipeline_state=%p u1_resource_id=%llu output35_resource_id=%llu output36_resource_id=%llu pattern35=1,0,1,1 pattern36=0,1,1,1 timing=after-execute-indirect-compute persistent_until-test-end=1 uav_barriers=4 commands_modified=1.",
                static_cast<unsigned long long>(pass_index),
                state.pipeline_state,
                static_cast<unsigned long long>(u1_srv.resource.resource_id),
                static_cast<unsigned long long>(output35.resource.resource_id),
                static_cast<unsigned long long>(output36.resource.resource_id));
        }
        return true;
    }

'''
replace_once(impl_anchor, impl + impl_anchor, 'V76 implementation')

source.write_text(text, encoding='utf-8')
Path('v76-patch-report.txt').write_text(
    '\n'.join([
        'V76_CANARY_MUTATION_READBACK_PATCH_OK',
        'V75_RUNTIME_DISABLED=YES',
        'RUNTIME_GATE=KAIOZEN_V76_ACTIVE',
        'TARGET=FIRST_U1_CONSUMER_OUTPUT_PAIR',
        'OUTPUTS=ROOT0_OFFSETS35_AND36',
        'PATTERN35=1,0,1,1',
        'PATTERN36=0,1,1,1',
        'SAMPLE_POINTS=64,64|1380,888',
        'BEFORE_SAMPLES=4',
        'AFTER_SAMPLES=4',
        'COPY_TEXTURE_REGION_CALLS_RUNTIME=8',
        'READBACK_BYTES=4096',
        'ROW_PITCH=256',
        'PLACEMENT_STRIDE=512',
        'QUEUE_FENCE=ENABLED',
        'PERSISTENT_CANARY_CLEAR=ENABLED',
        'VISUAL_TIMER_REQUIRES_DECISIVE_READBACK_MATCH=YES',
        'COMMANDS_MODIFIED=YES',
    ]) + '\n',
    encoding='ascii')
print('V76_CANARY_MUTATION_READBACK_PATCH_OK')
