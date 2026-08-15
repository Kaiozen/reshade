#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 3:
    raise SystemExit(
        "usage: patch_reshade_atomic_present_hdr.py <runtime.cpp> <dxgi_swapchain.cpp>"
    )

runtime_path = Path(sys.argv[1])
dxgi_path = Path(sys.argv[2])

runtime = runtime_path.read_text(encoding="utf-8")
dxgi = dxgi_path.read_text(encoding="utf-8")

GUID_NAME = "KAIOZEN_HSR_HDR_ARMED_GUID"
GUID_DECL = (
    "static const GUID KAIOZEN_HSR_HDR_ARMED_GUID = "
    "{ 0x6a6f1d42, 0x4f0d, 0x4c8d, "
    "{ 0x9f, 0x31, 0x7a, 0x6b, 0x4d, 0x31, 0x58, 0xa1 } };\n"
)

runtime_guid_anchor = '#include <dxgi1_6.h>\n'
if runtime.count(runtime_guid_anchor) != 1:
    raise SystemExit(
        f"FAIL: S runtime GUID anchor count={runtime.count(runtime_guid_anchor)}"
    )

if GUID_NAME not in runtime:
    runtime = runtime.replace(
        runtime_guid_anchor,
        runtime_guid_anchor + "\n" + GUID_DECL,
        1,
    )

arm_anchor = "\t\tswapchain3->Release();\n\n\t\t_frame_count = 0;\n"
if runtime.count(arm_anchor) != 1:
    raise SystemExit(
        f"FAIL: S runtime arm anchor count={runtime.count(arm_anchor)}"
    )

arm_block = r'''		{
			const UINT kaiozen_hsr_hdr_armed = 1;
			const HRESULT arm_hr = native_swapchain->SetPrivateData(
				KAIOZEN_HSR_HDR_ARMED_GUID,
				sizeof(kaiozen_hsr_hdr_armed),
				&kaiozen_hsr_hdr_armed);

			if (FAILED(arm_hr))
			{
				log::message(
					log::level::error,
					"[Kaiozen] S_HDR_BLOCKED=ARM_FLAG_FAILED hr=0x%08X",
					static_cast<unsigned int>(arm_hr));

				swapchain3->SetColorSpace1(
					DXGI_COLOR_SPACE_RGB_FULL_G22_NONE_P709);
				swapchain3->Release();
				goto exit_failure;
			}

			log::message(
				log::level::info,
				"[Kaiozen] S_PRESENT_ARMED=YES ATOMIC_HDR_HANDOFF=YES");
		}

		swapchain3->Release();

		_frame_count = 0;
'''

runtime = runtime.replace(arm_anchor, arm_block, 1)

reset_anchor = (
    "void reshade::runtime::on_reset()\n"
    "{\n"
    "\tif (_is_initialized)\n"
)
if runtime.count(reset_anchor) != 1:
    raise SystemExit(
        f"FAIL: S runtime reset anchor count={runtime.count(reset_anchor)}"
    )

reset_block = r'''void reshade::runtime::on_reset()
{
	if (_device->get_api() == api::device_api::d3d11)
	{
		auto *const kaiozen_native_swapchain =
			reinterpret_cast<IDXGISwapChain *>(_swapchain->get_native());

		if (kaiozen_native_swapchain != nullptr)
		{
			kaiozen_native_swapchain->SetPrivateData(
				KAIOZEN_HSR_HDR_ARMED_GUID,
				0,
				nullptr);
		}
	}

	if (_is_initialized)
'''

runtime = runtime.replace(reset_anchor, reset_block, 1)
runtime_path.write_text(runtime, encoding="utf-8", newline="\n")

dxgi_guid_anchor = (
    "inline constexpr GUID SKID_SwapChainColorSpace = "
    "{ 0x18b57e4, 0x1493, 0x4953, "
    "{ 0xad, 0xf2, 0xde, 0x6d, 0x99, 0xcc, 0x5, 0xe5 } }; "
    "// {018B57E4-1493-4953-ADF2-DE6D99CC05E5}\n"
)
if dxgi.count(dxgi_guid_anchor) != 1:
    raise SystemExit(
        f"FAIL: S DXGI GUID anchor count={dxgi.count(dxgi_guid_anchor)}"
    )

