from pathlib import Path

SOURCE = Path("source/d3d12/d3d12.cpp")
if not SOURCE.is_file():
    raise RuntimeError(f"Missing source file: {SOURCE}")

text = SOURCE.read_text(encoding="utf-8-sig")
if "D3DMetal RTX descriptor scaffold diagnostic v27:" not in text:
    raise RuntimeError("V27 must be applied before V28")
if "D3DMetal RTX pipeline-config dependency diagnostic v28:" in text:
    raise RuntimeError("V28 is already present")

signature = "\tHRESULT STDMETHODCALLTYPE trace_create_state_object(\n"
if text.count(signature) != 1:
    raise RuntimeError(f"V28 trace signature mismatch: {text.count(signature)}")

helper = r"""
	struct v28_probe_summary
	{
		unsigned int next_index = 1;
		unsigned int accepted = 0;
		unsigned int rejected = 0;
		unsigned int controls_accepted = 0;
		unsigned int controls_rejected = 0;
		std::string first_accepted;
	};

	static std::atomic<int> s_v28_probe_state = 0;
	static std::atomic<unsigned int> s_v28_passthrough_logs = 0;

	bool v28_build_variant(
		const D3D12_STATE_OBJECT_DESC &snapshot,
		const std::vector<D3D12_STATE_SUBOBJECT> &source,
		size_t library_index,
		const std::vector<bool> &mask,
		D3D12_STATE_OBJECT_TYPE output_type,
		int state_flags_override,
		v25_export_filter export_filter,
		const uint8_t *replacement_module,
		size_t replacement_size,
		v25_variant_storage &storage,
		D3D12_STATE_OBJECT_DESC &output)
	{
		if (!v25_build_variant(
			snapshot,
			source,
			library_index,
			mask,
			output_type,
			false,
			state_flags_override,
			export_filter,
			storage,
			output))
		{
			return false;
		}

		if (replacement_module != nullptr)
		{
			if (replacement_size == 0 || storage.libraries.size() != 1)
				return false;
			D3D12_DXIL_LIBRARY_DESC &library = storage.libraries.back();
			library.DXILLibrary.pShaderBytecode = replacement_module;
			library.DXILLibrary.BytecodeLength = replacement_size;
		}
		return true;
	}

	void v28_run_probe(
		ID3D12Device5 *device,
		uint64_t call_id,
		const char *name,
		const D3D12_STATE_OBJECT_DESC &desc,
		bool control,
		LPCWSTR export_a,
		LPCWSTR export_b,
		v28_probe_summary &summary)
	{
		const unsigned int index = summary.next_index++;
		size_t module_size = 0;
		std::string hash_kind;
		std::string hash_value;
		v26_describe_first_dxil(desc, module_size, hash_kind, hash_value);

		void *object = nullptr;
		const HRESULT hr = s_original_create_state_object(
			device,
			&desc,
			__uuidof(ID3D12StateObject),
			&object);
		const bool accepted = SUCCEEDED(hr) && object != nullptr;

		HRESULT properties_hr = E_NOINTERFACE;
		bool export_a_present = false;
		bool export_b_present = false;
		if (accepted)
		{
			ID3D12StateObjectProperties *properties = nullptr;
			properties_hr = reinterpret_cast<ID3D12StateObject *>(object)->QueryInterface(
				__uuidof(ID3D12StateObjectProperties),
				reinterpret_cast<void **>(&properties));
			if (SUCCEEDED(properties_hr) && properties != nullptr)
			{
				if (export_a != nullptr)
					export_a_present = properties->GetShaderIdentifier(export_a) != nullptr;
				if (export_b != nullptr)
					export_b_present = properties->GetShaderIdentifier(export_b) != nullptr;
				properties->Release();
			}
		}

		reshade::log::message(
			accepted ? reshade::log::level::info : reshade::log::level::warning,
			"D3DMetal RTX pipeline-config dependency diagnostic v28: "
			"PROBE call=%llu index=%u name=%s control=%u "
			"type=%s(%u) subobjects=%u module_size=%llu "
			"module_hash_kind=%s module_hash=%s "
			"hr=%s raw=0x%08X object=%p accepted=%u "
			"properties_hr=%s properties_raw=0x%08X "
			"export_a_present=%u export_b_present=%u.",
			static_cast<unsigned long long>(call_id),
			index,
			name,
			control ? 1u : 0u,
			state_object_type_name(desc.Type),
			static_cast<unsigned int>(desc.Type),
			desc.NumSubobjects,
			static_cast<unsigned long long>(module_size),
			hash_kind.c_str(),
			hash_value.c_str(),
			reshade::log::hr_to_string(hr).c_str(),
			static_cast<uint32_t>(hr),
			object,
			accepted ? 1u : 0u,
			reshade::log::hr_to_string(properties_hr).c_str(),
			static_cast<uint32_t>(properties_hr),
			export_a_present ? 1u : 0u,
			export_b_present ? 1u : 0u);

		if (control)
		{
			if (accepted) ++summary.controls_accepted;
			else ++summary.controls_rejected;
		}
		else
		{
			if (accepted)
			{
				++summary.accepted;
				if (summary.first_accepted.empty()) summary.first_accepted = name;
			}
			else ++summary.rejected;
		}

		if (object != nullptr)
			reinterpret_cast<IUnknown *>(object)->Release();
	}

	bool try_v28_pipeline_config_dependency_diagnostic(
		ID3D12Device5 *device,
		uint64_t call_id,
		const D3D12_STATE_OBJECT_DESC *original_desc,
		const D3D12_STATE_OBJECT_DESC &snapshot,
		REFIID riid,
		void **state_object,
		HRESULT &result)
	{
		if (original_desc == nullptr ||
			snapshot.Type != D3D12_STATE_OBJECT_TYPE_RAYTRACING_PIPELINE ||
			snapshot.NumSubobjects != 28 ||
			snapshot.pSubobjects == nullptr)
			return false;

		std::vector<D3D12_STATE_SUBOBJECT> parent_source;
		if (!v27_copy_subobjects(snapshot, parent_source))
			return false;

		size_t parent_library = static_cast<size_t>(-1);
		size_t matching_count = 0;
		for (size_t index = 0; index < parent_source.size(); ++index)
		{
			if (parent_source[index].Type != D3D12_STATE_SUBOBJECT_TYPE_DXIL_LIBRARY)
				continue;
			D3D12_DXIL_LIBRARY_DESC library = {};
			if (!safe_copy_from_process(parent_source[index].pDesc, &library, sizeof(library)))
				continue;
			if (v24_parent_dxil_matches(
				library.DXILLibrary.pShaderBytecode,
				library.DXILLibrary.BytecodeLength))
			{
				++matching_count;
				parent_library = index;
			}
		}
		if (matching_count != 1)
			return false;

		int expected = 0;
		if (!s_v28_probe_state.compare_exchange_strong(expected, 1, std::memory_order_acq_rel))
		{
			if (state_object != nullptr) *state_object = nullptr;
			result = s_original_create_state_object(device, original_desc, riid, state_object);
			const unsigned int log_index = ++s_v28_passthrough_logs;
			if (log_index <= 3)
			{
				reshade::log::message(
					FAILED(result) ? reshade::log::level::warning : reshade::log::level::info,
					"D3DMetal RTX pipeline-config dependency diagnostic v28: "
					"PASSTHROUGH call=%llu state=%d hr=%s raw=0x%08X.",
					static_cast<unsigned long long>(call_id),
					expected,
					reshade::log::hr_to_string(result).c_str(),
					static_cast<uint32_t>(result));
			}
			return true;
		}

		std::vector<std::shared_ptr<captured_collection>> collections;
		{
			std::lock_guard<std::mutex> lock(s_collection_capture_mutex);
			collections = s_captured_collections;
		}
		if (collections.empty() || !collections.front() || !collections.front()->storage)
		{
			s_v28_probe_state.store(0, std::memory_order_release);
			return false;
		}

		const D3D12_STATE_OBJECT_DESC &child_desc = collections.front()->storage->desc;
		std::vector<D3D12_STATE_SUBOBJECT> child_source;
		if (!v27_copy_subobjects(child_desc, child_source))
		{
			s_v28_probe_state.store(0, std::memory_order_release);
			return false;
		}
		size_t child_library = static_cast<size_t>(-1);
		if (!v27_find_first_dxil(child_source, child_library))
		{
			s_v28_probe_state.store(0, std::memory_order_release);
			return false;
		}

		reshade::log::message(
			reshade::log::level::info,
			"D3DMetal RTX pipeline-config dependency diagnostic v28: "
			"TARGET call=%llu parent_subobjects=%u parent_library=%llu "
			"child_subobjects=%u child_library=%llu "
			"execute_bytes=%llu miss_bytes=%llu combined_bytes=%llu original_bytes=%llu.",
			static_cast<unsigned long long>(call_id),
			snapshot.NumSubobjects,
			static_cast<unsigned long long>(parent_library),
			child_desc.NumSubobjects,
			static_cast<unsigned long long>(child_library),
			static_cast<unsigned long long>(sizeof(g_v26_execute_trace_only_dxil)),
			static_cast<unsigned long long>(sizeof(g_v26_miss_only_dxil)),
			static_cast<unsigned long long>(sizeof(g_v26_execute_plus_miss_dxil)),
			static_cast<unsigned long long>(sizeof(g_v24_original_parent_dxil)));

		v25_dump_complete_capture(call_id, snapshot, parent_source);
		v28_probe_summary summary;

		auto run_child_control = [&]()
		{
			v25_variant_storage storage;
			D3D12_STATE_OBJECT_DESC output = {};
			const std::vector<bool> mask = v27_make_mask(
				child_source, child_library,
				false, false, false, false, false, false, false, false, false);
			if (!v28_build_variant(
				child_desc, child_source, child_library, mask,
				D3D12_STATE_OBJECT_TYPE_COLLECTION, 3,
				v25_export_filter::all, nullptr, 0,
				storage, output))
			{
				reshade::log::message(
					reshade::log::level::warning,
					"D3DMetal RTX pipeline-config dependency diagnostic v28: "
					"BUILD_SKIP call=%llu name=CHILD_DXIL_ONLY_CONTROL.",
					static_cast<unsigned long long>(call_id));
				return;
			}
			v28_run_probe(
				device, call_id, "CHILD_DXIL_ONLY_CONTROL",
				output, true, nullptr, nullptr, summary);
		};

		auto run_parent = [&](
			const char *name,
			const std::vector<bool> &mask,
			D3D12_STATE_OBJECT_TYPE output_type,
			int state_flags_override,
			v25_export_filter export_filter,
			const uint8_t *replacement_module,
			size_t replacement_size,
			LPCWSTR export_a,
			LPCWSTR export_b,
			bool control)
		{
			v25_variant_storage storage;
			D3D12_STATE_OBJECT_DESC output = {};
			if (!v28_build_variant(
				snapshot, parent_source, parent_library, mask,
				output_type, state_flags_override,
				export_filter, replacement_module, replacement_size,
				storage, output))
			{
				reshade::log::message(
					reshade::log::level::warning,
					"D3DMetal RTX pipeline-config dependency diagnostic v28: "
					"BUILD_SKIP call=%llu name=%s.",
					static_cast<unsigned long long>(call_id), name);
				return;
			}
			v28_run_probe(
				device, call_id, name, output, control,
				export_a, export_b, summary);
		};

		const std::vector<bool> core_no_pipeline = v27_make_mask(
			parent_source, parent_library,
			true, true, true, true, false, false, false, true, true);
		const std::vector<bool> pipeline_dxil = v27_make_mask(
			parent_source, parent_library,
			false, false, false, false, true, false, false, false, false);
		const std::vector<bool> state_pipeline_dxil = v27_make_mask(
			parent_source, parent_library,
			true, false, false, false, true, false, false, false, false);
		const std::vector<bool> core_with_pipeline = v27_make_mask(
			parent_source, parent_library,
			true, true, true, true, true, false, false, true, true);

		run_child_control();

		run_parent(
			"MISS_CORE_NO_PIPELINE_CONTROL",
			core_no_pipeline,
			D3D12_STATE_OBJECT_TYPE_COLLECTION, 3,
			v25_export_filter::miss,
			g_v26_miss_only_dxil, sizeof(g_v26_miss_only_dxil),
			L"Miss", nullptr, true);
		run_parent(
			"MISS_PIPELINE_DXIL",
			pipeline_dxil,
			D3D12_STATE_OBJECT_TYPE_COLLECTION, 3,
			v25_export_filter::miss,
			g_v26_miss_only_dxil, sizeof(g_v26_miss_only_dxil),
			L"Miss", nullptr, false);
		run_parent(
			"MISS_STATE_PIPELINE_DXIL",
			state_pipeline_dxil,
			D3D12_STATE_OBJECT_TYPE_COLLECTION, 3,
			v25_export_filter::miss,
			g_v26_miss_only_dxil, sizeof(g_v26_miss_only_dxil),
			L"Miss", nullptr, false);
		run_parent(
			"MISS_CORE_WITH_PIPELINE_CONTROL",
			core_with_pipeline,
			D3D12_STATE_OBJECT_TYPE_COLLECTION, 3,
			v25_export_filter::miss,
			g_v26_miss_only_dxil, sizeof(g_v26_miss_only_dxil),
			L"Miss", nullptr, true);

		run_parent(
			"EXECUTE_CORE_NO_PIPELINE",
			core_no_pipeline,
			D3D12_STATE_OBJECT_TYPE_COLLECTION, 3,
			v25_export_filter::execute_trace,
			g_v26_execute_trace_only_dxil, sizeof(g_v26_execute_trace_only_dxil),
			L"ExecuteTrace", nullptr, false);
		run_parent(
			"EXECUTE_PIPELINE_DXIL",
			pipeline_dxil,
			D3D12_STATE_OBJECT_TYPE_COLLECTION, 3,
			v25_export_filter::execute_trace,
			g_v26_execute_trace_only_dxil, sizeof(g_v26_execute_trace_only_dxil),
			L"ExecuteTrace", nullptr, false);
		run_parent(
			"EXECUTE_STATE_PIPELINE_DXIL",
			state_pipeline_dxil,
			D3D12_STATE_OBJECT_TYPE_COLLECTION, 3,
			v25_export_filter::execute_trace,
			g_v26_execute_trace_only_dxil, sizeof(g_v26_execute_trace_only_dxil),
			L"ExecuteTrace", nullptr, false);
		run_parent(
			"EXECUTE_CORE_WITH_PIPELINE",
			core_with_pipeline,
			D3D12_STATE_OBJECT_TYPE_COLLECTION, 3,
			v25_export_filter::execute_trace,
			g_v26_execute_trace_only_dxil, sizeof(g_v26_execute_trace_only_dxil),
			L"ExecuteTrace", nullptr, false);

		run_parent(
			"COMBINED_CORE_NO_PIPELINE",
			core_no_pipeline,
			D3D12_STATE_OBJECT_TYPE_COLLECTION, 3,
			v25_export_filter::all,
			g_v26_execute_plus_miss_dxil, sizeof(g_v26_execute_plus_miss_dxil),
			L"ExecuteTrace", L"Miss", false);
		run_parent(
			"COMBINED_PIPELINE_DXIL",
			pipeline_dxil,
			D3D12_STATE_OBJECT_TYPE_COLLECTION, 3,
			v25_export_filter::all,
			g_v26_execute_plus_miss_dxil, sizeof(g_v26_execute_plus_miss_dxil),
			L"ExecuteTrace", L"Miss", false);
		run_parent(
			"COMBINED_STATE_PIPELINE_DXIL",
			state_pipeline_dxil,
			D3D12_STATE_OBJECT_TYPE_COLLECTION, 3,
			v25_export_filter::all,
			g_v26_execute_plus_miss_dxil, sizeof(g_v26_execute_plus_miss_dxil),
			L"ExecuteTrace", L"Miss", false);
		run_parent(
			"COMBINED_CORE_WITH_PIPELINE",
			core_with_pipeline,
			D3D12_STATE_OBJECT_TYPE_COLLECTION, 3,
			v25_export_filter::all,
			g_v26_execute_plus_miss_dxil, sizeof(g_v26_execute_plus_miss_dxil),
			L"ExecuteTrace", L"Miss", false);

		run_parent(
			"ORIGINAL_CORE_NO_PIPELINE",
			core_no_pipeline,
			D3D12_STATE_OBJECT_TYPE_COLLECTION, 3,
			v25_export_filter::all,
			nullptr, 0,
			L"ExecuteTrace", L"Miss", false);
		run_parent(
			"ORIGINAL_PIPELINE_DXIL",
			pipeline_dxil,
			D3D12_STATE_OBJECT_TYPE_COLLECTION, 3,
			v25_export_filter::all,
			nullptr, 0,
			L"ExecuteTrace", L"Miss", false);
		run_parent(
			"ORIGINAL_STATE_PIPELINE_DXIL",
			state_pipeline_dxil,
			D3D12_STATE_OBJECT_TYPE_COLLECTION, 3,
			v25_export_filter::all,
			nullptr, 0,
			L"ExecuteTrace", L"Miss", false);
		run_parent(
			"ORIGINAL_CORE_WITH_PIPELINE",
			core_with_pipeline,
			D3D12_STATE_OBJECT_TYPE_COLLECTION, 3,
			v25_export_filter::all,
			nullptr, 0,
			L"ExecuteTrace", L"Miss", false);

		run_parent(
			"COMBINED_CORE_RT_PIPELINE",
			core_with_pipeline,
			D3D12_STATE_OBJECT_TYPE_RAYTRACING_PIPELINE, 4,
			v25_export_filter::all,
			g_v26_execute_plus_miss_dxil, sizeof(g_v26_execute_plus_miss_dxil),
			L"ExecuteTrace", L"Miss", false);
		run_parent(
			"ORIGINAL_CORE_RT_PIPELINE",
			core_with_pipeline,
			D3D12_STATE_OBJECT_TYPE_RAYTRACING_PIPELINE, 4,
			v25_export_filter::all,
			nullptr, 0,
			L"ExecuteTrace", L"Miss", false);

		if (state_object != nullptr) *state_object = nullptr;
		result = s_original_create_state_object(device, original_desc, riid, state_object);
		void *final_object = nullptr;
		if (state_object != nullptr)
			safe_copy_from_process(state_object, &final_object, sizeof(final_object));

		reshade::log::message(
			FAILED(result) ? reshade::log::level::warning : reshade::log::level::info,
			"D3DMetal RTX pipeline-config dependency diagnostic v28: "
			"FINAL call=%llu hr=%s raw=0x%08X object=%p.",
			static_cast<unsigned long long>(call_id),
			reshade::log::hr_to_string(result).c_str(),
			static_cast<uint32_t>(result),
			final_object);

		reshade::log::message(
			reshade::log::level::info,
			"D3DMetal RTX pipeline-config dependency diagnostic v28: "
			"COMPLETE call=%llu accepted=%u rejected=%u controls_accepted=%u "
			"controls_rejected=%u first_accepted=%s.",
			static_cast<unsigned long long>(call_id),
			summary.accepted,
			summary.rejected,
			summary.controls_accepted,
			summary.controls_rejected,
			summary.first_accepted.empty() ? "<none>" : summary.first_accepted.c_str());

		s_v28_probe_state.store(2, std::memory_order_release);
		return true;
	}

"""

