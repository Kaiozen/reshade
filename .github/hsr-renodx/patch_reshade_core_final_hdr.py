#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 3:
    raise SystemExit("usage: patch_reshade_core_final_hdr.py <runtime.cpp> <copy_ps.hlsl>")

runtime_path = Path(sys.argv[1])
shader_path = Path(sys.argv[2])
runtime = runtime_path.read_text(encoding="utf-8")

include_anchor = '#include "reshade_api_object_impl.hpp"\n'
if runtime.count(include_anchor) != 1:
    raise SystemExit("FAIL: include anchor invalid")
runtime = runtime.replace(include_anchor, include_anchor + '#include <dxgi1_6.h>\n', 1)

state_anchor = "\t_back_buffer_color_space = _swapchain->get_color_space();\n"
if runtime.count(state_anchor) != 1:
    raise SystemExit("FAIL: backbuffer state anchor invalid")
state_insert = state_anchor + r'''

	// HOTFIX R: only HSR-sized DX11 RGBA8-family swapchains.
	const bool kaiozen_hsr_minimal_hdr =
		_device->get_api() == api::device_api::d3d11 &&
		api::format_to_typeless(back_buffer_desc.texture.format) == api::format::r8g8b8a8_typeless &&
		_width >= 1000 &&
		_height >= 700;

	if (kaiozen_hsr_minimal_hdr)
	{
		log::message(
			log::level::info,
			"[Kaiozen] R_ROUTE_MATCH=YES raw_format=%u typed_format=%u size=%ux%u samples=%u",
			static_cast<uint32_t>(back_buffer_desc.texture.format),
			static_cast<uint32_t>(_back_buffer_format),
			_width,
			_height,
			_back_buffer_samples);
	}
'''
runtime = runtime.replace(state_anchor, state_insert, 1)

resolve_anchor = "\tif (back_buffer_desc.texture.samples > 1 ||\n"
if runtime.count(resolve_anchor) != 1:
    raise SystemExit("FAIL: resolve condition anchor invalid")
runtime = runtime.replace(
    resolve_anchor,
    "\tif (kaiozen_hsr_minimal_hdr ||\n\t\tback_buffer_desc.texture.samples > 1 ||\n",
    1,
)

# HOTFIX R3:
# ReShade's generic resolved texture is TYPELESS and asks for both linear and
# sRGB RTV reinterpretations. D3DMetal rejected that HSR path before HDR
# activation. Replace only the HSR branch with a fully typed RGBA8 UNORM
# resource and two RAW UNORM RTVs. Keep the generic ReShade path unchanged.
#
# Splitting the calls also gives exact runtime failure markers instead of the
# stock combined "Failed to create resolve texture resource!" message.
resolve_key = (
    "api::resource_desc(_width, _height, 1, 1, "
    "api::format_to_typeless(_back_buffer_format), 1, "
    "api::memory_heap::default_, usage),"
)
resolve_pos = runtime.find(resolve_key)
if resolve_pos < 0 or runtime.find(resolve_key, resolve_pos + 1) >= 0:
    raise SystemExit("FAIL: R3 generic resolve block key invalid")

resolve_block_start = runtime.rfind(
    "\t\tif (!_device->create_resource(\n",
    0,
    resolve_pos,
)
resolve_block_end = runtime.find(
    "\n\t\tif (need_copy_pipeline)",
    resolve_pos,
)

if resolve_block_start < 0 or resolve_block_end < 0:
    raise SystemExit("FAIL: R3 generic resolve block boundaries invalid")

stock_resolve_block = runtime[resolve_block_start:resolve_block_end]

