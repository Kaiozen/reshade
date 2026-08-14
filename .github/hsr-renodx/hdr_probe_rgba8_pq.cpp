#define WIN32_LEAN_AND_MEAN
#include <windows.h>

#include <d3d11.h>
#include <dxgi1_6.h>
#include <wrl/client.h>

#include <cmath>
#include <cstdarg>
#include <cstdio>
#include <string>

#pragma comment(lib, "d3d11.lib")
#pragma comment(lib, "dxgi.lib")
#pragma comment(lib, "user32.lib")

using Microsoft::WRL::ComPtr;

#ifndef KAIOZEN_HDR10
#define KAIOZEN_HDR10 0
#endif

static FILE* g_log = nullptr;
static bool g_running = true;

static void Log(const char* fmt, ...)
{
    char buffer[2048];

    va_list args;
    va_start(args, fmt);
    vsnprintf(buffer, sizeof(buffer), fmt, args);
    va_end(args);

    printf("%s\n", buffer);

    if (g_log != nullptr)
    {
        fprintf(g_log, "%s\n", buffer);
        fflush(g_log);
    }
}

static std::wstring GetLogPath()
{
    wchar_t path[MAX_PATH] = {};
    GetModuleFileNameW(nullptr, path, MAX_PATH);

    std::wstring result(path);

    const size_t slash = result.find_last_of(L"\\/");
    if (slash != std::wstring::npos)
        result.resize(slash + 1);
    else
        result.clear();

#if KAIOZEN_HDR10
    result += L"Kaiozen-DX11-RGBA8-PQ-Probe.log";
#else
    result += L"Kaiozen-DX11-scRGB-Probe.log";
#endif

    return result;
}

static LRESULT CALLBACK WindowProc(
    HWND hwnd,
    UINT message,
    WPARAM wparam,
    LPARAM lparam)
{
    switch (message)
    {
        case WM_CLOSE:
            DestroyWindow(hwnd);
            return 0;

        case WM_DESTROY:
            g_running = false;
            PostQuitMessage(0);
            return 0;

        case WM_KEYDOWN:
            if (wparam == VK_ESCAPE)
            {
                DestroyWindow(hwnd);
                return 0;
            }
            break;
    }

    return DefWindowProcW(
        hwnd,
        message,
        wparam,
        lparam);
}

static float PQEncode(float nits)
{
    const double m1 = 2610.0 / 16384.0;
    const double m2 = 2523.0 / 32.0;
    const double c1 = 3424.0 / 4096.0;
    const double c2 = 2413.0 / 128.0;
    const double c3 = 2392.0 / 128.0;

    double L = nits / 10000.0;

    if (L < 0.0)
        L = 0.0;
    if (L > 1.0)
        L = 1.0;

    const double Lm1 = std::pow(L, m1);

    return static_cast<float>(
        std::pow(
            (c1 + c2 * Lm1) /
            (1.0 + c3 * Lm1),
            m2));
}

static const char* FeatureLevelName(D3D_FEATURE_LEVEL level)
{
    switch (level)
    {
        case D3D_FEATURE_LEVEL_11_0: return "11.0";
        case D3D_FEATURE_LEVEL_10_1: return "10.1";
        case D3D_FEATURE_LEVEL_10_0: return "10.0";
        default: return "other";
    }
}

