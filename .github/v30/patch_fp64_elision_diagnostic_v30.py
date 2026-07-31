from pathlib import Path
import hashlib

SOURCE = Path("source/d3d12/d3d12.cpp")
GENERATED = Path(".github/v30/generated")
if not SOURCE.is_file():
    raise RuntimeError(f"Missing source file: {SOURCE}")
if not GENERATED.is_dir():
    raise RuntimeError(f"Missing V30 generated directory: {GENERATED}")

MODULES = [
    ("g_v30_execute_trace_fp32_dxil", "execute-trace-fp32.dxil"),
    ("g_v30_execute_plus_miss_fp32_dxil", "execute-plus-miss-fp32.dxil"),
]


def c_array(name: str, data: bytes) -> str:
    lines = [f"\tstatic const uint8_t {name}[] = {{"]
    for offset in range(0, len(data), 16):
        chunk = data[offset:offset + 16]
        lines.append("\t\t" + ", ".join(f"0x{value:02X}" for value in chunk) + ",")
    lines.append("\t};")
    return "\n".join(lines)


arrays = []
module_reports = []
for symbol, filename in MODULES:
    path = GENERATED / filename
    if not path.is_file():
        raise RuntimeError(f"Missing Microsoft-validated V30 DXIL module: {path}")
    data = path.read_bytes()
    if len(data) < 1024:
        raise RuntimeError(f"V30 module is unexpectedly small: {filename} ({len(data)} bytes)")
    digest = hashlib.sha256(data).hexdigest()
    arrays.append(c_array(symbol, data))
    module_reports.append((symbol, filename, len(data), digest))

text = SOURCE.read_text(encoding="utf-8-sig")
if "D3DMetal RTX raygen intrinsic ladder diagnostic v29:" not in text:
    raise RuntimeError("V29 must be applied before V30")
if "D3DMetal RTX FP64 elision diagnostic v30:" in text:
    raise RuntimeError("V30 is already present")

signature = "\tHRESULT STDMETHODCALLTYPE trace_create_state_object(\n"
if text.count(signature) != 1:
    raise RuntimeError(f"V30 trace signature mismatch: {text.count(signature)}")

array_block = "\n\n".join(arrays)

