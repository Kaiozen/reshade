from pathlib import Path

SOURCE = Path("source/d3d12/d3d12.cpp")
if not SOURCE.is_file():
    raise RuntimeError(f"Missing source file: {SOURCE}")

text = SOURCE.read_text(encoding="utf-8-sig")
for required in (
    "D3DMetal RTX RTX-exclusive compute suppression control v47:",
    "D3DMetal RTX non-RT PSO census v46:",
    "D3DMetal RTX RT-state bind suppression control v45:",
    "D3DMetal RTX ray-dispatch suppression control v44:",
):
    if required not in text:
        raise RuntimeError(f"V48 prerequisite is missing: {required}")
if "D3DMetal RTX stable post-RTX graphics suppression control v48:" in text:
    raise RuntimeError("V48 is already present")


def replace_once(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 occurrence, found {count}")
    return source.replace(old, new, 1)


forward_anchor = "\tvoid STDMETHODCALLTYPE v46_trace_set_pipeline_state(\n"
forward_insert = (
    "\tbool v48_lookup_target_graphics(\n"
    "\t\tID3D12GraphicsCommandList *command_list,\n"
    "\t\tuint64_t &pso_id,\n"
    "\t\tuint64_t &shader_hash);\n"
    "\tvoid v48_log_active();\n"
    "\tvoid v48_record_target_bind(\n"
    "\t\tID3D12GraphicsCommandList *command_list);\n"
    "\tbool v48_suppress_direct_draw(\n"
    "\t\tID3D12GraphicsCommandList *command_list,\n"
    "\t\tbool indexed,\n"
    "\t\tUINT element_count,\n"
    "\t\tUINT instance_count);\n"
    "\tbool v48_suppress_indirect_graphics(\n"
    "\t\tID3D12GraphicsCommandList *command_list,\n"
    "\t\tuint64_t type_mask,\n"
    "\t\tUINT max_command_count,\n"
    "\t\tID3D12Resource *argument_buffer,\n"
    "\t\tUINT64 argument_buffer_offset);\n\n"
)
text = replace_once(
    text,
    forward_anchor,
    forward_insert + forward_anchor,
    "V48 forward declaration",
)

helper_anchor = "\tvoid v33_install_command_list_method_hooks(IUnknown *command_list)\n"
if text.count(helper_anchor) != 1:
    raise RuntimeError(
        f"V48 helper anchor mismatch: {text.count(helper_anchor)}")

helper = r'''
	static std::atomic<uint64_t> s_v48_target_bind_count = 0;
	static std::atomic<uint64_t> s_v48_suppressed_draw_count = 0;
	static std::atomic<uint64_t> s_v48_suppressed_draw_indexed_count = 0;
	static std::atomic<uint64_t> s_v48_suppressed_indirect_count = 0;
	static std::once_flag s_v48_active_log_once;

	bool v48_target_graphics_hash(uint64_t shader_hash)
	{
		switch (shader_hash)
		{
		case 0x15CD7A2678DF6413ull:
		case 0x24CE5C897C2540BAull:
		case 0x185B940AA75F00FDull:
		case 0xC13359D44B9A5DA5ull:
		case 0x11BFE4C6F894901Full:
		case 0xA108343B0831ADADull:
		case 0xC4424F5B47A0C0F1ull:
		case 0x12260282FDC53D5Aull:
		case 0x16F2ED356C1F29A4ull:
		case 0x6FF442A8B56CBDC4ull:
			return true;
		default:
			return false;
		}
	}

	bool v48_lookup_target_graphics(
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
		if (info.metadata.kind != 1)
			return false;
		shader_hash = info.metadata.shader_hash;
		return v48_target_graphics_hash(shader_hash);
	}

	void v48_log_active()
	{
		std::call_once(
			s_v48_active_log_once,
			[]()
			{
				reshade::log::message(
					reshade::log::level::info,
					"D3DMetal RTX stable post-RTX graphics suppression control v48: ACTIVE target-hash-count=10 direct-draw-suppressed=1 direct-indexed-draw-suppressed=1 indirect-graphics-suppressed=1 ordinary-graphics-preserved=1 v47-compute-suppression-preserved=1 rt-bind-and-ray-suppression-preserved=1.");
			});
	}

	void v48_record_target_bind(
		ID3D12GraphicsCommandList *command_list)
	{
		if (!v46_post_phase())
			return;
		uint64_t pso_id = 0;
		uint64_t shader_hash = 0;
		if (!v48_lookup_target_graphics(command_list, pso_id, shader_hash))
			return;
		v48_log_active();
		const uint64_t index = ++s_v48_target_bind_count;
		if (index <= 10 || (index % 256ull) == 0)
		{
			reshade::log::message(
				reshade::log::level::info,
				"D3DMetal RTX stable post-RTX graphics suppression control v48: TARGET_BIND target_bind_index=%llu pso_id=%llu shader_hash=0x%llX command_list=%p.",
				static_cast<unsigned long long>(index),
				static_cast<unsigned long long>(pso_id),
				static_cast<unsigned long long>(shader_hash),
				command_list);
		}
	}

	bool v48_suppress_direct_draw(
		ID3D12GraphicsCommandList *command_list,
		bool indexed,
		UINT element_count,
		UINT instance_count)
	{
		if (!v46_post_phase())
			return false;
		uint64_t pso_id = 0;
		uint64_t shader_hash = 0;
		if (!v48_lookup_target_graphics(command_list, pso_id, shader_hash))
			return false;
		v48_log_active();
		const uint64_t index = indexed ?
			++s_v48_suppressed_draw_indexed_count :
			++s_v48_suppressed_draw_count;
		if (index <= 16 || (index % 256ull) == 0)
		{
			reshade::log::message(
				reshade::log::level::info,
				indexed ?
					"D3DMetal RTX stable post-RTX graphics suppression control v48: SUPPRESS_DRAW_INDEXED target_indexed_index=%llu pso_id=%llu shader_hash=0x%llX command_list=%p elements=%u instances=%u." :
					"D3DMetal RTX stable post-RTX graphics suppression control v48: SUPPRESS_DRAW target_draw_index=%llu pso_id=%llu shader_hash=0x%llX command_list=%p elements=%u instances=%u.",
				static_cast<unsigned long long>(index),
				static_cast<unsigned long long>(pso_id),
				static_cast<unsigned long long>(shader_hash),
				command_list,
				element_count,
				instance_count);
		}
		return true;
	}

	bool v48_suppress_indirect_graphics(
		ID3D12GraphicsCommandList *command_list,
		uint64_t type_mask,
		UINT max_command_count,
		ID3D12Resource *argument_buffer,
		UINT64 argument_buffer_offset)
	{
		if (!v46_post_phase())
			return false;
		if ((type_mask & (0x1ull | 0x2ull | 0x400ull)) == 0)
			return false;
		uint64_t pso_id = 0;
		uint64_t shader_hash = 0;
		if (!v48_lookup_target_graphics(command_list, pso_id, shader_hash))
			return false;
		v48_log_active();
		const uint64_t index = ++s_v48_suppressed_indirect_count;
		if (index <= 16 || (index % 256ull) == 0)
		{
			reshade::log::message(
				reshade::log::level::info,
				"D3DMetal RTX stable post-RTX graphics suppression control v48: SUPPRESS_INDIRECT target_indirect_index=%llu pso_id=%llu shader_hash=0x%llX command_list=%p type_mask=0x%llX max_count=%u argument_buffer=%p argument_offset=%llu.",
				static_cast<unsigned long long>(index),
				static_cast<unsigned long long>(pso_id),
				static_cast<unsigned long long>(shader_hash),
				command_list,
				static_cast<unsigned long long>(type_mask),
				max_command_count,
				argument_buffer,
				static_cast<unsigned long long>(argument_buffer_offset));
		}
		return true;
	}
'''
text = text.replace(helper_anchor, helper + "\n" + helper_anchor, 1)

set_pso_anchor = (
    "\t\tv46_bind_pso(command_list, pipeline_state, \"set-pso\");\n"
    "\t\tv47_record_target_bind(command_list);\n"
    "\t\tif (s_v46_original_set_pipeline_state != nullptr)\n"
)
set_pso_replacement = (
    "\t\tv46_bind_pso(command_list, pipeline_state, \"set-pso\");\n"
    "\t\tv47_record_target_bind(command_list);\n"
    "\t\tv48_record_target_bind(command_list);\n"
    "\t\tif (s_v46_original_set_pipeline_state != nullptr)\n"
)
text = replace_once(
    text,
    set_pso_anchor,
    set_pso_replacement,
    "V48 target bind observation",
)

draw_anchor = (
    "\t\tv46_record_command(command_list, 2, 1, \"draw\");\n"
    "\t\tif (s_v46_original_draw_instanced != nullptr)\n"
)
draw_replacement = (
    "\t\tv46_record_command(command_list, 2, 1, \"draw\");\n"
    "\t\tif (v48_suppress_direct_draw(\n"
    "\t\t\t\tcommand_list, false, vertex_count, instance_count))\n"
    "\t\t\treturn;\n"
    "\t\tif (s_v46_original_draw_instanced != nullptr)\n"
)
text = replace_once(
    text,
    draw_anchor,
    draw_replacement,
    "V48 direct draw suppression",
)

indexed_anchor = (
    "\t\tv46_record_command(command_list, 3, 1, \"draw-indexed\");\n"
    "\t\tif (s_v46_original_draw_indexed_instanced != nullptr)\n"
)
indexed_replacement = (
    "\t\tv46_record_command(command_list, 3, 1, \"draw-indexed\");\n"
    "\t\tif (v48_suppress_direct_draw(\n"
    "\t\t\t\tcommand_list, true, index_count, instance_count))\n"
    "\t\t\treturn;\n"
    "\t\tif (s_v46_original_draw_indexed_instanced != nullptr)\n"
)
text = replace_once(
    text,
    indexed_anchor,
    indexed_replacement,
    "V48 indexed draw suppression",
)

indirect_anchor = (
    "\t\tif (tracked_signature && !dispatch_rays &&\n"
    "\t\t\t(signature_info.type_mask & 0x4ull) != 0 &&\n"
)
indirect_replacement = (
    "\t\tif (tracked_signature && !dispatch_rays &&\n"
    "\t\t\tv48_suppress_indirect_graphics(\n"
    "\t\t\t\tcommand_list,\n"
    "\t\t\t\tsignature_info.type_mask,\n"
    "\t\t\t\tmax_command_count,\n"
    "\t\t\t\targument_buffer,\n"
    "\t\t\t\targument_buffer_offset))\n"
    "\t\t\treturn;\n\n"
    "\t\tif (tracked_signature && !dispatch_rays &&\n"
    "\t\t\t(signature_info.type_mask & 0x4ull) != 0 &&\n"
)
text = replace_once(
    text,
    indirect_anchor,
    indirect_replacement,
    "V48 indirect graphics suppression",
)

required_markers = [
    "D3DMetal RTX stable post-RTX graphics suppression control v48: ACTIVE",
    "TARGET_BIND target_bind_index=",
    "SUPPRESS_DRAW target_draw_index=",
    "SUPPRESS_DRAW_INDEXED target_indexed_index=",
    "SUPPRESS_INDIRECT target_indirect_index=",
    "target-hash-count=10",
    "ordinary-graphics-preserved=1",
    "v47-compute-suppression-preserved=1",
    "v48_record_target_bind(command_list);",
    "v48_suppress_direct_draw(",
    "v48_suppress_indirect_graphics(",
]
for marker in required_markers:
    if marker not in text:
        raise RuntimeError(f"Missing V48 source marker: {marker}")

if text.count("s_v46_original_draw_instanced(") != 1:
    raise RuntimeError(
        "V48 expected one ordinary direct draw forwarding call")
if text.count("s_v46_original_draw_indexed_instanced(") != 1:
    raise RuntimeError(
        "V48 expected one ordinary indexed draw forwarding call")
if text.count("s_v34_original_execute_indirect(") != 1:
    raise RuntimeError(
        "V48 expected one ordinary ExecuteIndirect forwarding call")

for declaration, call in (
    ("void v48_record_target_bind(\n\t\tID3D12GraphicsCommandList *command_list);",
     "v48_record_target_bind(command_list);"),
    ("bool v48_suppress_direct_draw(\n\t\tID3D12GraphicsCommandList *command_list,",
     "if (v48_suppress_direct_draw("),
    ("bool v48_suppress_indirect_graphics(\n\t\tID3D12GraphicsCommandList *command_list,",
     "\t\t\tv48_suppress_indirect_graphics("),
):
    declaration_pos = text.find(declaration)
    call_pos = text.find(call)
    if declaration_pos < 0 or call_pos < 0 or declaration_pos >= call_pos:
        raise RuntimeError(
            f"V48 declaration-order validation failed: {declaration.splitlines()[0]}")

SOURCE.write_text(text, encoding="utf-8", newline="\n")

report = Path("v48-patch-report.txt")
report.write_text("\n".join([
    "V48_STABLE_POST_RTX_GRAPHICS_SUPPRESSION_CONTROL_PATCH_OK",
    "TARGET_STABLE_GRAPHICS_HASH_COUNT=10",
    "TARGET_SET_SOURCE=INTERSECTION_OF_V46_AND_V47_ZERO_PRE_RTX_GRAPHICS_HASHES",
    "ONCE_PER_FRAME_FULLSCREEN_CANDIDATE=0x15CD7A2678DF6413",
    "TARGET_DIRECT_DRAW_SUPPRESSION=ENABLED",
    "TARGET_DIRECT_INDEXED_DRAW_SUPPRESSION=ENABLED",
    "TARGET_INDIRECT_GRAPHICS_SUPPRESSION=ENABLED",
    "ORDINARY_GRAPHICS_DRAWS_PRESERVED=YES",
    "V47_COMPUTE_SUPPRESSION_PRESERVED=YES",
    "V45_RT_BIND_SUPPRESSION_PRESERVED=YES",
    "V44_RAY_DISPATCH_SUPPRESSION_PRESERVED=YES",
    "SHADER_BYTES_MODIFIED_BY_V48=NO",
    "DESCRIPTORS_MODIFIED_BY_V48=NO",
    "RESOURCES_MODIFIED_BY_V48=NO",
    "CONTROL_FLOW_CHANGE=SKIP_TEN_STABLE_POST_RTX_GRAPHICS_PIPELINES",
    "RESULT=PASS",
    "",
]), encoding="utf-8", newline="\n")
print(report.read_text(encoding="utf-8"))
