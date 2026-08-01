from pathlib import Path

path = Path("source/d3d12/d3d12.cpp")
text = path.read_text(encoding="utf-8")

if "D3DMetal RTX descriptor-resource lineage v49: ACTIVE" not in text:
    raise RuntimeError("V50 requires the V49 descriptor-resource lineage patch")
if "D3DMetal RTX target-UAV exact-base probe v50: ACTIVE" in text:
    raise RuntimeError("V50 is already present")


def replace_once(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    return source.replace(old, new, 1)


def replace_between(source: str, start: str, end: str, replacement: str, label: str) -> str:
    start_at = source.find(start)
    if start_at < 0:
        raise RuntimeError(f"{label}: start marker missing")
    end_at = source.find(end, start_at)
    if end_at < 0:
        raise RuntimeError(f"{label}: end marker missing")
    return source[:start_at] + replacement + source[end_at:]


state_anchor = "\tstatic std::atomic<uint64_t> s_v49_descriptor_copy_count = 0;\n"
state_addition = state_anchor + r'''

	// V50 reduces V49 to one exact resource signature and exact table-base
	// descriptors only. This prevents the old 16-descriptor adjacency scan from
	// producing false lineage and keeps the renderer responsive.
	static std::unordered_map<void *, bool> s_v50_non_target_resources;
	static std::unordered_map<UINT64, SIZE_T> s_v50_gpu_base_cpu_cache;
	static std::atomic<uint64_t> s_v50_target_resource_count = 0;
	static std::atomic<uint64_t> s_v50_target_descriptor_count = 0;
	static std::atomic<uint64_t> s_v50_target_copy_count = 0;
	static std::atomic<uint64_t> s_v50_target_base_bind_count = 0;
	static std::atomic<uint64_t> s_v50_target_barrier_count = 0;
	static std::atomic<uint64_t> s_v50_target_rtv_count = 0;

	bool v50_is_target_resource_desc(const D3D12_RESOURCE_DESC &desc)
	{
		return
			desc.Dimension == D3D12_RESOURCE_DIMENSION_TEXTURE2D &&
			desc.Width == 1024ull &&
			desc.Height == 1024u &&
			desc.DepthOrArraySize == 1u &&
			desc.MipLevels == 11u &&
			desc.Format == DXGI_FORMAT_R32_TYPELESS &&
			(static_cast<unsigned int>(desc.Flags) & 0x5u) == 0x5u;
	}

	bool v50_should_sample(uint64_t event)
	{
		return event <= 16ull ||
			(event != 0ull && (event & (event - 1ull)) == 0ull);
	}
'''
text = replace_once(text, state_anchor, state_addition, "V50 state insertion")

old_active = r'''	void v49_log_active()
	{
		std::call_once(
			s_v49_active_log_once,
			[]()
			{
				reshade::log::message(
					reshade::log::level::info,
					"D3DMetal RTX descriptor-resource lineage v49: ACTIVE descriptor-heaps=1 cbv-srv-uav-rtv-creation=1 descriptor-copy-propagation=1 root-tables=1 direct-root-va=1 render-targets=1 clear-uav-rtv=1 resource-barriers=1 commands-modified=0.");
			});
	}
'''
new_active = r'''	void v49_log_active()
	{
		std::call_once(
			s_v49_active_log_once,
			[]()
			{
				reshade::log::message(
					reshade::log::level::info,
					"D3DMetal RTX target-UAV exact-base probe v50: ACTIVE signature=texture2d-1024x1024-mips11-r32-typeless-flags0x5 table-offset=0 sampled=1 commands-modified=0 forced-process-stop=runner.");
			});
	}
'''
text = replace_once(text, old_active, new_active, "V50 active marker")

register_replacement = r'''	uint64_t v49_register_resource(ID3D12Resource *resource)
	{
		if (resource == nullptr)
			return 0;
		void *const identity = v33_identity_pointer(
			reinterpret_cast<IUnknown *>(resource));
		if (identity == nullptr)
			return 0;
		{
			std::lock_guard<std::mutex> lock(s_v49_mutex);
			const auto found = s_v49_resource_ids_by_identity.find(identity);
			if (found != s_v49_resource_ids_by_identity.end())
				return found->second;
			if (s_v50_non_target_resources.find(identity) !=
				s_v50_non_target_resources.end())
				return 0;
		}

		const D3D12_RESOURCE_DESC desc = resource->GetDesc();
		if (!v50_is_target_resource_desc(desc))
		{
			std::lock_guard<std::mutex> lock(s_v49_mutex);
			s_v50_non_target_resources[identity] = true;
			return 0;
		}

		v49_resource_info info = {};
		info.resource_id = ++s_v49_next_resource_id;
		info.identity = identity;
		info.dimension = static_cast<unsigned int>(desc.Dimension);
		info.width = desc.Width;
		info.height = desc.Height;
		info.depth_or_array = desc.DepthOrArraySize;
		info.mip_levels = desc.MipLevels;
		info.format = static_cast<unsigned int>(desc.Format);
		info.layout = static_cast<unsigned int>(desc.Layout);
		info.flags = static_cast<unsigned int>(desc.Flags);
		info.gpu_va = resource->GetGPUVirtualAddress();

		{
			std::lock_guard<std::mutex> lock(s_v49_mutex);
			const auto found = s_v49_resource_ids_by_identity.find(identity);
			if (found != s_v49_resource_ids_by_identity.end())
				return found->second;
			s_v49_resource_ids_by_identity[identity] = info.resource_id;
			s_v49_resources[info.resource_id] = info;
		}

		const uint64_t event = ++s_v50_target_resource_count;
		reshade::log::message(
			reshade::log::level::info,
			"D3DMetal RTX target-UAV exact-base probe v50: TARGET_RESOURCE event=%llu resource_id=%llu resource=%p identity=%p dimension=%u width=%llu height=%u depth_or_array=%u mip_levels=%u format=%u flags=0x%X gpu_va=0x%llX.",
			static_cast<unsigned long long>(event),
			static_cast<unsigned long long>(info.resource_id),
			resource,
			identity,
			info.dimension,
			static_cast<unsigned long long>(info.width),
			info.height,
			static_cast<unsigned int>(info.depth_or_array),
			static_cast<unsigned int>(info.mip_levels),
			info.format,
			info.flags,
			static_cast<unsigned long long>(info.gpu_va));
		return info.resource_id;
	}
'''
text = replace_between(
    text,
    "\tuint64_t v49_register_resource(ID3D12Resource *resource)\n\t{\n",
    "\n\tbool v49_get_resource(\n",
    register_replacement,
    "V50 target resource registration")

store_replacement = r'''	void v49_store_descriptor(
		D3D12_CPU_DESCRIPTOR_HANDLE destination,
		const v49_descriptor_info &info)
	{
		if (destination.ptr == 0 || info.resource_id == 0)
			return;
		{
			std::lock_guard<std::mutex> lock(s_v49_mutex);
			s_v49_descriptors[destination.ptr] = info;
		}
		const uint64_t event = ++s_v50_target_descriptor_count;
		if (v50_should_sample(event))
			reshade::log::message(
				reshade::log::level::info,
				"D3DMetal RTX target-UAV exact-base probe v50: TARGET_DESCRIPTOR event=%llu cpu_handle=0x%llX descriptor_kind=%s resource_id=%llu view_format=%u view_dimension=%u.",
				static_cast<unsigned long long>(event),
				static_cast<unsigned long long>(destination.ptr),
				v49_descriptor_kind_name(info.kind),
				static_cast<unsigned long long>(info.resource_id),
				info.format,
				info.view_dimension);
	}
'''
text = replace_between(
    text,
    "\tvoid v49_store_descriptor(\n",
    "\n\tbool v49_get_descriptor(\n",
    store_replacement,
    "V50 target descriptor store")

copy_simple_replacement = r'''	void STDMETHODCALLTYPE v49_trace_copy_descriptors_simple(
		ID3D12Device *device,
		UINT count,
		D3D12_CPU_DESCRIPTOR_HANDLE destination,
		D3D12_CPU_DESCRIPTOR_HANDLE source,
		D3D12_DESCRIPTOR_HEAP_TYPE type)
	{
		if (s_v49_original_copy_descriptors_simple != nullptr)
			s_v49_original_copy_descriptors_simple(
				device, count, destination, source, type);
		if (type != D3D12_DESCRIPTOR_HEAP_TYPE_CBV_SRV_UAV ||
			count == 0 || source.ptr == 0 || destination.ptr == 0)
			return;
		const UINT increment = device->GetDescriptorHandleIncrementSize(type);
		if (increment == 0)
			return;

		std::vector<std::pair<SIZE_T, v49_descriptor_info>> tracked;
		{
			std::lock_guard<std::mutex> lock(s_v49_mutex);
			tracked.reserve(s_v49_descriptors.size());
			for (const auto &entry : s_v49_descriptors)
				tracked.push_back(entry);
		}
		for (const auto &entry : tracked)
		{
			if (entry.first < source.ptr)
				continue;
			const SIZE_T delta = entry.first - source.ptr;
			if (delta % increment != 0)
				continue;
			const UINT64 index = delta / increment;
			if (index >= count)
				continue;
			D3D12_CPU_DESCRIPTOR_HANDLE mapped = {};
			mapped.ptr = destination.ptr + static_cast<SIZE_T>(index) * increment;
			v49_store_descriptor(mapped, entry.second);
			const uint64_t event = ++s_v50_target_copy_count;
			if (v50_should_sample(event))
				reshade::log::message(
					reshade::log::level::info,
					"D3DMetal RTX target-UAV exact-base probe v50: TARGET_DESCRIPTOR_COPY event=%llu source=0x%llX destination=0x%llX resource_id=%llu.",
					static_cast<unsigned long long>(event),
					static_cast<unsigned long long>(entry.first),
					static_cast<unsigned long long>(mapped.ptr),
					static_cast<unsigned long long>(entry.second.resource_id));
		}
	}
'''
text = replace_between(
    text,
    "\tvoid STDMETHODCALLTYPE v49_trace_copy_descriptors_simple(\n",
    "\n\tvoid STDMETHODCALLTYPE v49_trace_copy_descriptors(\n",
    copy_simple_replacement,
    "V50 optimized simple descriptor copies")

copy_replacement = r'''	void STDMETHODCALLTYPE v49_trace_copy_descriptors(
		ID3D12Device *device,
		UINT destination_range_count,
		const D3D12_CPU_DESCRIPTOR_HANDLE *destination_starts,
		const UINT *destination_sizes,
		UINT source_range_count,
		const D3D12_CPU_DESCRIPTOR_HANDLE *source_starts,
		const UINT *source_sizes,
		D3D12_DESCRIPTOR_HEAP_TYPE type)
	{
		if (s_v49_original_copy_descriptors != nullptr)
			s_v49_original_copy_descriptors(
				device, destination_range_count, destination_starts,
				destination_sizes, source_range_count, source_starts,
				source_sizes, type);
		if (type != D3D12_DESCRIPTOR_HEAP_TYPE_CBV_SRV_UAV ||
			destination_starts == nullptr || source_starts == nullptr ||
			destination_range_count == 0 || source_range_count == 0)
			return;
		const UINT increment = device->GetDescriptorHandleIncrementSize(type);
		if (increment == 0)
			return;

		const UINT destination_cap =
			destination_range_count < 1024u ? destination_range_count : 1024u;
		const UINT source_cap =
			source_range_count < 1024u ? source_range_count : 1024u;
		std::vector<std::pair<SIZE_T, UINT>> destinations;
		std::vector<std::pair<SIZE_T, UINT>> sources;
		destinations.reserve(destination_cap);
		sources.reserve(source_cap);
		for (UINT index = 0; index < destination_cap; ++index)
		{
			D3D12_CPU_DESCRIPTOR_HANDLE handle = {};
			if (!safe_copy_from_process(
					destination_starts + index, &handle, sizeof(handle)))
				break;
			UINT size = 1;
			if (destination_sizes != nullptr &&
				!safe_copy_from_process(
					destination_sizes + index, &size, sizeof(size)))
				break;
			destinations.emplace_back(handle.ptr, size);
		}
		for (UINT index = 0; index < source_cap; ++index)
		{
			D3D12_CPU_DESCRIPTOR_HANDLE handle = {};
			if (!safe_copy_from_process(
					source_starts + index, &handle, sizeof(handle)))
				break;
			UINT size = 1;
			if (source_sizes != nullptr &&
				!safe_copy_from_process(
					source_sizes + index, &size, sizeof(size)))
				break;
			sources.emplace_back(handle.ptr, size);
		}

		std::vector<std::pair<SIZE_T, v49_descriptor_info>> tracked;
		{
			std::lock_guard<std::mutex> lock(s_v49_mutex);
			tracked.reserve(s_v49_descriptors.size());
			for (const auto &entry : s_v49_descriptors)
				tracked.push_back(entry);
		}
		for (const auto &entry : tracked)
		{
			UINT64 ordinal_base = 0;
			UINT64 ordinal = 0;
			bool found_source = false;
			for (const auto &range : sources)
			{
				if (entry.first >= range.first)
				{
					const SIZE_T delta = entry.first - range.first;
					if (delta % increment == 0 && delta / increment < range.second)
					{
						ordinal = ordinal_base + delta / increment;
						found_source = true;
						break;
					}
				}
				ordinal_base += range.second;
			}
			if (!found_source)
				continue;
			UINT64 destination_base = 0;
			for (const auto &range : destinations)
			{
				if (ordinal < destination_base + range.second)
				{
					D3D12_CPU_DESCRIPTOR_HANDLE mapped = {};
					mapped.ptr = range.first +
						static_cast<SIZE_T>(ordinal - destination_base) * increment;
					v49_store_descriptor(mapped, entry.second);
					const uint64_t event = ++s_v50_target_copy_count;
					if (v50_should_sample(event))
						reshade::log::message(
							reshade::log::level::info,
							"D3DMetal RTX target-UAV exact-base probe v50: TARGET_DESCRIPTOR_COPY event=%llu source=0x%llX destination=0x%llX resource_id=%llu.",
							static_cast<unsigned long long>(event),
							static_cast<unsigned long long>(entry.first),
							static_cast<unsigned long long>(mapped.ptr),
							static_cast<unsigned long long>(entry.second.resource_id));
					break;
				}
				destination_base += range.second;
			}
		}
	}
'''
text = replace_between(
    text,
    "\tvoid STDMETHODCALLTYPE v49_trace_copy_descriptors(\n",
    "\n\tvoid v49_log_table_binding(\n",
    copy_replacement,
    "V50 optimized ranged descriptor copies")

bind_replacement = r'''	void v49_log_table_binding(
		ID3D12GraphicsCommandList *command_list,
		const char *stage,
		UINT root_index,
		D3D12_GPU_DESCRIPTOR_HANDLE base)
	{
		if (!v46_post_phase() || base.ptr == 0)
			return;
		v49_log_active();

		SIZE_T cpu_ptr = 0;
		{
			std::lock_guard<std::mutex> lock(s_v49_mutex);
			const auto cached = s_v50_gpu_base_cpu_cache.find(base.ptr);
			if (cached != s_v50_gpu_base_cpu_cache.end())
				cpu_ptr = cached->second;
		}
		v49_heap_info heap = {};
		UINT descriptor_index = 0;
		if (cpu_ptr == 0)
		{
			if (!v49_find_heap_by_gpu(base.ptr, heap, descriptor_index))
				return;
			cpu_ptr = heap.cpu_start +
				static_cast<SIZE_T>(descriptor_index) * heap.increment;
			std::lock_guard<std::mutex> lock(s_v49_mutex);
			s_v50_gpu_base_cpu_cache[base.ptr] = cpu_ptr;
		}
		else
		{
			v49_find_heap_by_gpu(base.ptr, heap, descriptor_index);
		}

		v49_descriptor_info descriptor = {};
		if (!v49_get_descriptor(cpu_ptr, descriptor) || descriptor.resource_id == 0)
			return;
		v49_resource_info resource = {};
		if (!v49_get_resource(descriptor.resource_id, resource))
			return;

		uint64_t pso_id = 0;
		unsigned int pso_kind = 0;
		uint64_t shader_hash = 0;
		v49_lookup_pso(command_list, pso_id, pso_kind, shader_hash);
		const uint64_t event = ++s_v50_target_base_bind_count;
		uint64_t signature = v49_signature_seed(0x5001ull);
		signature = v49_signature_add(signature, stage[0] == 'g' ? 1ull : 2ull);
		signature = v49_signature_add(signature, pso_id);
		signature = v49_signature_add(signature, root_index);
		signature = v49_signature_add(signature, descriptor.kind);
		signature = v49_signature_add(signature, descriptor.resource_id);
		const bool unique = v49_take_unique(signature, 512);
		if (unique || v50_should_sample(event))
			reshade::log::message(
				reshade::log::level::info,
				"D3DMetal RTX target-UAV exact-base probe v50: TARGET_BASE_BIND event=%llu unique=%u stage=%s pso_id=%llu pso_kind=%u shader_hash=0x%llX root_index=%u gpu_handle=0x%llX cpu_handle=0x%llX heap_id=%llu descriptor_index=%u descriptor_offset=0 descriptor_kind=%s resource_id=%llu view_format=%u view_dimension=%u resource_format=%u resource_flags=0x%X.",
				static_cast<unsigned long long>(event),
				unique ? 1u : 0u,
				stage,
				static_cast<unsigned long long>(pso_id),
				pso_kind,
				static_cast<unsigned long long>(shader_hash),
				root_index,
				static_cast<unsigned long long>(base.ptr),
				static_cast<unsigned long long>(cpu_ptr),
				static_cast<unsigned long long>(heap.heap_id),
				descriptor_index,
				v49_descriptor_kind_name(descriptor.kind),
				static_cast<unsigned long long>(descriptor.resource_id),
				descriptor.format,
				descriptor.view_dimension,
				resource.format,
				resource.flags);
	}
'''
text = replace_between(
    text,
    "\tvoid v49_log_table_binding(\n",
    "\n\tvoid v49_log_direct_root(\n",
    bind_replacement,
    "V50 exact-base table binding")

direct_replacement = r'''	void v49_log_direct_root(
		ID3D12GraphicsCommandList *command_list,
		const char *stage,
		const char *kind,
		UINT root_index,
		D3D12_GPU_VIRTUAL_ADDRESS address)
	{
		(void)command_list;
		(void)stage;
		(void)kind;
		(void)root_index;
		(void)address;
	}
'''
text = replace_between(
    text,
    "\tvoid v49_log_direct_root(\n",
    "\n\tvoid v49_log_rtv(\n",
    direct_replacement,
    "V50 disable direct-root scans")

rtv_replacement = r'''	void v49_log_rtv(
		ID3D12GraphicsCommandList *command_list,
		UINT rtv_index,
		D3D12_CPU_DESCRIPTOR_HANDLE handle)
	{
		v49_descriptor_info descriptor = {};
		if (!v49_get_descriptor(handle.ptr, descriptor) ||
			descriptor.kind != 4 || descriptor.resource_id == 0)
			return;
		uint64_t pso_id = 0;
		unsigned int pso_kind = 0;
		uint64_t shader_hash = 0;
		v49_lookup_pso(command_list, pso_id, pso_kind, shader_hash);
		const uint64_t event = ++s_v50_target_rtv_count;
		if (v50_should_sample(event))
			reshade::log::message(
				reshade::log::level::info,
				"D3DMetal RTX target-UAV exact-base probe v50: TARGET_RTV_BIND event=%llu pso_id=%llu pso_kind=%u shader_hash=0x%llX rtv_index=%u resource_id=%llu view_format=%u view_dimension=%u.",
				static_cast<unsigned long long>(event),
				static_cast<unsigned long long>(pso_id),
				pso_kind,
				static_cast<unsigned long long>(shader_hash),
				rtv_index,
				static_cast<unsigned long long>(descriptor.resource_id),
				descriptor.format,
				descriptor.view_dimension);
	}
'''
text = replace_between(
    text,
    "\tvoid v49_log_rtv(\n",
    "\n\tvoid STDMETHODCALLTYPE v49_trace_resource_barrier(\n",
    rtv_replacement,
    "V50 target RTV tracing")

barrier_replacement = r'''	void STDMETHODCALLTYPE v49_trace_resource_barrier(
		ID3D12GraphicsCommandList *command_list,
		UINT count,
		const D3D12_RESOURCE_BARRIER *barriers)
	{
		if (v46_post_phase() && barriers != nullptr)
		{
			const UINT capped = count < 256u ? count : 256u;
			for (UINT index = 0; index < capped; ++index)
			{
				D3D12_RESOURCE_BARRIER barrier = {};
				if (!safe_copy_from_process(
						barriers + index, &barrier, sizeof(barrier)))
					break;
				ID3D12Resource *resource_before = nullptr;
				ID3D12Resource *resource_after = nullptr;
				unsigned int before_state = 0;
				unsigned int after_state = 0;
				if (barrier.Type == D3D12_RESOURCE_BARRIER_TYPE_TRANSITION)
				{
					resource_before = barrier.Transition.pResource;
					resource_after = resource_before;
					before_state = static_cast<unsigned int>(barrier.Transition.StateBefore);
					after_state = static_cast<unsigned int>(barrier.Transition.StateAfter);
				}
				else if (barrier.Type == D3D12_RESOURCE_BARRIER_TYPE_UAV)
				{
					resource_before = barrier.UAV.pResource;
					resource_after = resource_before;
				}
				else if (barrier.Type == D3D12_RESOURCE_BARRIER_TYPE_ALIASING)
				{
					resource_before = barrier.Aliasing.pResourceBefore;
					resource_after = barrier.Aliasing.pResourceAfter;
				}
				const uint64_t before_id = v49_register_resource(resource_before);
				const uint64_t after_id = v49_register_resource(resource_after);
				if (before_id == 0 && after_id == 0)
					continue;
				const uint64_t event = ++s_v50_target_barrier_count;
				uint64_t signature = v49_signature_seed(0x5002ull);
				signature = v49_signature_add(signature,
					static_cast<unsigned int>(barrier.Type));
				signature = v49_signature_add(signature, before_id);
				signature = v49_signature_add(signature, after_id);
				signature = v49_signature_add(signature, before_state);
				signature = v49_signature_add(signature, after_state);
				const bool unique = v49_take_unique(signature, 512);
				if (unique || v50_should_sample(event))
					reshade::log::message(
						reshade::log::level::info,
						"D3DMetal RTX target-UAV exact-base probe v50: TARGET_BARRIER event=%llu unique=%u type=%u flags=0x%X before_resource_id=%llu after_resource_id=%llu state_before=0x%X state_after=0x%X subresource=%u.",
						static_cast<unsigned long long>(event),
						unique ? 1u : 0u,
						static_cast<unsigned int>(barrier.Type),
						static_cast<unsigned int>(barrier.Flags),
						static_cast<unsigned long long>(before_id),
						static_cast<unsigned long long>(after_id),
						before_state,
						after_state,
						barrier.Type == D3D12_RESOURCE_BARRIER_TYPE_TRANSITION ?
							barrier.Transition.Subresource : 0u);
			}
		}
		if (s_v49_original_resource_barrier != nullptr)
			s_v49_original_resource_barrier(command_list, count, barriers);
	}
'''
text = replace_between(
    text,
    "\tvoid STDMETHODCALLTYPE v49_trace_resource_barrier(\n",
    "\n\tvoid STDMETHODCALLTYPE v49_trace_set_compute_root_table(\n",
    barrier_replacement,
    "V50 target barriers")

text = text.replace(
    "D3DMetal RTX descriptor-resource lineage v49: DEVICE_HOOKS installed=",
    "D3DMetal RTX target-UAV exact-base probe v50: DEVICE_HOOKS installed=")
text = text.replace(
    "D3DMetal RTX descriptor-resource lineage v49: COMMAND_HOOKS installed=",
    "D3DMetal RTX target-UAV exact-base probe v50: COMMAND_HOOKS installed=")

required = [
    "D3DMetal RTX target-UAV exact-base probe v50: ACTIVE",
    "TARGET_RESOURCE event=",
    "TARGET_DESCRIPTOR event=",
    "TARGET_DESCRIPTOR_COPY event=",
    "TARGET_BASE_BIND event=",
    "descriptor_offset=0",
    "TARGET_RTV_BIND event=",
    "TARGET_BARRIER event=",
    "signature=texture2d-1024x1024-mips11-r32-typeless-flags0x5",
    "commands-modified=0",
]
for marker in required:
    if marker not in text:
        raise RuntimeError(f"V50 generated source is missing marker: {marker}")
if "for (UINT offset = 0; offset < 16u; ++offset)" in text:
    raise RuntimeError("V50 failed to remove V49 adjacency scan")
if text.count("v50_is_target_resource_desc(") != 2:
    raise RuntimeError("V50 target signature helper count is unexpected")
if text.count("{") != text.count("}"):
    raise RuntimeError(
        f"V50 generated source has unbalanced braces: "
        f"{text.count('{')} vs {text.count('}')}")

path.write_text(text, encoding="utf-8")

report = """V50_TARGET_UAV_EXACT_BASE_PROBE_PATCH_OK
V49_FULL_LINEAGE_HOOK_SURFACE_PRESERVED=YES
TARGET_RESOURCE_SIGNATURE=TEXTURE2D_1024X1024_MIPS11_R32_TYPELESS_FLAGS_0X5
TARGET_RESOURCE_NEGATIVE_CACHE=ENABLED
TARGET_DESCRIPTOR_ONLY_LEDGER=ENABLED
TARGET_DESCRIPTOR_COPY_RANGE_FILTER=ENABLED
ROOT_DESCRIPTOR_TABLE_SCAN_WIDTH=1
ROOT_DESCRIPTOR_TABLE_REQUIRED_OFFSET=0
V49_SIXTEEN_DESCRIPTOR_ADJACENCY_SCAN=DISABLED
TARGET_RESOURCE_BARRIER_TRACE=ENABLED
TARGET_RTV_AND_CLEAR_TRACE=ENABLED
DIRECT_ROOT_TEXTURE_SCAN=DISABLED
SAMPLED_LOGGING=POWERS_OF_TWO_PLUS_UNIQUE
DRAWS_DISPATCHES_DESCRIPTORS_RESOURCES_MODIFIED=NO
RUNNER_SHUTDOWN_MODE=FORCED_PROCESS_TERMINATION_BEFORE_DLL_RESTORE
CONTROL_FLOW_CHANGE=OBSERVATION_ONLY
RESULT=PASS
"""
Path("v50-patch-report.txt").write_text(report, encoding="utf-8")
print(report, end="")