r3_resolve_block = """\t\tif (kaiozen_hsr_minimal_hdr)
\t\t{
\t\t\tconst api::format kaiozen_r3_raw_format =
\t\t\t\tapi::format_to_default_typed(_back_buffer_format, 0);

\t\t\tconst api::resource_desc kaiozen_r3_desc(
\t\t\t\t_width,
\t\t\t\t_height,
\t\t\t\t1,
\t\t\t\t1,
\t\t\t\tkaiozen_r3_raw_format,
\t\t\t\t1,
\t\t\t\tapi::memory_heap::default_,
\t\t\t\tusage);

\t\t\tif (!_device->create_resource(
\t\t\t\t\tkaiozen_r3_desc,
\t\t\t\t\tnullptr,
\t\t\t\t\tapi::resource_usage::copy_dest,
\t\t\t\t\t&_back_buffer_resolved))
\t\t\t{
\t\t\t\tlog::message(
\t\t\t\t\tlog::level::error,
\t\t\t\t\t"[Kaiozen] R3_RESOLVE_TEXTURE_FAILED format=%u size=%ux%u usage=0x%X",
\t\t\t\t\tstatic_cast<uint32_t>(kaiozen_r3_raw_format),
\t\t\t\t\t_width,
\t\t\t\t\t_height,
\t\t\t\t\tstatic_cast<uint32_t>(usage));
\t\t\t\tgoto exit_failure;
\t\t\t}

\t\t\tif (!_device->create_resource_view(
\t\t\t\t\t_back_buffer_resolved,
\t\t\t\t\tapi::resource_usage::render_target,
\t\t\t\t\tapi::resource_view_desc(kaiozen_r3_raw_format),
\t\t\t\t\t&_back_buffer_targets.emplace_back()))
\t\t\t{
\t\t\t\tlog::message(
\t\t\t\t\tlog::level::error,
\t\t\t\t\t"[Kaiozen] R3_RESOLVE_RTV0_FAILED format=%u",
\t\t\t\t\tstatic_cast<uint32_t>(kaiozen_r3_raw_format));
\t\t\t\tgoto exit_failure;
\t\t\t}

\t\t\t// Slot 1 intentionally duplicates the RAW UNORM view.
\t\t\t// It exists only to preserve ReShade's backbuffer target indexing.
\t\t\t// The HSR minimal Present path never uses an sRGB RTV here.
\t\t\tif (!_device->create_resource_view(
\t\t\t\t\t_back_buffer_resolved,
\t\t\t\t\tapi::resource_usage::render_target,
\t\t\t\t\tapi::resource_view_desc(kaiozen_r3_raw_format),
\t\t\t\t\t&_back_buffer_targets.emplace_back()))
\t\t\t{
\t\t\t\tlog::message(
\t\t\t\t\tlog::level::error,
\t\t\t\t\t"[Kaiozen] R3_RESOLVE_RTV1_FAILED format=%u",
\t\t\t\t\tstatic_cast<uint32_t>(kaiozen_r3_raw_format));
\t\t\t\tgoto exit_failure;
\t\t\t}

\t\t\tlog::message(
\t\t\t\tlog::level::info,
\t\t\t\t"[Kaiozen] R3_RESOLVE_RESOURCE_READY=TYPED_UNORM format=%u",
\t\t\t\tstatic_cast<uint32_t>(kaiozen_r3_raw_format));
\t\t}
\t\telse
\t\t{
""" + stock_resolve_block + """
\t\t}
"""

runtime = (
    runtime[:resolve_block_start]
    + r3_resolve_block
    + runtime[resolve_block_end:]
)

srv_anchor = "\t\t\t\tapi::resource_view_desc(_back_buffer_format),\n"
if runtime.count(srv_anchor) != 1:
    raise SystemExit("FAIL: resolved SRV anchor invalid")
runtime = runtime.replace(
    srv_anchor,
    "\t\t\t\tapi::resource_view_desc(\n"
    "\t\t\t\t\tkaiozen_hsr_minimal_hdr\n"
    "\t\t\t\t\t\t? api::format_to_default_typed(_back_buffer_format, 0)\n"
    "\t\t\t\t\t\t: _back_buffer_format),\n",
    1,
)

