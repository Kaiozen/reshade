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
    raise SystemExit("FAIL: DXGI include anchor invalid")
runtime = runtime.replace(include_anchor, include_anchor + '#include <dxgi1_6.h>\n', 1)

state_anchor = "\t_back_buffer_color_space = _swapchain->get_color_space();\n"
if runtime.count(state_anchor) != 1:
    raise SystemExit("FAIL: runtime color-space anchor invalid")

state_insert = state_anchor + r'''

	// Kaiozen HOTFIX Q: match the entire RGBA8 family instead of requiring a
	// single typed enum. This avoids silently missing sRGB/typeless variants.
	const bool kaiozen_hsr_core_hdr =
		_device->get_api() == api::device_api::d3d11 &&
		api::format_to_typeless(back_buffer_desc.texture.format) == api::format::r8g8b8a8_typeless &&
		_width >= 800 && _height >= 600;

	if (kaiozen_hsr_core_hdr)
	{
		_back_buffer_color_space = api::color_space::hdr10_pq;
		log::message(
			log::level::info,
			"[Kaiozen] Q_ROUTE_MATCH=YES raw_format=%u typed_format=%u size=%ux%u samples=%u",
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
    "\tif (kaiozen_hsr_core_hdr ||\n"
    "\t\tback_buffer_desc.texture.samples > 1 ||\n",
    1,
)

srv_anchor = "\t\t\t\tapi::resource_view_desc(_back_buffer_format),\n"
if runtime.count(srv_anchor) != 1:
    raise SystemExit("FAIL: resolved SRV anchor invalid")
runtime = runtime.replace(
    srv_anchor,
    "\t\t\t\tapi::resource_view_desc(\n"
    "\t\t\t\t\tkaiozen_hsr_core_hdr\n"
    "\t\t\t\t\t\t? api::format_to_default_typed(_back_buffer_format, 0)\n"
    "\t\t\t\t\t\t: _back_buffer_format),\n",
    1,
)

late_anchor = "\t// Reset frame count to zero so effects are loaded in 'update_effects'\n"
if runtime.count(late_anchor) != 1:
    raise SystemExit("FAIL: late HDR activation anchor invalid")

late_block = r'''
	// HOTFIX Q invariant:
	// NO confirmed final PQ copy path = NO HDR10 swapchain tag.
	if (kaiozen_hsr_core_hdr)
	{
		if (_back_buffer_resolved == 0 ||
			_back_buffer_resolved_srv == 0 ||
			_copy_pipeline == 0)
		{
			log::message(log::level::error, "[Kaiozen] Q_HDR_BLOCKED=COPY_PATH_NOT_READY");
			goto exit_failure;
		}

		auto *const native_swapchain =
			reinterpret_cast<IDXGISwapChain *>(_swapchain->get_native());
		IDXGISwapChain3 *swapchain3 = nullptr;

		if (native_swapchain == nullptr ||
			FAILED(native_swapchain->QueryInterface(IID_PPV_ARGS(&swapchain3))) ||
			swapchain3 == nullptr)
		{
			log::message(log::level::error, "[Kaiozen] Q_HDR_BLOCKED=NO_DXGI_SWAPCHAIN3");
			goto exit_failure;
		}

		constexpr DXGI_COLOR_SPACE_TYPE hdr10_color_space =
			DXGI_COLOR_SPACE_RGB_FULL_G2084_NONE_P2020;

		UINT support = 0;
		HRESULT hr = swapchain3->CheckColorSpaceSupport(hdr10_color_space, &support);

		if (FAILED(hr) ||
			(support & DXGI_SWAP_CHAIN_COLOR_SPACE_SUPPORT_FLAG_PRESENT) == 0)
		{
			log::message(
				log::level::error,
				"[Kaiozen] Q_HDR_BLOCKED=HDR10_COLORSPACE_UNSUPPORTED hr=0x%08X support=0x%08X",
				static_cast<unsigned int>(hr),
				support);
			swapchain3->Release();
			goto exit_failure;
		}

		hr = swapchain3->SetColorSpace1(hdr10_color_space);
		if (FAILED(hr))
		{
			log::message(
				log::level::error,
				"[Kaiozen] Q_HDR_BLOCKED=SETCOLORSPACE_FAILED hr=0x%08X",
				static_cast<unsigned int>(hr));
			swapchain3->Release();
			goto exit_failure;
		}

		IDXGISwapChain4 *swapchain4 = nullptr;
		if (SUCCEEDED(native_swapchain->QueryInterface(IID_PPV_ARGS(&swapchain4))) &&
			swapchain4 != nullptr)
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
			metadata.MaxContentLightLevel = 203;
			metadata.MaxFrameAverageLightLevel = 203;

			const HRESULT metadata_hr = swapchain4->SetHDRMetaData(
				DXGI_HDR_METADATA_TYPE_HDR10,
				sizeof(metadata),
				&metadata);

			log::message(
				SUCCEEDED(metadata_hr) ? log::level::info : log::level::warning,
				SUCCEEDED(metadata_hr)
					? "[Kaiozen] Q_HDR_METADATA_OK"
					: "[Kaiozen] Q_HDR_METADATA_FAILED");

			swapchain4->Release();
		}
		else
		{
			log::message(log::level::warning, "[Kaiozen] Q_HDR_METADATA_UNAVAILABLE");
		}

		swapchain3->Release();

		log::message(
			log::level::info,
			"[Kaiozen] Q_HDR10_CORE_ACTIVE PQ_COPY_AND_TAG_ATOMIC=YES");
		log::message(
			log::level::info,
			"[Kaiozen] Q_RESOLVED_RESOURCE_ACTIVE=YES RAW_UNORM_SRV=YES");
	}

