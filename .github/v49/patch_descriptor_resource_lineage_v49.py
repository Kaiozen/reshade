from pathlib import Path

SOURCE = Path("source/d3d12/d3d12.cpp")
if not SOURCE.is_file():
    raise RuntimeError(f"Missing source file: {SOURCE}")

text = SOURCE.read_text(encoding="utf-8-sig")
for required in (
    "D3DMetal RTX no-output raygen control v41:",
    "D3DMetal RTX ray-dispatch suppression control v44:",
    "D3DMetal RTX RT-state bind suppression control v45:",
    "D3DMetal RTX non-RT PSO census v46:",
):
    if required not in text:
        raise RuntimeError(f"V49 prerequisite is missing: {required}")
if "D3DMetal RTX descriptor-resource lineage v49:" in text:
    raise RuntimeError("V49 is already present")


def replace_once(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 occurrence, found {count}")
    return source.replace(old, new, 1)


text = replace_once(
    text,
    "(info.post_binds % 240ull) == 0;",
    "(info.post_binds % 4096ull) == 0;",
    "V49 V46 bind-log throttling",
)
text = replace_once(
    text,
    "(post_total % 120ull) < count);",
    "(post_total % 4096ull) < count);",
    "V49 V46 command-log throttling",
)

helper_anchor = "\tvoid v33_install_command_list_method_hooks(IUnknown *command_list)\n"
if text.count(helper_anchor) != 1:
    raise RuntimeError(
        f"V49 helper anchor mismatch: {text.count(helper_anchor)}")

helper = r'''
	// V49 descriptor/resource lineage tracer.
	// This observes D3D12 descriptor and resource usage without modifying any
	// descriptor, resource, clear, barrier, draw, dispatch, or binding command.
	using v49_create_descriptor_heap_fn = HRESULT (STDMETHODCALLTYPE *)(
		ID3D12Device *, const D3D12_DESCRIPTOR_HEAP_DESC *, REFIID, void **);
	using v49_create_cbv_fn = void (STDMETHODCALLTYPE *)(
		ID3D12Device *, const D3D12_CONSTANT_BUFFER_VIEW_DESC *,
		D3D12_CPU_DESCRIPTOR_HANDLE);
	using v49_create_srv_fn = void (STDMETHODCALLTYPE *)(
		ID3D12Device *, ID3D12Resource *,
		const D3D12_SHADER_RESOURCE_VIEW_DESC *,
		D3D12_CPU_DESCRIPTOR_HANDLE);
	using v49_create_uav_fn = void (STDMETHODCALLTYPE *)(
		ID3D12Device *, ID3D12Resource *, ID3D12Resource *,
		const D3D12_UNORDERED_ACCESS_VIEW_DESC *,
		D3D12_CPU_DESCRIPTOR_HANDLE);
	using v49_create_rtv_fn = void (STDMETHODCALLTYPE *)(
		ID3D12Device *, ID3D12Resource *,
		const D3D12_RENDER_TARGET_VIEW_DESC *,
		D3D12_CPU_DESCRIPTOR_HANDLE);
	using v49_copy_descriptors_fn = void (STDMETHODCALLTYPE *)(
		ID3D12Device *,
		UINT, const D3D12_CPU_DESCRIPTOR_HANDLE *, const UINT *,
		UINT, const D3D12_CPU_DESCRIPTOR_HANDLE *, const UINT *,
		D3D12_DESCRIPTOR_HEAP_TYPE);
	using v49_copy_descriptors_simple_fn = void (STDMETHODCALLTYPE *)(
		ID3D12Device *, UINT,
		D3D12_CPU_DESCRIPTOR_HANDLE,
		D3D12_CPU_DESCRIPTOR_HANDLE,
		D3D12_DESCRIPTOR_HEAP_TYPE);

	using v49_resource_barrier_fn = void (STDMETHODCALLTYPE *)(
		ID3D12GraphicsCommandList *, UINT,
		const D3D12_RESOURCE_BARRIER *);
	using v49_root_table_fn = void (STDMETHODCALLTYPE *)(
		ID3D12GraphicsCommandList *, UINT,
		D3D12_GPU_DESCRIPTOR_HANDLE);
	using v49_root_va_fn = void (STDMETHODCALLTYPE *)(
		ID3D12GraphicsCommandList *, UINT,
		D3D12_GPU_VIRTUAL_ADDRESS);
	using v49_om_set_render_targets_fn = void (STDMETHODCALLTYPE *)(
		ID3D12GraphicsCommandList *, UINT,
		const D3D12_CPU_DESCRIPTOR_HANDLE *, BOOL,
		const D3D12_CPU_DESCRIPTOR_HANDLE *);
	using v49_clear_rtv_fn = void (STDMETHODCALLTYPE *)(
		ID3D12GraphicsCommandList *,
		D3D12_CPU_DESCRIPTOR_HANDLE, const FLOAT[4],
		UINT, const D3D12_RECT *);
	using v49_clear_uav_uint_fn = void (STDMETHODCALLTYPE *)(
		ID3D12GraphicsCommandList *,
		D3D12_GPU_DESCRIPTOR_HANDLE,
		D3D12_CPU_DESCRIPTOR_HANDLE,
		ID3D12Resource *, const UINT[4],
		UINT, const D3D12_RECT *);
	using v49_clear_uav_float_fn = void (STDMETHODCALLTYPE *)(
		ID3D12GraphicsCommandList *,
		D3D12_GPU_DESCRIPTOR_HANDLE,
		D3D12_CPU_DESCRIPTOR_HANDLE,
		ID3D12Resource *, const FLOAT[4],
		UINT, const D3D12_RECT *);

	constexpr size_t v49_create_descriptor_heap_slot = 14;
	constexpr size_t v49_create_cbv_slot = 17;
	constexpr size_t v49_create_srv_slot = 18;
	constexpr size_t v49_create_uav_slot = 19;
	constexpr size_t v49_create_rtv_slot = 20;
	constexpr size_t v49_copy_descriptors_slot = 23;
	constexpr size_t v49_copy_descriptors_simple_slot = 24;

	constexpr size_t v49_resource_barrier_slot = 26;
	constexpr size_t v49_set_compute_root_table_slot = 31;
	constexpr size_t v49_set_graphics_root_table_slot = 32;
	constexpr size_t v49_set_compute_root_cbv_slot = 37;
	constexpr size_t v49_set_graphics_root_cbv_slot = 38;
	constexpr size_t v49_set_compute_root_srv_slot = 39;
	constexpr size_t v49_set_graphics_root_srv_slot = 40;
	constexpr size_t v49_set_compute_root_uav_slot = 41;
	constexpr size_t v49_set_graphics_root_uav_slot = 42;
	constexpr size_t v49_om_set_render_targets_slot = 46;
	constexpr size_t v49_clear_rtv_slot = 48;
	constexpr size_t v49_clear_uav_uint_slot = 49;
	constexpr size_t v49_clear_uav_float_slot = 50;

	static v49_create_descriptor_heap_fn
		s_v49_original_create_descriptor_heap = nullptr;
	static v49_create_cbv_fn s_v49_original_create_cbv = nullptr;
	static v49_create_srv_fn s_v49_original_create_srv = nullptr;
	static v49_create_uav_fn s_v49_original_create_uav = nullptr;
	static v49_create_rtv_fn s_v49_original_create_rtv = nullptr;
	static v49_copy_descriptors_fn
		s_v49_original_copy_descriptors = nullptr;
	static v49_copy_descriptors_simple_fn
		s_v49_original_copy_descriptors_simple = nullptr;

	static v49_resource_barrier_fn
		s_v49_original_resource_barrier = nullptr;
	static v49_root_table_fn
		s_v49_original_set_compute_root_table = nullptr;
	static v49_root_table_fn
		s_v49_original_set_graphics_root_table = nullptr;
	static v49_root_va_fn
		s_v49_original_set_compute_root_cbv = nullptr;
	static v49_root_va_fn
		s_v49_original_set_graphics_root_cbv = nullptr;
	static v49_root_va_fn
		s_v49_original_set_compute_root_srv = nullptr;
	static v49_root_va_fn
		s_v49_original_set_graphics_root_srv = nullptr;
	static v49_root_va_fn
		s_v49_original_set_compute_root_uav = nullptr;
	static v49_root_va_fn
		s_v49_original_set_graphics_root_uav = nullptr;
	static v49_om_set_render_targets_fn
		s_v49_original_om_set_render_targets = nullptr;
	static v49_clear_rtv_fn s_v49_original_clear_rtv = nullptr;
	static v49_clear_uav_uint_fn
		s_v49_original_clear_uav_uint = nullptr;
	static v49_clear_uav_float_fn
		s_v49_original_clear_uav_float = nullptr;

	struct v49_heap_info
	{
		uint64_t heap_id = 0;
		void *identity = nullptr;
		D3D12_DESCRIPTOR_HEAP_TYPE type =
			D3D12_DESCRIPTOR_HEAP_TYPE_CBV_SRV_UAV;
		UINT count = 0;
		UINT increment = 0;
		SIZE_T cpu_start = 0;
		UINT64 gpu_start = 0;
		bool shader_visible = false;
	};

	struct v49_resource_info
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

	struct v49_descriptor_info
	{
		unsigned int kind = 0;
		uint64_t resource_id = 0;
		unsigned int format = 0;
		unsigned int view_dimension = 0;
		UINT64 first_element = 0;
		UINT num_elements = 0;
		UINT structure_stride = 0;
		UINT view_flags = 0;
		UINT64 buffer_location = 0;
		UINT size_in_bytes = 0;
	};

	static std::once_flag s_v49_device_hook_once;
	static std::once_flag s_v49_command_hook_once;
	static std::once_flag s_v49_active_log_once;
	static std::mutex s_v49_mutex;
	static std::vector<v49_heap_info> s_v49_heaps;
	static std::unordered_map<SIZE_T, v49_descriptor_info>
		s_v49_descriptors;
	static std::unordered_map<void *, uint64_t>
		s_v49_resource_ids_by_identity;
	static std::unordered_map<uint64_t, v49_resource_info>
		s_v49_resources;
	static std::unordered_map<uint64_t, bool>
		s_v49_unique_signatures;
	static std::atomic<uint64_t> s_v49_next_heap_id = 0;
	static std::atomic<uint64_t> s_v49_next_resource_id = 0;
	static std::atomic<uint64_t> s_v49_table_event_count = 0;
	static std::atomic<uint64_t> s_v49_direct_root_event_count = 0;
	static std::atomic<uint64_t> s_v49_rtv_event_count = 0;
	static std::atomic<uint64_t> s_v49_clear_event_count = 0;
	static std::atomic<uint64_t> s_v49_barrier_event_count = 0;
	static std::atomic<uint64_t> s_v49_descriptor_copy_count = 0;

	const char *v49_descriptor_kind_name(unsigned int kind)
	{
		switch (kind)
		{
		case 1: return "cbv";
		case 2: return "srv";
		case 3: return "uav";
		case 4: return "rtv";
		default: return "unknown";
		}
	}

	void v49_log_active()
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

	uint64_t v49_signature_seed(uint64_t tag)
	{
		return v46_mix_hash(1469598103934665603ull, tag);
	}

	uint64_t v49_signature_add(uint64_t signature, uint64_t value)
	{
		return v46_mix_hash(signature, value);
	}

	bool v49_take_unique(uint64_t signature, uint64_t limit)
	{
		std::lock_guard<std::mutex> lock(s_v49_mutex);
		if (s_v49_unique_signatures.size() >= limit)
			return false;
		const auto inserted =
			s_v49_unique_signatures.emplace(signature, true);
		return inserted.second;
	}

	bool v49_lookup_pso(
		ID3D12GraphicsCommandList *command_list,
		uint64_t &pso_id,
		unsigned int &pso_kind,
		uint64_t &shader_hash)
	{
		pso_id = v46_lookup_bound_pso(command_list);
		pso_kind = 0;
		shader_hash = 0;
		if (pso_id == 0)
			return false;
		std::lock_guard<std::mutex> lock(s_v46_mutex);
		const auto found = s_v46_infos.find(pso_id);
		if (found == s_v46_infos.end())
			return false;
		pso_kind = found->second.metadata.kind;
		shader_hash = found->second.metadata.shader_hash;
		return true;
	}

	uint64_t v49_register_resource(ID3D12Resource *resource)
	{
		if (resource == nullptr)
			return 0;
		void *const identity = v33_identity_pointer(
			reinterpret_cast<IUnknown *>(resource));
		if (identity == nullptr)
			return 0;
		{
			std::lock_guard<std::mutex> lock(s_v49_mutex);
			const auto found =
				s_v49_resource_ids_by_identity.find(identity);
			if (found != s_v49_resource_ids_by_identity.end())
				return found->second;
		}

		const D3D12_RESOURCE_DESC desc = resource->GetDesc();
		const UINT64 gpu_va = resource->GetGPUVirtualAddress();
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
		info.gpu_va = gpu_va;

		{
			std::lock_guard<std::mutex> lock(s_v49_mutex);
			const auto found =
				s_v49_resource_ids_by_identity.find(identity);
			if (found != s_v49_resource_ids_by_identity.end())
				return found->second;
			s_v49_resource_ids_by_identity[identity] =
				info.resource_id;
			s_v49_resources[info.resource_id] = info;
		}

		reshade::log::message(
			reshade::log::level::info,
			"D3DMetal RTX descriptor-resource lineage v49: RESOURCE_REGISTER resource_id=%llu resource=%p identity=%p dimension=%u width=%llu height=%u depth_or_array=%u mip_levels=%u format=%u layout=%u flags=0x%X gpu_va=0x%llX.",
			static_cast<unsigned long long>(info.resource_id),
			resource,
			identity,
			info.dimension,
			static_cast<unsigned long long>(info.width),
			info.height,
			static_cast<unsigned int>(info.depth_or_array),
			static_cast<unsigned int>(info.mip_levels),
			info.format,
			info.layout,
			info.flags,
			static_cast<unsigned long long>(info.gpu_va));
		return info.resource_id;
	}

	bool v49_get_resource(
		uint64_t resource_id,
		v49_resource_info &info)
	{
		if (resource_id == 0)
			return false;
		std::lock_guard<std::mutex> lock(s_v49_mutex);
		const auto found = s_v49_resources.find(resource_id);
		if (found == s_v49_resources.end())
			return false;
		info = found->second;
		return true;
	}

	uint64_t v49_find_resource_by_va(
		UINT64 address,
		UINT64 &offset)
	{
		offset = 0;
		if (address == 0)
			return 0;
		std::lock_guard<std::mutex> lock(s_v49_mutex);
		for (const auto &entry : s_v49_resources)
		{
			const auto &info = entry.second;
			if (info.dimension !=
					static_cast<unsigned int>(
						D3D12_RESOURCE_DIMENSION_BUFFER) ||
				info.gpu_va == 0 ||
				info.width == 0)
				continue;
			const UINT64 end = info.gpu_va + info.width;
			if (address >= info.gpu_va && address < end)
			{
				offset = address - info.gpu_va;
				return info.resource_id;
			}
		}
		return 0;
	}

	void v49_store_descriptor(
		D3D12_CPU_DESCRIPTOR_HANDLE destination,
		const v49_descriptor_info &info)
	{
		if (destination.ptr == 0)
			return;
		std::lock_guard<std::mutex> lock(s_v49_mutex);
		s_v49_descriptors[destination.ptr] = info;
	}

	bool v49_get_descriptor(
		SIZE_T cpu_ptr,
		v49_descriptor_info &info)
	{
		std::lock_guard<std::mutex> lock(s_v49_mutex);
		const auto found = s_v49_descriptors.find(cpu_ptr);
		if (found == s_v49_descriptors.end())
			return false;
		info = found->second;
		return true;
	}

	bool v49_find_heap_by_gpu(
		UINT64 gpu_ptr,
		v49_heap_info &heap,
		UINT &descriptor_index)
	{
		std::lock_guard<std::mutex> lock(s_v49_mutex);
		for (const auto &candidate : s_v49_heaps)
		{
			if (!candidate.shader_visible ||
				candidate.type !=
					D3D12_DESCRIPTOR_HEAP_TYPE_CBV_SRV_UAV ||
				candidate.increment == 0 ||
				candidate.gpu_start == 0)
				continue;
			const UINT64 span =
				static_cast<UINT64>(candidate.count) *
				candidate.increment;
			if (gpu_ptr >= candidate.gpu_start &&
				gpu_ptr < candidate.gpu_start + span)
			{
				heap = candidate;
				descriptor_index = static_cast<UINT>(
					(gpu_ptr - candidate.gpu_start) /
					candidate.increment);
				return true;
			}
		}
		return false;
	}

	bool v49_find_heap_by_cpu(
		SIZE_T cpu_ptr,
		v49_heap_info &heap,
		UINT &descriptor_index)
	{
		std::lock_guard<std::mutex> lock(s_v49_mutex);
		for (const auto &candidate : s_v49_heaps)
		{
			if (candidate.increment == 0 ||
				candidate.cpu_start == 0)
				continue;
			const SIZE_T span =
				static_cast<SIZE_T>(candidate.count) *
				candidate.increment;
			if (cpu_ptr >= candidate.cpu_start &&
				cpu_ptr < candidate.cpu_start + span)
			{
				heap = candidate;
				descriptor_index = static_cast<UINT>(
					(cpu_ptr - candidate.cpu_start) /
					candidate.increment);
				return true;
			}
		}
		return false;
	}

	HRESULT STDMETHODCALLTYPE v49_trace_create_descriptor_heap(
		ID3D12Device *device,
		const D3D12_DESCRIPTOR_HEAP_DESC *desc,
		REFIID riid,
		void **heap_out)
	{
		if (s_v49_original_create_descriptor_heap == nullptr)
			return E_FAIL;
		D3D12_DESCRIPTOR_HEAP_DESC snapshot = {};
		const bool readable =
			desc != nullptr &&
			safe_copy_from_process(desc, &snapshot, sizeof(snapshot));
		const HRESULT result =
			s_v49_original_create_descriptor_heap(
				device, desc, riid, heap_out);
		void *created = nullptr;
		if (heap_out != nullptr)
			safe_copy_from_process(
				heap_out, &created, sizeof(created));
		if (SUCCEEDED(result) && created != nullptr && readable)
		{
			ID3D12DescriptorHeap *heap = nullptr;
			reinterpret_cast<IUnknown *>(created)->QueryInterface(
				__uuidof(ID3D12DescriptorHeap),
				reinterpret_cast<void **>(&heap));
			if (heap != nullptr)
			{
				v49_heap_info info = {};
				info.heap_id = ++s_v49_next_heap_id;
				info.identity = v33_identity_pointer(heap);
				info.type = snapshot.Type;
				info.count = snapshot.NumDescriptors;
				info.increment =
					device->GetDescriptorHandleIncrementSize(
						snapshot.Type);
				info.cpu_start =
					heap->GetCPUDescriptorHandleForHeapStart().ptr;
				info.shader_visible =
					(snapshot.Flags &
					 D3D12_DESCRIPTOR_HEAP_FLAG_SHADER_VISIBLE) != 0;
				if (info.shader_visible)
					info.gpu_start =
						heap->GetGPUDescriptorHandleForHeapStart().ptr;
				{
					std::lock_guard<std::mutex> lock(s_v49_mutex);
					s_v49_heaps.push_back(info);
				}
				reshade::log::message(
					reshade::log::level::info,
					"D3DMetal RTX descriptor-resource lineage v49: HEAP_REGISTER heap_id=%llu heap=%p identity=%p type=%u count=%u increment=%u cpu_start=0x%llX gpu_start=0x%llX shader_visible=%u.",
					static_cast<unsigned long long>(info.heap_id),
					heap,
					info.identity,
					static_cast<unsigned int>(info.type),
					info.count,
					info.increment,
					static_cast<unsigned long long>(
						info.cpu_start),
					static_cast<unsigned long long>(
						info.gpu_start),
					info.shader_visible ? 1u : 0u);
				heap->Release();
			}
		}
		return result;
	}

	void STDMETHODCALLTYPE v49_trace_create_cbv(
		ID3D12Device *device,
		const D3D12_CONSTANT_BUFFER_VIEW_DESC *desc,
		D3D12_CPU_DESCRIPTOR_HANDLE destination)
	{
		if (s_v49_original_create_cbv != nullptr)
			s_v49_original_create_cbv(device, desc, destination);
		D3D12_CONSTANT_BUFFER_VIEW_DESC snapshot = {};
		if (desc == nullptr ||
			!safe_copy_from_process(desc, &snapshot, sizeof(snapshot)))
			return;
		v49_descriptor_info info = {};
		info.kind = 1;
		info.buffer_location = snapshot.BufferLocation;
		info.size_in_bytes = snapshot.SizeInBytes;
		UINT64 offset = 0;
		info.resource_id =
			v49_find_resource_by_va(
				snapshot.BufferLocation, offset);
		v49_store_descriptor(destination, info);
	}

	void STDMETHODCALLTYPE v49_trace_create_srv(
		ID3D12Device *device,
		ID3D12Resource *resource,
		const D3D12_SHADER_RESOURCE_VIEW_DESC *desc,
		D3D12_CPU_DESCRIPTOR_HANDLE destination)
	{
		if (s_v49_original_create_srv != nullptr)
			s_v49_original_create_srv(
				device, resource, desc, destination);
		v49_descriptor_info info = {};
		info.kind = 2;
		info.resource_id = v49_register_resource(resource);
		D3D12_SHADER_RESOURCE_VIEW_DESC snapshot = {};
		if (desc != nullptr &&
			safe_copy_from_process(desc, &snapshot, sizeof(snapshot)))
		{
			info.format =
				static_cast<unsigned int>(snapshot.Format);
			info.view_dimension =
				static_cast<unsigned int>(
					snapshot.ViewDimension);
			if (snapshot.ViewDimension ==
				D3D12_SRV_DIMENSION_BUFFER)
			{
				info.first_element =
					snapshot.Buffer.FirstElement;
				info.num_elements =
					snapshot.Buffer.NumElements;
				info.structure_stride =
					snapshot.Buffer.StructureByteStride;
				info.view_flags =
					static_cast<UINT>(snapshot.Buffer.Flags);
			}
		}
		v49_store_descriptor(destination, info);
	}

	void STDMETHODCALLTYPE v49_trace_create_uav(
		ID3D12Device *device,
		ID3D12Resource *resource,
		ID3D12Resource *counter_resource,
		const D3D12_UNORDERED_ACCESS_VIEW_DESC *desc,
		D3D12_CPU_DESCRIPTOR_HANDLE destination)
	{
		if (s_v49_original_create_uav != nullptr)
			s_v49_original_create_uav(
				device, resource, counter_resource,
				desc, destination);
		v49_descriptor_info info = {};
		info.kind = 3;
		info.resource_id = v49_register_resource(resource);
		v49_register_resource(counter_resource);
		D3D12_UNORDERED_ACCESS_VIEW_DESC snapshot = {};
		if (desc != nullptr &&
			safe_copy_from_process(desc, &snapshot, sizeof(snapshot)))
		{
			info.format =
				static_cast<unsigned int>(snapshot.Format);
			info.view_dimension =
				static_cast<unsigned int>(
					snapshot.ViewDimension);
			if (snapshot.ViewDimension ==
				D3D12_UAV_DIMENSION_BUFFER)
			{
				info.first_element =
					snapshot.Buffer.FirstElement;
				info.num_elements =
					snapshot.Buffer.NumElements;
				info.structure_stride =
					snapshot.Buffer.StructureByteStride;
				info.view_flags =
					static_cast<UINT>(snapshot.Buffer.Flags);
			}
		}
		v49_store_descriptor(destination, info);
	}

	void STDMETHODCALLTYPE v49_trace_create_rtv(
		ID3D12Device *device,
		ID3D12Resource *resource,
		const D3D12_RENDER_TARGET_VIEW_DESC *desc,
		D3D12_CPU_DESCRIPTOR_HANDLE destination)
	{
		if (s_v49_original_create_rtv != nullptr)
			s_v49_original_create_rtv(
				device, resource, desc, destination);
		v49_descriptor_info info = {};
		info.kind = 4;
		info.resource_id = v49_register_resource(resource);
		D3D12_RENDER_TARGET_VIEW_DESC snapshot = {};
		if (desc != nullptr &&
			safe_copy_from_process(desc, &snapshot, sizeof(snapshot)))
		{
			info.format =
				static_cast<unsigned int>(snapshot.Format);
			info.view_dimension =
				static_cast<unsigned int>(
					snapshot.ViewDimension);
		}
		v49_store_descriptor(destination, info);
	}

	void v49_copy_one_descriptor(
		SIZE_T destination,
		SIZE_T source)
	{
		v49_descriptor_info info = {};
		if (!v49_get_descriptor(source, info))
			return;
		{
			std::lock_guard<std::mutex> lock(s_v49_mutex);
			s_v49_descriptors[destination] = info;
		}
		++s_v49_descriptor_copy_count;
	}

	void STDMETHODCALLTYPE v49_trace_copy_descriptors_simple(
		ID3D12Device *device,
		UINT count,
		D3D12_CPU_DESCRIPTOR_HANDLE destination,
		D3D12_CPU_DESCRIPTOR_HANDLE source,
		D3D12_DESCRIPTOR_HEAP_TYPE type)
	{
		if (s_v49_original_copy_descriptors_simple != nullptr)
			s_v49_original_copy_descriptors_simple(
				device, count, destination, source, type);
		const UINT increment =
			device->GetDescriptorHandleIncrementSize(type);
		const UINT capped = count < 16384u ? count : 16384u;
		for (UINT index = 0; index < capped; ++index)
			v49_copy_one_descriptor(
				destination.ptr +
					static_cast<SIZE_T>(index) * increment,
				source.ptr +
					static_cast<SIZE_T>(index) * increment);
	}

	void STDMETHODCALLTYPE v49_trace_copy_descriptors(
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
				device,
				destination_range_count,
				destination_starts,
				destination_sizes,
				source_range_count,
				source_starts,
				source_sizes,
				type);
		if (destination_starts == nullptr ||
			source_starts == nullptr)
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
			v49_copy_one_descriptor(
				destination_start.ptr +
					static_cast<SIZE_T>(destination_offset) *
						increment,
				source_start.ptr +
					static_cast<SIZE_T>(source_offset) *
						increment);
			++destination_offset;
			++source_offset;
			++copied;
		}
	}

	void v49_log_table_binding(
		ID3D12GraphicsCommandList *command_list,
		const char *stage,
		UINT root_index,
		D3D12_GPU_DESCRIPTOR_HANDLE base)
	{
		if (!v46_post_phase())
			return;
		v49_log_active();
		uint64_t pso_id = 0;
		unsigned int pso_kind = 0;
		uint64_t shader_hash = 0;
		v49_lookup_pso(
			command_list, pso_id, pso_kind, shader_hash);
		v49_heap_info base_heap = {};
		UINT base_index = 0;
		if (!v49_find_heap_by_gpu(
				base.ptr, base_heap, base_index))
		{
			uint64_t signature = v49_signature_seed(0x4901ull);
			signature = v49_signature_add(
				signature,
				stage[0] == 'g' ? 1ull : 2ull);
			signature = v49_signature_add(signature, pso_id);
			signature = v49_signature_add(signature, root_index);
			signature = v49_signature_add(signature, base.ptr);
			if (v49_take_unique(signature, 20000))
			{
				const uint64_t index = ++s_v49_table_event_count;
				reshade::log::message(
					reshade::log::level::info,
					"D3DMetal RTX descriptor-resource lineage v49: TABLE_UNKNOWN unique_index=%llu stage=%s pso_id=%llu pso_kind=%u shader_hash=0x%llX root_index=%u gpu_handle=0x%llX.",
					static_cast<unsigned long long>(index),
					stage,
					static_cast<unsigned long long>(pso_id),
					pso_kind,
					static_cast<unsigned long long>(shader_hash),
					root_index,
					static_cast<unsigned long long>(base.ptr));
			}
			return;
		}

		bool found_any = false;
		for (UINT offset = 0; offset < 16u; ++offset)
		{
			const UINT descriptor_index = base_index + offset;
			if (descriptor_index >= base_heap.count)
				break;
			const SIZE_T cpu_ptr =
				base_heap.cpu_start +
				static_cast<SIZE_T>(descriptor_index) *
					base_heap.increment;
			v49_descriptor_info descriptor = {};
			if (!v49_get_descriptor(cpu_ptr, descriptor))
				continue;
			found_any = true;
			v49_resource_info resource = {};
			v49_get_resource(descriptor.resource_id, resource);
			uint64_t signature = v49_signature_seed(0x4902ull);
			signature = v49_signature_add(
				signature,
				stage[0] == 'g' ? 1ull : 2ull);
			signature = v49_signature_add(signature, pso_id);
			signature = v49_signature_add(signature, root_index);
			signature = v49_signature_add(
				signature, base_heap.heap_id);
			signature = v49_signature_add(
				signature, descriptor_index);
			signature = v49_signature_add(
				signature, descriptor.kind);
			signature = v49_signature_add(
				signature, descriptor.resource_id);
			if (!v49_take_unique(signature, 20000))
				continue;
			const uint64_t index = ++s_v49_table_event_count;
			reshade::log::message(
				reshade::log::level::info,
				"D3DMetal RTX descriptor-resource lineage v49: TABLE_BIND unique_index=%llu stage=%s pso_id=%llu pso_kind=%u shader_hash=0x%llX root_index=%u heap_id=%llu descriptor_index=%u descriptor_offset=%u descriptor_kind=%s resource_id=%llu view_format=%u view_dimension=%u first_element=%llu num_elements=%u stride=%u view_flags=0x%X resource_dimension=%u resource_width=%llu resource_height=%u resource_format=%u resource_flags=0x%X resource_gpu_va=0x%llX.",
				static_cast<unsigned long long>(index),
				stage,
				static_cast<unsigned long long>(pso_id),
				pso_kind,
				static_cast<unsigned long long>(shader_hash),
				root_index,
				static_cast<unsigned long long>(
					base_heap.heap_id),
				descriptor_index,
				offset,
				v49_descriptor_kind_name(descriptor.kind),
				static_cast<unsigned long long>(
					descriptor.resource_id),
				descriptor.format,
				descriptor.view_dimension,
				static_cast<unsigned long long>(
					descriptor.first_element),
				descriptor.num_elements,
				descriptor.structure_stride,
				descriptor.view_flags,
				resource.dimension,
				static_cast<unsigned long long>(resource.width),
				resource.height,
				resource.format,
				resource.flags,
				static_cast<unsigned long long>(
					resource.gpu_va));
		}
		if (!found_any)
		{
			uint64_t signature = v49_signature_seed(0x4903ull);
			signature = v49_signature_add(
				signature,
				stage[0] == 'g' ? 1ull : 2ull);
			signature = v49_signature_add(signature, pso_id);
			signature = v49_signature_add(signature, root_index);
			signature = v49_signature_add(
				signature, base_heap.heap_id);
			signature = v49_signature_add(
				signature, base_index);
			if (v49_take_unique(signature, 20000))
			{
				const uint64_t index = ++s_v49_table_event_count;
				reshade::log::message(
					reshade::log::level::info,
					"D3DMetal RTX descriptor-resource lineage v49: TABLE_EMPTY unique_index=%llu stage=%s pso_id=%llu pso_kind=%u shader_hash=0x%llX root_index=%u heap_id=%llu descriptor_index=%u gpu_handle=0x%llX.",
					static_cast<unsigned long long>(index),
					stage,
					static_cast<unsigned long long>(pso_id),
					pso_kind,
					static_cast<unsigned long long>(shader_hash),
					root_index,
					static_cast<unsigned long long>(
						base_heap.heap_id),
					base_index,
					static_cast<unsigned long long>(
						base.ptr));
			}
		}
	}

	void v49_log_direct_root(
		ID3D12GraphicsCommandList *command_list,
		const char *stage,
		const char *kind,
		UINT root_index,
		D3D12_GPU_VIRTUAL_ADDRESS address)
	{
		if (!v46_post_phase())
			return;
		v49_log_active();
		uint64_t pso_id = 0;
		unsigned int pso_kind = 0;
		uint64_t shader_hash = 0;
		v49_lookup_pso(
			command_list, pso_id, pso_kind, shader_hash);
		UINT64 resource_offset = 0;
		const uint64_t resource_id =
			v49_find_resource_by_va(
				address, resource_offset);
		uint64_t signature = v49_signature_seed(0x4904ull);
		signature = v49_signature_add(
			signature,
			stage[0] == 'g' ? 1ull : 2ull);
		signature = v49_signature_add(
			signature,
			kind[0] == 'u' ? 3ull :
			(kind[0] == 's' ? 2ull : 1ull));
		signature = v49_signature_add(signature, pso_id);
		signature = v49_signature_add(signature, root_index);
		signature = v49_signature_add(signature, resource_id);
		signature = v49_signature_add(
			signature, resource_offset);
		if (!v49_take_unique(signature, 20000))
			return;
		const uint64_t index =
			++s_v49_direct_root_event_count;
		reshade::log::message(
			reshade::log::level::info,
			"D3DMetal RTX descriptor-resource lineage v49: DIRECT_ROOT unique_index=%llu stage=%s root_kind=%s pso_id=%llu pso_kind=%u shader_hash=0x%llX root_index=%u gpu_va=0x%llX resource_id=%llu resource_offset=%llu.",
			static_cast<unsigned long long>(index),
			stage,
			kind,
			static_cast<unsigned long long>(pso_id),
			pso_kind,
			static_cast<unsigned long long>(shader_hash),
			root_index,
			static_cast<unsigned long long>(address),
			static_cast<unsigned long long>(resource_id),
			static_cast<unsigned long long>(resource_offset));
	}

	void v49_log_rtv(
		ID3D12GraphicsCommandList *command_list,
		UINT rtv_index,
		D3D12_CPU_DESCRIPTOR_HANDLE handle)
	{
		v49_descriptor_info descriptor = {};
		if (!v49_get_descriptor(handle.ptr, descriptor) ||
			descriptor.kind != 4)
			return;
		uint64_t pso_id = 0;
		unsigned int pso_kind = 0;
		uint64_t shader_hash = 0;
		v49_lookup_pso(
			command_list, pso_id, pso_kind, shader_hash);
		v49_resource_info resource = {};
		v49_get_resource(descriptor.resource_id, resource);
		uint64_t signature = v49_signature_seed(0x4905ull);
		signature = v49_signature_add(signature, pso_id);
		signature = v49_signature_add(signature, rtv_index);
		signature = v49_signature_add(
			signature, descriptor.resource_id);
		if (!v49_take_unique(signature, 20000))
			return;
		const uint64_t index = ++s_v49_rtv_event_count;
		reshade::log::message(
			reshade::log::level::info,
			"D3DMetal RTX descriptor-resource lineage v49: RTV_BIND unique_index=%llu pso_id=%llu pso_kind=%u shader_hash=0x%llX rtv_index=%u resource_id=%llu view_format=%u view_dimension=%u resource_dimension=%u resource_width=%llu resource_height=%u resource_format=%u resource_flags=0x%X.",
			static_cast<unsigned long long>(index),
			static_cast<unsigned long long>(pso_id),
			pso_kind,
			static_cast<unsigned long long>(shader_hash),
			rtv_index,
			static_cast<unsigned long long>(
				descriptor.resource_id),
			descriptor.format,
			descriptor.view_dimension,
			resource.dimension,
			static_cast<unsigned long long>(resource.width),
			resource.height,
			resource.format,
			resource.flags);
	}

	void STDMETHODCALLTYPE v49_trace_resource_barrier(
		ID3D12GraphicsCommandList *command_list,
		UINT count,
		const D3D12_RESOURCE_BARRIER *barriers)
	{
		if (v46_post_phase() && barriers != nullptr)
		{
			v49_log_active();
			const UINT capped = count < 256u ? count : 256u;
			for (UINT index = 0; index < capped; ++index)
			{
				D3D12_RESOURCE_BARRIER barrier = {};
				if (!safe_copy_from_process(
						barriers + index,
						&barrier,
						sizeof(barrier)))
					break;
				ID3D12Resource *resource_before = nullptr;
				ID3D12Resource *resource_after = nullptr;
				unsigned int before_state = 0;
				unsigned int after_state = 0;
				if (barrier.Type ==
					D3D12_RESOURCE_BARRIER_TYPE_TRANSITION)
				{
					resource_before =
						barrier.Transition.pResource;
					resource_after = resource_before;
					before_state =
						static_cast<unsigned int>(
							barrier.Transition.StateBefore);
					after_state =
						static_cast<unsigned int>(
							barrier.Transition.StateAfter);
				}
				else if (barrier.Type ==
					D3D12_RESOURCE_BARRIER_TYPE_UAV)
				{
					resource_before = barrier.UAV.pResource;
					resource_after = resource_before;
				}
				else if (barrier.Type ==
					D3D12_RESOURCE_BARRIER_TYPE_ALIASING)
				{
					resource_before =
						barrier.Aliasing.pResourceBefore;
					resource_after =
						barrier.Aliasing.pResourceAfter;
				}
				const uint64_t before_id =
					v49_register_resource(resource_before);
				const uint64_t after_id =
					v49_register_resource(resource_after);
				uint64_t signature =
					v49_signature_seed(0x4906ull);
				signature = v49_signature_add(
					signature,
					static_cast<unsigned int>(barrier.Type));
				signature = v49_signature_add(
					signature, before_id);
				signature = v49_signature_add(
					signature, after_id);
				signature = v49_signature_add(
					signature, before_state);
				signature = v49_signature_add(
					signature, after_state);
				signature = v49_signature_add(
					signature, barrier.Flags);
				if (!v49_take_unique(signature, 20000))
					continue;
				const uint64_t event =
					++s_v49_barrier_event_count;
				reshade::log::message(
					reshade::log::level::info,
					"D3DMetal RTX descriptor-resource lineage v49: RESOURCE_BARRIER unique_index=%llu type=%u flags=0x%X before_resource_id=%llu after_resource_id=%llu state_before=0x%X state_after=0x%X subresource=%u.",
					static_cast<unsigned long long>(event),
					static_cast<unsigned int>(barrier.Type),
					static_cast<unsigned int>(barrier.Flags),
					static_cast<unsigned long long>(before_id),
					static_cast<unsigned long long>(after_id),
					before_state,
					after_state,
					barrier.Type ==
						D3D12_RESOURCE_BARRIER_TYPE_TRANSITION ?
						barrier.Transition.Subresource : 0u);
			}
		}
		if (s_v49_original_resource_barrier != nullptr)
			s_v49_original_resource_barrier(
				command_list, count, barriers);
	}

	void STDMETHODCALLTYPE v49_trace_set_compute_root_table(
		ID3D12GraphicsCommandList *command_list,
		UINT root_index,
		D3D12_GPU_DESCRIPTOR_HANDLE base)
	{
		v49_log_table_binding(
			command_list, "compute", root_index, base);
		if (s_v49_original_set_compute_root_table != nullptr)
			s_v49_original_set_compute_root_table(
				command_list, root_index, base);
	}

	void STDMETHODCALLTYPE v49_trace_set_graphics_root_table(
		ID3D12GraphicsCommandList *command_list,
		UINT root_index,
		D3D12_GPU_DESCRIPTOR_HANDLE base)
	{
		v49_log_table_binding(
			command_list, "graphics", root_index, base);
		if (s_v49_original_set_graphics_root_table != nullptr)
			s_v49_original_set_graphics_root_table(
				command_list, root_index, base);
	}

#define V49_DIRECT_ROOT_WRAPPER(NAME, ORIGINAL, STAGE, KIND) \
	void STDMETHODCALLTYPE NAME( \
		ID3D12GraphicsCommandList *command_list, \
		UINT root_index, \
		D3D12_GPU_VIRTUAL_ADDRESS address) \
	{ \
		v49_log_direct_root( \
			command_list, STAGE, KIND, root_index, address); \
		if (ORIGINAL != nullptr) \
			ORIGINAL(command_list, root_index, address); \
	}

	V49_DIRECT_ROOT_WRAPPER(
		v49_trace_set_compute_root_cbv,
		s_v49_original_set_compute_root_cbv,
		"compute", "cbv")
	V49_DIRECT_ROOT_WRAPPER(
		v49_trace_set_graphics_root_cbv,
		s_v49_original_set_graphics_root_cbv,
		"graphics", "cbv")
	V49_DIRECT_ROOT_WRAPPER(
		v49_trace_set_compute_root_srv,
		s_v49_original_set_compute_root_srv,
		"compute", "srv")
	V49_DIRECT_ROOT_WRAPPER(
		v49_trace_set_graphics_root_srv,
		s_v49_original_set_graphics_root_srv,
		"graphics", "srv")
	V49_DIRECT_ROOT_WRAPPER(
		v49_trace_set_compute_root_uav,
		s_v49_original_set_compute_root_uav,
		"compute", "uav")
	V49_DIRECT_ROOT_WRAPPER(
		v49_trace_set_graphics_root_uav,
		s_v49_original_set_graphics_root_uav,
		"graphics", "uav")
#undef V49_DIRECT_ROOT_WRAPPER

	void STDMETHODCALLTYPE v49_trace_om_set_render_targets(
		ID3D12GraphicsCommandList *command_list,
		UINT count,
		const D3D12_CPU_DESCRIPTOR_HANDLE *render_targets,
		BOOL single_range,
		const D3D12_CPU_DESCRIPTOR_HANDLE *depth_stencil)
	{
		if (v46_post_phase() && render_targets != nullptr)
		{
			v49_log_active();
			D3D12_CPU_DESCRIPTOR_HANDLE first = {};
			if (safe_copy_from_process(
					render_targets, &first, sizeof(first)))
			{
				v49_heap_info heap = {};
				UINT first_index = 0;
				const bool has_heap =
					v49_find_heap_by_cpu(
						first.ptr, heap, first_index);
				const UINT capped = count < 16u ? count : 16u;
				for (UINT index = 0; index < capped; ++index)
				{
					D3D12_CPU_DESCRIPTOR_HANDLE handle = {};
					if (single_range && has_heap)
					{
						handle.ptr =
							first.ptr +
							static_cast<SIZE_T>(index) *
								heap.increment;
					}
					else if (!safe_copy_from_process(
							render_targets + index,
							&handle,
							sizeof(handle)))
					{
						break;
					}
					v49_log_rtv(
						command_list, index, handle);
				}
			}
		}
		if (s_v49_original_om_set_render_targets != nullptr)
			s_v49_original_om_set_render_targets(
				command_list,
				count,
				render_targets,
				single_range,
				depth_stencil);
	}

	void STDMETHODCALLTYPE v49_trace_clear_rtv(
		ID3D12GraphicsCommandList *command_list,
		D3D12_CPU_DESCRIPTOR_HANDLE target,
		const FLOAT color[4],
		UINT rect_count,
		const D3D12_RECT *rects)
	{
		if (v46_post_phase())
		{
			v49_log_active();
			v49_descriptor_info descriptor = {};
			v49_get_descriptor(target.ptr, descriptor);
			FLOAT values[4] = {};
			if (color != nullptr)
				safe_copy_from_process(
					color, values, sizeof(values));
			uint64_t signature = v49_signature_seed(0x4907ull);
			signature = v49_signature_add(
				signature, descriptor.resource_id);
			for (unsigned int index = 0; index < 4; ++index)
			{
				uint32_t bits = 0;
				memcpy(&bits, &values[index], sizeof(bits));
				signature = v49_signature_add(
					signature, bits);
			}
			if (v49_take_unique(signature, 20000))
			{
				const uint64_t event =
					++s_v49_clear_event_count;
				reshade::log::message(
					reshade::log::level::info,
					"D3DMetal RTX descriptor-resource lineage v49: CLEAR_RTV unique_index=%llu resource_id=%llu color=%g,%g,%g,%g rect_count=%u.",
					static_cast<unsigned long long>(event),
					static_cast<unsigned long long>(
						descriptor.resource_id),
					values[0], values[1], values[2], values[3],
					rect_count);
			}
		}
		if (s_v49_original_clear_rtv != nullptr)
			s_v49_original_clear_rtv(
				command_list, target, color, rect_count, rects);
	}

	void v49_log_clear_uav(
		const char *value_type,
		D3D12_GPU_DESCRIPTOR_HANDLE gpu_handle,
		D3D12_CPU_DESCRIPTOR_HANDLE cpu_handle,
		ID3D12Resource *resource,
		const void *values,
		UINT rect_count)
	{
		if (!v46_post_phase())
			return;
		v49_log_active();
		const uint64_t resource_id =
			v49_register_resource(resource);
		v49_descriptor_info descriptor = {};
		v49_get_descriptor(cpu_handle.ptr, descriptor);
		uint64_t signature = v49_signature_seed(0x4908ull);
		signature = v49_signature_add(signature, resource_id);
		signature = v49_signature_add(
			signature,
			value_type[0] == 'u' ? 1ull : 2ull);
		if (values != nullptr)
		{
			unsigned char bytes[16] = {};
			if (safe_copy_from_process(values, bytes, sizeof(bytes)))
				for (unsigned int index = 0;
					index < sizeof(bytes); ++index)
					signature = v49_signature_add(
						signature, bytes[index]);
		}
		if (!v49_take_unique(signature, 20000))
			return;
		const uint64_t event = ++s_v49_clear_event_count;
		reshade::log::message(
			reshade::log::level::info,
			"D3DMetal RTX descriptor-resource lineage v49: CLEAR_UAV unique_index=%llu value_type=%s resource_id=%llu descriptor_resource_id=%llu gpu_handle=0x%llX cpu_handle=0x%llX rect_count=%u.",
			static_cast<unsigned long long>(event),
			value_type,
			static_cast<unsigned long long>(resource_id),
			static_cast<unsigned long long>(
				descriptor.resource_id),
			static_cast<unsigned long long>(gpu_handle.ptr),
			static_cast<unsigned long long>(cpu_handle.ptr),
			rect_count);
	}

	void STDMETHODCALLTYPE v49_trace_clear_uav_uint(
		ID3D12GraphicsCommandList *command_list,
		D3D12_GPU_DESCRIPTOR_HANDLE gpu_handle,
		D3D12_CPU_DESCRIPTOR_HANDLE cpu_handle,
		ID3D12Resource *resource,
		const UINT values[4],
		UINT rect_count,
		const D3D12_RECT *rects)
	{
		v49_log_clear_uav(
			"uint", gpu_handle, cpu_handle,
			resource, values, rect_count);
		if (s_v49_original_clear_uav_uint != nullptr)
			s_v49_original_clear_uav_uint(
				command_list, gpu_handle, cpu_handle,
				resource, values, rect_count, rects);
	}

	void STDMETHODCALLTYPE v49_trace_clear_uav_float(
		ID3D12GraphicsCommandList *command_list,
		D3D12_GPU_DESCRIPTOR_HANDLE gpu_handle,
		D3D12_CPU_DESCRIPTOR_HANDLE cpu_handle,
		ID3D12Resource *resource,
		const FLOAT values[4],
		UINT rect_count,
		const D3D12_RECT *rects)
	{
		v49_log_clear_uav(
			"float", gpu_handle, cpu_handle,
			resource, values, rect_count);
		if (s_v49_original_clear_uav_float != nullptr)
			s_v49_original_clear_uav_float(
				command_list, gpu_handle, cpu_handle,
				resource, values, rect_count, rects);
	}

	void v49_install_descriptor_device_hooks(ID3D12Device *device)
	{
		if (device == nullptr)
			return;
		std::call_once(
			s_v49_device_hook_once,
			[device]()
			{
				void **const vtable =
					*reinterpret_cast<void ***>(device);
				s_v49_original_create_descriptor_heap =
					reinterpret_cast<
						v49_create_descriptor_heap_fn>(
							vtable[
								v49_create_descriptor_heap_slot]);
				s_v49_original_create_cbv =
					reinterpret_cast<v49_create_cbv_fn>(
						vtable[v49_create_cbv_slot]);
				s_v49_original_create_srv =
					reinterpret_cast<v49_create_srv_fn>(
						vtable[v49_create_srv_slot]);
				s_v49_original_create_uav =
					reinterpret_cast<v49_create_uav_fn>(
						vtable[v49_create_uav_slot]);
				s_v49_original_create_rtv =
					reinterpret_cast<v49_create_rtv_fn>(
						vtable[v49_create_rtv_slot]);
				s_v49_original_copy_descriptors =
					reinterpret_cast<
						v49_copy_descriptors_fn>(
							vtable[
								v49_copy_descriptors_slot]);
				s_v49_original_copy_descriptors_simple =
					reinterpret_cast<
						v49_copy_descriptors_simple_fn>(
							vtable[
								v49_copy_descriptors_simple_slot]);

				DWORD old_protect = 0;
				if (!VirtualProtect(
						&vtable[
							v49_create_descriptor_heap_slot],
						sizeof(void *) *
							(v49_copy_descriptors_simple_slot -
							 v49_create_descriptor_heap_slot + 1),
						PAGE_EXECUTE_READWRITE,
						&old_protect))
				{
					reshade::log::message(
						reshade::log::level::warning,
						"D3DMetal RTX descriptor-resource lineage v49: DEVICE_HOOKS installed=0 error=%lu.",
						GetLastError());
					return;
				}

#define V49_INSTALL_DEVICE_SLOT(SLOT, FUNCTION) \
				InterlockedExchangePointer( \
					reinterpret_cast<PVOID volatile *>( \
						&vtable[SLOT]), \
					reinterpret_cast<PVOID>(&FUNCTION))
				V49_INSTALL_DEVICE_SLOT(
					v49_create_descriptor_heap_slot,
					v49_trace_create_descriptor_heap);
				V49_INSTALL_DEVICE_SLOT(
					v49_create_cbv_slot,
					v49_trace_create_cbv);
				V49_INSTALL_DEVICE_SLOT(
					v49_create_srv_slot,
					v49_trace_create_srv);
				V49_INSTALL_DEVICE_SLOT(
					v49_create_uav_slot,
					v49_trace_create_uav);
				V49_INSTALL_DEVICE_SLOT(
					v49_create_rtv_slot,
					v49_trace_create_rtv);
				V49_INSTALL_DEVICE_SLOT(
					v49_copy_descriptors_slot,
					v49_trace_copy_descriptors);
				V49_INSTALL_DEVICE_SLOT(
					v49_copy_descriptors_simple_slot,
					v49_trace_copy_descriptors_simple);
#undef V49_INSTALL_DEVICE_SLOT

				DWORD ignored = 0;
				VirtualProtect(
					&vtable[
						v49_create_descriptor_heap_slot],
					sizeof(void *) *
						(v49_copy_descriptors_simple_slot -
						 v49_create_descriptor_heap_slot + 1),
					old_protect,
					&ignored);
				FlushInstructionCache(
					GetCurrentProcess(),
					&vtable[
						v49_create_descriptor_heap_slot],
					sizeof(void *) *
						(v49_copy_descriptors_simple_slot -
						 v49_create_descriptor_heap_slot + 1));

				const bool verified =
					vtable[v49_create_descriptor_heap_slot] ==
						reinterpret_cast<void *>(
							&v49_trace_create_descriptor_heap) &&
					vtable[v49_create_cbv_slot] ==
						reinterpret_cast<void *>(
							&v49_trace_create_cbv) &&
					vtable[v49_create_srv_slot] ==
						reinterpret_cast<void *>(
							&v49_trace_create_srv) &&
					vtable[v49_create_uav_slot] ==
						reinterpret_cast<void *>(
							&v49_trace_create_uav) &&
					vtable[v49_create_rtv_slot] ==
						reinterpret_cast<void *>(
							&v49_trace_create_rtv) &&
					vtable[v49_copy_descriptors_slot] ==
						reinterpret_cast<void *>(
							&v49_trace_copy_descriptors) &&
					vtable[v49_copy_descriptors_simple_slot] ==
						reinterpret_cast<void *>(
							&v49_trace_copy_descriptors_simple);
				reshade::log::message(
					verified ?
						reshade::log::level::info :
						reshade::log::level::warning,
					"D3DMetal RTX descriptor-resource lineage v49: DEVICE_HOOKS installed=%u heap_slot=%zu cbv_slot=%zu srv_slot=%zu uav_slot=%zu rtv_slot=%zu copy_slot=%zu copy_simple_slot=%zu.",
					verified ? 1u : 0u,
					v49_create_descriptor_heap_slot,
					v49_create_cbv_slot,
					v49_create_srv_slot,
					v49_create_uav_slot,
					v49_create_rtv_slot,
					v49_copy_descriptors_slot,
					v49_copy_descriptors_simple_slot);
			});
	}

	void v49_install_descriptor_command_hooks(
		IUnknown *command_list)
	{
		if (command_list == nullptr)
			return;
		std::call_once(
			s_v49_command_hook_once,
			[command_list]()
			{
				ID3D12GraphicsCommandList *list = nullptr;
				const HRESULT query_hr =
					command_list->QueryInterface(
						__uuidof(ID3D12GraphicsCommandList),
						reinterpret_cast<void **>(&list));
				if (FAILED(query_hr) || list == nullptr)
				{
					reshade::log::message(
						reshade::log::level::warning,
						"D3DMetal RTX descriptor-resource lineage v49: COMMAND_HOOKS installed=0 query_raw=0x%08X.",
						static_cast<uint32_t>(query_hr));
					return;
				}
				void **const vtable =
					*reinterpret_cast<void ***>(list);
				s_v49_original_resource_barrier =
					reinterpret_cast<v49_resource_barrier_fn>(
						vtable[v49_resource_barrier_slot]);
				s_v49_original_set_compute_root_table =
					reinterpret_cast<v49_root_table_fn>(
						vtable[
							v49_set_compute_root_table_slot]);
				s_v49_original_set_graphics_root_table =
					reinterpret_cast<v49_root_table_fn>(
						vtable[
							v49_set_graphics_root_table_slot]);
				s_v49_original_set_compute_root_cbv =
					reinterpret_cast<v49_root_va_fn>(
						vtable[
							v49_set_compute_root_cbv_slot]);
				s_v49_original_set_graphics_root_cbv =
					reinterpret_cast<v49_root_va_fn>(
						vtable[
							v49_set_graphics_root_cbv_slot]);
				s_v49_original_set_compute_root_srv =
					reinterpret_cast<v49_root_va_fn>(
						vtable[
							v49_set_compute_root_srv_slot]);
				s_v49_original_set_graphics_root_srv =
					reinterpret_cast<v49_root_va_fn>(
						vtable[
							v49_set_graphics_root_srv_slot]);
				s_v49_original_set_compute_root_uav =
					reinterpret_cast<v49_root_va_fn>(
						vtable[
							v49_set_compute_root_uav_slot]);
				s_v49_original_set_graphics_root_uav =
					reinterpret_cast<v49_root_va_fn>(
						vtable[
							v49_set_graphics_root_uav_slot]);
				s_v49_original_om_set_render_targets =
					reinterpret_cast<
						v49_om_set_render_targets_fn>(
							vtable[
								v49_om_set_render_targets_slot]);
				s_v49_original_clear_rtv =
					reinterpret_cast<v49_clear_rtv_fn>(
						vtable[v49_clear_rtv_slot]);
				s_v49_original_clear_uav_uint =
					reinterpret_cast<v49_clear_uav_uint_fn>(
						vtable[v49_clear_uav_uint_slot]);
				s_v49_original_clear_uav_float =
					reinterpret_cast<v49_clear_uav_float_fn>(
						vtable[v49_clear_uav_float_slot]);

				DWORD old_protect = 0;
				if (!VirtualProtect(
						&vtable[v49_resource_barrier_slot],
						sizeof(void *) *
							(v49_clear_uav_float_slot -
							 v49_resource_barrier_slot + 1),
						PAGE_EXECUTE_READWRITE,
						&old_protect))
				{
					reshade::log::message(
						reshade::log::level::warning,
						"D3DMetal RTX descriptor-resource lineage v49: COMMAND_HOOKS installed=0 error=%lu.",
						GetLastError());
					list->Release();
					return;
				}

#define V49_INSTALL_COMMAND_SLOT(SLOT, FUNCTION) \
				InterlockedExchangePointer( \
					reinterpret_cast<PVOID volatile *>( \
						&vtable[SLOT]), \
					reinterpret_cast<PVOID>(&FUNCTION))
				V49_INSTALL_COMMAND_SLOT(
					v49_resource_barrier_slot,
					v49_trace_resource_barrier);
				V49_INSTALL_COMMAND_SLOT(
					v49_set_compute_root_table_slot,
					v49_trace_set_compute_root_table);
				V49_INSTALL_COMMAND_SLOT(
					v49_set_graphics_root_table_slot,
					v49_trace_set_graphics_root_table);
				V49_INSTALL_COMMAND_SLOT(
					v49_set_compute_root_cbv_slot,
					v49_trace_set_compute_root_cbv);
				V49_INSTALL_COMMAND_SLOT(
					v49_set_graphics_root_cbv_slot,
					v49_trace_set_graphics_root_cbv);
				V49_INSTALL_COMMAND_SLOT(
					v49_set_compute_root_srv_slot,
					v49_trace_set_compute_root_srv);
				V49_INSTALL_COMMAND_SLOT(
					v49_set_graphics_root_srv_slot,
					v49_trace_set_graphics_root_srv);
				V49_INSTALL_COMMAND_SLOT(
					v49_set_compute_root_uav_slot,
					v49_trace_set_compute_root_uav);
				V49_INSTALL_COMMAND_SLOT(
					v49_set_graphics_root_uav_slot,
					v49_trace_set_graphics_root_uav);
				V49_INSTALL_COMMAND_SLOT(
					v49_om_set_render_targets_slot,
					v49_trace_om_set_render_targets);
				V49_INSTALL_COMMAND_SLOT(
					v49_clear_rtv_slot,
					v49_trace_clear_rtv);
				V49_INSTALL_COMMAND_SLOT(
					v49_clear_uav_uint_slot,
					v49_trace_clear_uav_uint);
				V49_INSTALL_COMMAND_SLOT(
					v49_clear_uav_float_slot,
					v49_trace_clear_uav_float);
#undef V49_INSTALL_COMMAND_SLOT

				DWORD ignored = 0;
				VirtualProtect(
					&vtable[v49_resource_barrier_slot],
					sizeof(void *) *
						(v49_clear_uav_float_slot -
						 v49_resource_barrier_slot + 1),
					old_protect,
					&ignored);
				FlushInstructionCache(
					GetCurrentProcess(),
					&vtable[v49_resource_barrier_slot],
					sizeof(void *) *
						(v49_clear_uav_float_slot -
						 v49_resource_barrier_slot + 1));

				const bool verified =
					vtable[v49_resource_barrier_slot] ==
						reinterpret_cast<void *>(
							&v49_trace_resource_barrier) &&
					vtable[v49_set_compute_root_table_slot] ==
						reinterpret_cast<void *>(
							&v49_trace_set_compute_root_table) &&
					vtable[v49_set_graphics_root_table_slot] ==
						reinterpret_cast<void *>(
							&v49_trace_set_graphics_root_table) &&
					vtable[v49_set_compute_root_uav_slot] ==
						reinterpret_cast<void *>(
							&v49_trace_set_compute_root_uav) &&
					vtable[v49_set_graphics_root_uav_slot] ==
						reinterpret_cast<void *>(
							&v49_trace_set_graphics_root_uav) &&
					vtable[v49_om_set_render_targets_slot] ==
						reinterpret_cast<void *>(
							&v49_trace_om_set_render_targets) &&
					vtable[v49_clear_uav_uint_slot] ==
						reinterpret_cast<void *>(
							&v49_trace_clear_uav_uint) &&
					vtable[v49_clear_uav_float_slot] ==
						reinterpret_cast<void *>(
							&v49_trace_clear_uav_float);
				reshade::log::message(
					verified ?
						reshade::log::level::info :
						reshade::log::level::warning,
					"D3DMetal RTX descriptor-resource lineage v49: COMMAND_HOOKS installed=%u barrier_slot=%zu compute_table_slot=%zu graphics_table_slot=%zu compute_uav_slot=%zu graphics_uav_slot=%zu rtv_slot=%zu clear_rtv_slot=%zu clear_uav_uint_slot=%zu clear_uav_float_slot=%zu.",
					verified ? 1u : 0u,
					v49_resource_barrier_slot,
					v49_set_compute_root_table_slot,
					v49_set_graphics_root_table_slot,
					v49_set_compute_root_uav_slot,
					v49_set_graphics_root_uav_slot,
					v49_om_set_render_targets_slot,
					v49_clear_rtv_slot,
					v49_clear_uav_uint_slot,
					v49_clear_uav_float_slot);
				list->Release();
			});
	}
'''
text = text.replace(
    helper_anchor,
    helper + "\n" + helper_anchor,
    1,
)

command_install_anchor = (
    "\t\t\tv46_install_nonrt_command_hooks(\n"
    "\t\t\t\treinterpret_cast<IUnknown *>(created));\n"
)
command_install_replacement = (
    command_install_anchor +
    "\t\t\tv49_install_descriptor_command_hooks(\n"
    "\t\t\t\treinterpret_cast<IUnknown *>(created));\n"
)
count = text.count(command_install_anchor)
if count != 2:
    raise RuntimeError(
        f"V49 command-hook installation: expected 2 occurrences, found {count}")
text = text.replace(
    command_install_anchor,
    command_install_replacement,
)

device_install_anchor = "\t\tv46_install_pso_creation_hooks(device);\n"
device_install_replacement = (
    device_install_anchor +
    "\t\tv49_install_descriptor_device_hooks(device);\n"
)
text = replace_once(
    text,
    device_install_anchor,
    device_install_replacement,
    "V49 device-hook installation",
)

required_markers = (
    "D3DMetal RTX descriptor-resource lineage v49: ACTIVE",
    "HEAP_REGISTER heap_id=",
    "RESOURCE_REGISTER resource_id=",
    "TABLE_BIND unique_index=",
    "TABLE_UNKNOWN unique_index=",
    "DIRECT_ROOT unique_index=",
    "RTV_BIND unique_index=",
    "CLEAR_RTV unique_index=",
    "CLEAR_UAV unique_index=",
    "RESOURCE_BARRIER unique_index=",
    "DEVICE_HOOKS installed=",
    "COMMAND_HOOKS installed=",
)
for marker in required_markers:
    if marker not in text:
        raise RuntimeError(f"V49 generated source is missing marker: {marker}")

if text.count("v49_install_descriptor_command_hooks(") != 3:
    raise RuntimeError(
        "V49 expected one definition and two command-list install calls")
if "\\t" in text:
    raise RuntimeError(
        "V49 generated source contains literal tab escape text")
if text.count("{") != text.count("}"):
    raise RuntimeError(
        f"V49 generated source has unbalanced braces: "
        f"{text.count('{')} vs {text.count('}')}")

SOURCE.write_text(text, encoding="utf-8", newline="\n")

report = '''V49_DESCRIPTOR_RESOURCE_LINEAGE_PATCH_OK
BASELINE=V41_NO_OUTPUT_V45_ZERO_RT_BIND_V44_ZERO_RAY_DISPATCH
V46_NONRT_PSO_CENSUS_PRESERVED=YES
V46_REPETITIVE_LOG_CADENCE_REDUCED=YES
CREATE_DESCRIPTOR_HEAP_SLOT=14
CREATE_CBV_SLOT=17
CREATE_SRV_SLOT=18
CREATE_UAV_SLOT=19
CREATE_RTV_SLOT=20
COPY_DESCRIPTORS_SLOT=23
COPY_DESCRIPTORS_SIMPLE_SLOT=24
RESOURCE_BARRIER_SLOT=26
SET_COMPUTE_ROOT_DESCRIPTOR_TABLE_SLOT=31
SET_GRAPHICS_ROOT_DESCRIPTOR_TABLE_SLOT=32
DIRECT_ROOT_CBV_SRV_UAV_SLOTS=37_TO_42
OM_SET_RENDER_TARGETS_SLOT=46
CLEAR_RENDER_TARGET_VIEW_SLOT=48
CLEAR_UNORDERED_ACCESS_VIEW_UINT_SLOT=49
CLEAR_UNORDERED_ACCESS_VIEW_FLOAT_SLOT=50
DESCRIPTOR_COPY_PROPAGATION=ENABLED
RESOURCE_METADATA_LEDGER=ENABLED
GPU_DESCRIPTOR_TABLE_TO_RESOURCE_MAPPING=ENABLED
DIRECT_ROOT_GPU_VA_TO_BUFFER_MAPPING=ENABLED
RENDER_TARGET_MAPPING=ENABLED
CLEAR_VALUE_TRACING=ENABLED
RESOURCE_BARRIER_TRACING=ENABLED
DRAWS_DISPATCHES_DESCRIPTORS_RESOURCES_MODIFIED=NO
CONTROL_FLOW_CHANGE=NONE
RESULT=PASS
'''
Path("v49-patch-report.txt").write_text(
    report, encoding="utf-8", newline="\n")
print(report, end="")
