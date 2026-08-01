from pathlib import Path

SOURCE = Path("source/d3d12/d3d12.cpp")
if not SOURCE.is_file():
    raise RuntimeError(f"Missing source file: {SOURCE}")

text = SOURCE.read_text(encoding="utf-8-sig")
if "D3DMetal RTX indirect execution trace v34:" not in text:
    raise RuntimeError("V34 must be applied before V54")
if "D3DMetal RTX shader-identifier query trace v36:" not in text:
    raise RuntimeError("V36 must be applied before V54")
if "D3DMetal RTX ray-hit output pattern control v53:" not in text:
    raise RuntimeError("V53 must be applied before V54")
if "D3DMetal RTX ray-hit pattern inheritance census v54:" in text:
    raise RuntimeError("V54 is already present")

globals_anchor = "\tstatic std::atomic<uint64_t> s_v33_dispatch_rewritten = 0;\n"
if text.count(globals_anchor) != 1:
    raise RuntimeError(f"V54 globals anchor mismatch: {text.count(globals_anchor)}")

helper = r"""
	// V33 and V36 define these helpers later in the same namespace. V54 is
	// injected before those definitions, so declare them before use.
	void *v33_identity_pointer(IUnknown *object);
	void v36_identifier_to_hex(const void *identifier, char (&hex)[65]);

	struct v54_pipeline_info
	{
		uint64_t pipeline_id = 0;
		uint64_t bind_count = 0;
		uint64_t direct_ray_count = 0;
		uint64_t indirect_ray_count = 0;
		bool rewritten = false;
		uint64_t rewritten_state_call = 0;
		void *identity = nullptr;
		void *properties = nullptr;
		bool execute_present = false;
		bool miss_present = false;
		bool sort_present = false;
		char execute_hex[65] = {};
		char miss_hex[65] = {};
		char sort_hex[65] = {};
	};

	static std::mutex s_v54_pipeline_mutex;
	static std::unordered_map<void *, uint64_t> s_v54_pipeline_ids_by_identity;
	static std::unordered_map<uint64_t, v54_pipeline_info> s_v54_pipeline_infos;
	static std::unordered_map<ID3D12GraphicsCommandList4 *, uint64_t> s_v54_bound_pipeline_ids;
	static std::atomic<uint64_t> s_v54_next_pipeline_id = 0;
	static std::atomic<uint64_t> s_v54_total_binds = 0;
	static std::atomic<uint64_t> s_v54_total_direct_rays = 0;
	static std::atomic<uint64_t> s_v54_total_indirect_rays = 0;
	static std::once_flag s_v54_active_log_once;
	static std::mutex s_v54_baseline_mutex;
	static bool s_v54_baseline_ready = false;
	static char s_v54_baseline_execute_hex[65] = {};
	static char s_v54_baseline_miss_hex[65] = {};

	uint64_t v54_register_pipeline(
		ID3D12StateObject *state_object,
		bool rewritten,
		uint64_t rewritten_state_call)
	{
		if (state_object == nullptr)
			return 0;

		void *const identity = v33_identity_pointer(
			reinterpret_cast<IUnknown *>(state_object));
		if (identity == nullptr)
			return 0;

		uint64_t pipeline_id = 0;
		bool created = false;
		{
			std::lock_guard<std::mutex> lock(s_v54_pipeline_mutex);
			const auto found = s_v54_pipeline_ids_by_identity.find(identity);
			if (found != s_v54_pipeline_ids_by_identity.end())
			{
				pipeline_id = found->second;
				auto &info = s_v54_pipeline_infos[pipeline_id];
				if (rewritten)
				{
					info.rewritten = true;
					info.rewritten_state_call = rewritten_state_call;
				}
			}
			else
			{
				pipeline_id = ++s_v54_next_pipeline_id;
				v54_pipeline_info info = {};
				info.pipeline_id = pipeline_id;
				info.rewritten = rewritten;
				info.rewritten_state_call = rewritten_state_call;
				info.identity = identity;
				s_v54_pipeline_ids_by_identity[identity] = pipeline_id;
				s_v54_pipeline_infos[pipeline_id] = info;
				created = true;
			}
		}

		if (created)
		{
			ID3D12StateObjectProperties *properties = nullptr;
			const HRESULT properties_hr =
				state_object->QueryInterface(
					__uuidof(ID3D12StateObjectProperties),
					reinterpret_cast<void **>(&properties));

			void *properties_pointer = properties;
			const void *execute_identifier = nullptr;
			const void *miss_identifier = nullptr;
			const void *sort_identifier = nullptr;
			if (properties != nullptr)
			{
				execute_identifier =
					properties->GetShaderIdentifier(L"ExecuteTrace");
				miss_identifier =
					properties->GetShaderIdentifier(L"Miss");
				sort_identifier =
					properties->GetShaderIdentifier(L"ExecuteTrace_SortRay");
			}

			char execute_hex[65] = {};
			char miss_hex[65] = {};
			char sort_hex[65] = {};
			v36_identifier_to_hex(execute_identifier, execute_hex);
			v36_identifier_to_hex(miss_identifier, miss_hex);
			v36_identifier_to_hex(sort_identifier, sort_hex);

			if (rewritten)
			{
				std::lock_guard<std::mutex> baseline_lock(s_v54_baseline_mutex);
				memcpy(s_v54_baseline_execute_hex, execute_hex, sizeof(execute_hex));
				memcpy(s_v54_baseline_miss_hex, miss_hex, sizeof(miss_hex));
				s_v54_baseline_ready = true;
			}

			if (properties != nullptr)
				properties->Release();

			{
				std::lock_guard<std::mutex> lock(s_v54_pipeline_mutex);
				auto found = s_v54_pipeline_infos.find(pipeline_id);
				if (found != s_v54_pipeline_infos.end())
				{
					found->second.properties = properties_pointer;
					found->second.execute_present = execute_identifier != nullptr;
					found->second.miss_present = miss_identifier != nullptr;
					found->second.sort_present = sort_identifier != nullptr;
					memcpy(found->second.execute_hex, execute_hex, sizeof(execute_hex));
					memcpy(found->second.miss_hex, miss_hex, sizeof(miss_hex));
					memcpy(found->second.sort_hex, sort_hex, sizeof(sort_hex));
				}
			}

			std::call_once(
				s_v54_active_log_once,
				[]()
				{
					reshade::log::message(
						reshade::log::level::info,
						"D3DMetal RTX ray-hit pattern inheritance census v54: ACTIVE tracks=all-bound-state-objects direct-and-indirect-rays=1 patterned-export-probes=1 shader-bytes-modified=0.");
				});

			reshade::log::message(
				reshade::log::level::info,
				"D3DMetal RTX ray-hit pattern inheritance census v54: PIPELINE_REGISTER pipeline_id=%llu rewritten=%u rewritten_state_call=%llu state_object=%p identity=%p properties=%p properties_hr=%s properties_raw=0x%08X probe_execute=%u execute_hex=%s probe_miss=%u miss_hex=%s probe_sort=%u sort_hex=%s.",
				static_cast<unsigned long long>(pipeline_id),
				rewritten ? 1u : 0u,
				static_cast<unsigned long long>(rewritten_state_call),
				state_object,
				identity,
				properties_pointer,
				reshade::log::hr_to_string(properties_hr).c_str(),
				static_cast<uint32_t>(properties_hr),
				execute_identifier != nullptr ? 1u : 0u,
				execute_hex,
				miss_identifier != nullptr ? 1u : 0u,
				miss_hex,
				sort_identifier != nullptr ? 1u : 0u,
				sort_hex);
		}

		return pipeline_id;
	}

	void v54_bind_pipeline(
		ID3D12GraphicsCommandList4 *command_list,
		uint64_t pipeline_id,
		ID3D12StateObject *state_object)
	{
		if (command_list == nullptr)
			return;

		uint64_t pipeline_bind_index = 0;
		{
			std::lock_guard<std::mutex> lock(s_v54_pipeline_mutex);
			if (pipeline_id != 0)
			{
				s_v54_bound_pipeline_ids[command_list] = pipeline_id;
				pipeline_bind_index =
					++s_v54_pipeline_infos[pipeline_id].bind_count;
			}
			else
			{
				s_v54_bound_pipeline_ids.erase(command_list);
			}
		}

		const uint64_t bind_total = ++s_v54_total_binds;
		reshade::log::message(
			reshade::log::level::info,
			"D3DMetal RTX ray-hit pattern inheritance census v54: PIPELINE_BIND bind_total=%llu pipeline_id=%llu pipeline_bind_index=%llu command_list=%p state_object=%p.",
			static_cast<unsigned long long>(bind_total),
			static_cast<unsigned long long>(pipeline_id),
			static_cast<unsigned long long>(pipeline_bind_index),
			command_list,
			state_object);
	}

	uint64_t v54_lookup_bound_pipeline(
		ID3D12GraphicsCommandList4 *command_list)
	{
		if (command_list == nullptr)
			return 0;

		std::lock_guard<std::mutex> lock(s_v54_pipeline_mutex);
		const auto found = s_v54_bound_pipeline_ids.find(command_list);
		return found != s_v54_bound_pipeline_ids.end() ? found->second : 0;
	}

	void v54_record_pipeline_ray(
		ID3D12GraphicsCommandList4 *command_list,
		bool indirect,
		uint64_t global_ray_index)
	{
		const uint64_t pipeline_id =
			v54_lookup_bound_pipeline(command_list);

		uint64_t pipeline_ray_index = 0;
		uint64_t pipeline_bind_count = 0;
		bool rewritten = false;
		uint64_t rewritten_state_call = 0;
		{
			std::lock_guard<std::mutex> lock(s_v54_pipeline_mutex);
			const auto found = s_v54_pipeline_infos.find(pipeline_id);
			if (found != s_v54_pipeline_infos.end())
			{
				auto &info = found->second;
				pipeline_ray_index = indirect ?
					++info.indirect_ray_count :
					++info.direct_ray_count;
				pipeline_bind_count = info.bind_count;
				rewritten = info.rewritten;
				rewritten_state_call = info.rewritten_state_call;
			}
		}

		if (indirect)
			++s_v54_total_indirect_rays;
		else
			++s_v54_total_direct_rays;

		reshade::log::message(
			pipeline_id != 0 ?
				reshade::log::level::info :
				reshade::log::level::warning,
			"D3DMetal RTX ray-hit pattern inheritance census v54: PIPELINE_RAY kind=%s global_ray_index=%llu pipeline_id=%llu pipeline_ray_index=%llu pipeline_bind_count=%llu rewritten=%u rewritten_state_call=%llu command_list=%p.",
			indirect ? "indirect" : "direct",
			static_cast<unsigned long long>(global_ray_index),
			static_cast<unsigned long long>(pipeline_id),
			static_cast<unsigned long long>(pipeline_ray_index),
			static_cast<unsigned long long>(pipeline_bind_count),
			rewritten ? 1u : 0u,
			static_cast<unsigned long long>(rewritten_state_call),
			command_list);
	}
"""

