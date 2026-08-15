#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit(
        "usage: patch_reshade_srv_only_intermediate.py <runtime.cpp>"
    )

path = Path(sys.argv[1])
runtime = path.read_text(encoding="utf-8")

r3_start_marker = (
    "\t\tif (kaiozen_hsr_minimal_hdr)\n"
    "\t\t{\n"
    "\t\t\tconst api::format kaiozen_r3_raw_format =\n"
)
r3_start = runtime.find(r3_start_marker)
if r3_start < 0 or runtime.find(r3_start_marker, r3_start + 1) >= 0:
    raise SystemExit("FAIL: T R3 branch start invalid")

r3_else = runtime.find("\t\telse\n\t\t{\n", r3_start)
if r3_else < 0:
    raise SystemExit("FAIL: T R3 branch end invalid")

t_intermediate = r'''		if (kaiozen_hsr_minimal_hdr)
		{
			const api::format kaiozen_t_raw_format =
				api::format_to_default_typed(_back_buffer_format, 0);

			const api::resource_usage kaiozen_t_usage =
				api::resource_usage::copy_dest |
				api::resource_usage::shader_resource;

			const api::resource_desc kaiozen_t_desc(
				_width,
				_height,
				1,
				1,
				kaiozen_t_raw_format,
				1,
				api::memory_heap::default_,
				kaiozen_t_usage);

			if (!_device->create_resource(
					kaiozen_t_desc,
					nullptr,
					api::resource_usage::copy_dest,
					&_back_buffer_resolved))
			{
				log::message(
					log::level::error,
					"[Kaiozen] T_INTERMEDIATE_TEXTURE_FAILED "
					"format=%u size=%ux%u usage=0x%X",
					static_cast<uint32_t>(kaiozen_t_raw_format),
					_width,
					_height,
					static_cast<uint32_t>(kaiozen_t_usage));
				goto exit_failure;
			}

			_back_buffer_targets.emplace_back();
			_back_buffer_targets.emplace_back();

			log::message(
				log::level::info,
				"[Kaiozen] T_INTERMEDIATE_READY=SRV_ONLY "
				"FORMAT=R8G8B8A8_UNORM RTV_COUNT=0");
		}
'''

runtime = runtime[:r3_start] + t_intermediate + runtime[r3_else:]

minimal_comment = (
    "\t// HOTFIX R minimal HSR initialization. "
    "No ReShade effects or GUI required.\n"
)
minimal_pos = runtime.find(minimal_comment)
if minimal_pos < 0:
    raise SystemExit("FAIL: T minimal-init comment missing")

loop_start_marker = (
    "\t\tfor (uint32_t i = 0, "
    "count = _swapchain->get_back_buffer_count(); i < count; ++i)\n"
)
loop_start = runtime.find(loop_start_marker, minimal_pos)
state_block_pos = runtime.find(
    "\n\t\tcreate_state_block(_device, &_app_state);",
    loop_start,
)
if loop_start < 0 or state_block_pos < 0:
    raise SystemExit("FAIL: T minimal backbuffer-view block invalid")

t_backbuffer_views = r'''		for (uint32_t i = 0, count = _swapchain->get_back_buffer_count(); i < count; ++i)
		{
			const api::resource back_buffer_resource =
				_swapchain->get_back_buffer(i);

			if (!_device->create_resource_view(
					back_buffer_resource,
					api::resource_usage::render_target,
					api::resource_view_desc(
						back_buffer_desc.texture.samples > 1
							? api::resource_view_type::texture_2d_multisample
							: api::resource_view_type::texture_2d,
						api::format_to_default_typed(
							back_buffer_desc.texture.format, 0),
						0, 1, 0, 1),
					&_back_buffer_targets.emplace_back()))
			{
				log::message(
					log::level::error,
					"[Kaiozen] T_BACKBUFFER_RAW_RTV_FAILED index=%u",
					i);
				goto exit_failure;
			}

			_back_buffer_targets.emplace_back();
		}

		log::message(
			log::level::info,
			"[Kaiozen] T_BACKBUFFER_RTV_READY=RAW_UNORM_ONLY");
'''

runtime = (
    runtime[:loop_start]
    + t_backbuffer_views
    + runtime[state_block_pos:]
)

present_resource_anchor = (
    "\tuint32_t back_buffer_index = "
    "(_back_buffer_resolved != 0 ? 2 : 0) + "
    "_swapchain->get_current_back_buffer_index() * 2;\n"
    "\tconst api::resource back_buffer_resource = "
    "_device->get_resource_from_view("
    "_back_buffer_targets[back_buffer_index]);\n"
)
if runtime.count(present_resource_anchor) != 1:
    raise SystemExit(
        f"FAIL: T present resource anchor count="
        f"{runtime.count(present_resource_anchor)}"
    )

