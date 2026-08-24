#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit(
        "usage: patch_reshade_hdr_state_latch_w11a.py <dxgi_swapchain.cpp>"
    )

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")

start_marker = "static const GUID KAIOZEN_HSR_HDR_ARMED_GUID =\n"
end_marker = "\nDXGISwapChain::DXGISwapChain("

if text.count(start_marker) != 1:
    raise SystemExit(
        f"FAIL: W11A helper start count={text.count(start_marker)}"
    )

start = text.index(start_marker)
end = text.find(end_marker, start)
if end < 0:
    raise SystemExit("FAIL: W11A constructor boundary not found")

old = text[start:end]

required = [
    "kaiozen_hsr_apply_hdr_at_native_present",
    "DXGI_COLOR_SPACE_RGB_FULL_G2084_NONE_P2020",
    "SetHDRMetaData",
    "W4B_NATIVE_PRESENT_HEARTBEAT",
]
for marker in required:
    if marker not in old:
        raise SystemExit(f"FAIL: W11A prerequisite missing: {marker}")

helper = r'''static const GUID KAIOZEN_HSR_HDR_ARMED_GUID =
{ 0x6a6f1d42, 0x4f0d, 0x4c8d,
{ 0x9f, 0x31, 0x7a, 0x6b, 0x4d, 0x31, 0x58, 0xa1 } };

static void kaiozen_hsr_apply_hdr_at_native_present(
    IDXGISwapChain *swapchain,
    reshade::api::device_api direct3d_version)
{
    if (direct3d_version != reshade::api::device_api::d3d11 ||
        swapchain == nullptr)
        return;

    UINT hdr_state = 0;
    UINT hdr_state_size = sizeof(hdr_state);
    if (FAILED(swapchain->GetPrivateData(
            KAIOZEN_HSR_HDR_ARMED_GUID,
            &hdr_state_size,
            &hdr_state)))
        return;

    static unsigned long long kaiozen_w11a_native_present_count = 0;
    ++kaiozen_w11a_native_present_count;

    // State 1 = armed by runtime initialization.
    // State 2 = persistent HDR state was applied successfully once.
    // Existing on_reset() clears the GUID. Runtime initialization re-arms
    // state 1, so a new swapchain generation naturally applies once again.
    if (hdr_state == 2)
    {
        if ((kaiozen_w11a_native_present_count % 300) == 0)
        {
            reshade::log::message(
                reshade::log::level::info,
                "[Kaiozen] W11A_NATIVE_PRESENT_HEARTBEAT count=%llu "
                "HDR_STATE_LATCHED=YES HDR_STATE_CALLS_THIS_PRESENT=0",
                kaiozen_w11a_native_present_count);
        }
        return;
    }

    if (hdr_state != 1)
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
                "[Kaiozen] W11A_HDR_STATE_LATCH=FAIL NO_SWAPCHAIN3");
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

    HRESULT latch_hr = E_FAIL;
    if (SUCCEEDED(color_hr) && SUCCEEDED(metadata_hr))
    {
        const UINT hdr_state_latched = 2;
        latch_hr = swapchain->SetPrivateData(
            KAIOZEN_HSR_HDR_ARMED_GUID,
            sizeof(hdr_state_latched),
            &hdr_state_latched);
    }

    static bool logged_success = false;
    static bool logged_failure = false;

    if (SUCCEEDED(color_hr) &&
        SUCCEEDED(metadata_hr) &&
        SUCCEEDED(latch_hr))
    {
        if (!logged_success)
        {
            reshade::log::message(
                reshade::log::level::info,
                "[Kaiozen] W11A_HDR_STATE_LATCH=ACTIVE "
                "COLORSPACE_CALLS_PER_SWAPCHAIN_GENERATION=1 "
                "METADATA_CALLS_PER_SWAPCHAIN_GENERATION=1 "
                "color_hr=0x%08X metadata_hr=0x%08X latch_hr=0x%08X",
                static_cast<unsigned int>(color_hr),
                static_cast<unsigned int>(metadata_hr),
                static_cast<unsigned int>(latch_hr));
            logged_success = true;
        }
    }
    else if (!logged_failure)
    {
        reshade::log::message(
            reshade::log::level::error,
            "[Kaiozen] W11A_HDR_STATE_LATCH=FAIL "
            "color_hr=0x%08X metadata_hr=0x%08X latch_hr=0x%08X",
            static_cast<unsigned int>(color_hr),
            static_cast<unsigned int>(metadata_hr),
            static_cast<unsigned int>(latch_hr));
        logged_failure = true;
    }
}
'''

text = text[:start] + helper + text[end:]
path.write_text(text, encoding="utf-8", newline="\n")

print("HOTFIX=W11A")
print("HDR_STATE_LATCH=YES")
print("COLORSPACE_PER_PRESENT=NO")
print("METADATA_PER_PRESENT=NO")
print("REAPPLY_AFTER_RESET=YES")
print("PQ_COPY_MATH_CHANGED=NO")
print("SWAPCHAIN_FORMAT_CHANGED=NO")
