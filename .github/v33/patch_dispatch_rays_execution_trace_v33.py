from pathlib import Path

SOURCE = Path("source/d3d12/d3d12.cpp")
if not SOURCE.is_file():
    raise RuntimeError(f"Missing source file: {SOURCE}")

text = SOURCE.read_text(encoding="utf-8-sig")
if "D3DMetal RTX FP32 universal bridge v32:" not in text:
    raise RuntimeError("V32 must be applied before V33")
if "D3DMetal RTX execution trace v33:" in text:
    raise RuntimeError("V33 is already present")

include_anchor = "#include <unordered_map>\n"
if include_anchor not in text:
    anchor = "#include <initializer_list>\n"
    if text.count(anchor) != 1:
        raise RuntimeError("V33 include anchor mismatch")
    text = text.replace(anchor, anchor + "#include <unordered_map>\n", 1)

v32_anchor = "\tstatic std::atomic<unsigned int> s_v32_rewrite_attempts = 0;\n"
if text.count(v32_anchor) != 1:
    raise RuntimeError(f"V33 V32 helper anchor mismatch: {text.count(v32_anchor)}")

helper = r'''
	using v33_create_command_list_fn = HRESULT (STDMETHODCALLTYPE *)(
		ID3D12Device *,
		UINT,
		D3D12_COMMAND_LIST_TYPE,
		ID3D12CommandAllocator *,
		ID3D12PipelineState *,
		REFIID,
		void **);

	using v33_create_command_list1_fn = HRESULT (STDMETHODCALLTYPE *)(
		ID3D12Device4 *,
		UINT,
		D3D12_COMMAND_LIST_TYPE,
		D3D12_COMMAND_LIST_FLAGS,
		REFIID,
		void **);

	using v33_set_pipeline_state1_fn = void (STDMETHODCALLTYPE *)(
		ID3D12GraphicsCommandList4 *,
		ID3D12StateObject *);

	using v33_dispatch_rays_fn = void (STDMETHODCALLTYPE *)(
		ID3D12GraphicsCommandList4 *,
		const D3D12_DISPATCH_RAYS_DESC *);

	constexpr size_t v33_create_command_list_slot = 12;
	constexpr size_t v33_create_command_list1_slot = 51;
	constexpr size_t v33_set_pipeline_state1_slot = 75;
	constexpr size_t v33_dispatch_rays_slot = 76;

	static v33_create_command_list_fn s_v33_original_create_command_list = nullptr;
	static v33_create_command_list1_fn s_v33_original_create_command_list1 = nullptr;
	static v33_set_pipeline_state1_fn s_v33_original_set_pipeline_state1 = nullptr;
	static v33_dispatch_rays_fn s_v33_original_dispatch_rays = nullptr;

	static std::once_flag s_v33_device_hook_once;
	static std::atomic<bool> s_v33_command_list_hooks_installed = false;
	static std::mutex s_v33_command_list_install_mutex;
	static std::mutex s_v33_state_mutex;
	static std::mutex s_v33_binding_mutex;
	static std::unordered_map<void *, uint64_t> s_v33_rewritten_state_calls;
	static std::unordered_map<void *, uint64_t> s_v33_bound_state_calls;
	static std::atomic<uint64_t> s_v33_created_command_lists = 0;
	static std::atomic<uint64_t> s_v33_bind_total = 0;
	static std::atomic<uint64_t> s_v33_bind_rewritten = 0;
	static std::atomic<uint64_t> s_v33_dispatch_total = 0;
	static std::atomic<uint64_t> s_v33_dispatch_rewritten = 0;

	void *v33_identity_pointer(IUnknown *object)
	{
		if (object == nullptr)
			return nullptr;

		IUnknown *identity = nullptr;
		if (FAILED(object->QueryInterface(
			IID_IUnknown,
			reinterpret_cast<void **>(&identity))) ||
			identity == nullptr)
			return nullptr;

		void *const value = identity;
		identity->Release();
		return value;
	}

	void v33_register_rewritten_state_object(void *state_object, uint64_t create_call)
	{
		void *const identity = v33_identity_pointer(
			reinterpret_cast<IUnknown *>(state_object));
		if (identity == nullptr)
		{
			reshade::log::message(
				reshade::log::level::warning,
				"D3DMetal RTX execution trace v33: REGISTER_FAILED state_call=%llu object=%p reason=no-iunknown-identity.",
				static_cast<unsigned long long>(create_call),
				state_object);
			return;
		}

		{
			std::lock_guard<std::mutex> lock(s_v33_state_mutex);
			s_v33_rewritten_state_calls[identity] = create_call;
		}

		reshade::log::message(
			reshade::log::level::info,
			"D3DMetal RTX execution trace v33: REGISTER state_call=%llu object=%p identity=%p.",
			static_cast<unsigned long long>(create_call),
			state_object,
			identity);
	}

	bool v33_lookup_rewritten_state_object(
		ID3D12StateObject *state_object,
		uint64_t &create_call)
	{
		create_call = 0;
		void *const identity = v33_identity_pointer(
			reinterpret_cast<IUnknown *>(state_object));
		if (identity == nullptr)
			return false;

		std::lock_guard<std::mutex> lock(s_v33_state_mutex);
		const auto found = s_v33_rewritten_state_calls.find(identity);
		if (found == s_v33_rewritten_state_calls.end())
			return false;

		create_call = found->second;
		return true;
	}

	void STDMETHODCALLTYPE v33_trace_set_pipeline_state1(
		ID3D12GraphicsCommandList4 *command_list,
		ID3D12StateObject *state_object)
	{
		const uint64_t bind_total = ++s_v33_bind_total;
		uint64_t state_call = 0;
		const bool rewritten = v33_lookup_rewritten_state_object(
			state_object, state_call);

		if (s_v33_original_set_pipeline_state1 != nullptr)
			s_v33_original_set_pipeline_state1(command_list, state_object);

		{
			std::lock_guard<std::mutex> lock(s_v33_binding_mutex);
			if (rewritten)
				s_v33_bound_state_calls[command_list] = state_call;
			else
				s_v33_bound_state_calls.erase(command_list);
		}

		if (rewritten)
		{
			const uint64_t rewritten_index = ++s_v33_bind_rewritten;
			if (rewritten_index <= 16 || (rewritten_index % 120) == 0)
			{
				reshade::log::message(
					reshade::log::level::info,
					"D3DMetal RTX execution trace v33: BIND_REWRITTEN bind_index=%llu bind_total=%llu state_call=%llu command_list=%p state_object=%p.",
					static_cast<unsigned long long>(rewritten_index),
					static_cast<unsigned long long>(bind_total),
					static_cast<unsigned long long>(state_call),
					command_list,
					state_object);
			}
		}
		else if (bind_total <= 8)
		{
			reshade::log::message(
				reshade::log::level::info,
				"D3DMetal RTX execution trace v33: BIND_OTHER bind_total=%llu command_list=%p state_object=%p.",
				static_cast<unsigned long long>(bind_total),
				command_list,
				state_object);
		}
	}

	void STDMETHODCALLTYPE v33_trace_dispatch_rays(
		ID3D12GraphicsCommandList4 *command_list,
		const D3D12_DISPATCH_RAYS_DESC *desc)
	{
		const uint64_t dispatch_total = ++s_v33_dispatch_total;
		uint64_t state_call = 0;
		bool rewritten = false;
		{
			std::lock_guard<std::mutex> lock(s_v33_binding_mutex);
			const auto found = s_v33_bound_state_calls.find(command_list);
			if (found != s_v33_bound_state_calls.end())
			{
				rewritten = true;
				state_call = found->second;
			}
		}

		D3D12_DISPATCH_RAYS_DESC snapshot = {};
		const bool readable =
			desc != nullptr &&
			safe_copy_from_process(desc, &snapshot, sizeof(snapshot));

		uint64_t rewritten_index = 0;
		if (rewritten)
			rewritten_index = ++s_v33_dispatch_rewritten;

		const bool should_log =
			(rewritten && (rewritten_index <= 24 || (rewritten_index % 120) == 0)) ||
			(!rewritten && dispatch_total <= 8);

		if (should_log)
		{
			if (readable)
			{
				const uint64_t raygen_address =
					static_cast<uint64_t>(snapshot.RayGenerationShaderRecord.StartAddress);
				const uint64_t miss_address =
					static_cast<uint64_t>(snapshot.MissShaderTable.StartAddress);
				const uint64_t hit_address =
					static_cast<uint64_t>(snapshot.HitGroupTable.StartAddress);
				const uint64_t callable_address =
					static_cast<uint64_t>(snapshot.CallableShaderTable.StartAddress);

				reshade::log::message(
					reshade::log::level::info,
					"D3DMetal RTX execution trace v33: DISPATCH sample=%llu dispatch_total=%llu rewritten=%u rewritten_index=%llu state_call=%llu command_list=%p width=%u height=%u depth=%u raygen_addr=0x%llX raygen_size=%llu raygen_align64=%llu miss_addr=0x%llX miss_size=%llu miss_stride=%llu miss_addr_align64=%llu miss_stride_align32=%llu hit_addr=0x%llX hit_size=%llu hit_stride=%llu hit_addr_align64=%llu hit_stride_align32=%llu callable_addr=0x%llX callable_size=%llu callable_stride=%llu callable_addr_align64=%llu callable_stride_align32=%llu.",
					static_cast<unsigned long long>(
						rewritten ? rewritten_index : dispatch_total),
					static_cast<unsigned long long>(dispatch_total),
					rewritten ? 1u : 0u,
					static_cast<unsigned long long>(rewritten_index),
					static_cast<unsigned long long>(state_call),
					command_list,
					snapshot.Width,
					snapshot.Height,
					snapshot.Depth,
					static_cast<unsigned long long>(raygen_address),
					static_cast<unsigned long long>(
						snapshot.RayGenerationShaderRecord.SizeInBytes),
					static_cast<unsigned long long>(raygen_address % 64ull),
					static_cast<unsigned long long>(miss_address),
					static_cast<unsigned long long>(
						snapshot.MissShaderTable.SizeInBytes),
					static_cast<unsigned long long>(
						snapshot.MissShaderTable.StrideInBytes),
					static_cast<unsigned long long>(miss_address % 64ull),
					static_cast<unsigned long long>(
						snapshot.MissShaderTable.StrideInBytes % 32ull),
					static_cast<unsigned long long>(hit_address),
					static_cast<unsigned long long>(
						snapshot.HitGroupTable.SizeInBytes),
					static_cast<unsigned long long>(
						snapshot.HitGroupTable.StrideInBytes),
					static_cast<unsigned long long>(hit_address % 64ull),
					static_cast<unsigned long long>(
						snapshot.HitGroupTable.StrideInBytes % 32ull),
					static_cast<unsigned long long>(callable_address),
					static_cast<unsigned long long>(
						snapshot.CallableShaderTable.SizeInBytes),
					static_cast<unsigned long long>(
						snapshot.CallableShaderTable.StrideInBytes),
					static_cast<unsigned long long>(callable_address % 64ull),
					static_cast<unsigned long long>(
						snapshot.CallableShaderTable.StrideInBytes % 32ull));
			}
			else
			{
				reshade::log::message(
					reshade::log::level::warning,
					"D3DMetal RTX execution trace v33: DISPATCH_UNREADABLE dispatch_total=%llu rewritten=%u rewritten_index=%llu state_call=%llu command_list=%p desc=%p.",
					static_cast<unsigned long long>(dispatch_total),
					rewritten ? 1u : 0u,
					static_cast<unsigned long long>(rewritten_index),
					static_cast<unsigned long long>(state_call),
					command_list,
					desc);
			}
		}

		if (s_v33_original_dispatch_rays != nullptr)
			s_v33_original_dispatch_rays(command_list, desc);
	}

	void v33_install_command_list_method_hooks(IUnknown *command_list)
	{
		if (command_list == nullptr ||
			s_v33_command_list_hooks_installed.load(std::memory_order_acquire))
			return;

		std::lock_guard<std::mutex> install_lock(
			s_v33_command_list_install_mutex);
		if (s_v33_command_list_hooks_installed.load(
			std::memory_order_relaxed))
			return;

		ID3D12GraphicsCommandList4 *list4 = nullptr;
		const HRESULT query_hr = command_list->QueryInterface(
			__uuidof(ID3D12GraphicsCommandList4),
			reinterpret_cast<void **>(&list4));
		if (FAILED(query_hr) || list4 == nullptr)
		{
			reshade::log::message(
				reshade::log::level::warning,
				"D3DMetal RTX execution trace v33: ID3D12GraphicsCommandList4 unavailable hr=%s raw=0x%08X; later command lists will be retried.",
				reshade::log::hr_to_string(query_hr).c_str(),
				static_cast<uint32_t>(query_hr));
			return;
		}

		void **const vtable =
			*reinterpret_cast<void ***>(list4);
		void *const current_set =
			vtable[v33_set_pipeline_state1_slot];
		void *const current_dispatch =
			vtable[v33_dispatch_rays_slot];

		if (current_set == reinterpret_cast<void *>(
				&v33_trace_set_pipeline_state1) &&
			current_dispatch == reinterpret_cast<void *>(
				&v33_trace_dispatch_rays))
		{
			s_v33_command_list_hooks_installed.store(
				true, std::memory_order_release);
			list4->Release();
			return;
		}

		s_v33_original_set_pipeline_state1 =
			reinterpret_cast<v33_set_pipeline_state1_fn>(current_set);
		s_v33_original_dispatch_rays =
			reinterpret_cast<v33_dispatch_rays_fn>(current_dispatch);

		DWORD old_protect = 0;
		if (!VirtualProtect(
			&vtable[v33_set_pipeline_state1_slot],
			sizeof(void *) * 2,
			PAGE_EXECUTE_READWRITE,
			&old_protect))
		{
			reshade::log::message(
				reshade::log::level::warning,
				"D3DMetal RTX execution trace v33: command-list VirtualProtect failed error=%lu.",
				GetLastError());
			s_v33_original_set_pipeline_state1 = nullptr;
			s_v33_original_dispatch_rays = nullptr;
			list4->Release();
			return;
		}

		InterlockedExchangePointer(
			reinterpret_cast<PVOID volatile *>(
				&vtable[v33_set_pipeline_state1_slot]),
			reinterpret_cast<PVOID>(
				&v33_trace_set_pipeline_state1));
		InterlockedExchangePointer(
			reinterpret_cast<PVOID volatile *>(
				&vtable[v33_dispatch_rays_slot]),
			reinterpret_cast<PVOID>(
				&v33_trace_dispatch_rays));

		DWORD ignored = 0;
		VirtualProtect(
			&vtable[v33_set_pipeline_state1_slot],
			sizeof(void *) * 2,
			old_protect,
			&ignored);
		FlushInstructionCache(
			GetCurrentProcess(),
			&vtable[v33_set_pipeline_state1_slot],
			sizeof(void *) * 2);

		const bool verified =
			vtable[v33_set_pipeline_state1_slot] ==
				reinterpret_cast<void *>(
					&v33_trace_set_pipeline_state1) &&
			vtable[v33_dispatch_rays_slot] ==
				reinterpret_cast<void *>(
					&v33_trace_dispatch_rays);

		reshade::log::message(
			verified ?
				reshade::log::level::info :
				reshade::log::level::warning,
			"D3DMetal RTX execution trace v33: COMMAND_LIST_HOOKS installed=%u set_slot=%zu dispatch_slot=%zu original_set=%p original_dispatch=%p replacement_set=%p replacement_dispatch=%p.",
			verified ? 1u : 0u,
			v33_set_pipeline_state1_slot,
			v33_dispatch_rays_slot,
			reinterpret_cast<void *>(
				s_v33_original_set_pipeline_state1),
			reinterpret_cast<void *>(
				s_v33_original_dispatch_rays),
			reinterpret_cast<void *>(
				&v33_trace_set_pipeline_state1),
			reinterpret_cast<void *>(
				&v33_trace_dispatch_rays));

		if (verified)
		{
			s_v33_command_list_hooks_installed.store(
				true, std::memory_order_release);
		}
		else
		{
			s_v33_original_set_pipeline_state1 = nullptr;
			s_v33_original_dispatch_rays = nullptr;
		}

		list4->Release();
	}

	HRESULT STDMETHODCALLTYPE v33_trace_create_command_list(
		ID3D12Device *device,
		UINT node_mask,
		D3D12_COMMAND_LIST_TYPE type,
		ID3D12CommandAllocator *allocator,
		ID3D12PipelineState *initial_state,
		REFIID riid,
		void **command_list)
	{
		if (s_v33_original_create_command_list == nullptr)
			return E_FAIL;

		const HRESULT result = s_v33_original_create_command_list(
			device,
			node_mask,
			type,
			allocator,
			initial_state,
			riid,
			command_list);

		void *created = nullptr;
		if (command_list != nullptr)
			safe_copy_from_process(command_list, &created, sizeof(created));

		if (SUCCEEDED(result) && created != nullptr)
		{
			const uint64_t index = ++s_v33_created_command_lists;
			v33_install_command_list_method_hooks(
				reinterpret_cast<IUnknown *>(created));
			if (index <= 8)
			{
				reshade::log::message(
					reshade::log::level::info,
					"D3DMetal RTX execution trace v33: COMMAND_LIST_CREATED index=%llu api=CreateCommandList type=%u object=%p.",
					static_cast<unsigned long long>(index),
					static_cast<unsigned int>(type),
					created);
			}
		}

		return result;
	}

	HRESULT STDMETHODCALLTYPE v33_trace_create_command_list1(
		ID3D12Device4 *device,
		UINT node_mask,
		D3D12_COMMAND_LIST_TYPE type,
		D3D12_COMMAND_LIST_FLAGS flags,
		REFIID riid,
		void **command_list)
	{
		if (s_v33_original_create_command_list1 == nullptr)
			return E_FAIL;

		const HRESULT result = s_v33_original_create_command_list1(
			device,
			node_mask,
			type,
			flags,
			riid,
			command_list);

		void *created = nullptr;
		if (command_list != nullptr)
			safe_copy_from_process(command_list, &created, sizeof(created));

		if (SUCCEEDED(result) && created != nullptr)
		{
			const uint64_t index = ++s_v33_created_command_lists;
			v33_install_command_list_method_hooks(
				reinterpret_cast<IUnknown *>(created));
			if (index <= 8)
			{
				reshade::log::message(
					reshade::log::level::info,
					"D3DMetal RTX execution trace v33: COMMAND_LIST_CREATED index=%llu api=CreateCommandList1 type=%u flags=0x%X object=%p.",
					static_cast<unsigned long long>(index),
					static_cast<unsigned int>(type),
					static_cast<unsigned int>(flags),
					created);
			}
		}

		return result;
	}

	void v33_install_device_command_list_hooks(ID3D12Device *device)
	{
		if (device == nullptr)
			return;

		std::call_once(
			s_v33_device_hook_once,
			[device]()
			{
				void **const base_vtable =
					*reinterpret_cast<void ***>(device);
				s_v33_original_create_command_list =
					reinterpret_cast<v33_create_command_list_fn>(
						base_vtable[v33_create_command_list_slot]);

				ID3D12Device4 *device4 = nullptr;
				const HRESULT query_hr = device->QueryInterface(
					__uuidof(ID3D12Device4),
					reinterpret_cast<void **>(&device4));
				if (FAILED(query_hr) || device4 == nullptr)
				{
					reshade::log::message(
						reshade::log::level::warning,
						"D3DMetal RTX execution trace v33: ID3D12Device4 unavailable hr=%s raw=0x%08X.",
						reshade::log::hr_to_string(query_hr).c_str(),
						static_cast<uint32_t>(query_hr));
					s_v33_original_create_command_list = nullptr;
					return;
				}

				void **const vtable4 =
					*reinterpret_cast<void ***>(device4);
				s_v33_original_create_command_list1 =
					reinterpret_cast<v33_create_command_list1_fn>(
						vtable4[v33_create_command_list1_slot]);

				DWORD old_base = 0;
				if (!VirtualProtect(
					&base_vtable[v33_create_command_list_slot],
					sizeof(void *),
					PAGE_EXECUTE_READWRITE,
					&old_base))
				{
					reshade::log::message(
						reshade::log::level::warning,
						"D3DMetal RTX execution trace v33: CreateCommandList VirtualProtect failed error=%lu.",
						GetLastError());
					s_v33_original_create_command_list = nullptr;
					s_v33_original_create_command_list1 = nullptr;
					device4->Release();
					return;
				}

				InterlockedExchangePointer(
					reinterpret_cast<PVOID volatile *>(
						&base_vtable[v33_create_command_list_slot]),
					reinterpret_cast<PVOID>(
						&v33_trace_create_command_list));
				DWORD ignored_base = 0;
				VirtualProtect(
					&base_vtable[v33_create_command_list_slot],
					sizeof(void *),
					old_base,
					&ignored_base);
				FlushInstructionCache(
					GetCurrentProcess(),
					&base_vtable[v33_create_command_list_slot],
					sizeof(void *));

				DWORD old_v4 = 0;
				if (!VirtualProtect(
					&vtable4[v33_create_command_list1_slot],
					sizeof(void *),
					PAGE_EXECUTE_READWRITE,
					&old_v4))
				{
					reshade::log::message(
						reshade::log::level::warning,
						"D3DMetal RTX execution trace v33: CreateCommandList1 VirtualProtect failed error=%lu.",
						GetLastError());
					device4->Release();
					return;
				}

				InterlockedExchangePointer(
					reinterpret_cast<PVOID volatile *>(
						&vtable4[v33_create_command_list1_slot]),
					reinterpret_cast<PVOID>(
						&v33_trace_create_command_list1));
				DWORD ignored_v4 = 0;
				VirtualProtect(
					&vtable4[v33_create_command_list1_slot],
					sizeof(void *),
					old_v4,
					&ignored_v4);
				FlushInstructionCache(
					GetCurrentProcess(),
					&vtable4[v33_create_command_list1_slot],
					sizeof(void *));

				const bool base_verified =
					base_vtable[v33_create_command_list_slot] ==
						reinterpret_cast<void *>(
							&v33_trace_create_command_list);
				const bool v4_verified =
					vtable4[v33_create_command_list1_slot] ==
						reinterpret_cast<void *>(
							&v33_trace_create_command_list1);

				reshade::log::message(
					(base_verified && v4_verified) ?
						reshade::log::level::info :
						reshade::log::level::warning,
					"D3DMetal RTX execution trace v33: DEVICE_COMMAND_LIST_HOOKS installed=%u create_slot=%zu create1_slot=%zu original_create=%p original_create1=%p.",
					(base_verified && v4_verified) ? 1u : 0u,
					v33_create_command_list_slot,
					v33_create_command_list1_slot,
					reinterpret_cast<void *>(
						s_v33_original_create_command_list),
					reinterpret_cast<void *>(
						s_v33_original_create_command_list1));

				if (!base_verified)
					s_v33_original_create_command_list = nullptr;
				if (!v4_verified)
					s_v33_original_create_command_list1 = nullptr;

				device4->Release();
			});
	}

'''
text = text.replace(v32_anchor, helper + "\n" + v32_anchor, 1)