present_state = present_resource_anchor + r'''
	const bool kaiozen_hsr_t_srv_only_present =
		_device->get_api() == api::device_api::d3d11 &&
		api::format_to_typeless(_back_buffer_format) ==
			api::format::r8g8b8a8_typeless &&
		_width >= 1000 &&
		_height >= 700 &&
		_back_buffer_resolved != 0 &&
		_back_buffer_resolved_srv != 0 &&
		_copy_pipeline != 0;
'''

runtime = runtime.replace(
    present_resource_anchor,
    present_state,
    1,
)

copy_barrier = (
    "\t\t\tcmd_list->barrier("
    "_back_buffer_resolved, "
    "api::resource_usage::copy_dest, "
    "api::resource_usage::render_target);\n"
)
if runtime.count(copy_barrier) != 1:
    raise SystemExit(
        f"FAIL: T copy barrier count={runtime.count(copy_barrier)}"
    )

runtime = runtime.replace(
    copy_barrier,
    "\t\t\tcmd_list->barrier(\n"
    "\t\t\t\t_back_buffer_resolved,\n"
    "\t\t\t\tapi::resource_usage::copy_dest,\n"
    "\t\t\t\tkaiozen_hsr_t_srv_only_present\n"
    "\t\t\t\t\t? api::resource_usage::shader_resource\n"
    "\t\t\t\t\t: api::resource_usage::render_target);\n",
    1,
)

r3_present_decl_start = runtime.find(
    "\tconst bool kaiozen_hsr_minimal_hdr_present =\n"
)
if r3_present_decl_start < 0:
    raise SystemExit("FAIL: T R3 minimal-present declaration missing")

r3_present_if = runtime.find(
    "\tif (kaiozen_hsr_minimal_hdr_present)\n\t{\n",
    r3_present_decl_start,
)
if r3_present_if < 0:
    raise SystemExit("FAIL: T R3 minimal-present branch missing")

input_comment = (
    "\t// Lock input so it cannot be modified by other threads "
    "while we are reading it here\n"
)
r3_present_end = runtime.find(input_comment, r3_present_if)
if r3_present_end < 0:
    raise SystemExit("FAIL: T minimal-present end anchor missing")

t_present = r'''	const bool kaiozen_hsr_minimal_hdr_present =
		kaiozen_hsr_t_srv_only_present;

	if (kaiozen_hsr_minimal_hdr_present)
	{
		cmd_list->barrier(
			back_buffer_resource,
			api::resource_usage::copy_source |
				api::resource_usage::resolve_source,
			api::resource_usage::render_target);

		cmd_list->bind_pipeline(
			api::pipeline_stage::all_graphics,
			_copy_pipeline);

		cmd_list->push_descriptors(
			api::shader_stage::pixel,
			_copy_pipeline_layout,
			0,
			api::descriptor_table_update {
				{}, 0, 0, 1,
				api::descriptor_type::sampler,
				&_copy_sampler_state });

		cmd_list->push_descriptors(
			api::shader_stage::pixel,
			_copy_pipeline_layout,
			1,
			api::descriptor_table_update {
				{}, 0, 0, 1,
				api::descriptor_type::shader_resource_view,
				&_back_buffer_resolved_srv });

		const api::viewport viewport = {
			0.0f, 0.0f,
			static_cast<float>(_width),
			static_cast<float>(_height),
			0.0f, 1.0f
		};
		cmd_list->bind_viewports(0, 1, &viewport);

		const api::rect scissor_rect = {
			0, 0,
			static_cast<int32_t>(_width),
			static_cast<int32_t>(_height)
		};
		cmd_list->bind_scissor_rects(0, 1, &scissor_rect);

		cmd_list->bind_render_targets_and_depth_stencil(
			1,
			&_back_buffer_targets[back_buffer_index]);

		cmd_list->draw(3, 1, 0, 0);

		cmd_list->barrier(
			back_buffer_resource,
			api::resource_usage::render_target,
			api::resource_usage::present);

		cmd_list->barrier(
			_back_buffer_resolved,
			api::resource_usage::shader_resource,
			api::resource_usage::copy_dest);

		apply_state(cmd_list, _app_state);

		_frame_count++;
		if (_frame_count == 1)
			log::message(
				log::level::info,
				"[Kaiozen] R_COPY_DRAW_EXECUTED=YES "
				"RAW_UNORM_SRV=YES RAW_UNORM_RTV=YES "
				"T_INTERMEDIATE_RTV=NO");

#if RESHADE_ADDON
		_is_in_present_call = false;
#endif
		_effects_rendered_this_frame = false;
		return;
	}

'''

runtime = (
    runtime[:r3_present_decl_start]
    + t_present
    + runtime[r3_present_end:]
)

path.write_text(runtime, encoding="utf-8", newline="\n")

print("HOTFIX=T")
print("INTERMEDIATE=SRV_ONLY")
print("INTERMEDIATE_USAGE=COPY_DEST|SHADER_RESOURCE")
print("INTERMEDIATE_RTV_COUNT=0")
print("BACKBUFFER_RTV=RAW_UNORM_ONLY")
print("PRESENT_STATE_MACHINE=EXPLICIT")