'''
runtime = runtime.replace(late_anchor, late_block + late_anchor, 1)

rtv_anchor = (
    "\t\t\tconst bool srgb_write_enable = "
    "(_back_buffer_format == api::format::r8g8b8a8_unorm_srgb || "
    "_back_buffer_format == api::format::b8g8r8a8_unorm_srgb);\n"
)
if runtime.count(rtv_anchor) != 1:
    raise SystemExit("FAIL: sRGB RTV anchor invalid")

rtv_replacement = r'''			const bool kaiozen_hsr_core_hdr_present =
				_device->get_api() == api::device_api::d3d11 &&
				api::format_to_typeless(_back_buffer_format) == api::format::r8g8b8a8_typeless &&
				_width >= 800 && _height >= 600;

			const bool srgb_write_enable =
				!kaiozen_hsr_core_hdr_present &&
				(_back_buffer_format == api::format::r8g8b8a8_unorm_srgb ||
				 _back_buffer_format == api::format::b8g8r8a8_unorm_srgb);
'''
runtime = runtime.replace(rtv_anchor, rtv_replacement, 1)

draw_anchor = "\t\t\tcmd_list->draw(3, 1, 0, 0);\n"
if runtime.count(draw_anchor) != 1:
    raise SystemExit("FAIL: final copy draw anchor invalid")

draw_replacement = r'''			cmd_list->draw(3, 1, 0, 0);

			if (kaiozen_hsr_core_hdr_present && _frame_count == 1)
			{
				log::message(
					log::level::info,
					"[Kaiozen] Q_COPY_DRAW_EXECUTED=YES RAW_UNORM_RTV=YES");
			}
'''
runtime = runtime.replace(draw_anchor, draw_replacement, 1)

runtime_path.write_text(runtime, encoding="utf-8", newline="\n")

shader = r'''Texture2D t0 : register(t0);
SamplerState s0 : register(s0);

// KAIOZEN_HSR_CORE_HDR_COPY_Q
// RAW UNORM input and RAW UNORM output are forced by runtime.cpp.

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

void main(
    float4 vpos : SV_POSITION,
    float2 uv : TEXCOORD0,
    out float4 col : SV_TARGET)
{
    float3 encoded709 = saturate(t0.Sample(s0, uv).rgb);
    float3 linear709 = SRGBDecode(encoded709);

    // Deliberately visible witness + current oversaturation correction.
    const float SATURATION_RETENTION = 0.70;
    const float luma709 = dot(linear709, float3(0.2126, 0.7152, 0.0722));
    linear709 = lerp(luma709.xxx, linear709, SATURATION_RETENTION);

    float3 linear2020 = max(BT709ToBT2020(linear709), 0.0);

    const float SDR_WHITE_NITS = 203.0;
    float3 nits2020 = linear2020 * SDR_WHITE_NITS;

    col.rgb = saturate(PQEncode(nits2020));
    col.a = 1.0;
}
'''
shader_path.write_text(shader, encoding="utf-8", newline="\n")

print("HOTFIX=Q")
print("ROUTE_MATCH=RGBA8_TYPELESS_FAMILY")
print("RAW_UNORM_SRV=YES")
print("RAW_UNORM_RTV=YES")
print("HDR10_OWNER=RESHade_CORE")
print("HDR10_REQUIRES_COPY_PATH=YES")
print("SOURCE_TRANSFER=EXACT_SRGB")
print("BT709_TO_BT2020=YES")
print("PQ=YES")
print("SDR_WHITE_NITS=203")
print("SATURATION_RETENTION=70_PERCENT")
print("HIGHLIGHT_EXPANSION=NONE")
print("BT2446A=NONE")
