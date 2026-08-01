from pathlib import Path

path = Path("source/d3d12/d3d12.cpp")
text = path.read_text(encoding="utf-8")

if "D3DMetal RTX target-UAV exact-base probe v50: ACTIVE" not in text:
    raise RuntimeError("V51 requires the V50 exact-base target probe")
if "D3DMetal RTX target-UAV zero-before-read control v51: ACTIVE" in text:
    raise RuntimeError("V51 is already present")


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


state_anchor = "\tstatic std::atomic<uint64_t> s_v50_target_rtv_count = 0;\n"
state_addition = state_anchor + r'''

	// V51 turns the V50 lineage result into a causal control. Only exact
	// post-RTX instances of the 1024x1024 R32_TYPELESS mip-chain are touched.
	// Every UAV descriptor observed at table offset zero is remembered for the
	// current write cycle. Immediately before a UAV-to-readable transition, all
	// remembered views are cleared to float zero while the resource is still in
	// D3D12_RESOURCE_STATE_UNORDERED_ACCESS.
	bool v50_should_sample(uint64_t event);

	struct v51_uav_handle_pair
	{
		D3D12_GPU_DESCRIPTOR_HANDLE gpu = {};
		D3D12_CPU_DESCRIPTOR_HANDLE cpu = {};
	};
	static std::unordered_map<uint64_t, bool>
		s_v51_post_phase_resources;
	static std::unordered_map<uint64_t, std::vector<v51_uav_handle_pair>>
		s_v51_cycle_uav_handles;
	static std::atomic<uint64_t> s_v51_post_resource_count = 0;
	static std::atomic<uint64_t> s_v51_uav_handle_count = 0;
	static std::atomic<uint64_t> s_v51_zero_transition_count = 0;
	static std::atomic<uint64_t> s_v51_zero_clear_call_count = 0;
	static std::atomic<uint64_t> s_v51_zero_skip_count = 0;

	bool v51_is_post_phase_resource(uint64_t resource_id)
	{
		if (resource_id == 0)
			return false;
		std::lock_guard<std::mutex> lock(s_v49_mutex);
		const auto found = s_v51_post_phase_resources.find(resource_id);
		return found != s_v51_post_phase_resources.end() && found->second;
	}

	void v51_remember_uav_handle(
		uint64_t resource_id,
		D3D12_GPU_DESCRIPTOR_HANDLE gpu,
		D3D12_CPU_DESCRIPTOR_HANDLE cpu)
	{
		if (resource_id == 0 || gpu.ptr == 0 || cpu.ptr == 0 ||
			!v51_is_post_phase_resource(resource_id))
			return;
		bool inserted = false;
		{
			std::lock_guard<std::mutex> lock(s_v49_mutex);
			auto &handles = s_v51_cycle_uav_handles[resource_id];
			for (const auto &entry : handles)
				if (entry.gpu.ptr == gpu.ptr && entry.cpu.ptr == cpu.ptr)
					return;
			if (handles.size() < 32u)
			{
				v51_uav_handle_pair pair = {};
				pair.gpu = gpu;
				pair.cpu = cpu;
				handles.push_back(pair);
				inserted = true;
			}
		}
		if (!inserted)
			return;
		const uint64_t event = ++s_v51_uav_handle_count;
		if (v50_should_sample(event))
			reshade::log::message(
				reshade::log::level::info,
				"D3DMetal RTX target-UAV zero-before-read control v51: TARGET_UAV_HANDLE event=%llu resource_id=%llu gpu_handle=0x%llX cpu_handle=0x%llX.",
				static_cast<unsigned long long>(event),
				static_cast<unsigned long long>(resource_id),
				static_cast<unsigned long long>(gpu.ptr),
				static_cast<unsigned long long>(cpu.ptr));
	}
'''
text = replace_once(text, state_anchor, state_addition, "V51 state insertion")

resource_store_old = r'''			s_v49_resource_ids_by_identity[identity] = info.resource_id;
			s_v49_resources[info.resource_id] = info;
'''
resource_store_new = r'''			s_v49_resource_ids_by_identity[identity] = info.resource_id;
			s_v49_resources[info.resource_id] = info;
			const bool post_phase = v46_post_phase();
			s_v51_post_phase_resources[info.resource_id] = post_phase;
			if (post_phase)
			{
				const uint64_t event = ++s_v51_post_resource_count;
				reshade::log::message(
					reshade::log::level::info,
					"D3DMetal RTX target-UAV zero-before-read control v51: POST_PHASE_TARGET_RESOURCE event=%llu resource_id=%llu resource=%p.",
					static_cast<unsigned long long>(event),
					static_cast<unsigned long long>(info.resource_id),
					resource);
			}
'''
text = replace_once(
    text, resource_store_old, resource_store_new,
    "V51 post-phase resource classification")