empty_anchor = "\t// Create an empty texture, which is bound to shader resource view slots with an unknown semantic"
if runtime.count(empty_anchor) != 1:
    raise SystemExit("FAIL: minimal-init insertion anchor invalid")

minimal_init = r'''
	// HOTFIX R minimal HSR initialization. No ReShade effects or GUI required.
	if (kaiozen_hsr_minimal_hdr)
	{
		if (_back_buffer_resolved == 0 ||
			_back_buffer_resolved_srv == 0 ||
			_copy_pipeline == 0 ||
			_copy_pipeline_layout == 0 ||
			_copy_sampler_state == 0)
		{
			log::message(log::level::error, "[Kaiozen] R_HDR_BLOCKED=COPY_RESOURCES_NOT_READY");
			goto exit_failure;
		}

		for (uint32_t i = 0, count = _swapchain->get_back_buffer_count(); i < count; ++i)
		{
			const api::resource back_buffer_resource = _swapchain->get_back_buffer(i);

			if (!_device->create_resource_view(
					back_buffer_resource,
					api::resource_usage::render_target,
					api::resource_view_desc(
						back_buffer_desc.texture.samples > 1 ? api::resource_view_type::texture_2d_multisample : api::resource_view_type::texture_2d,
						api::format_to_default_typed(back_buffer_desc.texture.format, 0), 0, 1, 0, 1),
					&_back_buffer_targets.emplace_back()) ||
				!_device->create_resource_view(
					back_buffer_resource,
					api::resource_usage::render_target,
					api::resource_view_desc(
						back_buffer_desc.texture.samples > 1 ? api::resource_view_type::texture_2d_multisample : api::resource_view_type::texture_2d,
						api::format_to_default_typed(back_buffer_desc.texture.format, 1), 0, 1, 0, 1),
					&_back_buffer_targets.emplace_back()))
			{
				log::message(log::level::error, "[Kaiozen] R_HDR_BLOCKED=BACKBUFFER_VIEWS_FAILED");
				goto exit_failure;
			}
		}

		create_state_block(_device, &_app_state);

		auto *const native_swapchain = reinterpret_cast<IDXGISwapChain *>(_swapchain->get_native());
		IDXGISwapChain3 *swapchain3 = nullptr;

		if (native_swapchain == nullptr ||
			FAILED(native_swapchain->QueryInterface(IID_PPV_ARGS(&swapchain3))) ||
			swapchain3 == nullptr)
		{
			log::message(log::level::error, "[Kaiozen] R_HDR_BLOCKED=NO_DXGI_SWAPCHAIN3");
			goto exit_failure;
		}

		constexpr DXGI_COLOR_SPACE_TYPE hdr10_color_space = DXGI_COLOR_SPACE_RGB_FULL_G2084_NONE_P2020;
		UINT support = 0;
		HRESULT hr = swapchain3->CheckColorSpaceSupport(hdr10_color_space, &support);

		if (FAILED(hr) || (support & DXGI_SWAP_CHAIN_COLOR_SPACE_SUPPORT_FLAG_PRESENT) == 0)
		{
			log::message(log::level::error,
				"[Kaiozen] R_HDR_BLOCKED=HDR10_UNSUPPORTED hr=0x%08X support=0x%08X",
				static_cast<unsigned int>(hr), support);
			swapchain3->Release();
			goto exit_failure;
		}

		hr = swapchain3->SetColorSpace1(hdr10_color_space);
		if (FAILED(hr))
		{
			log::message(log::level::error,
				"[Kaiozen] R_HDR_BLOCKED=SETCOLORSPACE_FAILED hr=0x%08X",
				static_cast<unsigned int>(hr));
			swapchain3->Release();
			goto exit_failure;
		}

		_back_buffer_color_space = api::color_space::hdr10_pq;

		IDXGISwapChain4 *swapchain4 = nullptr;
		if (SUCCEEDED(native_swapchain->QueryInterface(IID_PPV_ARGS(&swapchain4))) && swapchain4 != nullptr)
		{
			DXGI_HDR_METADATA_HDR10 metadata = {};
			metadata.RedPrimary[0] = 34000;
			metadata.RedPrimary[1] = 16000;
			metadata.GreenPrimary[0] = 13250;
			metadata.GreenPrimary[1] = 34500;
			metadata.BluePrimary[0] = 7500;
			metadata.BluePrimary[1] = 3000;
			metadata.WhitePoint[0] = 15635;
			metadata.WhitePoint[1] = 16450;
			metadata.MaxMasteringLuminance = 1000u * 10000u;
			metadata.MinMasteringLuminance = 0;
			metadata.MaxContentLightLevel = 1000;
			metadata.MaxFrameAverageLightLevel = 400;

			const HRESULT metadata_hr = swapchain4->SetHDRMetaData(
				DXGI_HDR_METADATA_TYPE_HDR10, sizeof(metadata), &metadata);
			log::message(
				SUCCEEDED(metadata_hr) ? log::level::info : log::level::warning,
				SUCCEEDED(metadata_hr) ? "[Kaiozen] R_HDR_METADATA_OK" : "[Kaiozen] R_HDR_METADATA_FAILED");
			swapchain4->Release();
		}
		else
		{
			log::message(log::level::warning, "[Kaiozen] R_HDR_METADATA_UNAVAILABLE");
		}

		swapchain3->Release();

		_frame_count = 0;
		_is_initialized = true;
		_last_reload_time = std::chrono::high_resolution_clock::now();

		log::message(log::level::info,
			"[Kaiozen] R_MINIMAL_RUNTIME=READY EFFECT_RUNTIME=BYPASSED GUI=BYPASSED");
		log::message(log::level::info,
			"[Kaiozen] R_HDR10_ACTIVE=YES PQ_COPY_READY=YES RAW_UNORM=YES");
		return true;
	}

'''
runtime = runtime.replace(empty_anchor, minimal_init + empty_anchor, 1)