text = text.replace(globals_anchor, globals_anchor + helper + "\n", 1)

bind_anchor = (
    "\t\tconst bool rewritten = v33_lookup_rewritten_state_object(\n"
    "\t\t\tstate_object, state_call);\n\n"
    "\t\tif (s_v33_original_set_pipeline_state1 != nullptr)\n"
)
if text.count(bind_anchor) != 1:
    raise RuntimeError(f"V54 bind anchor mismatch: {text.count(bind_anchor)}")

bind_replacement = (
    "\t\tconst bool rewritten = v33_lookup_rewritten_state_object(\n"
    "\t\t\tstate_object, state_call);\n"
    "\t\tconst uint64_t v54_pipeline_id = v54_register_pipeline(\n"
    "\t\t\tstate_object, rewritten, state_call);\n\n"
    "\t\tif (s_v33_original_set_pipeline_state1 != nullptr)\n"
)
text = text.replace(bind_anchor, bind_replacement, 1)

post_bind_anchor = (
    "\t\tif (s_v33_original_set_pipeline_state1 != nullptr)\n"
    "\t\t\ts_v33_original_set_pipeline_state1(command_list, state_object);\n\n"
    "\t\t{\n"
)
if text.count(post_bind_anchor) != 1:
    raise RuntimeError(f"V54 post-bind anchor mismatch: {text.count(post_bind_anchor)}")

