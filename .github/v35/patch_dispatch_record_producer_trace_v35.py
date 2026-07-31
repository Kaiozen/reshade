from pathlib import Path

SOURCE = Path("source/d3d12/d3d12.cpp")
if not SOURCE.is_file():
    raise RuntimeError(f"Missing source file: {SOURCE}")

text = SOURCE.read_text(encoding="utf-8-sig")
if "D3DMetal RTX indirect execution trace v34:" not in text:
    raise RuntimeError("V34 must be applied before V35")
if "D3DMetal RTX dispatch-record producer trace v35:" in text:
    raise RuntimeError("V35 is already present")


def replace_once(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 occurrence, found {count}")
    return source.replace(old, new, 1)

# Add exact shader-identifier bytes to the already accepted V32 object report.
identifier_old = '''\t\t\tif (SUCCEEDED(properties_hr) && properties != nullptr)
\t\t\t{
\t\t\t\texecute_present = properties->GetShaderIdentifier(L"ExecuteTrace") != nullptr;
\t\t\t\tmiss_present = properties->GetShaderIdentifier(L"Miss") != nullptr;
\t\t\t\tproperties->Release();
\t\t\t}
'''
identifier_new = '''\t\t\tif (SUCCEEDED(properties_hr) && properties != nullptr)
\t\t\t{
\t\t\t\tconst unsigned char *const execute_identifier =
\t\t\t\t\treinterpret_cast<const unsigned char *>(
\t\t\t\t\t\tproperties->GetShaderIdentifier(L"ExecuteTrace"));
\t\t\t\tconst unsigned char *const miss_identifier =
\t\t\t\t\treinterpret_cast<const unsigned char *>(
\t\t\t\t\t\tproperties->GetShaderIdentifier(L"Miss"));
\t\t\t\texecute_present = execute_identifier != nullptr;
\t\t\t\tmiss_present = miss_identifier != nullptr;

\t\t\t\tchar execute_hex[D3D12_SHADER_IDENTIFIER_SIZE_IN_BYTES * 2 + 1] = {};
\t\t\t\tchar miss_hex[D3D12_SHADER_IDENTIFIER_SIZE_IN_BYTES * 2 + 1] = {};
\t\t\t\tstatic const char digits[] = "0123456789abcdef";
\t\t\t\tif (execute_identifier != nullptr)
\t\t\t\t{
\t\t\t\t\tfor (size_t byte = 0; byte < D3D12_SHADER_IDENTIFIER_SIZE_IN_BYTES; ++byte)
\t\t\t\t\t{
\t\t\t\t\t\texecute_hex[byte * 2] = digits[execute_identifier[byte] >> 4];
\t\t\t\t\t\texecute_hex[byte * 2 + 1] = digits[execute_identifier[byte] & 0x0F];
\t\t\t\t\t}
\t\t\t\t}
\t\t\t\tif (miss_identifier != nullptr)
\t\t\t\t{
\t\t\t\t\tfor (size_t byte = 0; byte < D3D12_SHADER_IDENTIFIER_SIZE_IN_BYTES; ++byte)
\t\t\t\t\t{
\t\t\t\t\t\tmiss_hex[byte * 2] = digits[miss_identifier[byte] >> 4];
\t\t\t\t\t\tmiss_hex[byte * 2 + 1] = digits[miss_identifier[byte] & 0x0F];
\t\t\t\t\t}
\t\t\t\t}

\t\t\t\treshade::log::message(
\t\t\t\t\treshade::log::level::info,
\t\t\t\t\t"D3DMetal RTX dispatch-record producer trace v35: STATE_IDENTIFIERS call=%llu execute_present=%u miss_present=%u execute_hex=%s miss_hex=%s.",
\t\t\t\t\tstatic_cast<unsigned long long>(call_id),
\t\t\t\t\texecute_present ? 1u : 0u,
\t\t\t\t\tmiss_present ? 1u : 0u,
\t\t\t\t\texecute_present ? execute_hex : "NONE",
\t\t\t\t\tmiss_present ? miss_hex : "NONE");

\t\t\t\tproperties->Release();
\t\t\t}
'''
# Target only the V32 universal bridge. V31 intentionally contains the same
# five-line identifier-presence block, so a whole-file replace is ambiguous.
v32_function_start_marker = "\tbool try_v32_fp32_universal_bridge(\n"
v32_start = text.find(v32_function_start_marker)
if v32_start < 0:
    raise RuntimeError("V35 could not find try_v32_fp32_universal_bridge")

v32_open_brace = text.find("{", v32_start)
if v32_open_brace < 0:
    raise RuntimeError("V35 could not find the V32 bridge opening brace")

depth = 0
v32_end = -1
for position in range(v32_open_brace, len(text)):
    character = text[position]
    if character == "{":
        depth += 1
    elif character == "}":
        depth -= 1
        if depth == 0:
            v32_end = position + 1
            break
if v32_end < 0:
    raise RuntimeError("V35 could not find the V32 bridge closing brace")

v32_function = text[v32_start:v32_end]
v32_count = v32_function.count(identifier_old)
if v32_count != 1:
    raise RuntimeError(
        f"V35 V32 identifier block: expected 1 occurrence, found {v32_count}")
v32_function = v32_function.replace(identifier_old, identifier_new, 1)
text = text[:v32_start] + v32_function + text[v32_end:]

if text.count("D3DMetal RTX dispatch-record producer trace v35: STATE_IDENTIFIERS") != 1:
    raise RuntimeError("V35 identifier logging was not inserted exactly once")
if text.count(identifier_old) != 1:
    raise RuntimeError(
        "V35 expected the duplicate V31 identifier block to remain exactly once")

helper_anchor = "\tvoid v33_install_command_list_method_hooks(IUnknown *command_list)\n"
if text.count(helper_anchor) != 1:
    raise RuntimeError(
        f"V35 command-list helper anchor mismatch: {text.count(helper_anchor)}")

helper = '''
\tusing v35_copy_buffer_region_fn = void (STDMETHODCALLTYPE *)(
\t\tID3D12GraphicsCommandList *,
\t\tID3D12Resource *,
\t\tUINT64,
\t\tID3D12Resource *,
\t\tUINT64,
\t\tUINT64);

\tusing v35_copy_resource_fn = void (STDMETHODCALLTYPE *)(
\t\tID3D12GraphicsCommandList *,
\t\tID3D12Resource *,
\t\tID3D12Resource *);

\tconstexpr size_t v35_copy_buffer_region_slot = 15;
\tconstexpr size_t v35_copy_resource_slot = 17;
\tconstexpr UINT64 v35_dispatch_record_bytes = 104;
\tconstexpr uint64_t v35_max_upload_capture_attempts = 64;

\tstatic v35_copy_buffer_region_fn
\t\ts_v35_original_copy_buffer_region = nullptr;
\tstatic v35_copy_resource_fn
\t\ts_v35_original_copy_resource = nullptr;
\tstatic std::once_flag s_v35_copy_buffer_hook_once;
\tstatic std::once_flag s_v35_copy_resource_hook_once;
\tstatic std::atomic<uint64_t> s_v35_copy_candidate_total = 0;
\tstatic std::atomic<uint64_t> s_v35_upload_map_attempt_total = 0;
\tstatic std::atomic<uint64_t> s_v35_upload_capture_total = 0;
\tstatic std::mutex s_v35_capture_hash_mutex;
\tstatic uint64_t s_v35_seen_capture_hashes[64] = {};
\tstatic size_t s_v35_seen_capture_hash_count = 0;

\tuint64_t v35_fnv1a64(const unsigned char *data, size_t size)
\t{
\t\tuint64_t hash = 1469598103934665603ull;
\t\tfor (size_t index = 0; index < size; ++index)
\t\t{
\t\t\thash ^= data[index];
\t\t\thash *= 1099511628211ull;
\t\t}
\t\treturn hash;
\t}

\tbool v35_mark_capture_hash_new(uint64_t hash)
\t{
\t\tstd::lock_guard<std::mutex> lock(s_v35_capture_hash_mutex);
\t\tfor (size_t index = 0; index < s_v35_seen_capture_hash_count; ++index)
\t\t{
\t\t\tif (s_v35_seen_capture_hashes[index] == hash)
\t\t\t\treturn false;
\t\t}
\t\tif (s_v35_seen_capture_hash_count < 64)
\t\t\ts_v35_seen_capture_hashes[s_v35_seen_capture_hash_count++] = hash;
\t\treturn true;
\t}

\tvoid v35_log_dispatch_record(
\t\tconst char *producer,
\t\tuint64_t candidate_index,
\t\tID3D12Resource *destination,
\t\tUINT64 destination_offset,
\t\tID3D12Resource *source,
\t\tUINT64 source_offset,
\t\tUINT64 copied_bytes,
\t\tD3D12_HEAP_TYPE destination_heap,
\t\tD3D12_HEAP_TYPE source_heap,
\t\tconst unsigned char *bytes)
\t{
\t\tD3D12_DISPATCH_RAYS_DESC desc = {};
\t\tconst size_t copy_size = sizeof(desc) < v35_dispatch_record_bytes ?
\t\t\tsizeof(desc) : static_cast<size_t>(v35_dispatch_record_bytes);
\t\tmemcpy(&desc, bytes, copy_size);

\t\tchar raw_hex[v35_dispatch_record_bytes * 2 + 1] = {};
\t\tstatic const char digits[] = "0123456789abcdef";
\t\tfor (size_t byte = 0; byte < v35_dispatch_record_bytes; ++byte)
\t\t{
\t\t\traw_hex[byte * 2] = digits[bytes[byte] >> 4];
\t\t\traw_hex[byte * 2 + 1] = digits[bytes[byte] & 0x0F];
\t\t}

\t\tconst uint64_t hash = v35_fnv1a64(bytes, v35_dispatch_record_bytes);
\t\tconst bool new_hash = v35_mark_capture_hash_new(hash);
\t\tconst uint64_t capture_index = ++s_v35_upload_capture_total;
\t\tif (!new_hash && capture_index > 16)
\t\t\treturn;

\t\tconst D3D12_GPU_VIRTUAL_ADDRESS destination_gpu_va =
\t\t\tdestination != nullptr ? destination->GetGPUVirtualAddress() : 0;
\t\tconst D3D12_GPU_VIRTUAL_ADDRESS source_gpu_va =
\t\t\tsource != nullptr ? source->GetGPUVirtualAddress() : 0;

\t\treshade::log::message(
\t\t\treshade::log::level::info,
\t\t\t"D3DMetal RTX dispatch-record producer trace v35: DISPATCH_DESC_CAPTURE producer=%s candidate_index=%llu capture_index=%llu new_hash=%u hash=0x%llX dst=%p dst_gpu_va=0x%llX dst_offset=%llu dst_heap=%u src=%p src_gpu_va=0x%llX src_offset=%llu src_heap=%u copied_bytes=%llu struct_size=%zu raygen_start=0x%llX raygen_size=%llu miss_start=0x%llX miss_size=%llu miss_stride=%llu hit_start=0x%llX hit_size=%llu hit_stride=%llu callable_start=0x%llX callable_size=%llu callable_stride=%llu width=%u height=%u depth=%u raygen_align64=%llu miss_align64=%llu miss_stride_align32=%llu hit_align64=%llu hit_stride_align32=%llu callable_align64=%llu callable_stride_align32=%llu raw=%s.",
\t\t\tproducer,
\t\t\tstatic_cast<unsigned long long>(candidate_index),
\t\t\tstatic_cast<unsigned long long>(capture_index),
\t\t\tnew_hash ? 1u : 0u,
\t\t\tstatic_cast<unsigned long long>(hash),
\t\t\tdestination,
\t\t\tstatic_cast<unsigned long long>(destination_gpu_va),
\t\t\tstatic_cast<unsigned long long>(destination_offset),
\t\t\tstatic_cast<unsigned int>(destination_heap),
\t\t\tsource,
\t\t\tstatic_cast<unsigned long long>(source_gpu_va),
\t\t\tstatic_cast<unsigned long long>(source_offset),
\t\t\tstatic_cast<unsigned int>(source_heap),
\t\t\tstatic_cast<unsigned long long>(copied_bytes),
\t\t\tsizeof(desc),
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
\t\t\tstatic_cast<unsigned long long>(desc.RayGenerationShaderRecord.StartAddress % 64ull),
\t\t\tstatic_cast<unsigned long long>(desc.MissShaderTable.StartAddress % 64ull),
\t\t\tstatic_cast<unsigned long long>(desc.MissShaderTable.StrideInBytes % 32ull),
\t\t\tstatic_cast<unsigned long long>(desc.HitGroupTable.StartAddress % 64ull),
\t\t\tstatic_cast<unsigned long long>(desc.HitGroupTable.StrideInBytes % 32ull),
\t\t\tstatic_cast<unsigned long long>(desc.CallableShaderTable.StartAddress % 64ull),
\t\t\tstatic_cast<unsigned long long>(desc.CallableShaderTable.StrideInBytes % 32ull),
\t\t\traw_hex);
\t}

\tvoid v35_trace_candidate_copy(
\t\tconst char *producer,
\t\tID3D12Resource *destination,
\t\tUINT64 destination_offset,
\t\tID3D12Resource *source,
\t\tUINT64 source_offset,
\t\tUINT64 copied_bytes)
\t{
\t\tif (destination == nullptr || source == nullptr)
\t\t\treturn;

\t\tconst D3D12_RESOURCE_DESC destination_desc = destination->GetDesc();
\t\tif (destination_desc.Dimension != D3D12_RESOURCE_DIMENSION_BUFFER ||
\t\t\tdestination_desc.Width != v35_dispatch_record_bytes ||
\t\t\tdestination_offset != 0 ||
\t\t\tcopied_bytes < v35_dispatch_record_bytes)
\t\t\treturn;

\t\tconst uint64_t candidate_index = ++s_v35_copy_candidate_total;
\t\tD3D12_HEAP_PROPERTIES destination_properties = {};
\t\tD3D12_HEAP_FLAGS destination_flags = D3D12_HEAP_FLAG_NONE;
\t\tconst HRESULT destination_heap_hr = destination->GetHeapProperties(
\t\t\t&destination_properties, &destination_flags);
\t\tD3D12_HEAP_PROPERTIES source_properties = {};
\t\tD3D12_HEAP_FLAGS source_flags = D3D12_HEAP_FLAG_NONE;
\t\tconst HRESULT source_heap_hr = source->GetHeapProperties(
\t\t\t&source_properties, &source_flags);

\t\tconst D3D12_RESOURCE_DESC source_desc = source->GetDesc();
\t\treshade::log::message(
\t\t\treshade::log::level::info,
\t\t\t"D3DMetal RTX dispatch-record producer trace v35: COPY_CANDIDATE producer=%s candidate_index=%llu dst=%p dst_gpu_va=0x%llX dst_width=%llu dst_offset=%llu dst_heap_hr=%s dst_heap_raw=0x%08X dst_heap=%u src=%p src_gpu_va=0x%llX src_width=%llu src_offset=%llu src_heap_hr=%s src_heap_raw=0x%08X src_heap=%u copied_bytes=%llu.",
\t\t\tproducer,
\t\t\tstatic_cast<unsigned long long>(candidate_index),
\t\t\tdestination,
\t\t\tstatic_cast<unsigned long long>(destination->GetGPUVirtualAddress()),
\t\t\tstatic_cast<unsigned long long>(destination_desc.Width),
\t\t\tstatic_cast<unsigned long long>(destination_offset),
\t\t\treshade::log::hr_to_string(destination_heap_hr).c_str(),
\t\t\tstatic_cast<uint32_t>(destination_heap_hr),
\t\t\tSUCCEEDED(destination_heap_hr) ? static_cast<unsigned int>(destination_properties.Type) : 0u,
\t\t\tsource,
\t\t\tstatic_cast<unsigned long long>(source->GetGPUVirtualAddress()),
\t\t\tstatic_cast<unsigned long long>(source_desc.Width),
\t\t\tstatic_cast<unsigned long long>(source_offset),
\t\t\treshade::log::hr_to_string(source_heap_hr).c_str(),
\t\t\tstatic_cast<uint32_t>(source_heap_hr),
\t\t\tSUCCEEDED(source_heap_hr) ? static_cast<unsigned int>(source_properties.Type) : 0u,
\t\t\tstatic_cast<unsigned long long>(copied_bytes));

\t\tif (FAILED(source_heap_hr) || source_properties.Type != D3D12_HEAP_TYPE_UPLOAD)
\t\t\treturn;
\t\tif (source_desc.Dimension != D3D12_RESOURCE_DIMENSION_BUFFER ||
\t\t\tsource_offset > source_desc.Width ||
\t\t\tv35_dispatch_record_bytes > source_desc.Width - source_offset)
\t\t\treturn;
\t\tif (++s_v35_upload_map_attempt_total > v35_max_upload_capture_attempts)
\t\t\treturn;

\t\tvoid *mapped = nullptr;
\t\tD3D12_RANGE read_range = {
\t\t\tstatic_cast<SIZE_T>(source_offset),
\t\t\tstatic_cast<SIZE_T>(source_offset + v35_dispatch_record_bytes)};
\t\tconst HRESULT map_hr = source->Map(0, &read_range, &mapped);
\t\tif (FAILED(map_hr) || mapped == nullptr)
\t\t{
\t\t\treshade::log::message(
\t\t\t\treshade::log::level::warning,
\t\t\t\t"D3DMetal RTX dispatch-record producer trace v35: UPLOAD_MAP_FAILED candidate_index=%llu hr=%s raw=0x%08X src=%p src_offset=%llu.",
\t\t\t\tstatic_cast<unsigned long long>(candidate_index),
\t\t\t\treshade::log::hr_to_string(map_hr).c_str(),
\t\t\t\tstatic_cast<uint32_t>(map_hr),
\t\t\t\tsource,
\t\t\t\tstatic_cast<unsigned long long>(source_offset));
\t\t\treturn;
\t\t}

\t\tunsigned char bytes[v35_dispatch_record_bytes] = {};
\t\tmemcpy(
\t\t\tbytes,
\t\t\tstatic_cast<const unsigned char *>(mapped) + source_offset,
\t\t\tstatic_cast<size_t>(v35_dispatch_record_bytes));
\t\tD3D12_RANGE written_range = {0, 0};
\t\tsource->Unmap(0, &written_range);

\t\tv35_log_dispatch_record(
\t\t\tproducer,
\t\t\tcandidate_index,
\t\t\tdestination,
\t\t\tdestination_offset,
\t\t\tsource,
\t\t\tsource_offset,
\t\t\tcopied_bytes,
\t\t\tSUCCEEDED(destination_heap_hr) ? destination_properties.Type : static_cast<D3D12_HEAP_TYPE>(0),
\t\t\tsource_properties.Type,
\t\t\tbytes);
\t}

\tvoid STDMETHODCALLTYPE v35_trace_copy_buffer_region(
\t\tID3D12GraphicsCommandList *command_list,
\t\tID3D12Resource *destination,
\t\tUINT64 destination_offset,
\t\tID3D12Resource *source,
\t\tUINT64 source_offset,
\t\tUINT64 copied_bytes)
\t{
\t\tv35_trace_candidate_copy(
\t\t\t"CopyBufferRegion",
\t\t\tdestination,
\t\t\tdestination_offset,
\t\t\tsource,
\t\t\tsource_offset,
\t\t\tcopied_bytes);
\t\tif (s_v35_original_copy_buffer_region != nullptr)
\t\t\ts_v35_original_copy_buffer_region(
\t\t\t\tcommand_list,
\t\t\t\tdestination,
\t\t\t\tdestination_offset,
\t\t\t\tsource,
\t\t\t\tsource_offset,
\t\t\t\tcopied_bytes);
\t}

\tvoid STDMETHODCALLTYPE v35_trace_copy_resource(
\t\tID3D12GraphicsCommandList *command_list,
\t\tID3D12Resource *destination,
\t\tID3D12Resource *source)
\t{
\t\tUINT64 copied_bytes = 0;
\t\tif (destination != nullptr)
\t\t\tcopied_bytes = destination->GetDesc().Width;
\t\tv35_trace_candidate_copy(
\t\t\t"CopyResource",
\t\t\tdestination,
\t\t\t0,
\t\t\tsource,
\t\t\t0,
\t\t\tcopied_bytes);
\t\tif (s_v35_original_copy_resource != nullptr)
\t\t\ts_v35_original_copy_resource(command_list, destination, source);
\t}

\tvoid v35_install_copy_hooks(ID3D12GraphicsCommandList4 *command_list)
\t{
\t\tif (command_list == nullptr)
\t\t\treturn;

\t\tvoid **const vtable = *reinterpret_cast<void ***>(command_list);
\t\tstd::call_once(
\t\t\ts_v35_copy_buffer_hook_once,
\t\t\t[vtable]()
\t\t\t{
\t\t\t\tvoid *const current = vtable[v35_copy_buffer_region_slot];
\t\t\t\ts_v35_original_copy_buffer_region =
\t\t\t\t\treinterpret_cast<v35_copy_buffer_region_fn>(current);
\t\t\t\tDWORD old_protect = 0;
\t\t\t\tbool installed = false;
\t\t\t\tif (VirtualProtect(
\t\t\t\t\t&vtable[v35_copy_buffer_region_slot],
\t\t\t\t\tsizeof(void *), PAGE_EXECUTE_READWRITE, &old_protect))
\t\t\t\t{
\t\t\t\t\tInterlockedExchangePointer(
\t\t\t\t\t\treinterpret_cast<PVOID volatile *>(
\t\t\t\t\t\t\t&vtable[v35_copy_buffer_region_slot]),
\t\t\t\t\t\treinterpret_cast<PVOID>(&v35_trace_copy_buffer_region));
\t\t\t\t\tDWORD ignored = 0;
\t\t\t\t\tVirtualProtect(
\t\t\t\t\t\t&vtable[v35_copy_buffer_region_slot],
\t\t\t\t\t\tsizeof(void *), old_protect, &ignored);
\t\t\t\t\tFlushInstructionCache(
\t\t\t\t\t\tGetCurrentProcess(),
\t\t\t\t\t\t&vtable[v35_copy_buffer_region_slot],
\t\t\t\t\t\tsizeof(void *));
\t\t\t\t\tinstalled = vtable[v35_copy_buffer_region_slot] ==
\t\t\t\t\t\treinterpret_cast<void *>(&v35_trace_copy_buffer_region);
\t\t\t\t}
\t\t\t\treshade::log::message(
\t\t\t\t\tinstalled ? reshade::log::level::info : reshade::log::level::warning,
\t\t\t\t\t"D3DMetal RTX dispatch-record producer trace v35: COPY_BUFFER_HOOK installed=%u slot=%zu original=%p replacement=%p.",
\t\t\t\t\tinstalled ? 1u : 0u,
\t\t\t\t\tv35_copy_buffer_region_slot,
\t\t\t\t\treinterpret_cast<void *>(s_v35_original_copy_buffer_region),
\t\t\t\t\treinterpret_cast<void *>(&v35_trace_copy_buffer_region));
\t\t\t\tif (!installed)
\t\t\t\t\ts_v35_original_copy_buffer_region = nullptr;
\t\t\t});

\t\tstd::call_once(
\t\t\ts_v35_copy_resource_hook_once,
\t\t\t[vtable]()
\t\t\t{
\t\t\t\tvoid *const current = vtable[v35_copy_resource_slot];
\t\t\t\ts_v35_original_copy_resource =
\t\t\t\t\treinterpret_cast<v35_copy_resource_fn>(current);
\t\t\t\tDWORD old_protect = 0;
\t\t\t\tbool installed = false;
\t\t\t\tif (VirtualProtect(
\t\t\t\t\t&vtable[v35_copy_resource_slot],
\t\t\t\t\tsizeof(void *), PAGE_EXECUTE_READWRITE, &old_protect))
\t\t\t\t{
\t\t\t\t\tInterlockedExchangePointer(
\t\t\t\t\t\treinterpret_cast<PVOID volatile *>(
\t\t\t\t\t\t\t&vtable[v35_copy_resource_slot]),
\t\t\t\t\t\treinterpret_cast<PVOID>(&v35_trace_copy_resource));
\t\t\t\t\tDWORD ignored = 0;
\t\t\t\t\tVirtualProtect(
\t\t\t\t\t\t&vtable[v35_copy_resource_slot],
\t\t\t\t\t\tsizeof(void *), old_protect, &ignored);
\t\t\t\t\tFlushInstructionCache(
\t\t\t\t\t\tGetCurrentProcess(),
\t\t\t\t\t\t&vtable[v35_copy_resource_slot],
\t\t\t\t\t\tsizeof(void *));
\t\t\t\t\tinstalled = vtable[v35_copy_resource_slot] ==
\t\t\t\t\t\treinterpret_cast<void *>(&v35_trace_copy_resource);
\t\t\t\t}
\t\t\t\treshade::log::message(
\t\t\t\t\tinstalled ? reshade::log::level::info : reshade::log::level::warning,
\t\t\t\t\t"D3DMetal RTX dispatch-record producer trace v35: COPY_RESOURCE_HOOK installed=%u slot=%zu original=%p replacement=%p.",
\t\t\t\t\tinstalled ? 1u : 0u,
\t\t\t\t\tv35_copy_resource_slot,
\t\t\t\t\treinterpret_cast<void *>(s_v35_original_copy_resource),
\t\t\t\t\treinterpret_cast<void *>(&v35_trace_copy_resource));
\t\t\t\tif (!installed)
\t\t\t\t\ts_v35_original_copy_resource = nullptr;
\t\t\t});
\t}
'''
text = text.replace(helper_anchor, helper + "\n" + helper_anchor, 1)

install_old = "\t\tv34_install_execute_indirect_hook(list4);\n\n"
install_new = (
    "\t\tv34_install_execute_indirect_hook(list4);\n"
    "\t\tv35_install_copy_hooks(list4);\n\n"
)
text = replace_once(text, install_old, install_new, "V35 copy hook installation")

required = [
    "D3DMetal RTX dispatch-record producer trace v35:",
    "STATE_IDENTIFIERS call=",
    "COPY_BUFFER_HOOK installed=",
    "COPY_RESOURCE_HOOK installed=",
    "COPY_CANDIDATE producer=",
    "DISPATCH_DESC_CAPTURE producer=",
    "raygen_start=0x",
    "raw=%s",
    "v35_install_copy_hooks(list4);",
    "v35_copy_buffer_region_slot = 15",
    "v35_copy_resource_slot = 17",
]
for marker in required:
    if marker not in text:
        raise RuntimeError(f"Missing V35 source marker: {marker}")

SOURCE.write_text(text, encoding="utf-8", newline="\n")

report = Path("v35-patch-report.txt")
report.write_text(
    "\n".join([
        "V35_DISPATCH_RECORD_PRODUCER_TRACE_PATCH_OK",
        "V34_INDIRECT_RAY_TRACE_PRESERVED=YES",
        "COPY_BUFFER_REGION_SLOT=15",
        "COPY_RESOURCE_SLOT=17",
        "TARGET_DESTINATION_WIDTH=104",
        "UPLOAD_SOURCE_MAP_LIMIT=64",
        "DISPATCH_RAYS_DESC_DECODER=ENABLED",
        "STATE_OBJECT_IDENTIFIER_HEX_LOGGING=ENABLED",
        "COPY_COMMANDS_UNMODIFIED=YES",
        "RESOURCE_CONTENTS_UNMODIFIED=YES",
        "EXECUTE_INDIRECT_UNMODIFIED=YES",
        "RESULT=PASS",
        "",
    ]),
    encoding="utf-8",
    newline="\n",
)
print(report.read_text(encoding="utf-8"))
