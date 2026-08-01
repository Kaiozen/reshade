from __future__ import annotations

from pathlib import Path

SOURCE = Path('source/d3d12/d3d12.cpp')
REPORT = Path('v61-patch-report.txt')


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: expected exactly one anchor, found {count}')
    return text.replace(old, new, 1)


text = SOURCE.read_text(encoding='utf-8')
if 'D3DMetal RTX AddToStateObject lineage bridge v61' in text:
    raise RuntimeError('V61 patch appears to be applied already')
if 'D3DMetal RTX real FP32 visual candidate v60' not in text:
    raise RuntimeError('V60 baseline marker is missing')

# Add the ID3D12Device7::AddToStateObject function type and slot. Slot 66 follows
# ID3D12Device6::SetBackgroundProcessingMode in the inherited device vtable.
text = replace_once(
    text,
    '''\tusing v33_dispatch_rays_fn = void (STDMETHODCALLTYPE *)(
\t\tID3D12GraphicsCommandList4 *,
\t\tconst D3D12_DISPATCH_RAYS_DESC *);
''',
    '''\tusing v33_dispatch_rays_fn = void (STDMETHODCALLTYPE *)(
\t\tID3D12GraphicsCommandList4 *,
\t\tconst D3D12_DISPATCH_RAYS_DESC *);

\tusing v61_add_to_state_object_fn = HRESULT (STDMETHODCALLTYPE *)(
\t\tID3D12Device7 *,
\t\tconst D3D12_STATE_OBJECT_DESC *,
\t\tID3D12StateObject *,
\t\tREFIID,
\t\tvoid **);
''',
    'add AddToStateObject function type',
)

text = replace_once(
    text,
    '''\tconstexpr size_t v33_create_command_list_slot = 12;
\tconstexpr size_t v33_create_command_list1_slot = 51;
\tconstexpr size_t v33_set_pipeline_state1_slot = 75;
\tconstexpr size_t v33_dispatch_rays_slot = 76;
''',
    '''\tconstexpr size_t v33_create_command_list_slot = 12;
\tconstexpr size_t v33_create_command_list1_slot = 51;
\tconstexpr size_t v33_set_pipeline_state1_slot = 75;
\tconstexpr size_t v33_dispatch_rays_slot = 76;
\tconstexpr size_t v61_add_to_state_object_slot = 66;
''',
    'add AddToStateObject slot',
)

text = replace_once(
    text,
    '''\tstatic v33_create_command_list_fn s_v33_original_create_command_list = nullptr;
\tstatic v33_create_command_list1_fn s_v33_original_create_command_list1 = nullptr;
\tstatic v33_set_pipeline_state1_fn s_v33_original_set_pipeline_state1 = nullptr;
\tstatic v33_dispatch_rays_fn s_v33_original_dispatch_rays = nullptr;
''',
    '''\tstatic v33_create_command_list_fn s_v33_original_create_command_list = nullptr;
\tstatic v33_create_command_list1_fn s_v33_original_create_command_list1 = nullptr;
\tstatic v33_set_pipeline_state1_fn s_v33_original_set_pipeline_state1 = nullptr;
\tstatic v33_dispatch_rays_fn s_v33_original_dispatch_rays = nullptr;
\tstatic v61_add_to_state_object_fn s_v61_original_add_to_state_object = nullptr;
\tstatic std::once_flag s_v61_add_to_state_object_hook_once;
\tstatic std::atomic<uint64_t> s_v61_add_call_total = 0;
\tstatic std::atomic<uint64_t> s_v61_add_success_total = 0;
\tstatic std::atomic<uint64_t> s_v61_lineage_propagated_total = 0;
\tstatic std::atomic<uint64_t> s_v61_addition_rewrite_total = 0;
''',
    'add V61 hook state',
)