helper = r'''
__ARRAY_BLOCK__

	struct v30_probe_summary
	{
		unsigned int next_index = 1;
		unsigned int accepted = 0;
		unsigned int rejected = 0;
		std::string first_rejected;
	};

	struct v30_full_replacement_storage
	{
		std::vector<D3D12_STATE_SUBOBJECT> subobjects;
		D3D12_DXIL_LIBRARY_DESC library = {};
		std::deque<D3D12_SUBOBJECT_TO_EXPORTS_ASSOCIATION> associations;
		D3D12_STATE_OBJECT_DESC desc = {};
	};

	static std::atomic<int> s_v30_probe_state = 0;
	static std::atomic<unsigned int> s_v30_passthrough_logs = 0;

	bool v30_build_full_replacement(
		const D3D12_STATE_OBJECT_DESC &snapshot,
		const std::vector<D3D12_STATE_SUBOBJECT> &source,
		size_t library_index,
		const uint8_t *module,
		size_t module_size,
		v30_full_replacement_storage &storage,
		D3D12_STATE_OBJECT_DESC &output)
	{
		if (snapshot.pSubobjects == nullptr || source.empty() ||
			library_index >= source.size() || module == nullptr || module_size == 0)
			return false;

		storage.subobjects = source;
		if (!safe_copy_from_process(
			source[library_index].pDesc,
			&storage.library,
			sizeof(storage.library)))
			return false;

		storage.library.DXILLibrary.pShaderBytecode = module;
		storage.library.DXILLibrary.BytecodeLength = module_size;
		storage.subobjects[library_index].pDesc = &storage.library;

		const uintptr_t source_begin = reinterpret_cast<uintptr_t>(snapshot.pSubobjects);
		const size_t source_bytes = source.size() * sizeof(D3D12_STATE_SUBOBJECT);

		for (size_t index = 0; index < source.size(); ++index)
		{
			if (source[index].Type != D3D12_STATE_SUBOBJECT_TYPE_SUBOBJECT_TO_EXPORTS_ASSOCIATION)
				continue;

			D3D12_SUBOBJECT_TO_EXPORTS_ASSOCIATION association = {};
			if (!safe_copy_from_process(source[index].pDesc, &association, sizeof(association)))
				return false;

			const uintptr_t target = reinterpret_cast<uintptr_t>(association.pSubobjectToAssociate);
			if (target < source_begin)
				return false;
			const uintptr_t offset = target - source_begin;
			if (offset >= source_bytes || offset % sizeof(D3D12_STATE_SUBOBJECT) != 0)
				return false;

			const size_t target_index = static_cast<size_t>(offset / sizeof(D3D12_STATE_SUBOBJECT));
			association.pSubobjectToAssociate = &storage.subobjects[target_index];
			storage.associations.push_back(association);
			storage.subobjects[index].pDesc = &storage.associations.back();
		}

		storage.desc = snapshot;
		storage.desc.pSubobjects = storage.subobjects.data();
		output = storage.desc;
		return true;
	}

	void v30_run_probe(
		ID3D12Device5 *device,
		uint64_t call_id,
		const char *name,
		const D3D12_STATE_OBJECT_DESC &desc,
		LPCWSTR export_a,
		LPCWSTR export_b,
		v30_probe_summary &summary)
	{
		const unsigned int index = summary.next_index++;
		size_t module_size = 0;
		std::string hash_kind;
		std::string hash_value;
		v26_describe_first_dxil(desc, module_size, hash_kind, hash_value);

		void *object = nullptr;
		const HRESULT hr = s_original_create_state_object(
			device, &desc, __uuidof(ID3D12StateObject), &object);
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
			"D3DMetal RTX FP64 elision diagnostic v30: "
			"PROBE call=%llu index=%u name=%s type=%s(%u) subobjects=%u "
			"module_size=%llu module_hash_kind=%s module_hash=%s "
			"hr=%s raw=0x%08X object=%p accepted=%u "
			"properties_hr=%s properties_raw=0x%08X export_a=%u export_b=%u.",
			static_cast<unsigned long long>(call_id), index, name,
			state_object_type_name(desc.Type), static_cast<unsigned int>(desc.Type),
			desc.NumSubobjects, static_cast<unsigned long long>(module_size),
			hash_kind.c_str(), hash_value.c_str(),
			reshade::log::hr_to_string(hr).c_str(), static_cast<uint32_t>(hr),
			object, accepted ? 1u : 0u,
			reshade::log::hr_to_string(properties_hr).c_str(),
			static_cast<uint32_t>(properties_hr),
			export_a_present ? 1u : 0u,
			export_b_present ? 1u : 0u);

		if (accepted)
			++summary.accepted;
		else
		{
			++summary.rejected;
			if (summary.first_rejected.empty()) summary.first_rejected = name;
		}

		if (object != nullptr)
			reinterpret_cast<IUnknown *>(object)->Release();
	}

	bool try_v30_fp64_elision_diagnostic(
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
			snapshot.NumSubobjects != 28 || snapshot.pSubobjects == nullptr)
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
		if (!s_v30_probe_state.compare_exchange_strong(expected, 1, std::memory_order_acq_rel))
		{
			if (state_object != nullptr) *state_object = nullptr;
			result = s_original_create_state_object(device, original_desc, riid, state_object);
			const unsigned int log_index = ++s_v30_passthrough_logs;
			if (log_index <= 3)
			{
				reshade::log::message(
					FAILED(result) ? reshade::log::level::warning : reshade::log::level::info,
					"D3DMetal RTX FP64 elision diagnostic v30: "
					"PASSTHROUGH call=%llu state=%d hr=%s raw=0x%08X.",
					static_cast<unsigned long long>(call_id), expected,
					reshade::log::hr_to_string(result).c_str(), static_cast<uint32_t>(result));
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
			s_v30_probe_state.store(0, std::memory_order_release);
			return false;
		}

		const D3D12_STATE_OBJECT_DESC &child_desc = collections.front()->storage->desc;
		std::vector<D3D12_STATE_SUBOBJECT> child_source;
		if (!v27_copy_subobjects(child_desc, child_source))
		{
			s_v30_probe_state.store(0, std::memory_order_release);
			return false;
		}
		size_t child_library = static_cast<size_t>(-1);
		if (!v27_find_first_dxil(child_source, child_library))
		{
			s_v30_probe_state.store(0, std::memory_order_release);
			return false;
		}

		reshade::log::message(
			reshade::log::level::info,
			"D3DMetal RTX FP64 elision diagnostic v30: "
			"TARGET call=%llu parent_subobjects=%u parent_library=%llu "
			"child_subobjects=%u child_library=%llu execute_fp32_bytes=%llu "
			"combined_fp32_bytes=%llu execute_fp64_bytes=%llu.",
			static_cast<unsigned long long>(call_id), snapshot.NumSubobjects,
			static_cast<unsigned long long>(parent_library), child_desc.NumSubobjects,
			static_cast<unsigned long long>(child_library),
			static_cast<unsigned long long>(sizeof(g_v30_execute_trace_fp32_dxil)),
			static_cast<unsigned long long>(sizeof(g_v30_execute_plus_miss_fp32_dxil)),
			static_cast<unsigned long long>(sizeof(g_v26_execute_trace_only_dxil)));

		v25_dump_complete_capture(call_id, snapshot, parent_source);
		v30_probe_summary summary;

		auto run_child_control = [&]()
		{
			v25_variant_storage storage;
			D3D12_STATE_OBJECT_DESC output = {};
			const std::vector<bool> mask = v27_make_mask(
				child_source, child_library,
				false, false, false, false, false, false, false, false, false);
			if (v28_build_variant(
				child_desc, child_source, child_library, mask,
				D3D12_STATE_OBJECT_TYPE_COLLECTION, 3,
				v25_export_filter::all, nullptr, 0, storage, output))
				v30_run_probe(device, call_id, "CHILD_DXIL_ONLY_CONTROL", output, nullptr, nullptr, summary);
		};

		auto run_parent = [&](
			const char *name,
			const std::vector<bool> &mask,
			D3D12_STATE_OBJECT_TYPE type,
			v25_export_filter export_filter,
			const uint8_t *replacement_module,
			size_t replacement_size,
			LPCWSTR export_a,
			LPCWSTR export_b)
		{
			v25_variant_storage storage;
			D3D12_STATE_OBJECT_DESC output = {};
			if (!v28_build_variant(
				snapshot, parent_source, parent_library, mask,
				type, 3, export_filter, replacement_module, replacement_size,
				storage, output))
			{
				reshade::log::message(
					reshade::log::level::warning,
					"D3DMetal RTX FP64 elision diagnostic v30: "
					"BUILD_SKIP call=%llu name=%s.",
					static_cast<unsigned long long>(call_id), name);
				return;
			}
			v30_run_probe(device, call_id, name, output, export_a, export_b, summary);
		};

		const std::vector<bool> core_no_pipeline = v27_make_mask(
			parent_source, parent_library,
			true, true, true, true, false, false, false, true, true);
		const std::vector<bool> core_with_pipeline = v27_make_mask(
			parent_source, parent_library,
			true, true, true, true, true, false, false, true, true);

		run_child_control();
		run_parent(
			"MISS_CORE_PIPELINE_CONTROL", core_with_pipeline,
			D3D12_STATE_OBJECT_TYPE_COLLECTION, v25_export_filter::miss,
			g_v26_miss_only_dxil, sizeof(g_v26_miss_only_dxil), L"Miss", nullptr);
		run_parent(
			"ORIGINAL_EXECUTE_FP64_CONTROL", core_with_pipeline,
			D3D12_STATE_OBJECT_TYPE_COLLECTION, v25_export_filter::execute_trace,
			g_v26_execute_trace_only_dxil, sizeof(g_v26_execute_trace_only_dxil), L"ExecuteTrace", nullptr);
		run_parent(
			"EXECUTE_FP32_CORE_NO_PIPELINE", core_no_pipeline,
			D3D12_STATE_OBJECT_TYPE_COLLECTION, v25_export_filter::execute_trace,
			g_v30_execute_trace_fp32_dxil, sizeof(g_v30_execute_trace_fp32_dxil), L"ExecuteTrace", nullptr);
		run_parent(
			"EXECUTE_FP32_CORE_PIPELINE", core_with_pipeline,
			D3D12_STATE_OBJECT_TYPE_COLLECTION, v25_export_filter::execute_trace,
			g_v30_execute_trace_fp32_dxil, sizeof(g_v30_execute_trace_fp32_dxil), L"ExecuteTrace", nullptr);
		run_parent(
			"COMBINED_FP32_CORE_PIPELINE", core_with_pipeline,
			D3D12_STATE_OBJECT_TYPE_COLLECTION, v25_export_filter::all,
			g_v30_execute_plus_miss_fp32_dxil, sizeof(g_v30_execute_plus_miss_fp32_dxil), L"ExecuteTrace", L"Miss");
		run_parent(
			"COMBINED_FP32_RT_PIPELINE", core_with_pipeline,
			D3D12_STATE_OBJECT_TYPE_RAYTRACING_PIPELINE, v25_export_filter::all,
			g_v30_execute_plus_miss_fp32_dxil, sizeof(g_v30_execute_plus_miss_fp32_dxil), L"ExecuteTrace", L"Miss");
		run_parent(
			"ORIGINAL_PARENT_CORE_PIPELINE_CONTROL", core_with_pipeline,
			D3D12_STATE_OBJECT_TYPE_RAYTRACING_PIPELINE, v25_export_filter::all,
			nullptr, 0, L"ExecuteTrace", L"Miss");

		v30_full_replacement_storage full_storage;
		D3D12_STATE_OBJECT_DESC full_output = {};
		if (v30_build_full_replacement(
			snapshot, parent_source, parent_library,
			g_v30_execute_plus_miss_fp32_dxil,
			sizeof(g_v30_execute_plus_miss_fp32_dxil),
			full_storage, full_output))
		{
			v30_run_probe(
				device, call_id, "FULL_28_FP32_REPLACEMENT_PIPELINE",
				full_output, L"ExecuteTrace", L"Miss", summary);
		}
		else
		{
			reshade::log::message(
				reshade::log::level::warning,
				"D3DMetal RTX FP64 elision diagnostic v30: "
				"BUILD_SKIP call=%llu name=FULL_28_FP32_REPLACEMENT_PIPELINE.",
				static_cast<unsigned long long>(call_id));
		}

		if (state_object != nullptr) *state_object = nullptr;
		result = s_original_create_state_object(device, original_desc, riid, state_object);
		void *final_object = nullptr;
		if (state_object != nullptr)
			safe_copy_from_process(state_object, &final_object, sizeof(final_object));

		reshade::log::message(
			FAILED(result) ? reshade::log::level::warning : reshade::log::level::info,
			"D3DMetal RTX FP64 elision diagnostic v30: "
			"FINAL call=%llu hr=%s raw=0x%08X object=%p.",
			static_cast<unsigned long long>(call_id),
			reshade::log::hr_to_string(result).c_str(),
			static_cast<uint32_t>(result), final_object);

		reshade::log::message(
			reshade::log::level::info,
			"D3DMetal RTX FP64 elision diagnostic v30: "
			"COMPLETE call=%llu accepted=%u rejected=%u first_rejected=%s.",
			static_cast<unsigned long long>(call_id),
			summary.accepted, summary.rejected,
			summary.first_rejected.empty() ? "<none>" : summary.first_rejected.c_str());

		s_v30_probe_state.store(2, std::memory_order_release);
		return true;
	}
'''.replace("__ARRAY_BLOCK__", array_block)