register_anchor = (
    "\t\tif (SUCCEEDED(replacement_hr) && replacement_object != nullptr)\n"
    "\t\t{\n"
    "\t\t\t*state_object = replacement_object;\n"
    "\t\t\tresult = replacement_hr;\n"
    "\t\t\tconst unsigned int success = ++s_v32_rewrite_successes;\n"
)
if text.count(register_anchor) != 1:
    raise RuntimeError(
        f"V33 V32 success anchor mismatch: {text.count(register_anchor)}")
register_replacement = (
    "\t\tif (SUCCEEDED(replacement_hr) && replacement_object != nullptr)\n"
    "\t\t{\n"
    "\t\t\tv33_register_rewritten_state_object(replacement_object, call_id);\n"
    "\t\t\t*state_object = replacement_object;\n"
    "\t\t\tresult = replacement_hr;\n"
    "\t\t\tconst unsigned int success = ++s_v32_rewrite_successes;\n"
)
text = text.replace(register_anchor, register_replacement, 1)

install_anchor = (
    "\tinstall_v25_root_signature_trace(static_cast<ID3D12Device *>(*ppDevice));\n"
    "\tinstall_d3dmetal_state_object_trace(static_cast<ID3D12Device *>(*ppDevice));\n"
)
if text.count(install_anchor) != 1:
    raise RuntimeError(
        f"V33 device install anchor mismatch: {text.count(install_anchor)}")