# Insert the AddToStateObject bridge after the existing rewritten-state lookup.
anchor = '''\tbool v33_lookup_rewritten_state_object(
\t\tID3D12StateObject *state_object,
\t\tuint64_t &create_call)
\t{
\t\tcreate_call = 0;
\t\tvoid *const identity = v33_identity_pointer(
\t\t\treinterpret_cast<IUnknown *>(state_object));
\t\tif (identity == nullptr)
\t\t\treturn false;

\t\tstd::lock_guard<std::mutex> lock(s_v33_state_mutex);
\t\tconst auto found = s_v33_rewritten_state_calls.find(identity);
\t\tif (found == s_v33_rewritten_state_calls.end())
\t\t\treturn false;

\t\tcreate_call = found->second;
\t\treturn true;
\t}
'''
insert = anchor + r'''

	HRESULT STDMETHODCALLTYPE v61_trace_add_to_state_object(
		ID3D12Device7 *device,
		const D3D12_STATE_OBJECT_DESC *addition,
		ID3D12StateObject *grow_from,
		REFIID riid,
		void **new_state_object)
	{
		const uint64_t add_call = ++s_v61_add_call_total;
		if (s_v61_original_add_to_state_object == nullptr)
			return E_FAIL;

		uint64_t base_state_call = 0;
		const bool base_rewritten =
			v33_lookup_rewritten_state_object(grow_from, base_state_call);

		D3D12_STATE_OBJECT_DESC snapshot = {};
		const bool readable =
			addition != nullptr &&
			safe_copy_from_process(addition, &snapshot, sizeof(snapshot));

		bool addition_rewritten = false;
		size_t matching_parent_libraries = 0;
		const D3D12_STATE_OBJECT_DESC *forwarded_addition = addition;
		v30_full_replacement_storage replacement_storage;
		D3D12_STATE_OBJECT_DESC replacement_desc = {};

		if (readable && snapshot.pSubobjects != nullptr &&
			snapshot.NumSubobjects > 0 && snapshot.NumSubobjects <= 128)
		{
			std::vector<D3D12_STATE_SUBOBJECT> source;
			if (v27_copy_subobjects(snapshot, source))
			{
				size_t parent_library = static_cast<size_t>(-1);
				for (size_t index = 0; index < source.size(); ++index)
				{
					if (source[index].Type !=
						D3D12_STATE_SUBOBJECT_TYPE_DXIL_LIBRARY)
						continue;

					D3D12_DXIL_LIBRARY_DESC library = {};
					if (!safe_copy_from_process(
						source[index].pDesc, &library, sizeof(library)))
						continue;

					if (v24_parent_dxil_matches(
						library.DXILLibrary.pShaderBytecode,
						library.DXILLibrary.BytecodeLength))
					{
						parent_library = index;
						++matching_parent_libraries;
					}
				}

				if (matching_parent_libraries == 1 &&
					v30_build_full_replacement(
						snapshot,
						source,
						parent_library,
						g_v30_execute_plus_miss_fp32_dxil,
						sizeof(g_v30_execute_plus_miss_fp32_dxil),
						replacement_storage,
						replacement_desc))
				{
					forwarded_addition = &replacement_desc;
					addition_rewritten = true;
					++s_v61_addition_rewrite_total;
				}
			}
		}

		void *created = nullptr;
		HRESULT result = s_v61_original_add_to_state_object(
			device,
			forwarded_addition,
			grow_from,
			riid,
			new_state_object != nullptr ? &created : nullptr);

		bool addition_rewrite_fallback = false;
		if (addition_rewritten && FAILED(result))
		{
			if (created != nullptr)
			{
				reinterpret_cast<IUnknown *>(created)->Release();
				created = nullptr;
			}
			result = s_v61_original_add_to_state_object(
				device,
				addition,
				grow_from,
				riid,
				new_state_object != nullptr ? &created : nullptr);
			addition_rewrite_fallback = true;
		}

		if (new_state_object != nullptr)
			*new_state_object = created;

		const bool lineage_rewritten =
			base_rewritten || (addition_rewritten && !addition_rewrite_fallback);
		if (SUCCEEDED(result) && created != nullptr)
		{
			++s_v61_add_success_total;
			if (lineage_rewritten)
			{
				const uint64_t inherited_state_call =
					base_state_call != 0 ? base_state_call : add_call;
				v33_register_rewritten_state_object(
					created, inherited_state_call);
				++s_v61_lineage_propagated_total;
			}
		}

		reshade::log::message(
			lineage_rewritten ?
				reshade::log::level::info : reshade::log::level::debug,
			"D3DMetal RTX AddToStateObject lineage bridge v61: ADD_RESULT add_call=%llu readable=%u subobjects=%u parent_dxil_matches=%llu base_rewritten=%u base_state_call=%llu addition_rewritten=%u addition_rewrite_fallback=%u lineage_rewritten=%u hr=%s raw=0x%08X grow_from=%p new_object=%p total_success=%llu total_lineage=%llu total_addition_rewrites=%llu.",
			static_cast<unsigned long long>(add_call),
			readable ? 1u : 0u,
			readable ? snapshot.NumSubobjects : 0u,
			static_cast<unsigned long long>(matching_parent_libraries),
			base_rewritten ? 1u : 0u,
			static_cast<unsigned long long>(base_state_call),
			addition_rewritten ? 1u : 0u,
			addition_rewrite_fallback ? 1u : 0u,
			lineage_rewritten ? 1u : 0u,
			reshade::log::hr_to_string(result).c_str(),
			static_cast<uint32_t>(result),
			grow_from,
			created,
			static_cast<unsigned long long>(
				s_v61_add_success_total.load(std::memory_order_relaxed)),
			static_cast<unsigned long long>(
				s_v61_lineage_propagated_total.load(std::memory_order_relaxed)),
			static_cast<unsigned long long>(
				s_v61_addition_rewrite_total.load(std::memory_order_relaxed)));

		return result;
	}
'''
text = replace_once(text, anchor, insert, 'insert V61 AddToStateObject bridge')