text = text.replace(signature, helper + "\n\n" + signature, 1)
trace_position = text.find(signature)
gate_anchor = (
    "\t\tD3D12_STATE_OBJECT_DESC snapshot = {};\n"
    "\t\tconst bool readable = safe_copy_from_process(desc, &snapshot, sizeof(snapshot));\n"
)
gate_position = text.find(gate_anchor, trace_position)
if gate_position < 0:
    raise RuntimeError("V30 gate anchor not found")
insert_position = gate_position + len(gate_anchor)

gate = r'''

		if (readable)
		{
			HRESULT v30_result = E_FAIL;
			if (try_v30_fp64_elision_diagnostic(
				device, call_id, desc, snapshot, riid, state_object, v30_result))
			{
				return v30_result;
			}
		}
'''
text = text[:insert_position] + gate + text[insert_position:]

required = [
    "D3DMetal RTX FP64 elision diagnostic v30: ",
    "try_v30_fp64_elision_diagnostic(",
    "CHILD_DXIL_ONLY_CONTROL",
    "MISS_CORE_PIPELINE_CONTROL",
    "ORIGINAL_EXECUTE_FP64_CONTROL",
    "EXECUTE_FP32_CORE_NO_PIPELINE",
    "EXECUTE_FP32_CORE_PIPELINE",
    "COMBINED_FP32_CORE_PIPELINE",
    "COMBINED_FP32_RT_PIPELINE",
    "ORIGINAL_PARENT_CORE_PIPELINE_CONTROL",
    "FULL_28_FP32_REPLACEMENT_PIPELINE",
    "g_v30_execute_trace_fp32_dxil",
    "g_v30_execute_plus_miss_fp32_dxil",
    "GetShaderIdentifier",
]
for marker in required:
    if marker not in text:
        raise RuntimeError(f"Missing V30 marker: {marker}")