install_replacement = (
    "\tinstall_v25_root_signature_trace(static_cast<ID3D12Device *>(*ppDevice));\n"
    "\tinstall_d3dmetal_state_object_trace(static_cast<ID3D12Device *>(*ppDevice));\n"
    "\tv33_install_device_command_list_hooks(static_cast<ID3D12Device *>(*ppDevice));\n"
)
text = text.replace(install_anchor, install_replacement, 1)

required = [
    "D3DMetal RTX execution trace v33:",
    "v33_register_rewritten_state_object(replacement_object, call_id);",
    "DEVICE_COMMAND_LIST_HOOKS installed=",
    "COMMAND_LIST_HOOKS installed=",
    "BIND_REWRITTEN bind_index=",
    "DISPATCH sample=",
    "raygen_align64=",
    "hit_stride_align32=",
    "v33_install_device_command_list_hooks(",
]
for marker in required:
    if marker not in text:
        raise RuntimeError(f"Missing V33 source marker: {marker}")

SOURCE.write_text(text, encoding="utf-8", newline="\n")

report = Path("v33-patch-report.txt")
report.write_text(
    "\n".join([
        "V33_DISPATCH_RAYS_EXECUTION_TRACE_PATCH_OK",
        "V32_FP32_BRIDGE_PRESERVED=YES",
        "CREATE_COMMAND_LIST_SLOT=12",
        "CREATE_COMMAND_LIST1_SLOT=51",
        "SET_PIPELINE_STATE1_SLOT=75",
        "DISPATCH_RAYS_SLOT=76",
        "REWRITTEN_STATE_OBJECT_REGISTRATION=ENABLED",
        "SET_PIPELINE_STATE1_BIND_TRACKING=ENABLED",
        "DISPATCH_RAYS_SAMPLING=ENABLED",
        "SHADER_TABLE_ADDRESS_SIZE_STRIDE_LOGGING=ENABLED",
        "DISPATCH_PARAMETERS_UNMODIFIED=YES",
        "STATE_OBJECT_RETURN_UNMODIFIED_FROM_V32=YES",
        "FAKE_DISPATCH=DISABLED",
        "RESULT=PASS",
        "",
    ]),
    encoding="utf-8",
    newline="\n",
)
print(report.read_text(encoding="utf-8"))