int WINAPI wWinMain(
    HINSTANCE instance,
    HINSTANCE,
    PWSTR,
    int)
{
    const std::wstring log_path = GetLogPath();
    g_log = _wfopen(log_path.c_str(), L"w");

    Log("KAIOZEN_DX11_HDR_PROBE=1");

#if KAIOZEN_HDR10
    Log("MODE=HDR10_RGBA8_PQ");
#else
    Log("MODE=scRGB_FP16");
#endif

    Log("PROCESS_ARCH=x64");

    const wchar_t* class_name =
        L"KaiozenDX11HDRProbeWindow";

    WNDCLASSEXW wc = {};
    wc.cbSize = sizeof(wc);
    wc.hInstance = instance;
    wc.lpfnWndProc = WindowProc;
    wc.lpszClassName = class_name;
    wc.hCursor = LoadCursor(nullptr, IDC_ARROW);

    if (!RegisterClassExW(&wc))
    {
        Log(
            "RegisterClassExW=FAIL error=%lu",
            GetLastError());

        return 1;
    }

    RECT rect = {0, 0, 1280, 720};

    AdjustWindowRect(
        &rect,
        WS_OVERLAPPEDWINDOW,
        FALSE);

    HWND hwnd = CreateWindowExW(
        0,
        class_name,
        L"Kaiozen DX11 HDR Probe",
        WS_OVERLAPPEDWINDOW,
        CW_USEDEFAULT,
        CW_USEDEFAULT,
        rect.right - rect.left,
        rect.bottom - rect.top,
        nullptr,
        nullptr,
        instance,
        nullptr);

    if (hwnd == nullptr)
    {
        Log(
            "CreateWindowExW=FAIL error=%lu",
            GetLastError());

        return 1;
    }

    ShowWindow(hwnd, SW_SHOW);
    UpdateWindow(hwnd);

    ComPtr<IDXGIFactory2> factory;

    HRESULT hr = CreateDXGIFactory2(
        0,
        IID_PPV_ARGS(&factory));

    Log(
        "CreateDXGIFactory2=0x%08lX",
        static_cast<unsigned long>(hr));

    if (FAILED(hr))
        return 2;

    ComPtr<IDXGIAdapter1> adapter;

    hr = factory->EnumAdapters1(
        0,
        &adapter);

    Log(
        "EnumAdapters1=0x%08lX",
        static_cast<unsigned long>(hr));

    if (FAILED(hr))
        return 3;

    DXGI_ADAPTER_DESC1 adapter_desc = {};
    adapter->GetDesc1(&adapter_desc);

    char adapter_name[512] = {};
    WideCharToMultiByte(
        CP_UTF8,
        0,
        adapter_desc.Description,
        -1,
        adapter_name,
        sizeof(adapter_name),
        nullptr,
        nullptr);

    Log(
        "ADAPTER=%s",
        adapter_name);

    ComPtr<ID3D11Device> device;
    ComPtr<ID3D11DeviceContext> context;

    const D3D_FEATURE_LEVEL levels[] = {
        D3D_FEATURE_LEVEL_11_0,
        D3D_FEATURE_LEVEL_10_1,
        D3D_FEATURE_LEVEL_10_0
    };

    D3D_FEATURE_LEVEL actual_level = {};

    hr = D3D11CreateDevice(
        adapter.Get(),
        D3D_DRIVER_TYPE_UNKNOWN,
        nullptr,
        D3D11_CREATE_DEVICE_BGRA_SUPPORT,
        levels,
        ARRAYSIZE(levels),
        D3D11_SDK_VERSION,
        &device,
        &actual_level,
        &context);

    Log(
        "D3D11CreateDevice=0x%08lX",
        static_cast<unsigned long>(hr));

    Log(
        "FEATURE_LEVEL=%s",
        FeatureLevelName(actual_level));

    if (FAILED(hr))
        return 4;

    DXGI_SWAP_CHAIN_DESC1 desc = {};
    desc.Width = 1280;
    desc.Height = 720;

#if KAIOZEN_HDR10
    desc.Format =
        DXGI_FORMAT_R8G8B8A8_UNORM;
#else
    desc.Format =
        DXGI_FORMAT_R16G16B16A16_FLOAT;
#endif

    desc.Stereo = FALSE;
    desc.SampleDesc.Count = 1;
    desc.SampleDesc.Quality = 0;
    desc.BufferUsage =
        DXGI_USAGE_RENDER_TARGET_OUTPUT;
    desc.BufferCount = 2;
    desc.Scaling =
        DXGI_SCALING_STRETCH;
    desc.SwapEffect =
        DXGI_SWAP_EFFECT_FLIP_DISCARD;
    desc.AlphaMode =
        DXGI_ALPHA_MODE_IGNORE;
    desc.Flags = 0;

    ComPtr<IDXGISwapChain1> swapchain1;

    hr = factory->CreateSwapChainForHwnd(
        device.Get(),
        hwnd,
        &desc,
        nullptr,
        nullptr,
        &swapchain1);

    Log(
        "CreateSwapChainForHwnd=0x%08lX",
        static_cast<unsigned long>(hr));

    if (FAILED(hr))
        return 5;

    factory->MakeWindowAssociation(
        hwnd,
        DXGI_MWA_NO_ALT_ENTER);

    ComPtr<IDXGISwapChain3> swapchain3;

    hr = swapchain1.As(&swapchain3);

    Log(
        "Query_IDXGISwapChain3=0x%08lX",
        static_cast<unsigned long>(hr));

    if (FAILED(hr))
        return 6;

#if KAIOZEN_HDR10
    const DXGI_COLOR_SPACE_TYPE target_space =
        DXGI_COLOR_SPACE_RGB_FULL_G2084_NONE_P2020;
#else
    const DXGI_COLOR_SPACE_TYPE target_space =
        DXGI_COLOR_SPACE_RGB_FULL_G10_NONE_P709;
#endif

    UINT color_support = 0;

    hr = swapchain3->CheckColorSpaceSupport(
        target_space,
        &color_support);

    Log(
        "CheckColorSpaceSupport=0x%08lX support=0x%08X",
        static_cast<unsigned long>(hr),
        color_support);

    Log(
        "COLORSPACE_PRESENT_SUPPORT=%s",
        (color_support &
         DXGI_SWAP_CHAIN_COLOR_SPACE_SUPPORT_FLAG_PRESENT)
            ? "YES"
            : "NO");

    hr = swapchain3->SetColorSpace1(
        target_space);

    Log(
        "SetColorSpace1=0x%08lX",
        static_cast<unsigned long>(hr));

#if KAIOZEN_HDR10
    ComPtr<IDXGISwapChain4> swapchain4;

    if (SUCCEEDED(swapchain3.As(&swapchain4)))
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

        metadata.MaxMasteringLuminance =
            1000 * 10000;

        metadata.MinMasteringLuminance = 0;

        metadata.MaxContentLightLevel = 1000;
        metadata.MaxFrameAverageLightLevel = 400;

        HRESULT metadata_hr =
            swapchain4->SetHDRMetaData(
                DXGI_HDR_METADATA_TYPE_HDR10,
                sizeof(metadata),
                &metadata);

        Log(
            "SetHDRMetaData=0x%08lX",
            static_cast<unsigned long>(
                metadata_hr));
    }
    else
    {
        Log("IDXGISwapChain4=UNAVAILABLE");
    }
