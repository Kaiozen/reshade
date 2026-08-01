from pathlib import Path

SOURCE = Path("source/d3d12/d3d12.cpp")
if not SOURCE.is_file():
    raise RuntimeError(f"Missing source file: {SOURCE}")

text = SOURCE.read_text(encoding="utf-8-sig")
for marker in (
    "D3DMetal RTX execution trace v33:",
    "D3DMetal RTX live shader-table readback v39:",
    "D3DMetal RTX steady-state local-root resolution v56:",
):
    if marker not in text:
        raise RuntimeError(f"V57 prerequisite is missing: {marker}")

if "D3DMetal RTX shader-table resource recovery v57:" in text:
    raise RuntimeError("V57 is already present")


def replace_once(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 occurrence, found {count}")
    return source.replace(old, new, 1)


type_anchor = "\tconstexpr size_t v33_create_command_list_slot = 12;\n"
type_insert = r'''	using v57_copy_buffer_region_fn = void (STDMETHODCALLTYPE *)(
		ID3D12GraphicsCommandList *,
		ID3D12Resource *,
		UINT64,
		ID3D12Resource *,
		UINT64,
		UINT64);

	using v57_resource_map_fn = HRESULT (STDMETHODCALLTYPE *)(
		ID3D12Resource *,
		UINT,
		const D3D12_RANGE *,
		void **);

	constexpr size_t v57_copy_buffer_region_slot = 15;
	constexpr size_t v57_resource_map_slot = 8;
	constexpr UINT64 v57_max_recovery_buffer_bytes = 16ull * 1024ull * 1024ull;

	void v57_install_resource_map_hook(ID3D12Resource *resource);
	void v39_track_resource(void *created);

'''
text = replace_once(text, type_anchor, type_insert + type_anchor, "V57 type anchor")

static_anchor = "\tstatic std::once_flag s_v33_device_hook_once;\n"
static_insert = r'''	static v57_copy_buffer_region_fn s_v57_original_copy_buffer_region = nullptr;
	static std::mutex s_v57_map_hook_mutex;
	static std::unordered_map<void **, v57_resource_map_fn> s_v57_original_map_by_vtable;
	static std::mutex s_v57_recovery_mutex;
	static std::unordered_map<UINT64, UINT64> s_v57_recovered_buffer_bases;
	static std::atomic<uint64_t> s_v57_copy_buffer_calls = 0;
	static std::atomic<uint64_t> s_v57_map_calls = 0;
	static std::atomic<uint64_t> s_v57_recovered_resources = 0;
	static std::atomic<bool> s_v57_copy_hook_installed = false;
	static std::atomic<bool> s_v57_any_map_hook_installed = false;

'''
text = replace_once(text, static_anchor, static_insert + static_anchor, "V57 static anchor")

hook_anchor = "\tvoid v33_install_command_list_method_hooks(IUnknown *command_list)\n"
hook_code = r'''	bool v57_track_candidate_buffer(ID3D12Resource *resource, const char *source)
	{
		if (resource == nullptr)
			return false;

		const D3D12_RESOURCE_DESC desc = resource->GetDesc();
		const D3D12_GPU_VIRTUAL_ADDRESS base = resource->GetGPUVirtualAddress();
		if (desc.Dimension != D3D12_RESOURCE_DIMENSION_BUFFER ||
			desc.Width == 0 ||
			desc.Width > v57_max_recovery_buffer_bytes ||
			base == 0)
			return false;

		bool inserted = false;
		{
			std::lock_guard<std::mutex> lock(s_v57_recovery_mutex);
			const auto found = s_v57_recovered_buffer_bases.find(
				static_cast<UINT64>(base));
			if (found == s_v57_recovered_buffer_bases.end())
			{
				s_v57_recovered_buffer_bases[
					static_cast<UINT64>(base)] = desc.Width;
				inserted = true;
			}
		}

		if (!inserted)
			return false;

		v39_track_resource(resource);
		const uint64_t recovered_index = ++s_v57_recovered_resources;
		if (recovered_index <= 128)
		{
			reshade::log::message(
				reshade::log::level::info,
				"D3DMetal RTX shader-table resource recovery v57: RESOURCE_RECOVERED index=%llu source=%s resource=%p gpu_va=0x%llX width=%llu max_width=%llu.",
				static_cast<unsigned long long>(recovered_index),
				source != nullptr ? source : "unknown",
				resource,
				static_cast<unsigned long long>(base),
				static_cast<unsigned long long>(desc.Width),
				static_cast<unsigned long long>(
					v57_max_recovery_buffer_bytes));
		}
		return true;
	}

	HRESULT STDMETHODCALLTYPE v57_trace_resource_map(
		ID3D12Resource *resource,
		UINT subresource,
		const D3D12_RANGE *read_range,
		void **data)
	{
		++s_v57_map_calls;
		v57_resource_map_fn original = nullptr;
		if (resource != nullptr)
		{
			void **const vtable = *reinterpret_cast<void ***>(resource);
			std::lock_guard<std::mutex> lock(s_v57_map_hook_mutex);
			const auto found = s_v57_original_map_by_vtable.find(vtable);
			if (found != s_v57_original_map_by_vtable.end())
				original = found->second;
		}

		if (original == nullptr)
			return E_FAIL;

		const HRESULT hr = original(resource, subresource, read_range, data);
		if (SUCCEEDED(hr))
			v57_track_candidate_buffer(resource, "resource-map");
		return hr;
	}

	void v57_install_resource_map_hook(ID3D12Resource *resource)
	{
		if (resource == nullptr)
			return;

		void **const vtable = *reinterpret_cast<void ***>(resource);
		{
			std::lock_guard<std::mutex> lock(s_v57_map_hook_mutex);
			if (s_v57_original_map_by_vtable.find(vtable) !=
				s_v57_original_map_by_vtable.end())
				return;
		}

		void *const current = vtable[v57_resource_map_slot];
		if (current == reinterpret_cast<void *>(&v57_trace_resource_map))
			return;

		DWORD old_protect = 0;
		if (!VirtualProtect(
			&vtable[v57_resource_map_slot],
			sizeof(void *),
			PAGE_EXECUTE_READWRITE,
			&old_protect))
			return;

		{
			std::lock_guard<std::mutex> lock(s_v57_map_hook_mutex);
			s_v57_original_map_by_vtable[vtable] =
				reinterpret_cast<v57_resource_map_fn>(current);
		}

		InterlockedExchangePointer(
			reinterpret_cast<PVOID volatile *>(
				&vtable[v57_resource_map_slot]),
			reinterpret_cast<PVOID>(&v57_trace_resource_map));

		DWORD ignored = 0;
		VirtualProtect(
			&vtable[v57_resource_map_slot],
			sizeof(void *),
			old_protect,
			&ignored);
		FlushInstructionCache(
			GetCurrentProcess(),
			&vtable[v57_resource_map_slot],
			sizeof(void *));

		const bool installed =
			vtable[v57_resource_map_slot] ==
				reinterpret_cast<void *>(&v57_trace_resource_map);
		if (installed)
			s_v57_any_map_hook_installed.store(
				true, std::memory_order_release);

		reshade::log::message(
			installed ?
				reshade::log::level::info :
				reshade::log::level::warning,
			"D3DMetal RTX shader-table resource recovery v57: RESOURCE_MAP_HOOK installed=%u vtable=%p slot=%zu original=%p replacement=%p.",
			installed ? 1u : 0u,
			vtable,
			v57_resource_map_slot,
			current,
			reinterpret_cast<void *>(&v57_trace_resource_map));
	}

	void STDMETHODCALLTYPE v57_trace_copy_buffer_region(
		ID3D12GraphicsCommandList *command_list,
		ID3D12Resource *destination_buffer,
		UINT64 destination_offset,
		ID3D12Resource *source_buffer,
		UINT64 source_offset,
		UINT64 bytes)
	{
		++s_v57_copy_buffer_calls;
		v57_track_candidate_buffer(destination_buffer, "copy-destination");
		v57_track_candidate_buffer(source_buffer, "copy-source");

		if (s_v57_original_copy_buffer_region != nullptr)
			s_v57_original_copy_buffer_region(
				command_list,
				destination_buffer,
				destination_offset,
				source_buffer,
				source_offset,
				bytes);
	}

'''
text = replace_once(text, hook_anchor, hook_code + hook_anchor, "V57 hook helper anchor")

track_anchor = '''        if (FAILED(qi_hr) || resource == nullptr)
            return;

        const D3D12_RESOURCE_DESC desc = resource->GetDesc();
'''
track_replacement = '''        if (FAILED(qi_hr) || resource == nullptr)
            return;

        v57_install_resource_map_hook(resource);

        const D3D12_RESOURCE_DESC desc = resource->GetDesc();
'''
text = replace_once(text, track_anchor, track_replacement, "V57 V39 map hook install")

current_anchor = '''		void *const current_dispatch =
			vtable[v33_dispatch_rays_slot];
'''
current_replacement = current_anchor + '''		void *const current_copy_buffer =
			vtable[v57_copy_buffer_region_slot];
'''
text = replace_once(text, current_anchor, current_replacement, "V57 current CopyBufferRegion")

original_anchor = '''		s_v33_original_dispatch_rays =
			reinterpret_cast<v33_dispatch_rays_fn>(current_dispatch);

'''
original_replacement = original_anchor + '''		s_v57_original_copy_buffer_region =
			reinterpret_cast<v57_copy_buffer_region_fn>(
				current_copy_buffer);

'''
text = replace_once(text, original_anchor, original_replacement, "V57 original CopyBufferRegion")

log_anchor = '''		reshade::log::message(
			verified ?
'''
copy_install = r'''		bool v57_copy_verified = false;
		if (verified)
		{
			DWORD copy_old_protect = 0;
			const bool copy_protected = VirtualProtect(
				&vtable[v57_copy_buffer_region_slot],
				sizeof(void *),
				PAGE_EXECUTE_READWRITE,
				&copy_old_protect) != FALSE;
			if (copy_protected)
			{
				InterlockedExchangePointer(
					reinterpret_cast<PVOID volatile *>(
						&vtable[v57_copy_buffer_region_slot]),
					reinterpret_cast<PVOID>(
						&v57_trace_copy_buffer_region));
				DWORD copy_ignored = 0;
				VirtualProtect(
					&vtable[v57_copy_buffer_region_slot],
					sizeof(void *),
					copy_old_protect,
					&copy_ignored);
				FlushInstructionCache(
					GetCurrentProcess(),
					&vtable[v57_copy_buffer_region_slot],
					sizeof(void *));
			}
			v57_copy_verified =
				vtable[v57_copy_buffer_region_slot] ==
					reinterpret_cast<void *>(
						&v57_trace_copy_buffer_region);
			s_v57_copy_hook_installed.store(
				v57_copy_verified, std::memory_order_release);
		}

		reshade::log::message(
			v57_copy_verified ?
				reshade::log::level::info :
				reshade::log::level::warning,
			"D3DMetal RTX shader-table resource recovery v57: COPY_BUFFER_REGION_HOOK installed=%u slot=%zu original=%p replacement=%p.",
			v57_copy_verified ? 1u : 0u,
			v57_copy_buffer_region_slot,
			reinterpret_cast<void *>(
				s_v57_original_copy_buffer_region),
			reinterpret_cast<void *>(
				&v57_trace_copy_buffer_region));

'''
text = replace_once(text, log_anchor, copy_install + log_anchor, "V57 CopyBufferRegion install")

failure_old = '''"D3DMetal RTX live shader-table readback v39: SHADER_TABLE_CAPTURE recorded=0 reason=resource_lookup raygen=%u miss=%u hit=%u callable=%u tracked=%zu.",'''
failure_new = '''"D3DMetal RTX live shader-table readback v39: SHADER_TABLE_CAPTURE recorded=0 reason=resource_lookup raygen=%u miss=%u hit=%u callable=%u tracked=%zu v57_recovered=%llu v57_copy_calls=%llu v57_map_calls=%llu.",'''
text = replace_once(text, failure_old, failure_new, "V57 V39 failure format")

failure_args_old = '''                raygen_found ? 1u : 0u, miss_found ? 1u : 0u, hit_found ? 1u : 0u, callable_found ? 1u : 0u,
                s_v39_buffer_records.size());'''
failure_args_new = '''                raygen_found ? 1u : 0u, miss_found ? 1u : 0u, hit_found ? 1u : 0u, callable_found ? 1u : 0u,
                s_v39_buffer_records.size(),
                static_cast<unsigned long long>(
                    s_v57_recovered_resources.load(std::memory_order_acquire)),
                static_cast<unsigned long long>(
                    s_v57_copy_buffer_calls.load(std::memory_order_acquire)),
                static_cast<unsigned long long>(
                    s_v57_map_calls.load(std::memory_order_acquire)));'''
text = replace_once(text, failure_args_old, failure_args_new, "V57 V39 failure arguments")

required = [
    "D3DMetal RTX shader-table resource recovery v57:",
    "COPY_BUFFER_REGION_HOOK installed=",
    "RESOURCE_MAP_HOOK installed=",
    "RESOURCE_RECOVERED index=",
    "v57_copy_buffer_region_slot = 15",
    "v57_resource_map_slot = 8",
    "v57_install_resource_map_hook(resource);",
    "v57_trace_copy_buffer_region",
    "v57_trace_resource_map",
    "v57_recovered=",
]
for marker in required:
    if marker not in text:
        raise RuntimeError(f"Missing V57 source marker: {marker}")


map_hook_declaration = (
    "\tvoid v57_install_resource_map_hook("
    "ID3D12Resource *resource);\n"
)
map_hook_call = "\t\tv57_install_resource_map_hook(resource);\n"
map_hook_definition = (
    "\tvoid v57_install_resource_map_hook("
    "ID3D12Resource *resource)\n"
)

if text.count(map_hook_declaration) != 1:
    raise RuntimeError(
        "V57 resource-map hook forward declaration count is not exactly one")
if text.count(map_hook_call) != 1:
    raise RuntimeError(
        "V57 resource-map hook call count is not exactly one")
if text.count(map_hook_definition) != 1:
    raise RuntimeError(
        "V57 resource-map hook definition count is not exactly one")

declaration_position = text.find(map_hook_declaration)
call_position = text.find(map_hook_call)
definition_position = text.find(map_hook_definition)
if not (
    declaration_position >= 0 and
    call_position > declaration_position and
    definition_position > declaration_position
):
    raise RuntimeError(
        "V57 resource-map hook declaration ordering is invalid: "
        f"declaration={declaration_position} "
        f"call={call_position} "
        f"definition={definition_position}")

SOURCE.write_text(text, encoding="utf-8", newline="\n")

report = Path("v57-patch-report.txt")
report.write_text("\n".join([
    "V57_SHADER_TABLE_RESOURCE_RECOVERY_PATCH_OK",
    "BASELINE=V56_STEADY_STATE_LOCAL_ROOT_RESOLUTION",
    "COPY_BUFFER_REGION_SLOT=15",
    "RESOURCE_MAP_SLOT=8",
    "RESOURCE_MAP_HOOK_FORWARD_DECLARATION=YES",
    "COPY_DESTINATION_RESOURCE_TRACKING=ENABLED",
    "COPY_SOURCE_RESOURCE_TRACKING=ENABLED",
    "MAPPED_RESOURCE_TRACKING=ENABLED",
    "RECOVERY_BUFFER_MAX_BYTES=16777216",
    "RECOVERY_DEDUPLICATION=GPU_VIRTUAL_ADDRESS",
    "V39_RESOURCE_LOOKUP_INPUTS=RECOVERED_BEFORE_CAPTURE",
    "SHADERS_MODIFIED_BY_V57=NO",
    "DESCRIPTORS_MODIFIED_BY_V57=NO",
    "RESOURCES_MODIFIED_BY_V57=NO",
    "COPY_COMMANDS_MODIFIED_BY_V57=NO",
    "DISPATCH_ARGUMENTS_MODIFIED_BY_V57=NO",
    "RESULT=PASS",
    "",
]), encoding="utf-8", newline="\n")
print(report.read_text(encoding="utf-8"))