post_bind_replacement = (
    "\t\tif (s_v33_original_set_pipeline_state1 != nullptr)\n"
    "\t\t\ts_v33_original_set_pipeline_state1(command_list, state_object);\n\n"
    "\t\tv54_bind_pipeline(command_list, v54_pipeline_id, state_object);\n\n"
    "\t\t{\n"
)
text = text.replace(post_bind_anchor, post_bind_replacement, 1)

direct_anchor = (
    "\t\tuint64_t rewritten_index = 0;\n"
    "\t\tif (rewritten)\n"
    "\t\t\trewritten_index = ++s_v33_dispatch_rewritten;\n\n"
    "\t\tconst bool should_log =\n"
)
if text.count(direct_anchor) != 1:
    raise RuntimeError(f"V54 direct-ray anchor mismatch: {text.count(direct_anchor)}")

direct_replacement = (
    "\t\tuint64_t rewritten_index = 0;\n"
    "\t\tif (rewritten)\n"
    "\t\t\trewritten_index = ++s_v33_dispatch_rewritten;\n\n"
    "\t\tv54_record_pipeline_ray(command_list, false, dispatch_total);\n\n"
    "\t\tconst bool should_log =\n"
)
text = text.replace(direct_anchor, direct_replacement, 1)

indirect_anchor = (
    "\t\tif (dispatch_rays)\n"
    "\t\t{\n"
    "\t\t\tray_index = ++s_v34_ray_indirect_total;\n"
    "\t\t\tif (rewritten)\n"
    "\t\t\t\trewritten_ray_index =\n"
    "\t\t\t\t\t++s_v34_rewritten_ray_indirect_total;\n"
    "\t\t}\n\n"
    "\t\tD3D12_GPU_VIRTUAL_ADDRESS argument_gpu_va = 0;\n"
)
if text.count(indirect_anchor) != 1:
    raise RuntimeError(f"V54 indirect-ray anchor mismatch: {text.count(indirect_anchor)}")

