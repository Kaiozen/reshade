from pathlib import Path

SOURCE = Path("source/d3d12/d3d12.cpp")
if not SOURCE.is_file():
    raise RuntimeError(f"Missing source file: {SOURCE}")

text = SOURCE.read_text(encoding="utf-8-sig")
if "D3DMetal RTX physical single-export diagnostic v26:" not in text:
    raise RuntimeError("V26 must be applied before V27")
if "D3DMetal RTX descriptor scaffold diagnostic v27:" in text:
    raise RuntimeError("V27 is already present")

signature = "\tHRESULT STDMETHODCALLTYPE trace_create_state_object(\n"
if text.count(signature) != 1:
    raise RuntimeError(f"V27 trace signature mismatch: {text.count(signature)}")

helper = r"""
	struct v27_probe_summary
	{
		unsigned int next_index = 1;
		unsigned int accepted = 0;
		unsigned int rejected = 0;
		unsigned int controls_accepted = 0;
		unsigned int controls_rejected = 0;
		std::string first_accepted;
	};

	static std::atomic<int> s_v27_probe_state = 0;
	static std::atomic<unsigned int> s_v27_passthrough_logs = 0;

	bool v27_copy_subobjects(
		const D3D12_STATE_OBJECT_DESC &snapshot,
		std::vector<D3D12_STATE_SUBOBJECT> &source)
	{
		if (snapshot.NumSubobjects == 0 || snapshot.pSubobjects == nullptr ||
			snapshot.NumSubobjects > max_capture_subobjects)
			return false;

		source.resize(snapshot.NumSubobjects);
		return safe_copy_from_process(
			snapshot.pSubobjects,
			source.data(),
			source.size() * sizeof(D3D12_STATE_SUBOBJECT));
	}

	bool v27_find_first_dxil(
		const std::vector<D3D12_STATE_SUBOBJECT> &source,
		size_t &library_index)
	{
		library_index = static_cast<size_t>(-1);
		for (size_t index = 0; index < source.size(); ++index)
		{
			if (source[index].Type == D3D12_STATE_SUBOBJECT_TYPE_DXIL_LIBRARY)
			{
				library_index = index;
				return true;
			}
		}
		return false;
	}

	std::string v27_shape_string(
		const std::vector<D3D12_STATE_SUBOBJECT> &source)
	{
		std::ostringstream stream;
		for (size_t index = 0; index < source.size(); ++index)
		{
			if (index != 0) stream << ',';
			stream << index << ':' << subobject_type_name(source[index].Type);
		}
		return stream.str();
	}

	std::vector<bool> v27_make_mask(
		const std::vector<D3D12_STATE_SUBOBJECT> &source,
		size_t library_index,
		bool state_config,
		bool shader_config,
		bool global_root,
		bool local_root,
		bool pipeline_config,
		bool node_mask,
		bool hit_groups,
		bool associations,
		bool other_non_collection)
	{
		std::vector<bool> mask(source.size(), false);
		if (library_index < mask.size()) mask[library_index] = true;

		for (size_t index = 0; index < source.size(); ++index)
		{
			if (index == library_index) continue;
			switch (source[index].Type)
			{
			case D3D12_STATE_SUBOBJECT_TYPE_STATE_OBJECT_CONFIG:
				mask[index] = state_config;
				break;
			case D3D12_STATE_SUBOBJECT_TYPE_RAYTRACING_SHADER_CONFIG:
				mask[index] = shader_config;
				break;
			case D3D12_STATE_SUBOBJECT_TYPE_GLOBAL_ROOT_SIGNATURE:
				mask[index] = global_root;
				break;
			case D3D12_STATE_SUBOBJECT_TYPE_LOCAL_ROOT_SIGNATURE:
				mask[index] = local_root;
				break;
			case D3D12_STATE_SUBOBJECT_TYPE_RAYTRACING_PIPELINE_CONFIG:
			case D3D12_STATE_SUBOBJECT_TYPE_RAYTRACING_PIPELINE_CONFIG1:
				mask[index] = pipeline_config;
				break;
			case D3D12_STATE_SUBOBJECT_TYPE_NODE_MASK:
				mask[index] = node_mask;
				break;
			case D3D12_STATE_SUBOBJECT_TYPE_HIT_GROUP:
				mask[index] = hit_groups;
				break;
			case D3D12_STATE_SUBOBJECT_TYPE_SUBOBJECT_TO_EXPORTS_ASSOCIATION:
				mask[index] = associations;
				break;
			case D3D12_STATE_SUBOBJECT_TYPE_EXISTING_COLLECTION:
				mask[index] = false;
				break;
			case D3D12_STATE_SUBOBJECT_TYPE_DXIL_LIBRARY:
				mask[index] = false;
				break;
			default:
				mask[index] = other_non_collection;
				break;
			}
		}
		return mask;
	}

	bool v27_build_variant(
		const D3D12_STATE_OBJECT_DESC &snapshot,
		const std::vector<D3D12_STATE_SUBOBJECT> &source,
		size_t library_index,
		const std::vector<bool> &mask,
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
			D3D12_STATE_OBJECT_TYPE_COLLECTION,
			false,
			3,
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

	void v27_run_probe(
		ID3D12Device5 *device,
		uint64_t call_id,
		const char *name,
		const D3D12_STATE_OBJECT_DESC &desc,
		bool control,
		v27_probe_summary &summary)
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

		reshade::log::message(
			accepted ? reshade::log::level::info : reshade::log::level::warning,
			"D3DMetal RTX descriptor scaffold diagnostic v27: "
			"PROBE call=%llu index=%u name=%s control=%u "
			"type=%s(%u) subobjects=%u module_size=%llu "
			"module_hash_kind=%s module_hash=%s "
			"hr=%s raw=0x%08X object=%p accepted=%u.",
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
			accepted ? 1u : 0u);

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

	bool try_v27_descriptor_scaffold_diagnostic(
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
		if (!s_v27_probe_state.compare_exchange_strong(expected, 1, std::memory_order_acq_rel))
		{
			if (state_object != nullptr) *state_object = nullptr;
			result = s_original_create_state_object(device, original_desc, riid, state_object);
			const unsigned int log_index = ++s_v27_passthrough_logs;
			if (log_index <= 3)
			{
				reshade::log::message(
					FAILED(result) ? reshade::log::level::warning : reshade::log::level::info,
					"D3DMetal RTX descriptor scaffold diagnostic v27: "
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
			s_v27_probe_state.store(0, std::memory_order_release);
			return false;
		}

		const D3D12_STATE_OBJECT_DESC &child_desc = collections.front()->storage->desc;
		std::vector<D3D12_STATE_SUBOBJECT> child_source;
		if (!v27_copy_subobjects(child_desc, child_source))
		{
			s_v27_probe_state.store(0, std::memory_order_release);
			return false;
		}
		size_t child_library = static_cast<size_t>(-1);
		if (!v27_find_first_dxil(child_source, child_library))
		{
			s_v27_probe_state.store(0, std::memory_order_release);
			return false;
		}

		reshade::log::message(
			reshade::log::level::info,
			"D3DMetal RTX descriptor scaffold diagnostic v27: "
			"TARGET call=%llu parent_subobjects=%u parent_library=%llu "
			"child_subobjects=%u child_library=%llu miss_bytes=%llu.",
			static_cast<unsigned long long>(call_id),
			snapshot.NumSubobjects,
			static_cast<unsigned long long>(parent_library),
			child_desc.NumSubobjects,
			static_cast<unsigned long long>(child_library),
			static_cast<unsigned long long>(sizeof(g_v26_miss_only_dxil)));

		reshade::log::message(
			reshade::log::level::info,
			"D3DMetal RTX descriptor scaffold diagnostic v27: CHILD_SHAPE call=%llu shape=%s.",
			static_cast<unsigned long long>(call_id),
			v27_shape_string(child_source).c_str());
		reshade::log::message(
			reshade::log::level::info,
			"D3DMetal RTX descriptor scaffold diagnostic v27: PARENT_SHAPE call=%llu shape=%s.",
			static_cast<unsigned long long>(call_id),
			v27_shape_string(parent_source).c_str());

		v25_dump_complete_capture(call_id, snapshot, parent_source);
		v27_probe_summary summary;
		v27_run_probe(device, call_id, "CHILD_ORIGINAL_CONTROL", child_desc, true, summary);

		auto run_child = [&](const char *name, const std::vector<bool> &mask, bool control)
		{
			v25_variant_storage storage;
			D3D12_STATE_OBJECT_DESC output = {};
			if (!v27_build_variant(
				child_desc, child_source, child_library, mask,
				v25_export_filter::all, nullptr, 0, storage, output))
			{
				reshade::log::message(
					reshade::log::level::warning,
					"D3DMetal RTX descriptor scaffold diagnostic v27: BUILD_SKIP call=%llu name=%s.",
					static_cast<unsigned long long>(call_id), name);
				return;
			}
			v27_run_probe(device, call_id, name, output, control, summary);
		};

		auto run_miss = [&](const char *name, const std::vector<bool> &mask)
		{
			v25_variant_storage storage;
			D3D12_STATE_OBJECT_DESC output = {};
			if (!v27_build_variant(
				snapshot, parent_source, parent_library, mask,
				v25_export_filter::miss,
				g_v26_miss_only_dxil, sizeof(g_v26_miss_only_dxil),
				storage, output))
			{
				reshade::log::message(
					reshade::log::level::warning,
					"D3DMetal RTX descriptor scaffold diagnostic v27: BUILD_SKIP call=%llu name=%s.",
					static_cast<unsigned long long>(call_id), name);
				return;
			}
			v27_run_probe(device, call_id, name, output, false, summary);
		};

		std::vector<bool> child_full(child_source.size(), true);
		run_child("CHILD_FULL_CLONED", child_full, true);
		run_child(
			"CHILD_NO_ASSOCIATIONS",
			v27_make_mask(child_source, child_library, true, true, true, true, true, true, true, false, true),
			false);
		run_child(
			"CHILD_CONFIG_DXIL",
			v27_make_mask(child_source, child_library, true, false, false, false, false, false, false, false, false),
			false);
		run_child(
			"CHILD_DXIL_ONLY",
			v27_make_mask(child_source, child_library, false, false, false, false, false, false, false, false, false),
			false);

		run_miss(
			"MISS_CONFIG_DXIL",
			v27_make_mask(parent_source, parent_library, true, false, false, false, false, false, false, false, false));
		run_miss(
			"MISS_PLUS_SHADER_CONFIG",
			v27_make_mask(parent_source, parent_library, true, true, false, false, false, false, false, true, false));
		run_miss(
			"MISS_PLUS_GLOBAL_ROOT",
			v27_make_mask(parent_source, parent_library, true, false, true, false, false, false, false, true, false));
		run_miss(
			"MISS_PLUS_LOCAL_ROOT",
			v27_make_mask(parent_source, parent_library, true, false, false, true, false, false, false, true, false));
		run_miss(
			"MISS_PLUS_ROOTS_SHADER_CONFIG",
			v27_make_mask(parent_source, parent_library, true, true, true, true, false, false, false, true, false));
		run_miss(
			"MISS_NON_EXPORT_CORE",
			v27_make_mask(parent_source, parent_library, true, true, true, true, true, true, false, true, true));

		if (state_object != nullptr) *state_object = nullptr;
		result = s_original_create_state_object(device, original_desc, riid, state_object);
		void *final_object = nullptr;
		if (state_object != nullptr)
			safe_copy_from_process(state_object, &final_object, sizeof(final_object));

		reshade::log::message(
			FAILED(result) ? reshade::log::level::warning : reshade::log::level::info,
			"D3DMetal RTX descriptor scaffold diagnostic v27: "
			"FINAL call=%llu hr=%s raw=0x%08X object=%p.",
			static_cast<unsigned long long>(call_id),
			reshade::log::hr_to_string(result).c_str(),
			static_cast<uint32_t>(result),
			final_object);

		reshade::log::message(
			reshade::log::level::info,
			"D3DMetal RTX descriptor scaffold diagnostic v27: "
			"COMPLETE call=%llu accepted=%u rejected=%u controls_accepted=%u controls_rejected=%u first_accepted=%s.",
			static_cast<unsigned long long>(call_id),
			summary.accepted,
			summary.rejected,
			summary.controls_accepted,
			summary.controls_rejected,
			summary.first_accepted.empty() ? "<none>" : summary.first_accepted.c_str());

		s_v27_probe_state.store(2, std::memory_order_release);
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
    raise RuntimeError("V27 gate anchor not found")
insert_position = gate_position + len(gate_anchor)

gate = r"""

		if (readable)
		{
			HRESULT v27_result = E_FAIL;
			if (try_v27_descriptor_scaffold_diagnostic(
				device,
				call_id,
				desc,
				snapshot,
				riid,
				state_object,
				v27_result))
			{
				return v27_result;
			}
		}