# Add an installer before the existing CreateStateObject installer.
install_anchor = '''\tvoid install_d3dmetal_state_object_trace(ID3D12Device *device)
\t{
'''
install_code = r'''	void v61_install_add_to_state_object_hook(ID3D12Device *device)
	{
		if (device == nullptr)
			return;

		std::call_once(s_v61_add_to_state_object_hook_once, [device]()
		{
			com_ptr<ID3D12Device7> device7;
			if (FAILED(device->QueryInterface(&device7)))
			{
				reshade::log::message(
					reshade::log::level::warning,
					"D3DMetal RTX AddToStateObject lineage bridge v61: HOOK installed=0 reason=ID3D12Device7-unavailable.");
				return;
			}

			void **const vtable = *reinterpret_cast<void ***>(device7.get());
			void *const current = vtable[v61_add_to_state_object_slot];
			if (current == reinterpret_cast<void *>(&v61_trace_add_to_state_object))
				return;

			s_v61_original_add_to_state_object =
				reinterpret_cast<v61_add_to_state_object_fn>(current);

			DWORD old_protect = 0;
			if (!VirtualProtect(
				&vtable[v61_add_to_state_object_slot],
				sizeof(void *),
				PAGE_EXECUTE_READWRITE,
				&old_protect))
			{
				reshade::log::message(
					reshade::log::level::warning,
					"D3DMetal RTX AddToStateObject lineage bridge v61: HOOK installed=0 slot=%zu error=%lu.",
					v61_add_to_state_object_slot,
					GetLastError());
				s_v61_original_add_to_state_object = nullptr;
				return;
			}

			InterlockedExchangePointer(
				reinterpret_cast<PVOID volatile *>(
					&vtable[v61_add_to_state_object_slot]),
				reinterpret_cast<PVOID>(&v61_trace_add_to_state_object));

			DWORD ignored = 0;
			VirtualProtect(
				&vtable[v61_add_to_state_object_slot],
				sizeof(void *), old_protect, &ignored);
			FlushInstructionCache(
				GetCurrentProcess(),
				&vtable[v61_add_to_state_object_slot],
				sizeof(void *));

			const bool installed =
				vtable[v61_add_to_state_object_slot] ==
					reinterpret_cast<void *>(&v61_trace_add_to_state_object);
			reshade::log::message(
				installed ? reshade::log::level::info :
					reshade::log::level::warning,
				"D3DMetal RTX AddToStateObject lineage bridge v61: HOOK installed=%u slot=%zu original=%p replacement=%p.",
				installed ? 1u : 0u,
				v61_add_to_state_object_slot,
				reinterpret_cast<void *>(s_v61_original_add_to_state_object),
				reinterpret_cast<void *>(&v61_trace_add_to_state_object));

			if (!installed)
				s_v61_original_add_to_state_object = nullptr;
		});
	}

'''
text = replace_once(text, install_anchor, install_code + install_anchor, 'add V61 hook installer')