indirect_replacement = (
    "\t\tif (dispatch_rays)\n"
    "\t\t{\n"
    "\t\t\tray_index = ++s_v34_ray_indirect_total;\n"
    "\t\t\tif (rewritten)\n"
    "\t\t\t\trewritten_ray_index =\n"
    "\t\t\t\t\t++s_v34_rewritten_ray_indirect_total;\n"
    "\t\t\tv54_record_pipeline_ray(\n"
    "\t\t\t\treinterpret_cast<ID3D12GraphicsCommandList4 *>(command_list),\n"
    "\t\t\t\ttrue,\n"
    "\t\t\t\tray_index);\n"
    "\t\t}\n\n"
    "\t\tD3D12_GPU_VIRTUAL_ADDRESS argument_gpu_va = 0;\n"
)
text = text.replace(indirect_anchor, indirect_replacement, 1)

required = [
    "D3DMetal RTX ray-hit pattern inheritance census v54: ACTIVE",
    "PIPELINE_REGISTER pipeline_id=",
    "PIPELINE_BIND bind_total=",
    "PIPELINE_RAY kind=%s",
    "tracks=all-bound-state-objects",
    "patterned-export-probes=1",
    "probe_execute=%u",
    "execute_hex=%s",
    "probe_miss=%u",
    "miss_hex=%s",
    "shader-bytes-modified=0",
]
for marker in required:
    if marker not in text:
        raise RuntimeError(f"Missing V54 source marker: {marker}")

SOURCE.write_text(text, encoding="utf-8", newline="\n")

report = Path("v54-patch-report.txt")
report.write_text(
    "\n".join([
        "V54_RAYHIT_PATTERN_INHERITANCE_CENSUS_PATCH_OK",
        "V53_RAYHIT_OUTPUT_PATTERN_PRESERVED=YES",
        "ALL_BOUND_STATE_OBJECTS_TRACKED=YES",
        "DIRECT_DISPATCH_RAYS_TRACKED=YES",
        "INDIRECT_DISPATCH_RAYS_TRACKED=YES",
        "PIPELINE_PROPERTIES_POINTER_LOGGED=YES",
        "EVERY_BOUND_PIPELINE_EXECUTETRACE_PROBED=YES",
        "EVERY_BOUND_PIPELINE_MISS_PROBED=YES",
        "PATTERNED_BASELINE_IDENTIFIERS_CAPTURED=YES",
        "PIPELINE_BIND_COUNTS_LOGGED=YES",
        "PIPELINE_RAY_COUNTS_LOGGED=YES",
        "SHADER_BYTES_MODIFIED_BY_V54=NO",
        "STATE_OBJECTS_MODIFIED_BY_V54=NO",
        "SHADER_TABLES_MODIFIED_BY_V54=NO",
        "DISPATCH_ARGUMENTS_MODIFIED_BY_V54=NO",
        "RESULT=PASS",
        "",
    ]),
    encoding="utf-8",
    newline="\n",
)
print(report.read_text(encoding="utf-8"))