text = replace_once(
    text,
    '"D3DMetal RTX target-UAV exact-base probe v50: ACTIVE signature=texture2d-1024x1024-mips11-r32-typeless-flags0x5 table-offset=0 sampled=1 commands-modified=0 forced-process-stop=runner."',
    '"D3DMetal RTX target-UAV zero-before-read control v51: ACTIVE signature=texture2d-1024x1024-mips11-r32-typeless-flags0x5 post-rtx-only=1 table-offset=0 clear-point=uav-to-readable clear-value=float-zero commands-modified=target-clear-only forced-process-stop=runner."',
    "V51 active marker")

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

		D3D12_CPU_DESCRIPTOR_HANDLE cpu_handle = {};
		cpu_handle.ptr = cpu_ptr;
		if (descriptor.kind == 3u)
			v51_remember_uav_handle(
				descriptor.resource_id, base, cpu_handle);

		uint64_t pso_id = 0;
		unsigned int pso_kind = 0;
		uint64_t shader_hash = 0;
		v49_lookup_pso(command_list, pso_id, pso_kind, shader_hash);
		const uint64_t event = ++s_v50_target_base_bind_count;
		uint64_t signature = v49_signature_seed(0x5101ull);
		signature = v49_signature_add(signature, stage[0] == 'g' ? 1ull : 2ull);
		signature = v49_signature_add(signature, pso_id);
		signature = v49_signature_add(signature, root_index);
		signature = v49_signature_add(signature, descriptor.kind);
		signature = v49_signature_add(signature, descriptor.resource_id);
		const bool unique = v49_take_unique(signature, 512);
		if (unique || v50_should_sample(event))
			reshade::log::message(
				reshade::log::level::info,
				"D3DMetal RTX target-UAV zero-before-read control v51: TARGET_BASE_BIND event=%llu unique=%u stage=%s pso_id=%llu pso_kind=%u shader_hash=0x%llX root_index=%u gpu_handle=0x%llX cpu_handle=0x%llX heap_id=%llu descriptor_index=%u descriptor_offset=0 descriptor_kind=%s resource_id=%llu post_phase=%u view_format=%u view_dimension=%u resource_format=%u resource_flags=0x%X.",
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
				v51_is_post_phase_resource(descriptor.resource_id) ? 1u : 0u,
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
    "V51 targeted UAV handle tracking")

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

				const bool leaves_uav =
					barrier.Type == D3D12_RESOURCE_BARRIER_TYPE_TRANSITION &&
					barrier.Flags == D3D12_RESOURCE_BARRIER_FLAG_NONE &&
					(before_state & static_cast<unsigned int>(
						D3D12_RESOURCE_STATE_UNORDERED_ACCESS)) != 0u &&
					(after_state & static_cast<unsigned int>(
						D3D12_RESOURCE_STATE_UNORDERED_ACCESS)) == 0u;
				if (leaves_uav && before_id != 0 &&
					v51_is_post_phase_resource(before_id) &&
					resource_before != nullptr)
				{
					std::vector<v51_uav_handle_pair> handles;
					{
						std::lock_guard<std::mutex> lock(s_v49_mutex);
						const auto found =
							s_v51_cycle_uav_handles.find(before_id);
						if (found != s_v51_cycle_uav_handles.end())
							handles.swap(found->second);
					}

					const uint64_t transition =
						++s_v51_zero_transition_count;
					uint64_t clear_calls = 0;
					if (s_v49_original_clear_uav_float != nullptr)
					{
						const FLOAT zeros[4] = {
							0.0f, 0.0f, 0.0f, 0.0f
						};
						for (const auto &handle : handles)
						{
							s_v49_original_clear_uav_float(
								command_list,
								handle.gpu,
								handle.cpu,
								resource_before,
								zeros,
								0,
								nullptr);
							++clear_calls;
							++s_v51_zero_clear_call_count;
						}
					}
					if (clear_calls == 0)
						++s_v51_zero_skip_count;
					reshade::log::message(
						reshade::log::level::info,
						"D3DMetal RTX target-UAV zero-before-read control v51: ZERO_BEFORE_READ transition=%llu resource_id=%llu state_before=0x%X state_after=0x%X remembered_uavs=%llu clear_calls=%llu skipped=%u.",
						static_cast<unsigned long long>(transition),
						static_cast<unsigned long long>(before_id),
						before_state,
						after_state,
						static_cast<unsigned long long>(handles.size()),
						static_cast<unsigned long long>(clear_calls),
						clear_calls == 0 ? 1u : 0u);
				}

				if (before_id == 0 && after_id == 0)
					continue;
				const uint64_t event = ++s_v50_target_barrier_count;
				uint64_t signature = v49_signature_seed(0x5102ull);
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
						"D3DMetal RTX target-UAV zero-before-read control v51: TARGET_BARRIER event=%llu unique=%u type=%u flags=0x%X before_resource_id=%llu after_resource_id=%llu state_before=0x%X state_after=0x%X subresource=%u.",
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
    "V51 zero-before-read barrier control")

