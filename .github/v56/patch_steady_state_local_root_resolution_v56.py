from pathlib import Path

SOURCE = Path("source/d3d12/d3d12.cpp")
if not SOURCE.is_file():
    raise RuntimeError(f"Missing source file: {SOURCE}")

text = SOURCE.read_text(encoding="utf-8-sig")
for required in (
    "D3DMetal RTX ray-hit pattern inheritance census v54:",
    "D3DMetal RTX live dispatch readback v38:",
    "D3DMetal RTX live shader-table readback v39:",
    "D3DMetal RTX raygen local-root descriptor resolution v55:",
):
    if required not in text:
        raise RuntimeError(f"V56 prerequisite is missing: {required}")
if "D3DMetal RTX steady-state local-root resolution v56:" in text:
    raise RuntimeError("V56 is already present")

def replace_once(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 occurrence, found {count}")
    return source.replace(old, new, 1)

helper_anchor = "\tvoid v38_try_capture_dispatch_record(\n"
if text.count(helper_anchor) != 1:
    raise RuntimeError(f"V56 helper anchor mismatch: {text.count(helper_anchor)}")

helper = r'''
	bool v56_steady_state_pipeline_candidate(
		ID3D12GraphicsCommandList *command_list,
		uint64_t &pipeline_id,
		uint64_t &pipeline_ray_index)
	{
		pipeline_id = 0;
		pipeline_ray_index = 0;
		if (command_list == nullptr)
			return false;

		pipeline_id = v54_lookup_bound_pipeline(
			reinterpret_cast<ID3D12GraphicsCommandList4 *>(command_list));
		if (pipeline_id == 0)
			return false;

		v54_pipeline_info snapshot = {};
		{
			std::lock_guard<std::mutex> lock(s_v54_pipeline_mutex);
			const auto found = s_v54_pipeline_infos.find(pipeline_id);
			if (found == s_v54_pipeline_infos.end())
				return false;
			snapshot = found->second;
		}

		pipeline_ray_index = snapshot.indirect_ray_count;
		if (snapshot.rewritten || pipeline_ray_index < 512 ||
			!snapshot.execute_present || !snapshot.miss_present)
			return false;

		bool identifiers_match = false;
		{
			std::lock_guard<std::mutex> lock(s_v54_baseline_mutex);
			identifiers_match =
				s_v54_baseline_ready &&
				memcmp(
					snapshot.execute_hex,
					s_v54_baseline_execute_hex,
					sizeof(snapshot.execute_hex)) == 0 &&
				memcmp(
					snapshot.miss_hex,
					s_v54_baseline_miss_hex,
					sizeof(snapshot.miss_hex)) == 0;
		}
		if (!identifiers_match)
			return false;

		static std::once_flag active_once;
		std::call_once(
			active_once,
			[pipeline_id, pipeline_ray_index]()
			{
				reshade::log::message(
					reshade::log::level::info,
					"D3DMetal RTX steady-state local-root resolution v56: CANDIDATE_READY pipeline_id=%llu pipeline_ray_index=%llu minimum_pipeline_rays=512 execute_and_miss_match_pattern=1 rewritten=0 capture_scope=dominant-inherited-steady-state.",
					static_cast<unsigned long long>(pipeline_id),
					static_cast<unsigned long long>(pipeline_ray_index));
			});
		return true;
	}

'''
helper = helper.replace(r"\t", "\t")
text = text.replace(helper_anchor, helper + helper_anchor, 1)

old_v38_gate = (
    "\t\tif (!dispatch_rays || !rewritten || command_list == nullptr ||\n"
    "\t\t\targument_buffer == nullptr || rewritten_ray_index == 0)\n"
    "\t\t\treturn;\n\n"
)
new_v38_gate = (
    "\t\tuint64_t v56_pipeline_id = 0;\n"
    "\t\tuint64_t v56_pipeline_ray_index = 0;\n"
    "\t\tif (!dispatch_rays || command_list == nullptr ||\n"
    "\t\t\targument_buffer == nullptr ||\n"
    "\t\t\t!v56_steady_state_pipeline_candidate(\n"
    "\t\t\t\tcommand_list,\n"
    "\t\t\t\tv56_pipeline_id,\n"
    "\t\t\t\tv56_pipeline_ray_index))\n"
    "\t\t\treturn;\n\n"
)
text = replace_once(text, old_v38_gate, new_v38_gate, "V56 V38 steady-state gate")

old_v38_call = (
    "\t\tv38_try_capture_dispatch_record(\n"
    "\t\t\tcommand_list,\n"
    "\t\t\targument_buffer,\n"
    "\t\t\targument_buffer_offset,\n"
    "\t\t\tdispatch_rays,\n"
    "\t\t\trewritten,\n"
    "\t\t\tstate_call,\n"
    "\t\t\trewritten_ray_index);\n\n"
)
new_v38_call = (
    "\t\tv38_try_capture_dispatch_record(\n"
    "\t\t\tcommand_list,\n"
    "\t\t\targument_buffer,\n"
    "\t\t\targument_buffer_offset,\n"
    "\t\t\tdispatch_rays,\n"
    "\t\t\trewritten,\n"
    "\t\t\tstate_call,\n"
    "\t\t\tray_index);\n\n"
)
text = replace_once(text, old_v38_call, new_v38_call, "V56 V38 global ray index")

old_v39_gate = (
    "        if (!dispatch_rays || !rewritten || command_list == nullptr || rewritten_ray_index < 2)\n"
    "            return;\n"
)
new_v39_gate = (
    "        uint64_t v56_pipeline_id = 0;\n"
    "        uint64_t v56_pipeline_ray_index = 0;\n"
    "        if (!dispatch_rays || command_list == nullptr ||\n"
    "            !v56_steady_state_pipeline_candidate(\n"
    "                command_list,\n"
    "                v56_pipeline_id,\n"
    "                v56_pipeline_ray_index))\n"
    "            return;\n"
)
text = replace_once(text, old_v39_gate, new_v39_gate, "V56 V39 steady-state gate")

old_v39_call = (
    "\t\tv39_try_capture_shader_tables(\n"
    "\t\t\tcommand_list,\n"
    "\t\t\tdispatch_rays,\n"
    "\t\t\trewritten,\n"
    "\t\t\tstate_call,\n"
    "\t\t\trewritten_ray_index);\n\n"
)
new_v39_call = (
    "\t\tv39_try_capture_shader_tables(\n"
    "\t\t\tcommand_list,\n"
    "\t\t\tdispatch_rays,\n"
    "\t\t\trewritten,\n"
    "\t\t\tstate_call,\n"
    "\t\t\tray_index);\n\n"
)
text = replace_once(text, old_v39_call, new_v39_call, "V56 V39 global ray index")

old_result = (
    '"D3DMetal RTX raygen local-root descriptor resolution v55: '
    'LOCAL_ROOT_DESCRIPTOR_RESOLUTION_RESULT success=1 '
    'srv_resolved=%u/8 cbv_resolved=%u/1 uav_resolved=%u/2 '
    'u1_contract_match=%u descriptor_events=%llu descriptor_copy_events=%llu '
    'diagnosis=%s commands_modified=0."'
)
new_result = (
    '"D3DMetal RTX raygen local-root descriptor resolution v55: '
    'LOCAL_ROOT_DESCRIPTOR_RESOLUTION_RESULT success=1 '
    'srv_resolved=%u/8 cbv_resolved=%u/1 uav_resolved=%u/2 '
    'u1_contract_match=%u descriptor_events=%llu descriptor_copy_events=%llu '
    'diagnosis=%s commands_modified=0 capture_scope=v56-steady-state-inherited-pipeline."'
)
text = replace_once(text, old_result, new_result, "V56 result scope marker")

required_markers = [
    "D3DMetal RTX steady-state local-root resolution v56: CANDIDATE_READY",
    "minimum_pipeline_rays=512",
    "capture_scope=dominant-inherited-steady-state",
    "capture_scope=v56-steady-state-inherited-pipeline",
    "v56_steady_state_pipeline_candidate(",
]
for marker in required_markers:
    if marker not in text:
        raise RuntimeError(f"Missing V56 source marker: {marker}")

if text.count("v56_steady_state_pipeline_candidate(") != 3:
    raise RuntimeError(
        "V56 candidate helper definition/call count is not exactly three")

SOURCE.write_text(text, encoding="utf-8", newline="\n")

report = Path("v56-patch-report.txt")
report.write_text(
    "\n".join([
        "V56_STEADY_STATE_LOCAL_ROOT_RESOLUTION_PATCH_OK",
        "BASELINE=V55_ONE_SHOT_LOCAL_ROOT_RESOLVER",
        "DIRECT_REWRITTEN_BASE_PIPELINE_CAPTURE=DISABLED",
        "INHERITED_PIPELINE_REQUIRED=YES",
        "PATTERN_EXECUTETRACE_MATCH_REQUIRED=YES",
        "PATTERN_MISS_MATCH_REQUIRED=YES",
        "MINIMUM_PER_PIPELINE_INDIRECT_RAYS=512",
        "GLOBAL_INDIRECT_RAY_INDEX_FORWARDING=ENABLED",
        "V38_ARGUMENT_READBACK=STEADY_STATE_PIPELINE",
        "V39_SHADER_TABLE_READBACK=STEADY_STATE_PIPELINE",
        "V55_DESCRIPTOR_RESOLUTION=STEADY_STATE_PIPELINE",
        "SHADERS_MODIFIED_BY_V56=NO",
        "DESCRIPTORS_MODIFIED_BY_V56=NO",
        "RESOURCES_MODIFIED_BY_V56=NO",
        "DISPATCH_ARGUMENTS_MODIFIED_BY_V56=NO",
        "RESULT=PASS",
        "",
    ]),
    encoding="utf-8",
    newline="\n",
)
print(report.read_text(encoding="utf-8"))
