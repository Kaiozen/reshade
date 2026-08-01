from pathlib import Path

SOURCE = Path("source/d3d12/d3d12.cpp")
if not SOURCE.is_file():
    raise RuntimeError(f"Missing source file: {SOURCE}")

text = SOURCE.read_text(encoding="utf-8-sig")
for required in (
    "D3DMetal RTX ray-dispatch suppression control v44:",
    "D3DMetal RTX RT-state bind suppression control v45:",
    "D3DMetal RTX non-RT PSO census v46:",
):
    if required not in text:
        raise RuntimeError(f"V47 prerequisite is missing: {required}")
if "D3DMetal RTX RTX-exclusive compute suppression control v47:" in text:
    raise RuntimeError("V47 is already present")


def replace_once(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 occurrence, found {count}")
    return source.replace(old, new, 1)

# V34 and V46 command hooks occur before the V47 helper definition, so provide
# a forward declaration before V34's helper block.
forward_anchor = "\tusing v34_create_command_signature_fn = HRESULT (STDMETHODCALLTYPE *)(\n"
forward_insert = (
    "\tbool v47_lookup_target_compute(\n"
    "\t\tID3D12GraphicsCommandList *command_list,\n"
    "\t\tuint64_t &pso_id,\n"
    "\t\tuint64_t &shader_hash);\n"
    "\tvoid v47_log_active();\n\n"
)
text = replace_once(
    text,
    forward_anchor,
    forward_insert + forward_anchor,
    "V47 forward declaration",
)

helper_anchor = "\tvoid v33_install_command_list_method_hooks(IUnknown *command_list)\n"
if text.count(helper_anchor) != 1:
    raise RuntimeError(
        f"V47 helper anchor mismatch: {text.count(helper_anchor)}")

helper = r'''
	static std::atomic<uint64_t> s_v47_target_bind_count = 0;
	static std::atomic<uint64_t> s_v47_suppressed_direct_count = 0;
	static std::atomic<uint64_t> s_v47_suppressed_indirect_count = 0;
	static std::once_flag s_v47_active_log_once;

	bool v47_target_compute_hash(uint64_t shader_hash)
	{
		switch (shader_hash)
		{
		case 0xAAEF5BBACE7B3389ull:
		case 0xED8F27C1DCF85335ull:
		case 0x677591823B878F82ull:
		case 0xE4B0352F678C6F33ull:
		case 0x4ACBBFEFB0FFA3F3ull:
		case 0xED5C7961A010E8BBull:
		case 0x1C780AC73E753801ull:
		case 0x975729DFC30E842Bull:
		case 0x9575B9C16468BF21ull:
		case 0x9FF035409F9DADE4ull:
		case 0x12036DDCB8E19000ull:
		case 0x01B70FC0C54CD4A0ull:
		case 0x37FBFE80266BEA74ull:
		case 0xC1127EEEADA2E727ull:
			return true;
		default:
			return false;
		}
	}

	bool v47_lookup_target_compute(
		ID3D12GraphicsCommandList *command_list,
		uint64_t &pso_id,
		uint64_t &shader_hash)
	{
		pso_id = v46_lookup_bound_pso(command_list);
		shader_hash = 0;
		if (pso_id == 0)
			return false;

		std::lock_guard<std::mutex> lock(s_v46_mutex);
		const auto found = s_v46_infos.find(pso_id);
		if (found == s_v46_infos.end())
			return false;
		const auto &info = found->second;
		if (info.metadata.kind != 2)
			return false;
		shader_hash = info.metadata.cs_hash != 0 ?
			info.metadata.cs_hash : info.metadata.shader_hash;
		return v47_target_compute_hash(shader_hash);
	}

	void v47_log_active()
	{
		std::call_once(
			s_v47_active_log_once,
			[]()
			{
				reshade::log::message(
					reshade::log::level::info,
					"D3DMetal RTX RTX-exclusive compute suppression control v47: ACTIVE target-hash-count=14 direct-target-dispatch-suppressed=1 indirect-target-dispatch-suppressed=1 ordinary-compute-preserved=1 graphics-preserved=1 rt-bind-and-ray-suppression-preserved=1.");
			});
	}

	void v47_record_target_bind(
		ID3D12GraphicsCommandList *command_list)
	{
		if (!v46_post_phase())
			return;
		uint64_t pso_id = 0;
		uint64_t shader_hash = 0;
		if (!v47_lookup_target_compute(
				command_list, pso_id, shader_hash))
			return;
		v47_log_active();
		const uint64_t index = ++s_v47_target_bind_count;
		if (index <= 8 || (index % 256ull) == 0)
		{
			reshade::log::message(
				reshade::log::level::info,
				"D3DMetal RTX RTX-exclusive compute suppression control v47: TARGET_BIND target_bind_index=%llu pso_id=%llu shader_hash=0x%llX command_list=%p.",
				static_cast<unsigned long long>(index),
				static_cast<unsigned long long>(pso_id),
				static_cast<unsigned long long>(shader_hash),
				command_list);
		}
	}

	bool v47_suppress_direct_target_compute(
		ID3D12GraphicsCommandList *command_list,
		UINT x, UINT y, UINT z)
	{
		if (!v46_post_phase())
			return false;
		uint64_t pso_id = 0;
		uint64_t shader_hash = 0;
		if (!v47_lookup_target_compute(
				command_list, pso_id, shader_hash))
			return false;
		v47_log_active();
		const uint64_t index = ++s_v47_suppressed_direct_count;
		reshade::log::message(
			reshade::log::level::info,
			"D3DMetal RTX RTX-exclusive compute suppression control v47: SUPPRESS_DIRECT target_direct_index=%llu pso_id=%llu shader_hash=0x%llX command_list=%p groups=%ux%ux%u.",
			static_cast<unsigned long long>(index),
			static_cast<unsigned long long>(pso_id),
			static_cast<unsigned long long>(shader_hash),
			command_list, x, y, z);
		return true;
	}

	bool v47_suppress_indirect_target_compute(
		ID3D12GraphicsCommandList *command_list,
		UINT max_command_count,
		ID3D12Resource *argument_buffer,
		UINT64 argument_buffer_offset)
	{
		if (!v46_post_phase())
			return false;
		uint64_t pso_id = 0;
		uint64_t shader_hash = 0;
		if (!v47_lookup_target_compute(
				command_list, pso_id, shader_hash))
			return false;
		v47_log_active();
		const uint64_t index = ++s_v47_suppressed_indirect_count;
		reshade::log::message(
			reshade::log::level::info,
			"D3DMetal RTX RTX-exclusive compute suppression control v47: SUPPRESS_INDIRECT target_indirect_index=%llu pso_id=%llu shader_hash=0x%llX command_list=%p max_count=%u argument_buffer=%p argument_offset=%llu.",
			static_cast<unsigned long long>(index),
			static_cast<unsigned long long>(pso_id),
			static_cast<unsigned long long>(shader_hash),
			command_list,
			max_command_count,
			argument_buffer,
			static_cast<unsigned long long>(argument_buffer_offset));
		return true;
	}
'''
text = text.replace(helper_anchor, helper + "\n" + helper_anchor, 1)

# Record target bindings after V46 has updated the currently-bound PSO map.
set_pso_anchor = (
    "\t\tv46_bind_pso(command_list, pipeline_state, \"set-pso\");\n"
    "\t\tif (s_v46_original_set_pipeline_state != nullptr)\n"
)
set_pso_replacement = (
    "\t\tv46_bind_pso(command_list, pipeline_state, \"set-pso\");\n"
    "\t\tv47_record_target_bind(command_list);\n"
    "\t\tif (s_v46_original_set_pipeline_state != nullptr)\n"
)
text = replace_once(
    text, set_pso_anchor, set_pso_replacement,
    "V47 target bind observation")

# Direct dispatches from V46's RTX-exclusive compute hashes are not forwarded.
direct_anchor = (
    "\t\tv46_record_command(command_list, 1, 1, \"dispatch\");\n"
    "\t\tif (s_v46_original_dispatch != nullptr)\n"
)
direct_replacement = (
    "\t\tv46_record_command(command_list, 1, 1, \"dispatch\");\n"
    "\t\tif (v47_suppress_direct_target_compute(\n"
    "\t\t\t\tcommand_list, x, y, z))\n"
    "\t\t\treturn;\n"
    "\t\tif (s_v46_original_dispatch != nullptr)\n"
)
text = replace_once(
    text, direct_anchor, direct_replacement,
    "V47 direct compute suppression")

# V44 already returns for DISPATCH_RAYS. Suppress only ordinary indirect
# DISPATCH when one of the V46 RTX-exclusive compute PSOs is currently bound.
indirect_anchor = (
    "\t\tif (s_v34_original_execute_indirect != nullptr)\n"
    "\t\t\ts_v34_original_execute_indirect(\n"
)
indirect_replacement = (
    "\t\tif (tracked_signature && !dispatch_rays &&\n"
    "\t\t\t(signature_info.type_mask & 0x4ull) != 0 &&\n"
    "\t\t\tv47_suppress_indirect_target_compute(\n"
    "\t\t\t\tcommand_list,\n"
    "\t\t\t\tmax_command_count,\n"
    "\t\t\t\targument_buffer,\n"
    "\t\t\t\targument_buffer_offset))\n"
    "\t\t\treturn;\n\n"
    "\t\tif (s_v34_original_execute_indirect != nullptr)\n"
    "\t\t\ts_v34_original_execute_indirect(\n"
)
text = replace_once(
    text, indirect_anchor, indirect_replacement,
    "V47 indirect compute suppression")

# V46's original sampling interval generated a 500+ MB diagnostic. Keep the
# census active but reduce repeated snapshot logging without changing commands.
text = replace_once(
    text,
    "(info.post_binds % 240ull) == 0;",
    "(info.post_binds % 2048ull) == 0;",
    "V47 bind snapshot throttle",
)
text = replace_once(
    text,
    "(post_total % 120ull) < count);",
    "(post_total % 2048ull) < count);",
    "V47 command snapshot throttle",
)

required_markers = [
    "D3DMetal RTX RTX-exclusive compute suppression control v47: ACTIVE",
    "TARGET_BIND target_bind_index=",
    "SUPPRESS_DIRECT target_direct_index=",
    "SUPPRESS_INDIRECT target_indirect_index=",
    "target-hash-count=14",
    "ordinary-compute-preserved=1",
    "graphics-preserved=1",
    "rt-bind-and-ray-suppression-preserved=1",
    "v47_record_target_bind(command_list);",
    "v47_suppress_direct_target_compute(",
    "v47_suppress_indirect_target_compute(",
]
for marker in required_markers:
    if marker not in text:
        raise RuntimeError(f"Missing V47 source marker: {marker}")

for forbidden in (
    "\\tstatic std::atomic<uint64_t> s_v47",
    "\\tbool v47_target_compute_hash",
    "\\t\\tif (v47_suppress_direct_target_compute",
):
    if forbidden in text:
        raise RuntimeError(
            f"V47 emitted a literal tab escape into C++ source: {forbidden}")

if text.count("s_v46_original_dispatch(command_list, x, y, z);") != 1:
    raise RuntimeError(
        "V47 expected one ordinary direct-dispatch forwarding call")
if text.count("s_v34_original_execute_indirect(") != 1:
    raise RuntimeError(
        "V47 expected one ordinary non-target ExecuteIndirect forwarding call")

SOURCE.write_text(text, encoding="utf-8", newline="\n")

report = Path("v47-patch-report.txt")
report.write_text("\n".join([
    "V47_RTX_EXCLUSIVE_COMPUTE_SUPPRESSION_CONTROL_PATCH_OK",
    "V46_POST_ONLY_COMPUTE_HASH_SET_COUNT=14",
    "V46_STEADY_PER_FRAME_COMPUTE_HASH_COUNT=10",
    "V46_ONE_SHOT_COMPUTE_HASH_COUNT=4",
    "TARGET_DIRECT_DISPATCH_SUPPRESSION=ENABLED",
    "TARGET_INDIRECT_DISPATCH_SUPPRESSION=ENABLED",
    "TARGET_COMPUTE_BINDING_PRESERVED=YES",
    "ORDINARY_COMPUTE_DISPATCH_PRESERVED=YES",
    "ALL_GRAPHICS_DRAWS_PRESERVED=YES",
    "V45_RT_BIND_SUPPRESSION_PRESERVED=YES",
    "V44_RAY_DISPATCH_SUPPRESSION_PRESERVED=YES",
    "V46_CENSUS_PRESERVED_WITH_REDUCED_LOG_FREQUENCY=YES",
    "SHADER_BYTES_MODIFIED_BY_V47=NO",
    "DESCRIPTORS_MODIFIED_BY_V47=NO",
    "RESOURCES_MODIFIED_BY_V47=NO",
    "LITERAL_TAB_ESCAPES_IN_CPP=NO",
    "CONTROL_FLOW_CHANGE=SKIP_V46_RTX_EXCLUSIVE_COMPUTE_DISPATCHES",
    "RESULT=PASS",
    "",
]), encoding="utf-8", newline="\n")
print(report.read_text(encoding="utf-8"))