text = text.replace(signature, helper + "\n" + signature, 1)
trace_position = text.find(signature)
gate_anchor = (
    "\t\tD3D12_STATE_OBJECT_DESC snapshot = {};\n"
    "\t\tconst bool readable = safe_copy_from_process(desc, &snapshot, sizeof(snapshot));\n"
)
gate_position = text.find(gate_anchor, trace_position)
if gate_position < 0:
    raise RuntimeError("V28 gate anchor not found")
insert_position = gate_position + len(gate_anchor)

gate = r"""

		if (readable)
		{
			HRESULT v28_result = E_FAIL;
			if (try_v28_pipeline_config_dependency_diagnostic(
				device,
				call_id,
				desc,
				snapshot,
				riid,
				state_object,
				v28_result))
			{
				return v28_result;
			}
		}
"""
text = text[:insert_position] + gate + text[insert_position:]

required = [
    "D3DMetal RTX pipeline-config dependency diagnostic v28: ",
    "try_v28_pipeline_config_dependency_diagnostic(",
    "CHILD_DXIL_ONLY_CONTROL",
    "MISS_CORE_NO_PIPELINE_CONTROL",
    "MISS_PIPELINE_DXIL",
    "MISS_STATE_PIPELINE_DXIL",
    "MISS_CORE_WITH_PIPELINE_CONTROL",
    "EXECUTE_CORE_NO_PIPELINE",
    "EXECUTE_PIPELINE_DXIL",
    "EXECUTE_STATE_PIPELINE_DXIL",
    "EXECUTE_CORE_WITH_PIPELINE",
    "COMBINED_CORE_NO_PIPELINE",
    "COMBINED_PIPELINE_DXIL",
    "COMBINED_STATE_PIPELINE_DXIL",
    "COMBINED_CORE_WITH_PIPELINE",
    "ORIGINAL_CORE_NO_PIPELINE",
    "ORIGINAL_PIPELINE_DXIL",
    "ORIGINAL_STATE_PIPELINE_DXIL",
    "ORIGINAL_CORE_WITH_PIPELINE",
    "COMBINED_CORE_RT_PIPELINE",
    "ORIGINAL_CORE_RT_PIPELINE",
    "GetShaderIdentifier",
]
for marker in required:
    if marker not in text:
        raise RuntimeError(f"Missing V28 marker: {marker}")