present_anchor = (
    "\t// Lock input so it cannot be modified by other threads while we are reading it here\n"
    "\tstd::unique_lock<std::recursive_mutex> input_lock;\n"
    "\tif (_input != nullptr)\n"
    "\t\tinput_lock = _input->lock();\n"
    "\n"
    "\tupdate_effects();\n"
)
if runtime.count(present_anchor) != 1:
    raise SystemExit(
        f"FAIL: minimal-present unique anchor count={runtime.count(present_anchor)}"
    )

minimal_present = r'''
	const bool kaiozen_hsr_minimal_hdr_present =
		_device->get_api() == api::device_api::d3d11 &&
		api::format_to_typeless(_back_buffer_format) == api::format::r8g8b8a8_typeless &&
		_width >= 1000 &&
		_height >= 700 &&
		_back_buffer_resolved != 0 &&
		_back_buffer_resolved_srv != 0 &&
		_copy_pipeline != 0;

	if (kaiozen_hsr_minimal_hdr_present)
	{
		const api::resource resources[2] = { back_buffer_resource, _back_buffer_resolved };
		const api::resource_usage state_old[2] = {
			api::resource_usage::copy_source | api::resource_usage::resolve_source,
			api::resource_usage::render_target };
		const api::resource_usage state_new[2] = {
			api::resource_usage::render_target,
			api::resource_usage::shader_resource };
		const api::resource_usage state_final[2] = {
			api::resource_usage::present,
			api::resource_usage::resolve_dest };

		cmd_list->barrier(2, resources, state_old, state_new);
		cmd_list->bind_pipeline(api::pipeline_stage::all_graphics, _copy_pipeline);
		cmd_list->push_descriptors(api::shader_stage::pixel, _copy_pipeline_layout, 0,
			api::descriptor_table_update { {}, 0, 0, 1, api::descriptor_type::sampler, &_copy_sampler_state });
		cmd_list->push_descriptors(api::shader_stage::pixel, _copy_pipeline_layout, 1,
			api::descriptor_table_update { {}, 0, 0, 1, api::descriptor_type::shader_resource_view, &_back_buffer_resolved_srv });

		const api::viewport viewport = { 0.0f, 0.0f, static_cast<float>(_width), static_cast<float>(_height), 0.0f, 1.0f };
		cmd_list->bind_viewports(0, 1, &viewport);
		const api::rect scissor_rect = { 0, 0, static_cast<int32_t>(_width), static_cast<int32_t>(_height) };
		cmd_list->bind_scissor_rects(0, 1, &scissor_rect);

		cmd_list->bind_render_targets_and_depth_stencil(1, &_back_buffer_targets[back_buffer_index]);
		cmd_list->draw(3, 1, 0, 0);
		cmd_list->barrier(2, resources, state_new, state_final);
		apply_state(cmd_list, _app_state);

		_frame_count++;
		if (_frame_count == 1)
			log::message(log::level::info,
				"[Kaiozen] R_COPY_DRAW_EXECUTED=YES RAW_UNORM_SRV=YES RAW_UNORM_RTV=YES");

#if RESHADE_ADDON
		_is_in_present_call = false;
#endif
		_effects_rendered_this_frame = false;
		return;
	}

'''
runtime = runtime.replace(present_anchor, minimal_present + present_anchor, 1)
runtime_path.write_text(runtime, encoding="utf-8", newline="\n")

