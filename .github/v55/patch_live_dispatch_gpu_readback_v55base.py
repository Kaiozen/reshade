from pathlib import Path

SOURCE = Path("source/d3d12/d3d12.cpp")
if not SOURCE.is_file():
    raise RuntimeError(f"Missing source file: {SOURCE}")

text = SOURCE.read_text(encoding="utf-8-sig")
if "D3DMetal RTX ray-hit pattern inheritance census v54:" not in text:
    raise RuntimeError("V54 must be applied before the V55 live-dispatch readback base")
if "D3DMetal RTX live dispatch readback v38:" in text:
    raise RuntimeError("V38 is already present")


def replace_once(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 occurrence, found {count}")
    return source.replace(old, new, 1)


v34_anchor = "\tusing v34_create_command_signature_fn = HRESULT (STDMETHODCALLTYPE *)(\n"
if text.count(v34_anchor) != 1:
    raise RuntimeError(
        f"V38 V34 helper anchor mismatch: {text.count(v34_anchor)}")

helper = r'''
\tusing v38_create_command_queue_fn = HRESULT (STDMETHODCALLTYPE *)(
\t\tID3D12Device *,
\t\tconst D3D12_COMMAND_QUEUE_DESC *,
\t\tREFIID,
\t\tvoid **);

\tusing v38_execute_command_lists_fn = void (STDMETHODCALLTYPE *)(
\t\tID3D12CommandQueue *,
\t\tUINT,
\t\tID3D12CommandList *const *);

\tconstexpr size_t v38_create_command_queue_slot = 8;
\tconstexpr size_t v38_execute_command_lists_slot = 10;
\tconstexpr UINT64 v38_dispatch_record_bytes = 104;

\tstatic v38_create_command_queue_fn
\t\ts_v38_original_create_command_queue = nullptr;
\tstatic v38_execute_command_lists_fn
\t\ts_v38_original_execute_command_lists = nullptr;

\tstatic std::once_flag s_v38_create_queue_hook_once;
\tstatic std::once_flag s_v38_execute_lists_hook_once;
\tstatic std::atomic<bool> s_v38_create_queue_hook_installed = false;
\tstatic std::atomic<bool> s_v38_execute_lists_hook_installed = false;
\tstatic std::atomic<bool> s_v38_capture_claimed = false;
\tstatic std::atomic<bool> s_v38_copy_recorded = false;
\tstatic std::atomic<bool> s_v38_queue_signaled = false;
\tstatic std::atomic<bool> s_v38_readback_complete = false;
\tstatic std::atomic<bool> s_v38_capture_failed = false;
\tstatic std::mutex s_v38_capture_mutex;
\tstatic ID3D12Resource *s_v38_readback_resource = nullptr;
\tstatic ID3D12Fence *s_v38_capture_fence = nullptr;
\tstatic HANDLE s_v38_capture_event = nullptr;
\tstatic void *s_v38_capture_command_list_identity = nullptr;
\tstatic D3D12_GPU_VIRTUAL_ADDRESS s_v38_argument_gpu_va = 0;
\tstatic UINT64 s_v38_argument_offset = 0;
\tstatic uint64_t s_v38_state_call = 0;
\tstatic uint64_t s_v38_ray_index = 0;

\tvoid v38_bytes_to_hex(
\t\tconst unsigned char *bytes,
\t\tsize_t count,
\t\tchar *hex,
\t\tsize_t hex_size)
\t{
\t\tif (hex == nullptr || hex_size == 0)
\t\t\treturn;
\t\thex[0] = '\\0';
\t\tif (bytes == nullptr || hex_size < count * 2 + 1)
\t\t\treturn;

\t\tstatic const char digits[] = "0123456789abcdef";
\t\tfor (size_t index = 0; index < count; ++index)
\t\t{
\t\t\thex[index * 2] = digits[bytes[index] >> 4];
\t\t\thex[index * 2 + 1] = digits[bytes[index] & 0x0F];
\t\t}
\t\thex[count * 2] = '\\0';
\t}

\tuint64_t v38_fnv1a64(const unsigned char *bytes, size_t count)
\t{
\t\tuint64_t hash = 1469598103934665603ull;
\t\tfor (size_t index = 0; index < count; ++index)
\t\t{
\t\t\thash ^= bytes[index];
\t\t\thash *= 1099511628211ull;
\t\t}
\t\treturn hash;
\t}

\tDWORD WINAPI v38_readback_worker(LPVOID)
\t{
\t\tHANDLE event_handle = nullptr;
\t\tID3D12Resource *readback = nullptr;
\t\tID3D12Fence *fence = nullptr;
\t\tD3D12_GPU_VIRTUAL_ADDRESS argument_gpu_va = 0;
\t\tUINT64 argument_offset = 0;
\t\tuint64_t state_call = 0;
\t\tuint64_t ray_index = 0;
\t\t{
\t\t\tstd::lock_guard<std::mutex> lock(s_v38_capture_mutex);
\t\t\tevent_handle = s_v38_capture_event;
\t\t\treadback = s_v38_readback_resource;
\t\t\tfence = s_v38_capture_fence;
\t\t\targument_gpu_va = s_v38_argument_gpu_va;
\t\t\targument_offset = s_v38_argument_offset;
\t\t\tstate_call = s_v38_state_call;
\t\t\tray_index = s_v38_ray_index;
\t\t\tif (readback != nullptr)
\t\t\t\treadback->AddRef();
\t\t\tif (fence != nullptr)
\t\t\t\tfence->AddRef();
\t\t}

\t\tif (event_handle == nullptr || readback == nullptr || fence == nullptr)
\t\t{
\t\t\ts_v38_capture_failed.store(true, std::memory_order_release);
\t\t\treshade::log::message(
\t\t\t\treshade::log::level::warning,
\t\t\t\t"D3DMetal RTX live dispatch readback v38: GPU_READBACK_RESULT success=0 reason=missing_capture_objects.");
\t\t\tif (readback != nullptr) readback->Release();
\t\t\tif (fence != nullptr) fence->Release();
\t\t\treturn 0;
\t\t}

\t\tconst DWORD wait_result = WaitForSingleObject(event_handle, 15000);
\t\tif (wait_result != WAIT_OBJECT_0)
\t\t{
\t\t\ts_v38_capture_failed.store(true, std::memory_order_release);
\t\t\treshade::log::message(
\t\t\t\treshade::log::level::warning,
\t\t\t\t"D3DMetal RTX live dispatch readback v38: GPU_READBACK_RESULT success=0 reason=fence_wait wait_result=%lu completed=%llu.",
\t\t\t\twait_result,
\t\t\t\tstatic_cast<unsigned long long>(fence->GetCompletedValue()));
\t\t\treadback->Release();
\t\t\tfence->Release();
\t\t\treturn 0;
\t\t}

\t\tunsigned char bytes[v38_dispatch_record_bytes] = {};
\t\tvoid *mapped = nullptr;
\t\tconst D3D12_RANGE read_range = { 0, v38_dispatch_record_bytes };
\t\tconst HRESULT map_hr = readback->Map(0, &read_range, &mapped);
\t\tif (FAILED(map_hr) || mapped == nullptr)
\t\t{
\t\t\ts_v38_capture_failed.store(true, std::memory_order_release);
\t\t\treshade::log::message(
\t\t\t\treshade::log::level::warning,
\t\t\t\t"D3DMetal RTX live dispatch readback v38: GPU_READBACK_RESULT success=0 reason=map hr=%s raw=0x%08X.",
\t\t\t\treshade::log::hr_to_string(map_hr).c_str(),
\t\t\t\tstatic_cast<uint32_t>(map_hr));
\t\t\treadback->Release();
\t\t\tfence->Release();
\t\t\treturn 0;
\t\t}

\t\tmemcpy(bytes, mapped, sizeof(bytes));
\t\tconst D3D12_RANGE written_range = { 0, 0 };
\t\treadback->Unmap(0, &written_range);

\t\tD3D12_DISPATCH_RAYS_DESC desc = {};
\t\tstatic_assert(
\t\t\tsizeof(D3D12_DISPATCH_RAYS_DESC) <=
\t\t\t\tv38_dispatch_record_bytes,
\t\t\t"Unexpected D3D12_DISPATCH_RAYS_DESC size");
\t\tmemcpy(&desc, bytes, sizeof(desc));

\t\tchar raw_hex[v38_dispatch_record_bytes * 2 + 1] = {};
\t\tv38_bytes_to_hex(bytes, sizeof(bytes), raw_hex, sizeof(raw_hex));
\t\tconst uint64_t hash = v38_fnv1a64(bytes, sizeof(bytes));

\t\tconst UINT64 raygen_align =
\t\t\tdesc.RayGenerationShaderRecord.StartAddress %
\t\t\t\tD3D12_RAYTRACING_SHADER_TABLE_BYTE_ALIGNMENT;
\t\tconst UINT64 miss_align =
\t\t\tdesc.MissShaderTable.StartAddress %
\t\t\t\tD3D12_RAYTRACING_SHADER_TABLE_BYTE_ALIGNMENT;
\t\tconst UINT64 hit_align =
\t\t\tdesc.HitGroupTable.StartAddress %
\t\t\t\tD3D12_RAYTRACING_SHADER_TABLE_BYTE_ALIGNMENT;
\t\tconst UINT64 callable_align =
\t\t\tdesc.CallableShaderTable.StartAddress %
\t\t\t\tD3D12_RAYTRACING_SHADER_TABLE_BYTE_ALIGNMENT;
\t\tconst UINT64 miss_stride_align =
\t\t\tdesc.MissShaderTable.StrideInBytes %
\t\t\t\tD3D12_RAYTRACING_SHADER_RECORD_BYTE_ALIGNMENT;
\t\tconst UINT64 hit_stride_align =
\t\t\tdesc.HitGroupTable.StrideInBytes %
\t\t\t\tD3D12_RAYTRACING_SHADER_RECORD_BYTE_ALIGNMENT;
\t\tconst UINT64 callable_stride_align =
\t\t\tdesc.CallableShaderTable.StrideInBytes %
\t\t\t\tD3D12_RAYTRACING_SHADER_RECORD_BYTE_ALIGNMENT;

\t\tconst bool dimensions_plausible =
\t\t\tdesc.Width > 0 && desc.Width <= 65535 &&
\t\t\tdesc.Height > 0 && desc.Height <= 65535 &&
\t\t\tdesc.Depth > 0 && desc.Depth <= 2048;
\t\tconst bool alignments_valid =
\t\t\traygen_align == 0 && miss_align == 0 && hit_align == 0 &&
\t\t\t(callable_align == 0 ||
\t\t\t\tdesc.CallableShaderTable.StartAddress == 0) &&
\t\t\tmiss_stride_align == 0 && hit_stride_align == 0 &&
\t\t\t(callable_stride_align == 0 ||
\t\t\t\tdesc.CallableShaderTable.StrideInBytes == 0);

\t\treshade::log::message(
\t\t\treshade::log::level::info,
\t\t\t"D3DMetal RTX live dispatch readback v38: GPU_READBACK_RESULT success=1 state_call=%llu ray_index=%llu argument_gpu_va=0x%llX argument_offset=%llu hash=0x%llX raw_hex=%s raygen_start=0x%llX raygen_size=%llu miss_start=0x%llX miss_size=%llu miss_stride=%llu hit_start=0x%llX hit_size=%llu hit_stride=%llu callable_start=0x%llX callable_size=%llu callable_stride=%llu width=%u height=%u depth=%u raygen_align64=%llu miss_align64=%llu miss_stride_align32=%llu hit_align64=%llu hit_stride_align32=%llu callable_align64=%llu callable_stride_align32=%llu alignments_valid=%u dimensions_plausible=%u padding_tail=%02x%02x%02x%02x.",
\t\t\tstatic_cast<unsigned long long>(state_call),
\t\t\tstatic_cast<unsigned long long>(ray_index),
\t\t\tstatic_cast<unsigned long long>(argument_gpu_va),
\t\t\tstatic_cast<unsigned long long>(argument_offset),
\t\t\tstatic_cast<unsigned long long>(hash),
\t\t\traw_hex,
\t\t\tstatic_cast<unsigned long long>(desc.RayGenerationShaderRecord.StartAddress),
\t\t\tstatic_cast<unsigned long long>(desc.RayGenerationShaderRecord.SizeInBytes),
\t\t\tstatic_cast<unsigned long long>(desc.MissShaderTable.StartAddress),
\t\t\tstatic_cast<unsigned long long>(desc.MissShaderTable.SizeInBytes),
\t\t\tstatic_cast<unsigned long long>(desc.MissShaderTable.StrideInBytes),
\t\t\tstatic_cast<unsigned long long>(desc.HitGroupTable.StartAddress),
\t\t\tstatic_cast<unsigned long long>(desc.HitGroupTable.SizeInBytes),
\t\t\tstatic_cast<unsigned long long>(desc.HitGroupTable.StrideInBytes),
\t\t\tstatic_cast<unsigned long long>(desc.CallableShaderTable.StartAddress),
\t\t\tstatic_cast<unsigned long long>(desc.CallableShaderTable.SizeInBytes),
\t\t\tstatic_cast<unsigned long long>(desc.CallableShaderTable.StrideInBytes),
\t\t\tdesc.Width,
\t\t\tdesc.Height,
\t\t\tdesc.Depth,
\t\t\tstatic_cast<unsigned long long>(raygen_align),
\t\t\tstatic_cast<unsigned long long>(miss_align),
\t\t\tstatic_cast<unsigned long long>(miss_stride_align),
\t\t\tstatic_cast<unsigned long long>(hit_align),
\t\t\tstatic_cast<unsigned long long>(hit_stride_align),
\t\t\tstatic_cast<unsigned long long>(callable_align),
\t\t\tstatic_cast<unsigned long long>(callable_stride_align),
\t\t\talignments_valid ? 1u : 0u,
\t\t\tdimensions_plausible ? 1u : 0u,
\t\t\tbytes[100], bytes[101], bytes[102], bytes[103]);

\t\ts_v38_readback_complete.store(true, std::memory_order_release);
\t\treadback->Release();
\t\tfence->Release();
\t\treturn 0;
\t}

\tvoid v38_install_execute_command_lists_hook(ID3D12CommandQueue *queue);

\tHRESULT STDMETHODCALLTYPE v38_trace_create_command_queue(
\t\tID3D12Device *device,
\t\tconst D3D12_COMMAND_QUEUE_DESC *desc,
\t\tREFIID riid,
\t\tvoid **command_queue)
\t{
\t\tif (s_v38_original_create_command_queue == nullptr)
\t\t\treturn E_FAIL;

\t\tconst HRESULT result = s_v38_original_create_command_queue(
\t\t\tdevice, desc, riid, command_queue);
\t\tvoid *created = nullptr;
\t\tif (command_queue != nullptr)
\t\t\tsafe_copy_from_process(command_queue, &created, sizeof(created));
\t\tif (SUCCEEDED(result) && created != nullptr)
\t\t\tv38_install_execute_command_lists_hook(
\t\t\t\treinterpret_cast<ID3D12CommandQueue *>(created));

\t\treshade::log::message(
\t\t\treshade::log::level::debug,
\t\t\t"D3DMetal RTX live dispatch readback v38: COMMAND_QUEUE_CREATED hr=%s raw=0x%08X object=%p.",
\t\t\treshade::log::hr_to_string(result).c_str(),
\t\t\tstatic_cast<uint32_t>(result),
\t\t\tcreated);
\t\treturn result;
\t}

\tvoid STDMETHODCALLTYPE v38_trace_execute_command_lists(
\t\tID3D12CommandQueue *queue,
\t\tUINT count,
\t\tID3D12CommandList *const *command_lists)
\t{
\t\tbool contains_capture = false;
\t\tvoid *capture_identity = nullptr;
\t\t{
\t\t\tstd::lock_guard<std::mutex> lock(s_v38_capture_mutex);
\t\t\tcapture_identity = s_v38_capture_command_list_identity;
\t\t}

\t\tif (capture_identity != nullptr && command_lists != nullptr)
\t\t{
\t\t\tfor (UINT index = 0; index < count; ++index)
\t\t\t{
\t\t\t\tID3D12CommandList *list = nullptr;
\t\t\t\tif (!safe_copy_from_process(
\t\t\t\t\t\tcommand_lists + index,
\t\t\t\t\t\t&list,
\t\t\t\t\t\tsizeof(list)) || list == nullptr)
\t\t\t\t\tcontinue;
\t\t\t\tvoid *const identity = v33_identity_pointer(
\t\t\t\t\treinterpret_cast<IUnknown *>(list));
\t\t\t\tif (identity == capture_identity)
\t\t\t\t{
\t\t\t\t\tcontains_capture = true;
\t\t\t\t\tbreak;
\t\t\t\t}
\t\t\t}
\t\t}

\t\tif (s_v38_original_execute_command_lists != nullptr)
\t\t\ts_v38_original_execute_command_lists(
\t\t\t\tqueue, count, command_lists);

\t\tbool expected = false;
\t\tif (!contains_capture ||
\t\t\t!s_v38_queue_signaled.compare_exchange_strong(
\t\t\t\texpected, true, std::memory_order_acq_rel))
\t\t\treturn;

\t\tID3D12Fence *fence = nullptr;
\t\tHANDLE event_handle = nullptr;
\t\t{
\t\t\tstd::lock_guard<std::mutex> lock(s_v38_capture_mutex);
\t\t\tfence = s_v38_capture_fence;
\t\t\tevent_handle = s_v38_capture_event;
\t\t}

\t\tHRESULT signal_hr = E_FAIL;
\t\tHRESULT event_hr = E_FAIL;
\t\tif (queue != nullptr && fence != nullptr && event_handle != nullptr)
\t\t{
\t\t\tsignal_hr = queue->Signal(fence, 1);
\t\t\tif (SUCCEEDED(signal_hr))
\t\t\t\tevent_hr = fence->SetEventOnCompletion(1, event_handle);
\t\t}

\t\treshade::log::message(
\t\t\tSUCCEEDED(signal_hr) && SUCCEEDED(event_hr) ?
\t\t\t\treshade::log::level::info :
\t\t\t\treshade::log::level::warning,
\t\t\t"D3DMetal RTX live dispatch readback v38: QUEUE_CAPTURE_SUBMITTED count=%u signal_hr=%s signal_raw=0x%08X event_hr=%s event_raw=0x%08X.",
\t\t\tcount,
\t\t\treshade::log::hr_to_string(signal_hr).c_str(),
\t\t\tstatic_cast<uint32_t>(signal_hr),
\t\t\treshade::log::hr_to_string(event_hr).c_str(),
\t\t\tstatic_cast<uint32_t>(event_hr));

\t\tif (SUCCEEDED(signal_hr) && SUCCEEDED(event_hr))
\t\t{
\t\t\tHANDLE thread_handle = CreateThread(
\t\t\t\tnullptr, 0, &v38_readback_worker, nullptr, 0, nullptr);
\t\t\tif (thread_handle != nullptr)
\t\t\t\tCloseHandle(thread_handle);
\t\t\telse
\t\t\t\ts_v38_capture_failed.store(true, std::memory_order_release);
\t\t}
\t\telse
\t\t{
\t\t\ts_v38_capture_failed.store(true, std::memory_order_release);
\t\t}
\t}

\tvoid v38_install_execute_command_lists_hook(ID3D12CommandQueue *queue)
\t{
\t\tif (queue == nullptr)
\t\t\treturn;

\t\tstd::call_once(
\t\t\ts_v38_execute_lists_hook_once,
\t\t\t[queue]()
\t\t\t{
\t\t\t\tvoid **const vtable =
\t\t\t\t\t*reinterpret_cast<void ***>(queue);
\t\t\t\tvoid *const current =
\t\t\t\t\tvtable[v38_execute_command_lists_slot];
\t\t\t\ts_v38_original_execute_command_lists =
\t\t\t\t\treinterpret_cast<v38_execute_command_lists_fn>(current);

\t\t\t\tDWORD old_protect = 0;
\t\t\t\tbool installed = false;
\t\t\t\tif (VirtualProtect(
\t\t\t\t\t&vtable[v38_execute_command_lists_slot],
\t\t\t\t\tsizeof(void *),
\t\t\t\t\tPAGE_EXECUTE_READWRITE,
\t\t\t\t\t&old_protect))
\t\t\t\t{
\t\t\t\t\tInterlockedExchangePointer(
\t\t\t\t\t\treinterpret_cast<PVOID volatile *>(
\t\t\t\t\t\t\t&vtable[v38_execute_command_lists_slot]),
\t\t\t\t\t\treinterpret_cast<PVOID>(
\t\t\t\t\t\t\t&v38_trace_execute_command_lists));
\t\t\t\t\tDWORD ignored = 0;
\t\t\t\t\tVirtualProtect(
\t\t\t\t\t\t&vtable[v38_execute_command_lists_slot],
\t\t\t\t\t\tsizeof(void *), old_protect, &ignored);
\t\t\t\t\tFlushInstructionCache(
\t\t\t\t\t\tGetCurrentProcess(),
\t\t\t\t\t\t&vtable[v38_execute_command_lists_slot],
\t\t\t\t\t\tsizeof(void *));
\t\t\t\t\tinstalled =
\t\t\t\t\t\tvtable[v38_execute_command_lists_slot] ==
\t\t\t\t\t\t\treinterpret_cast<void *>(
\t\t\t\t\t\t\t\t&v38_trace_execute_command_lists);
\t\t\t\t}
\t\t\t\ts_v38_execute_lists_hook_installed.store(
\t\t\t\t\tinstalled, std::memory_order_release);
\t\t\t\treshade::log::message(
\t\t\t\t\tinstalled ? reshade::log::level::info :
\t\t\t\t\t\treshade::log::level::warning,
\t\t\t\t\t"D3DMetal RTX live dispatch readback v38: EXECUTE_COMMAND_LISTS_HOOK installed=%u slot=%zu original=%p replacement=%p.",
\t\t\t\t\tinstalled ? 1u : 0u,
\t\t\t\t\tv38_execute_command_lists_slot,
\t\t\t\t\treinterpret_cast<void *>(
\t\t\t\t\t\ts_v38_original_execute_command_lists),
\t\t\t\t\treinterpret_cast<void *>(
\t\t\t\t\t\t&v38_trace_execute_command_lists));
\t\t\t\tif (!installed)
\t\t\t\t\ts_v38_original_execute_command_lists = nullptr;
\t\t\t});
\t}

\tvoid v38_install_create_command_queue_hook(ID3D12Device *device)
\t{
\t\tif (device == nullptr)
\t\t\treturn;

\t\tstd::call_once(
\t\t\ts_v38_create_queue_hook_once,
\t\t\t[device]()
\t\t\t{
\t\t\t\tvoid **const vtable =
\t\t\t\t\t*reinterpret_cast<void ***>(device);
\t\t\t\tvoid *const current =
\t\t\t\t\tvtable[v38_create_command_queue_slot];
\t\t\t\ts_v38_original_create_command_queue =
\t\t\t\t\treinterpret_cast<v38_create_command_queue_fn>(current);

\t\t\t\tDWORD old_protect = 0;
\t\t\t\tbool installed = false;
\t\t\t\tif (VirtualProtect(
\t\t\t\t\t&vtable[v38_create_command_queue_slot],
\t\t\t\t\tsizeof(void *),
\t\t\t\t\tPAGE_EXECUTE_READWRITE,
\t\t\t\t\t&old_protect))
\t\t\t\t{
\t\t\t\t\tInterlockedExchangePointer(
\t\t\t\t\t\treinterpret_cast<PVOID volatile *>(
\t\t\t\t\t\t\t&vtable[v38_create_command_queue_slot]),
\t\t\t\t\t\treinterpret_cast<PVOID>(
\t\t\t\t\t\t\t&v38_trace_create_command_queue));
\t\t\t\t\tDWORD ignored = 0;
\t\t\t\t\tVirtualProtect(
\t\t\t\t\t\t&vtable[v38_create_command_queue_slot],
\t\t\t\t\t\tsizeof(void *), old_protect, &ignored);
\t\t\t\t\tFlushInstructionCache(
\t\t\t\t\t\tGetCurrentProcess(),
\t\t\t\t\t\t&vtable[v38_create_command_queue_slot],
\t\t\t\t\t\tsizeof(void *));
\t\t\t\t\tinstalled =
\t\t\t\t\t\tvtable[v38_create_command_queue_slot] ==
\t\t\t\t\t\t\treinterpret_cast<void *>(
\t\t\t\t\t\t\t\t&v38_trace_create_command_queue);
\t\t\t\t}
\t\t\t\ts_v38_create_queue_hook_installed.store(
\t\t\t\t\tinstalled, std::memory_order_release);
\t\t\t\treshade::log::message(
\t\t\t\t\tinstalled ? reshade::log::level::info :
\t\t\t\t\t\treshade::log::level::warning,
\t\t\t\t\t"D3DMetal RTX live dispatch readback v38: CREATE_COMMAND_QUEUE_HOOK installed=%u slot=%zu original=%p replacement=%p.",
\t\t\t\t\tinstalled ? 1u : 0u,
\t\t\t\t\tv38_create_command_queue_slot,
\t\t\t\t\treinterpret_cast<void *>(
\t\t\t\t\t\ts_v38_original_create_command_queue),
\t\t\t\t\treinterpret_cast<void *>(
\t\t\t\t\t\t&v38_trace_create_command_queue));
\t\t\t\tif (!installed)
\t\t\t\t\ts_v38_original_create_command_queue = nullptr;
\t\t\t});
\t}

\tvoid v38_try_capture_dispatch_record(
\t\tID3D12GraphicsCommandList *command_list,
\t\tID3D12Resource *argument_buffer,
\t\tUINT64 argument_buffer_offset,
\t\tbool dispatch_rays,
\t\tbool rewritten,
\t\tuint64_t state_call,
\t\tuint64_t rewritten_ray_index)
\t{
\t\tif (!dispatch_rays || !rewritten || command_list == nullptr ||
\t\t\targument_buffer == nullptr || rewritten_ray_index == 0)
\t\t\treturn;

\t\tbool expected = false;
\t\tif (!s_v38_capture_claimed.compare_exchange_strong(
\t\t\texpected, true, std::memory_order_acq_rel))
\t\t\treturn;

\t\tconst D3D12_RESOURCE_DESC argument_desc =
\t\t\targument_buffer->GetDesc();
\t\tif (argument_desc.Dimension != D3D12_RESOURCE_DIMENSION_BUFFER ||
\t\t\targument_buffer_offset + v38_dispatch_record_bytes >
\t\t\t\targument_desc.Width)
\t\t{
\t\t\ts_v38_capture_failed.store(true, std::memory_order_release);
\t\t\treshade::log::message(
\t\t\t\treshade::log::level::warning,
\t\t\t\t"D3DMetal RTX live dispatch readback v38: GPU_READBACK_CAPTURE recorded=0 reason=argument_range width=%llu offset=%llu.",
\t\t\t\tstatic_cast<unsigned long long>(argument_desc.Width),
\t\t\t\tstatic_cast<unsigned long long>(argument_buffer_offset));
\t\t\treturn;
\t\t}

\t\tID3D12Device *device = nullptr;
\t\tHRESULT hr = argument_buffer->GetDevice(
\t\t\t__uuidof(ID3D12Device),
\t\t\treinterpret_cast<void **>(&device));
\t\tif (FAILED(hr) || device == nullptr)
\t\t{
\t\t\ts_v38_capture_failed.store(true, std::memory_order_release);
\t\t\treshade::log::message(
\t\t\t\treshade::log::level::warning,
\t\t\t\t"D3DMetal RTX live dispatch readback v38: GPU_READBACK_CAPTURE recorded=0 reason=get_device hr=%s raw=0x%08X.",
\t\t\t\treshade::log::hr_to_string(hr).c_str(),
\t\t\t\tstatic_cast<uint32_t>(hr));
\t\t\treturn;
\t\t}

\t\tD3D12_HEAP_PROPERTIES heap_properties = {};
\t\theap_properties.Type = D3D12_HEAP_TYPE_READBACK;
\t\theap_properties.CPUPageProperty =
\t\t\tD3D12_CPU_PAGE_PROPERTY_UNKNOWN;
\t\theap_properties.MemoryPoolPreference =
\t\t\tD3D12_MEMORY_POOL_UNKNOWN;
\t\theap_properties.CreationNodeMask = 1;
\t\theap_properties.VisibleNodeMask = 1;

\t\tD3D12_RESOURCE_DESC readback_desc = {};
\t\treadback_desc.Dimension = D3D12_RESOURCE_DIMENSION_BUFFER;
\t\treadback_desc.Alignment = 0;
\t\treadback_desc.Width = v38_dispatch_record_bytes;
\t\treadback_desc.Height = 1;
\t\treadback_desc.DepthOrArraySize = 1;
\t\treadback_desc.MipLevels = 1;
\t\treadback_desc.Format = DXGI_FORMAT_UNKNOWN;
\t\treadback_desc.SampleDesc.Count = 1;
\t\treadback_desc.SampleDesc.Quality = 0;
\t\treadback_desc.Layout = D3D12_TEXTURE_LAYOUT_ROW_MAJOR;
\t\treadback_desc.Flags = D3D12_RESOURCE_FLAG_NONE;

\t\tID3D12Resource *readback = nullptr;
\t\thr = device->CreateCommittedResource(
\t\t\t&heap_properties,
\t\t\tD3D12_HEAP_FLAG_NONE,
\t\t\t&readback_desc,
\t\t\tD3D12_RESOURCE_STATE_COPY_DEST,
\t\t\tnullptr,
\t\t\t__uuidof(ID3D12Resource),
\t\t\treinterpret_cast<void **>(&readback));
\t\tif (FAILED(hr) || readback == nullptr)
\t\t{
\t\t\ts_v38_capture_failed.store(true, std::memory_order_release);
\t\t\treshade::log::message(
\t\t\t\treshade::log::level::warning,
\t\t\t\t"D3DMetal RTX live dispatch readback v38: GPU_READBACK_CAPTURE recorded=0 reason=create_readback hr=%s raw=0x%08X.",
\t\t\t\treshade::log::hr_to_string(hr).c_str(),
\t\t\t\tstatic_cast<uint32_t>(hr));
\t\t\tdevice->Release();
\t\t\treturn;
\t\t}

\t\tID3D12Fence *fence = nullptr;
\t\thr = device->CreateFence(
\t\t\t0,
\t\t\tD3D12_FENCE_FLAG_NONE,
\t\t\t__uuidof(ID3D12Fence),
\t\t\treinterpret_cast<void **>(&fence));
\t\tHANDLE event_handle = CreateEventW(nullptr, FALSE, FALSE, nullptr);
\t\tif (FAILED(hr) || fence == nullptr || event_handle == nullptr)
\t\t{
\t\t\ts_v38_capture_failed.store(true, std::memory_order_release);
\t\t\treshade::log::message(
\t\t\t\treshade::log::level::warning,
\t\t\t\t"D3DMetal RTX live dispatch readback v38: GPU_READBACK_CAPTURE recorded=0 reason=create_sync hr=%s raw=0x%08X event=%p error=%lu.",
\t\t\t\treshade::log::hr_to_string(hr).c_str(),
\t\t\t\tstatic_cast<uint32_t>(hr),
\t\t\t\tevent_handle,
\t\t\t\tGetLastError());
\t\t\tif (event_handle != nullptr) CloseHandle(event_handle);
\t\t\tif (fence != nullptr) fence->Release();
\t\t\treadback->Release();
\t\t\tdevice->Release();
\t\t\treturn;
\t\t}

\t\tD3D12_RESOURCE_BARRIER to_copy = {};
\t\tto_copy.Type = D3D12_RESOURCE_BARRIER_TYPE_TRANSITION;
\t\tto_copy.Flags = D3D12_RESOURCE_BARRIER_FLAG_NONE;
\t\tto_copy.Transition.pResource = argument_buffer;
\t\tto_copy.Transition.Subresource = D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES;
\t\tto_copy.Transition.StateBefore =
\t\t\tD3D12_RESOURCE_STATE_INDIRECT_ARGUMENT;
\t\tto_copy.Transition.StateAfter =
\t\t\tD3D12_RESOURCE_STATE_COPY_SOURCE;
\t\tD3D12_RESOURCE_BARRIER to_indirect = to_copy;
\t\tto_indirect.Transition.StateBefore =
\t\t\tD3D12_RESOURCE_STATE_COPY_SOURCE;
\t\tto_indirect.Transition.StateAfter =
\t\t\tD3D12_RESOURCE_STATE_INDIRECT_ARGUMENT;

\t\tcommand_list->ResourceBarrier(1, &to_copy);
\t\tcommand_list->CopyBufferRegion(
\t\t\treadback,
\t\t\t0,
\t\t\targument_buffer,
\t\t\targument_buffer_offset,
\t\t\tv38_dispatch_record_bytes);
\t\tcommand_list->ResourceBarrier(1, &to_indirect);

\t\tvoid *const list_identity = v33_identity_pointer(
\t\t\treinterpret_cast<IUnknown *>(command_list));
\t\t{
\t\t\tstd::lock_guard<std::mutex> lock(s_v38_capture_mutex);
\t\t\ts_v38_readback_resource = readback;
\t\t\ts_v38_capture_fence = fence;
\t\t\ts_v38_capture_event = event_handle;
\t\t\ts_v38_capture_command_list_identity = list_identity;
\t\t\ts_v38_argument_gpu_va =
\t\t\t\targument_buffer->GetGPUVirtualAddress();
\t\t\ts_v38_argument_offset = argument_buffer_offset;
\t\t\ts_v38_state_call = state_call;
\t\t\ts_v38_ray_index = rewritten_ray_index;
\t\t}
\t\ts_v38_copy_recorded.store(true, std::memory_order_release);

\t\treshade::log::message(
\t\t\treshade::log::level::info,
\t\t\t"D3DMetal RTX live dispatch readback v38: GPU_READBACK_CAPTURE recorded=1 state_call=%llu ray_index=%llu command_list=%p identity=%p argument_resource=%p argument_gpu_va=0x%llX argument_offset=%llu bytes=%llu readback=%p fence=%p event=%p.",
\t\t\tstatic_cast<unsigned long long>(state_call),
\t\t\tstatic_cast<unsigned long long>(rewritten_ray_index),
\t\t\tcommand_list,
\t\t\tlist_identity,
\t\t\targument_buffer,
\t\t\tstatic_cast<unsigned long long>(
\t\t\t\targument_buffer->GetGPUVirtualAddress()),
\t\t\tstatic_cast<unsigned long long>(argument_buffer_offset),
\t\t\tstatic_cast<unsigned long long>(v38_dispatch_record_bytes),
\t\t\treadback,
\t\t\tfence,
\t\t\tevent_handle);

\t\tdevice->Release();
\t}

'''
# This helper is intentionally a raw Python string so C++ escapes such as
# '\0' remain intact. Convert only indentation markers to real tab bytes.
helper = helper.replace(r"\t", "	")

for forbidden in (
    r"\tusing v38_",
    r"\tconstexpr size_t v38_",
    r"\tstatic v38_",
    r"\tvoid v38_",
    r"\tHRESULT STDMETHODCALLTYPE v38_",
):
    if forbidden in helper:
        raise RuntimeError(
            f"V38 helper still contains a literal indentation escape: {forbidden}")

text = text.replace(v34_anchor, helper + "\n" + v34_anchor, 1)

for forbidden in (
    r"\tusing v38_",
    r"\tconstexpr size_t v38_",
    r"\tstatic v38_",
    r"\tvoid v38_",
    r"\tHRESULT STDMETHODCALLTYPE v38_",
):
    if forbidden in text:
        raise RuntimeError(
            f"V38 patched C++ contains a literal indentation escape: {forbidden}")

install_anchor = '''\tvoid v34_install_create_command_signature_hook(
\t\tID3D12Device *device)
\t{
\t\tif (device == nullptr)
\t\t\treturn;

'''
install_replacement = install_anchor + '''\t\tv38_install_create_command_queue_hook(device);

'''
text = replace_once(
    text,
    install_anchor,
    install_replacement,
    "V38 CreateCommandQueue hook install")

execute_anchor = '''\t\tif (s_v34_original_execute_indirect != nullptr)
\t\t\ts_v34_original_execute_indirect(
'''
execute_replacement = '''\t\tv38_try_capture_dispatch_record(
\t\t\tcommand_list,
\t\t\targument_buffer,
\t\t\targument_buffer_offset,
\t\t\tdispatch_rays,
\t\t\trewritten,
\t\t\tstate_call,
\t\t\trewritten_ray_index);

''' + execute_anchor
text = replace_once(
    text,
    execute_anchor,
    execute_replacement,
    "V38 live dispatch capture call")

required = [
    "D3DMetal RTX live dispatch readback v38:",
    "CREATE_COMMAND_QUEUE_HOOK installed=",
    "EXECUTE_COMMAND_LISTS_HOOK installed=",
    "GPU_READBACK_CAPTURE recorded=",
    "QUEUE_CAPTURE_SUBMITTED count=",
    "GPU_READBACK_RESULT success=",
    "v38_dispatch_record_bytes = 104",
    "D3D12_RESOURCE_STATE_INDIRECT_ARGUMENT",
    "D3D12_RESOURCE_STATE_COPY_SOURCE",
    "v38_try_capture_dispatch_record(",
    "v38_install_create_command_queue_hook(device);",
]
for marker in required:
    if marker not in text:
        raise RuntimeError(f"Missing V38 source marker: {marker}")

if text.count("v38_try_capture_dispatch_record(") != 2:
    raise RuntimeError(
        "V38 capture function/call count is not exactly two")

SOURCE.write_text(text, encoding="utf-8", newline="\n")

report = Path("v38-patch-report.txt")
report.write_text(
    "\n".join([
        "V38_LIVE_DISPATCH_GPU_READBACK_PATCH_OK",
        "V54_PATTERN_INHERITANCE_BASELINE_PRESERVED=YES",
        "CREATE_COMMAND_QUEUE_SLOT=8",
        "EXECUTE_COMMAND_LISTS_SLOT=10",
        "TARGET_RECORD_BYTES=104",
        "FIRST_REWRITTEN_INDIRECT_RAY_ONLY=YES",
        "ARGUMENT_STATE_BEFORE=INDIRECT_ARGUMENT",
        "CAPTURE_STATE=COPY_SOURCE",
        "ARGUMENT_STATE_RESTORED=INDIRECT_ARGUMENT",
        "READBACK_HEAP=ENABLED",
        "QUEUE_FENCE_SYNCHRONIZATION=ENABLED",
        "RAW_RECORD_HEX_LOGGING=ENABLED",
        "DISPATCH_DESC_FIELD_DECODING=ENABLED",
        "SHADER_TABLE_ALIGNMENT_CHECKS=ENABLED",
        "EXECUTE_INDIRECT_ARGUMENTS_UNMODIFIED=YES",
        "STATE_OBJECT_UNMODIFIED_BY_V38=YES",
        "RESULT=PASS",
        "",
    ]),
    encoding="utf-8",
    newline="\n",
)
print(report.read_text(encoding="utf-8"))