#endif

    ComPtr<IDXGIOutput> output;

    hr = swapchain1->GetContainingOutput(
        &output);

    Log(
        "GetContainingOutput=0x%08lX",
        static_cast<unsigned long>(hr));

    if (SUCCEEDED(hr) && output)
    {
        ComPtr<IDXGIOutput6> output6;

        HRESULT output6_hr =
            output.As(&output6);

        Log(
            "Query_IDXGIOutput6=0x%08lX",
            static_cast<unsigned long>(
                output6_hr));

        if (SUCCEEDED(output6_hr))
        {
            DXGI_OUTPUT_DESC1 output_desc = {};

            HRESULT desc_hr =
                output6->GetDesc1(
                    &output_desc);

            Log(
                "IDXGIOutput6_GetDesc1=0x%08lX",
                static_cast<unsigned long>(
                    desc_hr));

            if (SUCCEEDED(desc_hr))
            {
                Log(
                    "OUTPUT_COLORSPACE=%d",
                    static_cast<int>(
                        output_desc.ColorSpace));

                Log(
                    "OUTPUT_MIN_LUMINANCE=%.3f",
                    output_desc.MinLuminance);

                Log(
                    "OUTPUT_MAX_LUMINANCE=%.3f",
                    output_desc.MaxLuminance);

                Log(
                    "OUTPUT_MAX_FULL_FRAME_LUMINANCE=%.3f",
                    output_desc.MaxFullFrameLuminance);
            }
        }
    }

    ComPtr<ID3D11Texture2D> backbuffer;

    hr = swapchain1->GetBuffer(
        0,
        IID_PPV_ARGS(&backbuffer));

    Log(
        "GetBuffer=0x%08lX",
        static_cast<unsigned long>(hr));

    if (FAILED(hr))
        return 7;

    D3D11_TEXTURE2D_DESC actual_desc = {};
    backbuffer->GetDesc(&actual_desc);

    Log(
        "ACTUAL_BACKBUFFER_FORMAT=%u",
        static_cast<unsigned>(
            actual_desc.Format));

    Log(
        "ACTUAL_BACKBUFFER_SIZE=%ux%u",
        actual_desc.Width,
        actual_desc.Height);

    ComPtr<ID3D11RenderTargetView> rtv;

    hr = device->CreateRenderTargetView(
        backbuffer.Get(),
        nullptr,
        &rtv);

    Log(
        "CreateRenderTargetView=0x%08lX",
        static_cast<unsigned long>(hr));

    if (FAILED(hr))
        return 8;

    const float levels_nits[] = {
        80.0f,
        203.0f,
        400.0f,
        800.0f,
        1000.0f
    };

    constexpr int level_count =
        ARRAYSIZE(levels_nits);

    int current_level = 0;
    ULONGLONG next_change =
        GetTickCount64() + 2500;

    Log("PRESENT_LOOP=START");
    Log("ESC_TO_QUIT=YES");

    while (g_running)
    {
        MSG msg = {};

        while (PeekMessageW(
            &msg,
            nullptr,
            0,
            0,
            PM_REMOVE))
        {
            if (msg.message == WM_QUIT)
            {
                g_running = false;
                break;
            }

            TranslateMessage(&msg);
            DispatchMessageW(&msg);
        }

        if (!g_running)
            break;

        const float nits =
            levels_nits[current_level];

        float signal;

#if KAIOZEN_HDR10
        signal = PQEncode(nits);
#else
        // scRGB convention:
        // 1.0 linear = 80 nits.
        signal = nits / 80.0f;
#endif

        const float clear[4] = {
            signal,
            signal,
            signal,
            1.0f
        };

        context->ClearRenderTargetView(
            rtv.Get(),
            clear);

        hr = swapchain1->Present(1, 0);

        if (FAILED(hr))
        {
            Log(
                "Present=FAIL hr=0x%08lX",
                static_cast<unsigned long>(hr));

            break;
        }

        const ULONGLONG now =
            GetTickCount64();

        if (now >= next_change)
        {
#if KAIOZEN_HDR10
            wchar_t title[512] = {};
            swprintf_s(
                title,
                L"Kaiozen DX11 RGBA8 PQ Probe | %.0f nits | PQ %.5f | ESC quits",
                nits,
                signal);
#else
            wchar_t title[512] = {};
            swprintf_s(
                title,
                L"Kaiozen DX11 scRGB Probe | %.0f nits | linear %.4f | ESC quits",
                nits,
                signal);
#endif

            SetWindowTextW(
                hwnd,
                title);

            Log(
                "LEVEL nits=%.0f signal=%.6f",
                nits,
                signal);

            current_level =
                (current_level + 1) %
                level_count;

            next_change = now + 2500;
        }

        Sleep(1);
    }

    Log("PRESENT_LOOP=END");

    if (g_log != nullptr)
    {
        fclose(g_log);
        g_log = nullptr;
    }

    return 0;
}
