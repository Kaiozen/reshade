from pathlib import Path

SOURCE = Path("source/d3d12/d3d12.cpp")
if not SOURCE.is_file():
    raise RuntimeError(f"Missing source file: {SOURCE}")

text = SOURCE.read_text(encoding="utf-8-sig")

for marker in (
    "D3DMetal RTX live shader-table readback v39:",
    "D3DMetal RTX steady-state local-root resolution v56:",
    "D3DMetal RTX shader-table resource recovery v57:",
):
    if marker not in text:
        raise RuntimeError(f"V58 prerequisite is missing: {marker}")

if "D3DMetal RTX live GPU-VA relocation tracking v58:" in text:
    raise RuntimeError("V58 is already present")


def replace_once(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 occurrence, found {count}")
    return source.replace(old, new, 1)


type_anchor = "\tconstexpr size_t v57_copy_buffer_region_slot = 15;\n"
type_insert = r'''	using v58_get_gpu_virtual_address_fn =
		D3D12_GPU_VIRTUAL_ADDRESS (STDMETHODCALLTYPE *)(
			ID3D12Resource *);

	struct v58_resource_va_state
	{
		UINT64 address = 0;
		UINT64 width = 0;
	};

	constexpr size_t v58_get_gpu_virtual_address_slot = 11;
	constexpr UINT64 v58_max_tracked_buffer_bytes =
		64ull * 1024ull * 1024ull;

'''
text = replace_once(
    text, type_anchor, type_insert + type_anchor, "V58 type insertion")

declaration_anchor = (
    "\tvoid v57_install_resource_map_hook(ID3D12Resource *resource);\n"
)
declaration_insert = r'''	void v58_record_current_gpu_va(
		ID3D12Resource *resource,
		D3D12_GPU_VIRTUAL_ADDRESS address,
		const char *source);
	void v58_install_gpu_va_hook(ID3D12Resource *resource);
'''
text = replace_once(
    text,
    declaration_anchor,
    declaration_insert + declaration_anchor,
    "V58 forward declarations",
)

static_anchor = (
    "\tstatic v57_copy_buffer_region_fn "
    "s_v57_original_copy_buffer_region = nullptr;\n"
)
static_insert = r'''	static std::mutex s_v58_gpu_va_hook_mutex;
	static std::unordered_map<
		void **,
		v58_get_gpu_virtual_address_fn>
		s_v58_original_gpu_va_by_vtable;
	static std::mutex s_v58_gpu_va_state_mutex;
	static std::unordered_map<
		ID3D12Resource *,
		v58_resource_va_state>
		s_v58_last_gpu_va_by_resource;
	static std::atomic<uint64_t> s_v58_gpu_va_calls = 0;
	static std::atomic<uint64_t> s_v58_gpu_va_transitions = 0;
	static std::atomic<uint64_t> s_v58_gpu_va_hook_count = 0;

'''
text = replace_once(
    text, static_anchor, static_insert + static_anchor, "V58 static state")

hook_anchor = (
    "\tbool v57_track_candidate_buffer("
    "ID3D12Resource *resource, const char *source)\n"
)
hook_code = r'''	D3D12_GPU_VIRTUAL_ADDRESS STDMETHODCALLTYPE
	v58_trace_get_gpu_virtual_address(ID3D12Resource *resource)
	{
		++s_v58_gpu_va_calls;

		v58_get_gpu_virtual_address_fn original = nullptr;
		if (resource != nullptr)
		{
			void **const vtable =
				*reinterpret_cast<void ***>(resource);
			std::lock_guard<std::mutex> lock(
				s_v58_gpu_va_hook_mutex);
			const auto found =
				s_v58_original_gpu_va_by_vtable.find(vtable);
			if (found !=
				s_v58_original_gpu_va_by_vtable.end())
				original = found->second;
		}

		if (original == nullptr)
			return 0;

		const D3D12_GPU_VIRTUAL_ADDRESS address =
			original(resource);
		if (address != 0)
			v58_record_current_gpu_va(
				resource,
				address,
				"GetGPUVirtualAddress");
		return address;
	}

	void v58_install_gpu_va_hook(ID3D12Resource *resource)
	{
		if (resource == nullptr)
			return;

		void **const vtable =
			*reinterpret_cast<void ***>(resource);

		{
			std::lock_guard<std::mutex> lock(
				s_v58_gpu_va_hook_mutex);
			if (s_v58_original_gpu_va_by_vtable.find(vtable) !=
				s_v58_original_gpu_va_by_vtable.end())
				return;
		}

		void *const current =
			vtable[v58_get_gpu_virtual_address_slot];
		if (current ==
			reinterpret_cast<void *>(
				&v58_trace_get_gpu_virtual_address))
			return;

		DWORD old_protect = 0;
		if (!VirtualProtect(
			&vtable[v58_get_gpu_virtual_address_slot],
			sizeof(void *),
			PAGE_EXECUTE_READWRITE,
			&old_protect))
			return;

		{
			std::lock_guard<std::mutex> lock(
				s_v58_gpu_va_hook_mutex);
			s_v58_original_gpu_va_by_vtable[vtable] =
				reinterpret_cast<
					v58_get_gpu_virtual_address_fn>(
						current);
		}

		InterlockedExchangePointer(
			reinterpret_cast<PVOID volatile *>(
				&vtable[
					v58_get_gpu_virtual_address_slot]),
			reinterpret_cast<PVOID>(
				&v58_trace_get_gpu_virtual_address));

		DWORD ignored = 0;
		VirtualProtect(
			&vtable[v58_get_gpu_virtual_address_slot],
			sizeof(void *),
			old_protect,
			&ignored);
		FlushInstructionCache(
			GetCurrentProcess(),
			&vtable[v58_get_gpu_virtual_address_slot],
			sizeof(void *));

		const bool installed =
			vtable[v58_get_gpu_virtual_address_slot] ==
			reinterpret_cast<void *>(
				&v58_trace_get_gpu_virtual_address);

		if (installed)
			++s_v58_gpu_va_hook_count;

		reshade::log::message(
			installed ?
				reshade::log::level::info :
				reshade::log::level::warning,
			"D3DMetal RTX live GPU-VA relocation tracking v58: GPU_VA_HOOK installed=%u vtable=%p slot=%zu original=%p replacement=%p hook_count=%llu.",
			installed ? 1u : 0u,
			vtable,
			v58_get_gpu_virtual_address_slot,
			current,
			reinterpret_cast<void *>(
				&v58_trace_get_gpu_virtual_address),
			static_cast<unsigned long long>(
				s_v58_gpu_va_hook_count.load(
					std::memory_order_acquire)));
	}

'''
text = replace_once(
    text, hook_anchor, hook_code + hook_anchor, "V58 hook functions")

track_anchor = '''        v57_install_resource_map_hook(resource);

        const D3D12_RESOURCE_DESC desc = resource->GetDesc();
'''
track_replacement = '''        v57_install_resource_map_hook(resource);
        v58_install_gpu_va_hook(resource);

        const D3D12_RESOURCE_DESC desc = resource->GetDesc();
'''
text = replace_once(
    text, track_anchor, track_replacement, "V58 install from V39 tracker")

record_anchor = '''    bool v39_find_buffer(
'''
record_helper = r'''    void v58_record_current_gpu_va(
        ID3D12Resource *resource,
        D3D12_GPU_VIRTUAL_ADDRESS address,
        const char *source)
    {
        if (resource == nullptr || address == 0)
            return;

        const D3D12_RESOURCE_DESC desc =
            resource->GetDesc();
        if (desc.Dimension !=
                D3D12_RESOURCE_DIMENSION_BUFFER ||
            desc.Width == 0 ||
            desc.Width >
                v58_max_tracked_buffer_bytes)
            return;

        bool changed = false;
        UINT64 previous_address = 0;
        UINT64 previous_width = 0;

        {
            std::lock_guard<std::mutex> lock(
                s_v58_gpu_va_state_mutex);
            const auto found =
                s_v58_last_gpu_va_by_resource.find(
                    resource);
            if (found ==
                    s_v58_last_gpu_va_by_resource.end() ||
                found->second.address !=
                    static_cast<UINT64>(address) ||
                found->second.width != desc.Width)
            {
                if (found !=
                    s_v58_last_gpu_va_by_resource.end())
                {
                    previous_address =
                        found->second.address;
                    previous_width =
                        found->second.width;
                }

                v58_resource_va_state state = {};
                state.address =
                    static_cast<UINT64>(address);
                state.width = desc.Width;
                s_v58_last_gpu_va_by_resource[
                    resource] = state;
                changed = true;
            }
        }

        if (!changed)
            return;

        D3D12_HEAP_PROPERTIES properties = {};
        D3D12_HEAP_FLAGS flags =
            D3D12_HEAP_FLAG_NONE;
        const HRESULT heap_hr =
            resource->GetHeapProperties(
                &properties,
                &flags);

        v39_buffer_record record = {};
        record.resource = resource;
        record.base = address;
        record.width = desc.Width;
        record.heap_type =
            SUCCEEDED(heap_hr) ?
                properties.Type :
                D3D12_HEAP_TYPE_DEFAULT;
        record.sequence =
            ++s_v39_resource_sequence;

        size_t tracked_count = 0;
        {
            std::lock_guard<std::mutex> lock(
                s_v39_resource_mutex);
            s_v39_buffer_records.push_back(record);
            if (s_v39_buffer_records.size() > 16384)
                s_v39_buffer_records.erase(
                    s_v39_buffer_records.begin(),
                    s_v39_buffer_records.begin() +
                        4096);
            tracked_count =
                s_v39_buffer_records.size();
        }

        const uint64_t transition_index =
            ++s_v58_gpu_va_transitions;
        if (transition_index <= 256)
        {
            reshade::log::message(
                reshade::log::level::info,
                "D3DMetal RTX live GPU-VA relocation tracking v58: GPU_VA_TRANSITION index=%llu source=%s resource=%p previous=0x%llX previous_width=%llu current=0x%llX current_width=%llu heap_type=%u tracked=%zu.",
                static_cast<unsigned long long>(
                    transition_index),
                source != nullptr ?
                    source :
                    "unknown",
                resource,
                static_cast<unsigned long long>(
                    previous_address),
                static_cast<unsigned long long>(
                    previous_width),
                static_cast<unsigned long long>(
                    address),
                static_cast<unsigned long long>(
                    desc.Width),
                static_cast<unsigned>(
                    record.heap_type),
                tracked_count);
        }
    }

'''
text = replace_once(
    text, record_anchor, record_helper + record_anchor, "V58 mapping recorder")

required = (
    "D3DMetal RTX live GPU-VA relocation tracking v58:",
    "GPU_VA_HOOK installed=",
    "GPU_VA_TRANSITION index=",
    "v58_get_gpu_virtual_address_slot = 11",
    "v58_install_gpu_va_hook(resource);",
)
for marker in required:
    if marker not in text:
        raise RuntimeError(f"Missing V58 source marker: {marker}")

declaration = "\tvoid v58_record_current_gpu_va(\n"
call = "\t\t\tv58_record_current_gpu_va(\n"
definition = "    void v58_record_current_gpu_va(\n"

dpos = text.find(declaration)
cpos = text.find(call)
fpos = text.find(definition)
if not (dpos >= 0 and cpos > dpos and fpos > dpos):
    raise RuntimeError(
        f"V58 declaration order invalid: declaration={dpos} call={cpos} definition={fpos}")

SOURCE.write_text(text, encoding="utf-8", newline="\n")

report = Path("v58-patch-report.txt")
report.write_text("\n".join([
    "V58_LIVE_GPU_VA_RELOCATION_PATCH_OK",
    "BASELINE=V57_SHADER_TABLE_RESOURCE_RECOVERY",
    "GET_GPU_VIRTUAL_ADDRESS_SLOT=11",
    "RESOURCE_VTABLE_VARIANT_TRACKING=ENABLED",
    "LIVE_GPU_VA_QUERY_TRACKING=ENABLED",
    "RESOURCE_ADDRESS_CHANGE_TRACKING=ENABLED",
    "LATEST_MAPPING_INSERTED_INTO_V39=YES",
    "MAX_TRACKED_BUFFER_BYTES=67108864",
    "RAYGEN_MISS_CALLABLE_64K_ADJACENCY_TARGET=YES",
    "SHADERS_MODIFIED_BY_V58=NO",
    "DESCRIPTORS_MODIFIED_BY_V58=NO",
    "RESOURCES_MODIFIED_BY_V58=NO",
    "GPU_VA_RESULTS_MODIFIED_BY_V58=NO",
    "COPY_COMMANDS_MODIFIED_BY_V58=NO",
    "DISPATCH_ARGUMENTS_MODIFIED_BY_V58=NO",
    "RESULT=PASS",
    "",
]), encoding="utf-8", newline="\n")
print(report.read_text(encoding="utf-8"))