# Install the new device hook alongside the existing state-object and command-list hooks.
text = replace_once(
    text,
    '''\tinstall_v25_root_signature_trace(static_cast<ID3D12Device *>(*ppDevice));
\tinstall_d3dmetal_state_object_trace(static_cast<ID3D12Device *>(*ppDevice));
\tv33_install_device_command_list_hooks(static_cast<ID3D12Device *>(*ppDevice));
''',
    '''\tinstall_v25_root_signature_trace(static_cast<ID3D12Device *>(*ppDevice));
\tinstall_d3dmetal_state_object_trace(static_cast<ID3D12Device *>(*ppDevice));
\tv61_install_add_to_state_object_hook(static_cast<ID3D12Device *>(*ppDevice));
\tv33_install_device_command_list_hooks(static_cast<ID3D12Device *>(*ppDevice));
''',
    'install V61 device hook',
)

# Add a strict candidate helper that requires actual rewritten-lineage registration,
# rather than merely matching shader identifiers.
helper_anchor = '''\tvoid *v33_identity_pointer(IUnknown *object)
\t{
'''
helper_code = r'''	bool v61_rewritten_steady_state_candidate(
		ID3D12GraphicsCommandList4 *command_list,
		uint64_t &pipeline_id,
		uint64_t &pipeline_ray_index,
		uint64_t &rewritten_state_call)
	{
		pipeline_id = v54_lookup_bound_pipeline(command_list);
		pipeline_ray_index = 0;
		rewritten_state_call = 0;
		if (pipeline_id == 0)
			return false;

		std::lock_guard<std::mutex> lock(s_v54_pipeline_mutex);
		const auto found = s_v54_pipeline_infos.find(pipeline_id);
		if (found == s_v54_pipeline_infos.end())
			return false;

		const v54_pipeline_info &info = found->second;
		pipeline_ray_index = info.indirect_ray_count;
		rewritten_state_call = info.rewritten_state_call;
		return info.rewritten && rewritten_state_call != 0 &&
			pipeline_ray_index >= 512;
	}

'''
text = replace_once(text, helper_anchor, helper_code + helper_anchor, 'add strict V61 candidate helper')

text = replace_once(
    text,
    '\tstatic std::atomic<bool> s_v60_real_fp32_dispatch_seen = false;\n',
    '\tstatic std::atomic<bool> s_v61_rewritten_steady_state_seen = false;\n',
    'rename V60 proof state',
)

