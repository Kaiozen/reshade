#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit(
        "usage: patch_d3d11_view1_fallback.py <d3d11_impl_device.cpp>"
    )

p = Path(sys.argv[1])
s = p.read_text(encoding="utf-8")

include_anchor = '#include "d3d11_extensions.hpp"\n'
if s.count(include_anchor) != 1:
    raise SystemExit(
        f"FAIL: U include anchor count={s.count(include_anchor)}"
    )
if '#include "dll_log.hpp"' not in s:
    s = s.replace(
        include_anchor,
        include_anchor + '#include "dll_log.hpp"\n',
        1,
    )

old_rtv = '''		else
		{
			D3D11_RENDER_TARGET_VIEW_DESC1 internal_desc = {};
			convert_resource_view_desc(desc, internal_desc);

			if (com_ptr<ID3D11RenderTargetView1> object;
				SUCCEEDED(device3->CreateRenderTargetView1(reinterpret_cast<ID3D11Resource *>(resource.handle), desc.type != api::resource_view_type::unknown ? &internal_desc : nullptr, &object)))
			{
				*out_view = to_handle(object.release());
				return true;
			}
		}
'''

new_rtv = '''		else
		{
			D3D11_RENDER_TARGET_VIEW_DESC1 internal_desc = {};
			convert_resource_view_desc(desc, internal_desc);

			com_ptr<ID3D11RenderTargetView1> object;
			const HRESULT view1_hr = device3->CreateRenderTargetView1(
				reinterpret_cast<ID3D11Resource *>(resource.handle),
				desc.type != api::resource_view_type::unknown ? &internal_desc : nullptr,
				&object);

			if (SUCCEEDED(view1_hr))
			{
				*out_view = to_handle(object.release());
				return true;
			}

			D3D11_RENDER_TARGET_VIEW_DESC legacy_desc = {};
			convert_resource_view_desc(desc, legacy_desc);

			com_ptr<ID3D11RenderTargetView> legacy_object;
			const HRESULT legacy_hr = _orig->CreateRenderTargetView(
				reinterpret_cast<ID3D11Resource *>(resource.handle),
				desc.type != api::resource_view_type::unknown ? &legacy_desc : nullptr,
				&legacy_object);

			if (SUCCEEDED(legacy_hr))
			{
				static bool logged_u_rtv_fallback_success = false;
				if (!logged_u_rtv_fallback_success)
				{
					reshade::log::message(
						reshade::log::level::info,
						"[Kaiozen] U_RTV1_FALLBACK=LEGACY_OK "
						"view1_hr=0x%08X legacy_hr=0x%08X format=%u",
						static_cast<unsigned int>(view1_hr),
						static_cast<unsigned int>(legacy_hr),
						static_cast<unsigned int>(desc.format));
					logged_u_rtv_fallback_success = true;
				}

				*out_view = to_handle(legacy_object.release());
				return true;
			}

			static bool logged_u_rtv_fallback_failure = false;
			if (!logged_u_rtv_fallback_failure)
			{
				reshade::log::message(
					reshade::log::level::error,
					"[Kaiozen] U_RTV1_FALLBACK=FAILED "
					"view1_hr=0x%08X legacy_hr=0x%08X format=%u",
					static_cast<unsigned int>(view1_hr),
					static_cast<unsigned int>(legacy_hr),
					static_cast<unsigned int>(desc.format));
				logged_u_rtv_fallback_failure = true;
			}
		}
'''

if s.count(old_rtv) != 1:
    raise SystemExit(
        f"FAIL: U RTV block count={s.count(old_rtv)}"
    )
s = s.replace(old_rtv, new_rtv, 1)

old_srv = '''		else
		{
			D3D11_SHADER_RESOURCE_VIEW_DESC1 internal_desc = {};
			convert_resource_view_desc(desc, internal_desc);

			if (com_ptr<ID3D11ShaderResourceView1> object;
				SUCCEEDED(device3->CreateShaderResourceView1(reinterpret_cast<ID3D11Resource *>(resource.handle), desc.type != api::resource_view_type::unknown ? &internal_desc : nullptr, &object)))
			{
				*out_view = to_handle(object.release());
				return true;
			}
		}
'''

new_srv = '''		else
		{
			D3D11_SHADER_RESOURCE_VIEW_DESC1 internal_desc = {};
			convert_resource_view_desc(desc, internal_desc);

			com_ptr<ID3D11ShaderResourceView1> object;
			const HRESULT view1_hr = device3->CreateShaderResourceView1(
				reinterpret_cast<ID3D11Resource *>(resource.handle),
				desc.type != api::resource_view_type::unknown ? &internal_desc : nullptr,
				&object);

			if (SUCCEEDED(view1_hr))
			{
				*out_view = to_handle(object.release());
				return true;
			}

			D3D11_SHADER_RESOURCE_VIEW_DESC legacy_desc = {};
			convert_resource_view_desc(desc, legacy_desc);

			com_ptr<ID3D11ShaderResourceView> legacy_object;
			const HRESULT legacy_hr = _orig->CreateShaderResourceView(
				reinterpret_cast<ID3D11Resource *>(resource.handle),
				desc.type != api::resource_view_type::unknown ? &legacy_desc : nullptr,
				&legacy_object);

			if (SUCCEEDED(legacy_hr))
			{
				static bool logged_u_srv_fallback_success = false;
				if (!logged_u_srv_fallback_success)
				{
					reshade::log::message(
						reshade::log::level::info,
						"[Kaiozen] U_SRV1_FALLBACK=LEGACY_OK "
						"view1_hr=0x%08X legacy_hr=0x%08X format=%u",
						static_cast<unsigned int>(view1_hr),
						static_cast<unsigned int>(legacy_hr),
						static_cast<unsigned int>(desc.format));
					logged_u_srv_fallback_success = true;
				}

				*out_view = to_handle(legacy_object.release());
				return true;
			}

			static bool logged_u_srv_fallback_failure = false;
			if (!logged_u_srv_fallback_failure)
			{
				reshade::log::message(
					reshade::log::level::error,
					"[Kaiozen] U_SRV1_FALLBACK=FAILED "
					"view1_hr=0x%08X legacy_hr=0x%08X format=%u",
					static_cast<unsigned int>(view1_hr),
					static_cast<unsigned int>(legacy_hr),
					static_cast<unsigned int>(desc.format));
				logged_u_srv_fallback_failure = true;
			}
		}
'''

if s.count(old_srv) != 1:
    raise SystemExit(
        f"FAIL: U SRV block count={s.count(old_srv)}"
    )
s = s.replace(old_srv, new_srv, 1)

p.write_text(s, encoding="utf-8", newline="\n")

print("HOTFIX=U")
print("D3D11_VIEW1_FALLBACK=YES")
print("SRV1_TO_LEGACY=YES")
print("RTV1_TO_LEGACY=YES")
print("HRESULT_LOGGING=YES")
