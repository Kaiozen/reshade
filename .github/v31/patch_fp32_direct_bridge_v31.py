from pathlib import Path

SOURCE = Path("source/d3d12/d3d12.cpp")
if not SOURCE.is_file():
    raise RuntimeError(f"Missing source file: {SOURCE}")

text = SOURCE.read_text(encoding="utf-8-sig")
if "D3DMetal RTX FP64 elision diagnostic v30:" not in text:
    raise RuntimeError("V30 must be applied before V31")
if "D3DMetal RTX FP32 direct bridge v31:" in text:
    raise RuntimeError("V31 is already present")

signature = "\tHRESULT STDMETHODCALLTYPE trace_create_state_object(\n"
if text.count(signature) != 1:
    raise RuntimeError(f"V31 trace signature mismatch: {text.count(signature)}")

helper = r'''
	static std::atomic<unsigned int> s_v31_rewrite_attempts = 0;
	static std::atomic<unsigned int> s_v31_rewrite_successes = 0;
	static std::atomic<unsigned int> s_v31_rewrite_fallbacks = 0;

	bool try_v31_fp32_direct_bridge(
		ID3D12Device5 *device,
		uint64_t call_id,
		const D3D12_STATE_OBJECT_DESC *original_desc,
		const D3D12_STATE_OBJECT_DESC &snapshot,
		REFIID riid,
		void **state_object,
		HRESULT &result)
	{
		if (original_desc == nullptr || state_object == nullptr ||
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

		const unsigned int attempt = ++s_v31_rewrite_attempts;
		v30_full_replacement_storage storage;
		D3D12_STATE_OBJECT_DESC replacement_desc = {};
		if (!v30_build_full_replacement(
			snapshot, parent_source, parent_library,
			g_v30_execute_plus_miss_fp32_dxil,
			sizeof(g_v30_execute_plus_miss_fp32_dxil),
			storage, replacement_desc))
		{
			reshade::log::message(
				reshade::log::level::warning,
				"D3DMetal RTX FP32 direct bridge v31: BUILD_FAILED call=%llu attempt=%u; passing untouched descriptor to D3DMetal.",
				static_cast<unsigned long long>(call_id), attempt);
			*state_object = nullptr;
			result = s_original_create_state_object(device, original_desc, riid, state_object);
			++s_v31_rewrite_fallbacks;
			return true;
		}

		void *replacement_object = nullptr;
		const HRESULT replacement_hr = s_original_create_state_object(
			device, &replacement_desc, riid, &replacement_object);

		HRESULT properties_hr = E_NOINTERFACE;
		bool execute_present = false;
		bool miss_present = false;
		if (SUCCEEDED(replacement_hr) && replacement_object != nullptr)
		{
			ID3D12StateObjectProperties *properties = nullptr;
			properties_hr = reinterpret_cast<IUnknown *>(replacement_object)->QueryInterface(
				__uuidof(ID3D12StateObjectProperties),
				reinterpret_cast<void **>(&properties));
			if (SUCCEEDED(properties_hr) && properties != nullptr)
			{
				execute_present = properties->GetShaderIdentifier(L"ExecuteTrace") != nullptr;
				miss_present = properties->GetShaderIdentifier(L"Miss") != nullptr;
				properties->Release();
			}
		}

		if (SUCCEEDED(replacement_hr) && replacement_object != nullptr &&
			SUCCEEDED(properties_hr) && execute_present && miss_present)
		{
			*state_object = replacement_object;
			result = replacement_hr;
			const unsigned int success = ++s_v31_rewrite_successes;
			reshade::log::message(
				reshade::log::level::info,
				"D3DMetal RTX FP32 direct bridge v31: DIRECT_REWRITE call=%llu attempt=%u success=%u hr=%s raw=0x%08X object=%p subobjects=%u module_size=%llu execute=1 miss=1 returned_to_game=1 original_skipped=1.",
				static_cast<unsigned long long>(call_id), attempt, success,
				reshade::log::hr_to_string(result).c_str(), static_cast<uint32_t>(result),
				replacement_object, replacement_desc.NumSubobjects,
				static_cast<unsigned long long>(sizeof(g_v30_execute_plus_miss_fp32_dxil)));
			return true;
		}

		if (replacement_object != nullptr)
			reinterpret_cast<IUnknown *>(replacement_object)->Release();

		reshade::log::message(
			reshade::log::level::warning,
			"D3DMetal RTX FP32 direct bridge v31: REWRITE_REJECTED call=%llu attempt=%u hr=%s raw=0x%08X properties_hr=%s execute=%u miss=%u; passing untouched descriptor to D3DMetal.",
			static_cast<unsigned long long>(call_id), attempt,
			reshade::log::hr_to_string(replacement_hr).c_str(), static_cast<uint32_t>(replacement_hr),
			reshade::log::hr_to_string(properties_hr).c_str(),
			execute_present ? 1u : 0u, miss_present ? 1u : 0u);

		*state_object = nullptr;
		result = s_original_create_state_object(device, original_desc, riid, state_object);
		const unsigned int fallback = ++s_v31_rewrite_fallbacks;
		reshade::log::message(
			FAILED(result) ? reshade::log::level::warning : reshade::log::level::info,
			"D3DMetal RTX FP32 direct bridge v31: FALLBACK_RESULT call=%llu fallback=%u hr=%s raw=0x%08X.",
			static_cast<unsigned long long>(call_id), fallback,
			reshade::log::hr_to_string(result).c_str(), static_cast<uint32_t>(result));
		return true;
	}
'''