old_proof = '''\t\tif (dispatch_rays &&
\t\t\t!s_v60_real_fp32_dispatch_seen.load(std::memory_order_acquire))
\t\t{
\t\t\tuint64_t v60_pipeline_id = 0;
\t\t\tuint64_t v60_pipeline_ray_index = 0;
\t\t\tif (v56_steady_state_pipeline_candidate(
\t\t\t\treinterpret_cast<ID3D12GraphicsCommandList *>(command_list),
\t\t\t\tv60_pipeline_id,
\t\t\t\tv60_pipeline_ray_index))
\t\t\t{
\t\t\t\tbool expected = false;
\t\t\t\tif (s_v60_real_fp32_dispatch_seen.compare_exchange_strong(
\t\t\t\t\texpected, true, std::memory_order_acq_rel))
\t\t\t\t{
\t\t\t\t\treshade::log::message(
\t\t\t\t\t\treshade::log::level::info,
\t\t\t\t\t\t"D3DMetal RTX real FP32 visual candidate v60: REAL_FP32_DISPATCH_EXECUTED mode=indirect pipeline_id=%llu pipeline_ray_index=%llu global_ray_index=%llu state_call=%llu argument_gpu_va=0x%llX argument_offset=%llu commands_modified=0.",
\t\t\t\t\t\tstatic_cast<unsigned long long>(v60_pipeline_id),
\t\t\t\t\t\tstatic_cast<unsigned long long>(v60_pipeline_ray_index),
\t\t\t\t\t\tstatic_cast<unsigned long long>(ray_index),
\t\t\t\t\t\tstatic_cast<unsigned long long>(state_call),
\t\t\t\t\t\tstatic_cast<unsigned long long>(argument_gpu_va),
\t\t\t\t\t\tstatic_cast<unsigned long long>(argument_buffer_offset));
\t\t\t\t}
\t\t\t}
\t\t}
'''
new_proof = '''\t\tif (dispatch_rays &&
\t\t\t!s_v61_rewritten_steady_state_seen.load(std::memory_order_acquire))
\t\t{
\t\t\tuint64_t v61_pipeline_id = 0;
\t\t\tuint64_t v61_pipeline_ray_index = 0;
\t\t\tuint64_t v61_state_call = 0;
\t\t\tif (v61_rewritten_steady_state_candidate(
\t\t\t\treinterpret_cast<ID3D12GraphicsCommandList4 *>(command_list),
\t\t\t\tv61_pipeline_id,
\t\t\t\tv61_pipeline_ray_index,
\t\t\t\tv61_state_call))
\t\t\t{
\t\t\t\tbool expected = false;
\t\t\t\tif (s_v61_rewritten_steady_state_seen.compare_exchange_strong(
\t\t\t\t\texpected, true, std::memory_order_acq_rel))
\t\t\t\t{
\t\t\t\t\treshade::log::message(
\t\t\t\t\t\treshade::log::level::info,
\t\t\t\t\t\t"D3DMetal RTX AddToStateObject lineage bridge v61: REWRITTEN_STEADY_STATE_EXECUTED pipeline_id=%llu pipeline_ray_index=%llu global_ray_index=%llu state_call=%llu execute_indirect_state_call=%llu argument_gpu_va=0x%llX argument_offset=%llu commands_modified=0.",
\t\t\t\t\t\tstatic_cast<unsigned long long>(v61_pipeline_id),
\t\t\t\t\t\tstatic_cast<unsigned long long>(v61_pipeline_ray_index),
\t\t\t\t\t\tstatic_cast<unsigned long long>(ray_index),
\t\t\t\t\t\tstatic_cast<unsigned long long>(v61_state_call),
\t\t\t\t\t\tstatic_cast<unsigned long long>(state_call),
\t\t\t\t\t\tstatic_cast<unsigned long long>(argument_gpu_va),
\t\t\t\t\t\tstatic_cast<unsigned long long>(argument_buffer_offset));
\t\t\t\t}
\t\t\t}
\t\t}
'''
text = replace_once(text, old_proof, new_proof, 'replace false V60 execution proof')

# Add a durable marker near the V60 heading.
text = replace_once(
    text,
    '''    // D3DMetal RTX real FP32 visual candidate v60.
''',
    '''    // D3DMetal RTX AddToStateObject lineage bridge v61.
    // Hooks ID3D12Device7 slot 66, rewrites escaped parent DXIL additions,
    // propagates rewritten ancestry, and requires a rewritten dominant pipeline.

    // D3DMetal RTX real FP32 visual candidate v60.
''',
    'add V61 source heading',
)

SOURCE.write_text(text, encoding='utf-8', newline='\n')
REPORT.write_text(
    '\n'.join([
        'V61_ADD_TO_STATE_OBJECT_LINEAGE_BRIDGE_PATCH_OK',
        'BASELINE=V60_REAL_FP32_VISUAL_CANDIDATE',
        'ADD_TO_STATE_OBJECT_SLOT=66',
        'ADD_TO_STATE_OBJECT_HOOK=ENABLED',
        'PARENT_DXIL_IN_ADDITIONS_REWRITTEN=YES',
        'REWRITTEN_BASE_LINEAGE_PROPAGATED=YES',
        'DOMINANT_PIPELINE_PROOF_REQUIRES_REWRITTEN_LINEAGE=YES',
        'V60_IDENTIFIER_ONLY_PROOF_SUPERSEDED=YES',
        'RENDER_COMMANDS_MODIFIED=NO',
        'RESULT=PASS',
        '',
    ]),
    encoding='utf-8',
    newline='\n',
)
print('V61_ADD_TO_STATE_OBJECT_LINEAGE_BRIDGE_PATCH_OK')