shader = r'''Texture2D t0 : register(t0);
SamplerState s0 : register(s0);

float3 SRGBDecode(float3 v)
{
    v = max(v, 0.0);
    float3 lo = v / 12.92;
    float3 hi = pow((v + 0.055) / 1.055, 2.4);
    return lerp(lo, hi, step(0.04045, v));
}

float3 BT709ToBT2020(float3 c)
{
    return float3(
        dot(c, float3(0.6274040, 0.3292820, 0.0433136)),
        dot(c, float3(0.0690970, 0.9195400, 0.0113612)),
        dot(c, float3(0.0163916, 0.0880132, 0.8955950))
    );
}

float PQ1(float nits)
{
    const float m1 = 0.1593017578125;
    const float m2 = 78.84375;
    const float c1 = 0.8359375;
    const float c2 = 18.8515625;
    const float c3 = 18.6875;
    float L = saturate(max(nits, 0.0) / 10000.0);
    float p = pow(L, m1);
    return pow((c1 + c2 * p) / (1.0 + c3 * p), m2);
}

float3 PQEncode(float3 nits)
{
    return float3(PQ1(nits.r), PQ1(nits.g), PQ1(nits.b));
}

void main(float4 vpos : SV_POSITION, float2 uv : TEXCOORD0, out float4 col : SV_TARGET)
{
    float3 encoded709 = saturate(t0.Sample(s0, uv).rgb);
    float3 linear709 = SRGBDecode(encoded709);

    const float SATURATION_RETENTION = 0.70;
    const float luma709 = dot(linear709, float3(0.2126, 0.7152, 0.0722));
    linear709 = lerp(luma709.xxx, linear709, SATURATION_RETENTION);

    float3 linear2020 = max(BT709ToBT2020(linear709), 0.0);
    const float SDR_WHITE_NITS = 203.0;
    col.rgb = saturate(PQEncode(linear2020 * SDR_WHITE_NITS));
    col.a = 1.0;
}
'''
shader_path.write_text(shader, encoding="utf-8", newline="\n")

print("HOTFIX=R3")
print("MODE=MINIMAL_CORE_HDR_TYPED_UNORM_RESOLVE")
print("RESHade_EFFECT_RUNTIME=BYPASSED")
print("RESHade_GUI=BYPASSED")
print("RENODX=SHADER_ONLY")
print("RAW_UNORM_SRV=YES")
print("RAW_UNORM_RTV=YES")
print("PQ=YES")
print("HDR10_OWNER=MINIMAL_CORE")