text = text.replace(signature, helper + "\n\n" + signature, 1)
trace_position = text.find(signature)
gate_anchor = (
    "\t\tD3D12_STATE_OBJECT_DESC snapshot = {};\n"
    "\t\tconst bool readable = safe_copy_from_process(desc, &snapshot, sizeof(snapshot));\n"
)
gate_position = text.find(gate_anchor, trace_position)
if gate_position < 0:
    raise RuntimeError("V31 gate anchor not found")
insert_position = gate_position + len(gate_anchor)

gate = r'''

		if (readable)
		{
			HRESULT v31_result = E_FAIL;
			if (try_v31_fp32_direct_bridge(
				device, call_id, desc, snapshot, riid, state_object, v31_result))
			{
				return v31_result;
			}
		}
'''
text = text[:insert_position] + gate + text[insert_position:]

required = [
    "D3DMetal RTX FP32 direct bridge v31:",
    "try_v31_fp32_direct_bridge(",
    "DIRECT_REWRITE call=",
    "returned_to_game=1 original_skipped=1",
    "REWRITE_REJECTED call=",
    "FALLBACK_RESULT call=",
    "g_v30_execute_plus_miss_fp32_dxil",
    "v30_build_full_replacement(",
]
for marker in required:
    if marker not in text:
        raise RuntimeError(f"Missing V31 source marker: {marker}")

v31 = text.find("if (try_v31_fp32_direct_bridge(", trace_position)
v30 = text.find("if (try_v30_fp64_elision_diagnostic(", trace_position)
v29 = text.find("if (try_v29_raygen_intrinsic_ladder_diagnostic(", trace_position)
if not (v31 >= 0 and v30 > v31 and v29 > v30):
    raise RuntimeError("V31 gate was not inserted before V30 and V29")

SOURCE.write_text(text, encoding="utf-8", newline="\n")
report = Path("v31-patch-report.txt")
report.write_text(
    "\n".join([
        "V31_FP32_DIRECT_BRIDGE_PATCH_OK",
        "EXACT_PARENT_MATCH=26964_BYTE_SHA256_02d3db46...",
        "REPLACEMENT=MICROSOFT_VALIDATED_V30_COMBINED_FP32_DXIL",
        "FULL_28_SUBOBJECT_DESCRIPTOR_CLONE=ENABLED",
        "ASSOCIATION_REMAP=ENABLED",
        "RETURN_ACCEPTED_OBJECT_TO_GAME=ENABLED",
        "REQUIRE_EXECUTETRACE_SHADER_IDENTIFIER=ENABLED",
        "REQUIRE_MISS_SHADER_IDENTIFIER=ENABLED",
        "ORIGINAL_CALL_SKIPPED_ON_REWRITE_SUCCESS=ENABLED",
        "REAL_FAILURE_FALLBACK_TO_UNTOUCHED_ORIGINAL=ENABLED",
        "FAKE_SUCCESS=DISABLED",
        "V31_GATE_BEFORE_V30_GATE=PASS",
        "RESULT=PASS",
        "",
    ]),
    encoding="utf-8",
    newline="\n",
)
print(report.read_text(encoding="utf-8"))