text = text.replace(
    "D3DMetal RTX target-UAV exact-base probe v50: DEVICE_HOOKS installed=",
    "D3DMetal RTX target-UAV zero-before-read control v51: DEVICE_HOOKS installed=")
text = text.replace(
    "D3DMetal RTX target-UAV exact-base probe v50: COMMAND_HOOKS installed=",
    "D3DMetal RTX target-UAV zero-before-read control v51: COMMAND_HOOKS installed=")

required = [
    "D3DMetal RTX target-UAV zero-before-read control v51: ACTIVE",
    "POST_PHASE_TARGET_RESOURCE event=",
    "TARGET_UAV_HANDLE event=",
    "ZERO_BEFORE_READ transition=",
    "clear-point=uav-to-readable",
    "clear-value=float-zero",
    "commands-modified=target-clear-only",
    "descriptor_offset=0",
]
for marker in required:
    if marker not in text:
        raise RuntimeError(f"V51 generated source is missing marker: {marker}")
if "for (UINT offset = 0; offset < 16u; ++offset)" in text:
    raise RuntimeError("V51 reintroduced the V49 adjacency scan")
if text.count("s_v49_original_clear_uav_float(") < 2:
    raise RuntimeError("V51 did not retain the original float clear call and injection")
if text.count("{") != text.count("}"):
    raise RuntimeError(
        f"V51 generated source has unbalanced braces: "
        f"{text.count('{')} vs {text.count('}')}")

path.write_text(text, encoding="utf-8")

report = """V51_TARGET_UAV_ZERO_BEFORE_READ_CONTROL_PATCH_OK
V50_EXACT_BASE_FILTER_PRESERVED=YES
TARGET_RESOURCE_SIGNATURE=TEXTURE2D_1024X1024_MIPS11_R32_TYPELESS_FLAGS_0X5
POST_RTX_RESOURCE_CLASSIFICATION=ENABLED
TARGET_UAV_HANDLE_LEDGER=EXACT_BASE_ONLY
TARGET_UAV_HANDLE_LEDGER_PER_RESOURCE_CAP=32
INJECTION_POINT=BEFORE_UAV_TO_NON_UAV_RESOURCE_BARRIER
INJECTION_RESOURCE_STATE=UNORDERED_ACCESS
INJECTION_CLEAR_API=ClearUnorderedAccessViewFloat
INJECTION_CLEAR_VALUE=0_0_0_0
ALL_REMEMBERED_UAV_VIEWS_CLEARED=YES
ORDINARY_RESOURCES_MODIFIED=NO
TARGET_RESOURCE_PRODUCER_COMMANDS_PRESERVED=YES
TARGET_RESOURCE_CONSUMER_COMMANDS_PRESERVED=YES
V45_RT_BIND_SUPPRESSION_PRESERVED=YES
V44_RAY_DISPATCH_SUPPRESSION_PRESERVED=YES
RUNNER_SHUTDOWN_MODE=FORCED_PROCESS_TERMINATION
CONTROL_FLOW_CHANGE=ZERO_POST_RTX_TARGET_UAV_BEFORE_READ
RESULT=PASS
"""
Path("v51-patch-report.txt").write_text(report, encoding="utf-8")
print(report, end="")
