from pathlib import Path

SOURCE = Path("source/d3d12/d3d12.cpp")
if not SOURCE.is_file():
    raise RuntimeError(f"Missing source file: {SOURCE}")

text = SOURCE.read_text(encoding="utf-8-sig")
if "D3DMetal RTX execution trace v33:" not in text:
    raise RuntimeError("V33 must be applied before V34")
if "D3DMetal RTX indirect execution trace v34:" in text:
    raise RuntimeError("V34 is already present")

def replace_once(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 occurrence, found {count}")
    return source.replace(old, new, 1)

helper_anchor = "\tvoid v33_install_command_list_method_hooks(IUnknown *command_list)\n"
if text.count(helper_anchor) != 1:
    raise RuntimeError(
        f"V34 command-list helper anchor mismatch: {text.count(helper_anchor)}")

helper = r'''
	using v34_create_command_signature_fn = HRESULT (STDMETHODCALLTYPE *)(
		ID3D12Device *,
		const D3D12_COMMAND_SIGNATURE_DESC *,
		ID3D12RootSignature *,
		REFIID,
		void **);

	using v34_execute_indirect_fn = void (STDMETHODCALLTYPE *)(
		ID3D12GraphicsCommandList *,
		ID3D12CommandSignature *,
		UINT,
		ID3D12Resource *,
		UINT64,
		ID3D12Resource *,
		UINT64);

	constexpr size_t v34_create_command_signature_slot = 41;
	constexpr size_t v34_execute_indirect_slot = 59;

	struct v34_signature_info
	{
		bool dispatch_rays = false;
		UINT num_arguments = 0;
		UINT byte_stride = 0;
		uint64_t type_mask = 0;
	};

	static v34_create_command_signature_fn
		s_v34_original_create_command_signature = nullptr;
	static v34_execute_indirect_fn
		s_v34_original_execute_indirect = nullptr;

	static std::once_flag s_v34_signature_hook_once;
	static std::once_flag s_v34_execute_indirect_hook_once;
	static std::mutex s_v34_signature_mutex;
	static std::unordered_map<void *, v34_signature_info>
		s_v34_signature_infos;
	static std::atomic<uint64_t> s_v34_signature_total = 0;
	static std::atomic<uint64_t> s_v34_ray_signature_total = 0;
	static std::atomic<uint64_t> s_v34_execute_indirect_total = 0;
	static std::atomic<uint64_t> s_v34_ray_indirect_total = 0;
	static std::atomic<uint64_t> s_v34_rewritten_ray_indirect_total = 0;

	bool v34_read_signature_info(
		const D3D12_COMMAND_SIGNATURE_DESC *desc,
		v34_signature_info &info)
	{
		info = {};
		D3D12_COMMAND_SIGNATURE_DESC snapshot = {};
		if (desc == nullptr ||
			!safe_copy_from_process(desc, &snapshot, sizeof(snapshot)))
			return false;

		info.num_arguments = snapshot.NumArgumentDescs;
		info.byte_stride = snapshot.ByteStride;

		const UINT inspect_count =
			snapshot.NumArgumentDescs < 64u ?
				snapshot.NumArgumentDescs : 64u;
		for (UINT index = 0; index < inspect_count; ++index)
		{
			D3D12_INDIRECT_ARGUMENT_DESC argument = {};
			if (snapshot.pArgumentDescs == nullptr ||
				!safe_copy_from_process(
					snapshot.pArgumentDescs + index,
					&argument,
					sizeof(argument)))
				continue;

			const unsigned int type =
				static_cast<unsigned int>(argument.Type);
			if (type < 64u)
				info.type_mask |= (1ull << type);
			if (argument.Type ==
				D3D12_INDIRECT_ARGUMENT_TYPE_DISPATCH_RAYS)
				info.dispatch_rays = true;
		}

		return true;
	}

	bool v34_lookup_signature(
		ID3D12CommandSignature *signature,
		v34_signature_info &info)
	{
		info = {};
		if (signature == nullptr)
			return false;

		void *const identity = v33_identity_pointer(
			reinterpret_cast<IUnknown *>(signature));
		if (identity == nullptr)
			return false;

		std::lock_guard<std::mutex> lock(s_v34_signature_mutex);
		const auto found = s_v34_signature_infos.find(identity);
		if (found == s_v34_signature_infos.end())
			return false;

		info = found->second;
		return true;
	}

	HRESULT STDMETHODCALLTYPE v34_trace_create_command_signature(
		ID3D12Device *device,
		const D3D12_COMMAND_SIGNATURE_DESC *desc,
		ID3D12RootSignature *root_signature,
		REFIID riid,
		void **command_signature)
	{
		if (s_v34_original_create_command_signature == nullptr)
			return E_FAIL;

		v34_signature_info info = {};
		const bool readable = v34_read_signature_info(desc, info);

		const HRESULT result = s_v34_original_create_command_signature(
			device,
			desc,
			root_signature,
			riid,
			command_signature);

		void *created = nullptr;
		if (command_signature != nullptr)
			safe_copy_from_process(
				command_signature, &created, sizeof(created));

		const uint64_t signature_index = ++s_v34_signature_total;
		uint64_t ray_index = 0;
		if (SUCCEEDED(result) && created != nullptr && readable)
		{
			void *const identity = v33_identity_pointer(
				reinterpret_cast<IUnknown *>(created));
			if (identity != nullptr)
			{
				{
					std::lock_guard<std::mutex> lock(
						s_v34_signature_mutex);
					s_v34_signature_infos[identity] = info;
				}
				if (info.dispatch_rays)
					ray_index = ++s_v34_ray_signature_total;
			}
		}

		if (info.dispatch_rays || signature_index <= 12)
		{
			reshade::log::message(
				info.dispatch_rays ?
					reshade::log::level::info :
					reshade::log::level::debug,
				"D3DMetal RTX indirect execution trace v34: COMMAND_SIGNATURE signature_index=%llu ray_index=%llu hr=%s raw=0x%08X readable=%u dispatch_rays=%u num_arguments=%u byte_stride=%u type_mask=0x%llX object=%p.",
				static_cast<unsigned long long>(signature_index),
				static_cast<unsigned long long>(ray_index),
				reshade::log::hr_to_string(result).c_str(),
				static_cast<uint32_t>(result),
				readable ? 1u : 0u,
				info.dispatch_rays ? 1u : 0u,
				info.num_arguments,
				info.byte_stride,
				static_cast<unsigned long long>(info.type_mask),
				created);
		}

		return result;
	}

	void STDMETHODCALLTYPE v34_trace_execute_indirect(
		ID3D12GraphicsCommandList *command_list,
		ID3D12CommandSignature *command_signature,
		UINT max_command_count,
		ID3D12Resource *argument_buffer,
		UINT64 argument_buffer_offset,
		ID3D12Resource *count_buffer,
		UINT64 count_buffer_offset)
	{
		const uint64_t indirect_total = ++s_v34_execute_indirect_total;

		v34_signature_info signature_info = {};
		const bool tracked_signature =
			v34_lookup_signature(command_signature, signature_info);
		const bool dispatch_rays =
			tracked_signature && signature_info.dispatch_rays;

		uint64_t state_call = 0;
		bool rewritten = false;
		{
			std::lock_guard<std::mutex> lock(s_v33_binding_mutex);
			const auto found = s_v33_bound_state_calls.find(
				reinterpret_cast<ID3D12GraphicsCommandList4 *>(
					command_list));
			if (found != s_v33_bound_state_calls.end())
			{
				rewritten = true;
				state_call = found->second;
			}
		}

		uint64_t ray_index = 0;
		uint64_t rewritten_ray_index = 0;
		if (dispatch_rays)
		{
			ray_index = ++s_v34_ray_indirect_total;
			if (rewritten)
				rewritten_ray_index =
					++s_v34_rewritten_ray_indirect_total;
		}

		D3D12_GPU_VIRTUAL_ADDRESS argument_gpu_va = 0;
		UINT64 argument_width = 0;
		D3D12_HEAP_TYPE argument_heap_type =
			static_cast<D3D12_HEAP_TYPE>(0);
		HRESULT argument_heap_hr = E_NOINTERFACE;
		if (argument_buffer != nullptr)
		{
			argument_gpu_va =
				argument_buffer->GetGPUVirtualAddress();
			argument_width = argument_buffer->GetDesc().Width;
			D3D12_HEAP_PROPERTIES properties = {};
			D3D12_HEAP_FLAGS flags = D3D12_HEAP_FLAG_NONE;
			argument_heap_hr = argument_buffer->GetHeapProperties(
				&properties, &flags);
			if (SUCCEEDED(argument_heap_hr))
				argument_heap_type = properties.Type;
		}

		D3D12_GPU_VIRTUAL_ADDRESS count_gpu_va = 0;
		UINT64 count_width = 0;
		if (count_buffer != nullptr)
		{
			count_gpu_va = count_buffer->GetGPUVirtualAddress();
			count_width = count_buffer->GetDesc().Width;
		}

		const bool should_log =
			dispatch_rays ||
			indirect_total <= 12 ||
			(rewritten && indirect_total <= 32);
		if (should_log)
		{
			reshade::log::message(
				dispatch_rays ?
					reshade::log::level::info :
					reshade::log::level::debug,
				"D3DMetal RTX indirect execution trace v34: EXECUTE_INDIRECT indirect_total=%llu tracked_signature=%u dispatch_rays=%u ray_index=%llu rewritten=%u rewritten_ray_index=%llu state_call=%llu command_list=%p signature=%p max_count=%u argument_resource=%p argument_gpu_va=0x%llX argument_offset=%llu argument_width=%llu argument_heap_hr=%s argument_heap_raw=0x%08X argument_heap_type=%u count_resource=%p count_gpu_va=0x%llX count_offset=%llu count_width=%llu.",
				static_cast<unsigned long long>(indirect_total),
				tracked_signature ? 1u : 0u,
				dispatch_rays ? 1u : 0u,
				static_cast<unsigned long long>(ray_index),
				rewritten ? 1u : 0u,
				static_cast<unsigned long long>(
					rewritten_ray_index),
				static_cast<unsigned long long>(state_call),
				command_list,
				command_signature,
				max_command_count,
				argument_buffer,
				static_cast<unsigned long long>(argument_gpu_va),
				static_cast<unsigned long long>(
					argument_buffer_offset),
				static_cast<unsigned long long>(argument_width),
				reshade::log::hr_to_string(
					argument_heap_hr).c_str(),
				static_cast<uint32_t>(argument_heap_hr),
				static_cast<unsigned int>(argument_heap_type),
				count_buffer,
				static_cast<unsigned long long>(count_gpu_va),
				static_cast<unsigned long long>(
					count_buffer_offset),
				static_cast<unsigned long long>(count_width));
		}

		if (s_v34_original_execute_indirect != nullptr)
			s_v34_original_execute_indirect(
				command_list,
				command_signature,
				max_command_count,
				argument_buffer,
				argument_buffer_offset,
				count_buffer,
				count_buffer_offset);
	}

	void v34_install_create_command_signature_hook(
		ID3D12Device *device)
	{
		if (device == nullptr)
			return;

		std::call_once(
			s_v34_signature_hook_once,
			[device]()
			{
				void **const vtable =
					*reinterpret_cast<void ***>(device);
				void *const current =
					vtable[v34_create_command_signature_slot];

				s_v34_original_create_command_signature =
					reinterpret_cast<
						v34_create_command_signature_fn>(current);

				DWORD old_protect = 0;
				if (!VirtualProtect(
					&vtable[v34_create_command_signature_slot],
					sizeof(void *),
					PAGE_EXECUTE_READWRITE,
					&old_protect))
				{
					reshade::log::message(
						reshade::log::level::warning,
						"D3DMetal RTX indirect execution trace v34: CREATE_COMMAND_SIGNATURE_HOOK installed=0 slot=%zu error=%lu.",
						v34_create_command_signature_slot,
						GetLastError());
					s_v34_original_create_command_signature = nullptr;
					return;
				}

				InterlockedExchangePointer(
					reinterpret_cast<PVOID volatile *>(
						&vtable[
							v34_create_command_signature_slot]),
					reinterpret_cast<PVOID>(
						&v34_trace_create_command_signature));

				DWORD ignored = 0;
				VirtualProtect(
					&vtable[v34_create_command_signature_slot],
					sizeof(void *),
					old_protect,
					&ignored);
				FlushInstructionCache(
					GetCurrentProcess(),
					&vtable[v34_create_command_signature_slot],
					sizeof(void *));

				const bool verified =
					vtable[v34_create_command_signature_slot] ==
						reinterpret_cast<void *>(
							&v34_trace_create_command_signature);

				reshade::log::message(
					verified ?
						reshade::log::level::info :
						reshade::log::level::warning,
					"D3DMetal RTX indirect execution trace v34: CREATE_COMMAND_SIGNATURE_HOOK installed=%u slot=%zu original=%p replacement=%p.",
					verified ? 1u : 0u,
					v34_create_command_signature_slot,
					reinterpret_cast<void *>(
						s_v34_original_create_command_signature),
					reinterpret_cast<void *>(
						&v34_trace_create_command_signature));

				if (!verified)
					s_v34_original_create_command_signature =
						nullptr;
			});
	}

	void v34_install_execute_indirect_hook(
		ID3D12GraphicsCommandList4 *command_list)
	{
		if (command_list == nullptr)
			return;

		std::call_once(
			s_v34_execute_indirect_hook_once,
			[command_list]()
			{
				void **const vtable =
					*reinterpret_cast<void ***>(command_list);
				void *const current =
					vtable[v34_execute_indirect_slot];

				s_v34_original_execute_indirect =
					reinterpret_cast<v34_execute_indirect_fn>(
						current);

				DWORD old_protect = 0;
				if (!VirtualProtect(
					&vtable[v34_execute_indirect_slot],
					sizeof(void *),
					PAGE_EXECUTE_READWRITE,
					&old_protect))
				{
					reshade::log::message(
						reshade::log::level::warning,
						"D3DMetal RTX indirect execution trace v34: EXECUTE_INDIRECT_HOOK installed=0 slot=%zu error=%lu.",
						v34_execute_indirect_slot,
						GetLastError());
					s_v34_original_execute_indirect = nullptr;
					return;
				}

				InterlockedExchangePointer(
					reinterpret_cast<PVOID volatile *>(
						&vtable[v34_execute_indirect_slot]),
					reinterpret_cast<PVOID>(
						&v34_trace_execute_indirect));

				DWORD ignored = 0;
				VirtualProtect(
					&vtable[v34_execute_indirect_slot],
					sizeof(void *),
					old_protect,
					&ignored);
				FlushInstructionCache(
					GetCurrentProcess(),
					&vtable[v34_execute_indirect_slot],
					sizeof(void *));

				const bool verified =
					vtable[v34_execute_indirect_slot] ==
						reinterpret_cast<void *>(
							&v34_trace_execute_indirect);

				reshade::log::message(
					verified ?
						reshade::log::level::info :
						reshade::log::level::warning,
					"D3DMetal RTX indirect execution trace v34: EXECUTE_INDIRECT_HOOK installed=%u slot=%zu original=%p replacement=%p.",
					verified ? 1u : 0u,
					v34_execute_indirect_slot,
					reinterpret_cast<void *>(
						s_v34_original_execute_indirect),
					reinterpret_cast<void *>(
						&v34_trace_execute_indirect));

				if (!verified)
					s_v34_original_execute_indirect = nullptr;
			});
	}

'''
text = text.replace(helper_anchor, helper + "\n" + helper_anchor, 1)

list_vtable_anchor = (
    "\t\tvoid **const vtable =\n"
    "\t\t\t*reinterpret_cast<void ***>(list4);\n"
)
list_vtable_replacement = (
    "\t\tv34_install_execute_indirect_hook(list4);\n\n"
    "\t\tvoid **const vtable =\n"
    "\t\t\t*reinterpret_cast<void ***>(list4);\n"
)
text = replace_once(
    text,
    list_vtable_anchor,
    list_vtable_replacement,
    "V34 ExecuteIndirect hook install")

device_anchor = (
    "\tvoid v33_install_device_command_list_hooks(ID3D12Device *device)\n"
    "\t{\n"
    "\t\tif (device == nullptr)\n"
    "\t\t\treturn;\n\n"
    "\t\tstd::call_once(\n"
)
device_replacement = (
    "\tvoid v33_install_device_command_list_hooks(ID3D12Device *device)\n"
    "\t{\n"
    "\t\tif (device == nullptr)\n"
    "\t\t\treturn;\n\n"
    "\t\tv34_install_create_command_signature_hook(device);\n\n"
    "\t\tstd::call_once(\n"
)
text = replace_once(
    text,
    device_anchor,
    device_replacement,
    "V34 CreateCommandSignature hook install")

required = [
    "D3DMetal RTX indirect execution trace v34:",
    "CREATE_COMMAND_SIGNATURE_HOOK installed=",
    "EXECUTE_INDIRECT_HOOK installed=",
    "COMMAND_SIGNATURE signature_index=",
    "EXECUTE_INDIRECT indirect_total=",
    "D3D12_INDIRECT_ARGUMENT_TYPE_DISPATCH_RAYS",
    "v34_install_execute_indirect_hook(list4);",
    "v34_install_create_command_signature_hook(device);",
    "argument_heap_type=",
    "rewritten_ray_index=",
]
for marker in required:
    if marker not in text:
        raise RuntimeError(f"Missing V34 source marker: {marker}")

SOURCE.write_text(text, encoding="utf-8", newline="\n")

report = Path("v34-patch-report.txt")
report.write_text(
    "\n".join([
        "V34_INDIRECT_RAYS_EXECUTION_TRACE_PATCH_OK",
        "V33_DIRECT_DISPATCH_TRACE_PRESERVED=YES",
        "CREATE_COMMAND_SIGNATURE_SLOT=41",
        "EXECUTE_INDIRECT_SLOT=59",
        "DISPATCH_RAYS_COMMAND_SIGNATURE_TRACKING=ENABLED",
        "REWRITTEN_STATE_BIND_CORRELATION=ENABLED",
        "ARGUMENT_BUFFER_GPU_ADDRESS_LOGGING=ENABLED",
        "ARGUMENT_BUFFER_HEAP_TYPE_LOGGING=ENABLED",
        "EXECUTE_INDIRECT_ARGUMENTS_UNMODIFIED=YES",
        "COMMAND_SIGNATURES_UNMODIFIED=YES",
        "FAKE_INDIRECT_DISPATCH=DISABLED",
        "RESULT=PASS",
        "",
    ]),
    encoding="utf-8",
    newline="\n",
)
print(report.read_text(encoding="utf-8"))