helper = r'''
static const GUID KAIOZEN_HSR_HDR_ARMED_GUID =
{ 0x6a6f1d42, 0x4f0d, 0x4c8d,
{ 0x9f, 0x31, 0x7a, 0x6b, 0x4d, 0x31, 0x58, 0xa1 } };

static void kaiozen_hsr_apply_hdr_at_native_present(
	IDXGISwapChain *swapchain,
	reshade::api::device_api direct3d_version)
{
	if (direct3d_version != reshade::api::device_api::d3d11 ||
		swapchain == nullptr)
		return;

	UINT armed = 0;
	UINT armed_size = sizeof(armed);
	if (FAILED(swapchain->GetPrivateData(
			KAIOZEN_HSR_HDR_ARMED_GUID,
			&armed_size,
			&armed)) ||
		armed != 1)
		return;

	com_ptr<IDXGISwapChain3> swapchain3;
	if (FAILED(swapchain->QueryInterface(&swapchain3)) ||
		swapchain3 == nullptr)
	{
		static bool logged_no_swapchain3 = false;
		if (!logged_no_swapchain3)
		{
			reshade::log::message(
				reshade::log::level::error,
				"[Kaiozen] S_NATIVE_PRESENT_HDR10=FAIL NO_SWAPCHAIN3");
			logged_no_swapchain3 = true;
		}
		return;
	}

	const HRESULT color_hr = swapchain3->SetColorSpace1(
		DXGI_COLOR_SPACE_RGB_FULL_G2084_NONE_P2020);

	HRESULT metadata_hr = E_NOINTERFACE;
	com_ptr<IDXGISwapChain4> swapchain4;
	if (SUCCEEDED(swapchain->QueryInterface(&swapchain4)) &&
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
		metadata.MaxContentLightLevel = 1000;
		metadata.MaxFrameAverageLightLevel = 400;

		metadata_hr = swapchain4->SetHDRMetaData(
			DXGI_HDR_METADATA_TYPE_HDR10,
			sizeof(metadata),
			&metadata);
	}

	static bool logged_success = false;
	static bool logged_failure = false;

	if (SUCCEEDED(color_hr))
	{
		if (!logged_success)
		{
			reshade::log::message(
				reshade::log::level::info,
				"[Kaiozen] S_NATIVE_PRESENT_HDR10=YES "
				"COLORSPACE_IMMEDIATE_BEFORE_PRESENT=YES "
				"metadata_hr=0x%08X",
				static_cast<unsigned int>(metadata_hr));
			logged_success = true;
		}
	}
	else if (!logged_failure)
	{
		reshade::log::message(
			reshade::log::level::error,
			"[Kaiozen] S_NATIVE_PRESENT_HDR10=FAIL "
			"SETCOLORSPACE_hr=0x%08X",
			static_cast<unsigned int>(color_hr));
		logged_failure = true;
	}
}
'''

if GUID_NAME not in dxgi:
    dxgi = dxgi.replace(
        dxgi_guid_anchor,
        dxgi_guid_anchor + helper,
        1,
    )

present_anchor = "\tconst HRESULT hr = _orig->Present(SyncInterval, Flags);\n"
if dxgi.count(present_anchor) != 1:
    raise SystemExit(
        f"FAIL: S Present anchor count={dxgi.count(present_anchor)}"
    )

dxgi = dxgi.replace(
    present_anchor,
    "\tkaiozen_hsr_apply_hdr_at_native_present(_orig, _direct3d_version);\n"
    + present_anchor,
    1,
)

present1_anchor = (
    "\tconst HRESULT hr = "
    "static_cast<IDXGISwapChain1 *>(_orig)->Present1("
    "SyncInterval, PresentFlags, pPresentParameters);\n"
)
if dxgi.count(present1_anchor) != 1:
    raise SystemExit(
        f"FAIL: S Present1 anchor count={dxgi.count(present1_anchor)}"
    )

dxgi = dxgi.replace(
    present1_anchor,
    "\tkaiozen_hsr_apply_hdr_at_native_present(_orig, _direct3d_version);\n"
    + present1_anchor,
    1,
)

dxgi_path.write_text(dxgi, encoding="utf-8", newline="\n")

print("HOTFIX=S")
print("ATOMIC_NATIVE_PRESENT_HDR=YES")
print("ARMED_FAIL_SAFE=YES")
print("PRESENT=PATCHED")
print("PRESENT1=PATCHED")