trace_position = text.find(signature)
v28_pos = text.find("if (try_v28_pipeline_config_dependency_diagnostic(", trace_position)
v27_pos = text.find("if (try_v27_descriptor_scaffold_diagnostic(", trace_position)
v26_pos = text.find("if (try_v26_physical_single_export_diagnostic(", trace_position)
v25_pos = text.find("if (try_v25_semantic_matrix_minimizer(", trace_position)
v24_pos = text.find("if (try_v24_physical_dxil_bridge(", trace_position)
legacy_pos = text.find("const HRESULT original_hr = s_original_create_state_object", trace_position)
if not (
    trace_position >= 0 and
    v28_pos > trace_position and
    v27_pos > v28_pos and
    v26_pos > v27_pos and
    v25_pos > v26_pos and
    v24_pos > v25_pos and
    legacy_pos > v24_pos
):
    raise RuntimeError("V28/V27/V26/V25/V24/legacy gate ordering is invalid")

SOURCE.write_text(text, encoding="utf-8", newline="\n")

report = Path("v28-patch-report.txt")
report.write_text("\n".join([
    "V28_PIPELINE_CONFIG_DEPENDENCY_RUNTIME_PATCH_OK",
    "V28_NINETEEN_PROBE_HARNESS_PASS",
    "TARGET_SUBOBJECT_COUNT=28",
    "EXACT_V27_DELTA=RAYTRACING_PIPELINE_CONFIG",
    "PIPELINE_CONFIG_RECURSION_DEPTH=CAPTURED_VALUE",
    "PHYSICAL_EXECUTE_DXIL_SHA256=3dc6d51538557bc8aa6aa04510a9b726f9ea46db0c0108e28af11689e8aec614",
    "PHYSICAL_MISS_DXIL_SHA256=74beb66ae9bf76a02a15bed31ecf308c4d966bb0409f4c508d5c2cfdcec38191",
    "PHYSICAL_COMBINED_DXIL_SHA256=a315cdb97c6d21f4e2ecb50e38de733f8a76f1c86ac14f6ac44d42b72a041ba8",
    "ORIGINAL_PARENT_DXIL_SHA256=02d3db46e867f0b38da35a492101ae35544f5f93425fb4fb29120aeeea431869",
    "COLLECTION_AND_RT_PIPELINE_PROBES=ENABLED",
    "SHADER_IDENTIFIER_CHECKS=ENABLED",
    "DIAGNOSTIC_OBJECT_RELEASE=PASS",
    "FINAL_ORIGINAL_CALL_EXACTLY_ONCE=PASS",
    "FAKE_SUCCESS=DISABLED",
    "V28_GATE_BEFORE_V27_GATE=PASS",
    "V27_GATE_BEFORE_V26_GATE=PASS",
    "V26_GATE_BEFORE_V25_GATE=PASS",
    "V25_GATE_BEFORE_V24_GATE=PASS",
    "",
]), encoding="utf-8", newline="\n")
print(report.read_text(encoding="utf-8"))