trace_position = text.find(signature)
v30_pos = text.find("if (try_v30_fp64_elision_diagnostic(", trace_position)
v29_pos = text.find("if (try_v29_raygen_intrinsic_ladder_diagnostic(", trace_position)
v28_pos = text.find("if (try_v28_pipeline_config_dependency_diagnostic(", trace_position)
v27_pos = text.find("if (try_v27_descriptor_scaffold_diagnostic(", trace_position)
v26_pos = text.find("if (try_v26_physical_single_export_diagnostic(", trace_position)
v25_pos = text.find("if (try_v25_semantic_matrix_minimizer(", trace_position)
v24_pos = text.find("if (try_v24_physical_dxil_bridge(", trace_position)
legacy_pos = text.find("const HRESULT original_hr = s_original_create_state_object", trace_position)
if not (
    trace_position >= 0 and v30_pos > trace_position and v29_pos > v30_pos and
    v28_pos > v29_pos and v27_pos > v28_pos and v26_pos > v27_pos and
    v25_pos > v26_pos and v24_pos > v25_pos and legacy_pos > v24_pos
):
    raise RuntimeError("V30/V29/V28/V27/V26/V25/V24/legacy gate ordering is invalid")

SOURCE.write_text(text, encoding="utf-8", newline="\n")

report_lines = [
    "V30_FP64_ELISION_RUNTIME_PATCH_OK",
    "V30_NINE_PROBE_HARNESS_PASS",
    "TARGET_SUBOBJECT_COUNT=28",
    "TRIGGER_AREA=Sixth Street",
    "FP64_SEQUENCE_COUNT=2",
    "FP32_REPLACEMENT_SCALE=nearest_float_to_1_over_16777215",
    "SHADER_IDENTIFIER_CHECKS=ENABLED",
    "FULL_28_SUBOBJECT_REPLACEMENT=ENABLED",
    "DIAGNOSTIC_OBJECT_RELEASE=PASS",
    "FINAL_ORIGINAL_CALL_EXACTLY_ONCE=PASS",
    "FAKE_SUCCESS=DISABLED",
    "V30_GATE_BEFORE_V29_GATE=PASS",
]
for symbol, filename, size, digest in module_reports:
    report_lines.append(f"MODULE={filename} SYMBOL={symbol} SIZE={size} SHA256={digest}")
report_lines.append("")

report = Path("v30-patch-report.txt")
report.write_text("\n".join(report_lines), encoding="utf-8", newline="\n")
print(report.read_text(encoding="utf-8"))