"""
text = text[:insert_position] + gate + text[insert_position:]

required = [
    "D3DMetal RTX descriptor scaffold diagnostic v27: ",
    "try_v27_descriptor_scaffold_diagnostic(",
    "CHILD_ORIGINAL_CONTROL",
    "CHILD_FULL_CLONED",
    "CHILD_NO_ASSOCIATIONS",
    "CHILD_CONFIG_DXIL",
    "CHILD_DXIL_ONLY",
    "MISS_CONFIG_DXIL",
    "MISS_PLUS_SHADER_CONFIG",
    "MISS_PLUS_GLOBAL_ROOT",
    "MISS_PLUS_LOCAL_ROOT",
    "MISS_PLUS_ROOTS_SHADER_CONFIG",
    "MISS_NON_EXPORT_CORE",
]
for marker in required:
    if marker not in text:
        raise RuntimeError(f"Missing V27 marker: {marker}")

trace_position = text.find(signature)
v27_pos = text.find("if (try_v27_descriptor_scaffold_diagnostic(", trace_position)
v26_pos = text.find("if (try_v26_physical_single_export_diagnostic(", trace_position)
v25_pos = text.find("if (try_v25_semantic_matrix_minimizer(", trace_position)
v24_pos = text.find("if (try_v24_physical_dxil_bridge(", trace_position)
legacy_pos = text.find("const HRESULT original_hr = s_original_create_state_object", trace_position)
if not (trace_position >= 0 and v27_pos > trace_position and v26_pos > v27_pos and v25_pos > v26_pos and v24_pos > v25_pos and legacy_pos > v24_pos):
    raise RuntimeError("V27/V26/V25/V24/legacy gate ordering is invalid")

SOURCE.write_text(text, encoding="utf-8", newline="\n")

report = Path("v27-patch-report.txt")
report.write_text("\n".join([
    "V27_DESCRIPTOR_SCAFFOLD_RUNTIME_PATCH_OK",
    "V27_ELEVEN_PROBE_HARNESS_PASS",
    "TARGET_SUBOBJECT_COUNT=28",
    "CONTROL_CHILD_ORIGINAL=ENABLED",
    "CONTROL_CHILD_FULL_CLONED=ENABLED",
    "CHILD_DESCRIPTOR_REDUCTION=ENABLED",
    "MISS_SCAFFOLD_ADDBACK=ENABLED",
    "PHYSICAL_MISS_DXIL_SHA256=74beb66ae9bf76a02a15bed31ecf308c4d966bb0409f4c508d5c2cfdcec38191",
    "PROBE_OBJECT_TYPE=COLLECTION",
    "DIAGNOSTIC_OBJECT_RELEASE=PASS",
    "FINAL_ORIGINAL_CALL_EXACTLY_ONCE=PASS",
    "FAKE_SUCCESS=DISABLED",
    "V27_GATE_BEFORE_V26_GATE=PASS",
    "V26_GATE_BEFORE_V25_GATE=PASS",
    "V25_GATE_BEFORE_V24_GATE=PASS",
    "",
]), encoding="utf-8", newline="\n")
print(report.read_text(encoding="utf-8"))
