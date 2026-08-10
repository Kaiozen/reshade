from pathlib import Path


def read(p):
    return Path(p).read_text(encoding='utf-8-sig')


def write(p, s):
    Path(p).write_text(s, encoding='utf-8', newline='\n')


def once(s, old, new, label):
    c = s.count(old)
    if c != 1:
        raise RuntimeError(f'{label}: expected 1, found {c}')
    return s.replace(old, new, 1)


# ======================================================================================
# D3D12: native PSO shader-bytecode transplant only. No ReShade/RenoDX add-on runtime.
# ======================================================================================
p = Path('source/d3d12/d3d12.cpp')
s = read(p)
if 'KAIOZEN V24 NATIVE HDR SHADER TRANSPLANT' in s:
    raise RuntimeError('already patched')

s = once(
    s,
    '#include "addon_manager.hpp"\n',
    '#include "addon_manager.hpp"\n'
    '#include "v24hdr_renodx_shaders.hpp"\n'
    '#include "v24hdr_crc32_hash.hpp"\n'
    '#include <atomic>\n'
    '#include <cwchar>\n',
    'd3d12 include',
)

anchor = 'std::shared_mutex g_d3d12_adapter_mutex;\n'
helper = r'''

// KAIOZEN V24 NATIVE HDR SHADER TRANSPLANT
// Fail-safe design: if the sentinel file is absent, this code is inert.
// The game always receives the native ID3D12Device and native PSOs.
static bool v24hdr_enabled()
{
    static const bool enabled = []() {
        wchar_t exe[MAX_PATH] = {};
        const DWORD n = GetModuleFileNameW(nullptr, exe, MAX_PATH);
        if (n == 0 || n >= MAX_PATH)
            return false;
        wchar_t *slash = wcsrchr(exe, L'\\');
        if (slash == nullptr)
            return false;
        *(slash + 1) = L'\0';
        wcscat_s(exe, L"KAIOZEN_ZZZ_NATIVE_HDR.ENABLE");
        return GetFileAttributesW(exe) != INVALID_FILE_ATTRIBUTES;
    }();
    return enabled;
}

static const v24hdr_shader_blob *v24hdr_find_shader(uint32_t crc)
{
    for (size_t i = 0; i < g_v24hdr_shader_count; ++i)
        if (g_v24hdr_shaders[i].crc32 == crc)
            return &g_v24hdr_shaders[i];
    return nullptr;
}

static std::atomic<uint64_t> g_v24hdr_graphics_calls{0};
static std::atomic<uint64_t> g_v24hdr_replacements{0};
static std::atomic<uint64_t> g_v24hdr_pso_fallbacks{0};

static bool v24hdr_replace_bytecode(D3D12_SHADER_BYTECODE &bc, const char *stage, uint32_t &matched_crc)
{
    matched_crc = 0;
    if (bc.pShaderBytecode == nullptr || bc.BytecodeLength == 0)
        return false;

    // Use the exact same CRC implementation RenoDX itself uses. The header is
    // copied verbatim from the pinned RenoDX source during the build.
    const uint32_t crc = compute_crc32(
        static_cast<const uint8_t *>(bc.pShaderBytecode),
        bc.BytecodeLength);
    const auto *replacement = v24hdr_find_shader(crc);
    if (replacement == nullptr)
        return false;

    matched_crc = crc;
    bc.pShaderBytecode = replacement->data;
    bc.BytecodeLength = replacement->size;

    const uint64_t count = ++g_v24hdr_replacements;
    if (count <= 512)
    {
        reshade::log::message(
            reshade::log::level::info,
            "KAIOZEN V24 NATIVE HDR SHADER TRANSPLANT: REPLACE stage=%s crc=0x%08X bytes=%llu total=%llu.",
            stage,
            crc,
            static_cast<unsigned long long>(replacement->size),
            static_cast<unsigned long long>(count));
    }
    return true;
}

static HRESULT STDMETHODCALLTYPE v24hdr_CreateGraphicsPipelineState(
    ID3D12Device *device,
    const D3D12_GRAPHICS_PIPELINE_STATE_DESC *desc,
    REFIID riid,
    void **ppPipelineState)
{
    const auto trampoline = reshade::hooks::call(
        v24hdr_CreateGraphicsPipelineState,
        reshade::hooks::vtable_from_instance(device) + 10);
    ++g_v24hdr_graphics_calls;

    if (!v24hdr_enabled() || desc == nullptr)
        return trampoline(device, desc, riid, ppPipelineState);

    D3D12_GRAPHICS_PIPELINE_STATE_DESC d = *desc;
    uint32_t crc = 0;
    // The pinned ZZZ replacement-source gate proves every hash-addressed D3D12
    // RenoDX shader is a pixel shader. Touch PS only. All other stages remain
    // byte-for-byte the game originals.
    const bool changed = v24hdr_replace_bytecode(d.PS, "PS", crc);

    if (!changed)
        return trampoline(device, desc, riid, ppPipelineState);

    if (ppPipelineState != nullptr)
        *ppPipelineState = nullptr;

    HRESULT hr = trampoline(device, &d, riid, ppPipelineState);
    if (FAILED(hr))
    {
        // A replacement that the native compiler rejects must never prevent the
        // game from starting. Retry the exact original PSO unchanged.
        ++g_v24hdr_pso_fallbacks;
        reshade::log::message(
            reshade::log::level::warning,
            "KAIOZEN V24 NATIVE HDR SHADER TRANSPLANT: PSO_FALLBACK type=graphics replacement_hr=0x%08X.",
            static_cast<unsigned>(hr));
        if (ppPipelineState != nullptr)
            *ppPipelineState = nullptr;
        hr = trampoline(device, desc, riid, ppPipelineState);
    }
    return hr;
}

static void v24hdr_install_device_hooks(ID3D12Device *device)
{
    if (!v24hdr_enabled() || device == nullptr)
        return;

    auto *vtable = reshade::hooks::vtable_from_instance(device);
    const bool graphics = reshade::hooks::install(
        "ID3D12Device::CreateGraphicsPipelineState [V24HDR]",
        vtable,
        10,
        &v24hdr_CreateGraphicsPipelineState);
    reshade::log::message(
        reshade::log::level::info,
        "KAIOZEN V24 NATIVE HDR SHADER TRANSPLANT: ACTIVE shader_count=%llu native_psos=1 addons=0 pixel_only=1 graphics_hook=%u.",
        static_cast<unsigned long long>(g_v24hdr_shader_count),
        graphics ? 1u : 0u);
}
'''
s = once(s, anchor, anchor + helper, 'd3d12 helper')

# This marker exists in the already-patched V24 native-device bridge. Install
# native PSO vtable hooks immediately before V24 returns the original device.
early = (
    '#if RESHADE_ADDON >= 2\n'
    '\t// Balance the temporary add-on-manager reference without constructing a COM proxy.\n'
)
insert = (
    '\t// V24HDR: native vtable hooks only; game-visible COM identity remains unchanged.\n'
    '\tv24hdr_install_device_hooks(static_cast<ID3D12Device *>(*ppDevice));\n' + early
)
s = once(s, early, insert, 'v24 native early return hook')
write(p, s)


# ======================================================================================
# DXGI creation: rewrite only the proven ZZZ CreateSwapChainForHwnd R8 path to R10.
# Fail open: if R10 creation fails, immediately retry original R8.
# ======================================================================================
p = Path('source/dxgi/dxgi.cpp')
s = read(p)
s = once(s, '#include "addon_manager.hpp"\n', '#include "addon_manager.hpp"\n#include <cwchar>\n', 'dxgi include')
anchor = 'extern bool is_windows7();\n'
helper = r'''
static bool v24hdr_dxgi_enabled()
{
    static const bool enabled = []() {
        wchar_t exe[MAX_PATH] = {};
        const DWORD n = GetModuleFileNameW(nullptr, exe, MAX_PATH);
        if (n == 0 || n >= MAX_PATH)
            return false;
        wchar_t *slash = wcsrchr(exe, L'\\');
        if (slash == nullptr)
            return false;
        *(slash + 1) = L'\0';
        wcscat_s(exe, L"KAIOZEN_ZZZ_NATIVE_HDR.ENABLE");
        return GetFileAttributesW(exe) != INVALID_FILE_ATTRIBUTES;
    }();
    return enabled;
}

static bool v24hdr_is_native_d3d12_queue(IUnknown *obj)
{
    if (!v24hdr_dxgi_enabled() || obj == nullptr)
        return false;
    ID3D12CommandQueue *queue = nullptr;
    const HRESULT hr = obj->QueryInterface(IID_PPV_ARGS(&queue));
    if (queue != nullptr)
        queue->Release();
    return SUCCEEDED(hr);
}

static bool v24hdr_set_hdr10(IUnknown *swapchain)
{
    if (!v24hdr_dxgi_enabled() || swapchain == nullptr)
        return false;
    IDXGISwapChain3 *sc3 = nullptr;
    if (FAILED(swapchain->QueryInterface(IID_PPV_ARGS(&sc3))) || sc3 == nullptr)
        return false;

    UINT support = 0;
    const HRESULT check = sc3->CheckColorSpaceSupport(
        DXGI_COLOR_SPACE_RGB_FULL_G2084_NONE_P2020,
        &support);
    if (FAILED(check) || (support & DXGI_SWAP_CHAIN_COLOR_SPACE_SUPPORT_FLAG_PRESENT) == 0)
    {
        reshade::log::message(
            reshade::log::level::warning,
            "KAIOZEN V24 NATIVE HDR SHADER TRANSPLANT: HDR10_COLORSPACE_UNSUPPORTED check=0x%08X support=0x%X; SetColorSpace1 skipped.",
            static_cast<unsigned>(check),
            support);
        sc3->Release();
        return false;
    }

    const HRESULT set = sc3->SetColorSpace1(
        DXGI_COLOR_SPACE_RGB_FULL_G2084_NONE_P2020);
    reshade::log::message(
        SUCCEEDED(set) ? reshade::log::level::info : reshade::log::level::warning,
        "KAIOZEN V24 NATIVE HDR SHADER TRANSPLANT: HDR10_COLORSPACE check=0x%08X support=0x%X set=0x%08X.",
        static_cast<unsigned>(check),
        support,
        static_cast<unsigned>(set));
    sc3->Release();
    return SUCCEEDED(set);
}
'''
s = once(s, anchor, anchor + helper, 'dxgi helper')

fn = 'HRESULT STDMETHODCALLTYPE IDXGIFactory2_CreateSwapChainForHwnd_Impl'
pos = s.find(fn)
if pos < 0:
    raise RuntimeError('CreateSwapChainForHwnd impl missing')
end = s.find('HRESULT STDMETHODCALLTYPE IDXGIFactory2_CreateSwapChainForCoreWindow', pos)
if end < 0:
    raise RuntimeError('CreateSwapChainForHwnd end missing')
chunk = s[pos:end]

old = '\tDXGI_SWAP_CHAIN_DESC1 desc = *pDesc;\n\tUINT sync_interval = UINT_MAX;\n'
new = (
    '\tDXGI_SWAP_CHAIN_DESC1 desc = *pDesc;\n'
    '\tbool v24hdr_format_modified = false;\n'
    '\tif (v24hdr_is_native_d3d12_queue(pDevice) && desc.Format == DXGI_FORMAT_R8G8B8A8_UNORM)\n'
    '\t{\n'
    '\t\tdesc.Format = DXGI_FORMAT_R10G10B10A2_UNORM;\n'
    '\t\tv24hdr_format_modified = true;\n'
    '\t\treshade::log::message(reshade::log::level::info, "KAIOZEN V24 NATIVE HDR SHADER TRANSPLANT: SWAPCHAIN_CREATE R8_TO_R10.");\n'
    '\t}\n'
    '\tUINT sync_interval = UINT_MAX;\n'
)
if chunk.count(old) != 1:
    raise RuntimeError(f'hwnd desc anchor count={chunk.count(old)}')
chunk = chunk.replace(old, new, 1)

old = '\tconst bool modified = dump_and_modify_swapchain_desc(direct3d_version, desc, sync_interval, &fullscreen_desc, hWnd);\n'
new = '\tbool modified = dump_and_modify_swapchain_desc(direct3d_version, desc, sync_interval, &fullscreen_desc, hWnd) || v24hdr_format_modified;\n'
if chunk.count(old) != 1:
    raise RuntimeError(f'hwnd modified anchor count={chunk.count(old)}')
chunk = chunk.replace(old, new, 1)

old = (
    '\tg_in_dxgi_runtime = true;\n'
    '\tconst HRESULT hr = trampoline(pFactory, pDevice, hWnd, &desc, fullscreen_desc.Windowed ? nullptr : &fullscreen_desc, pRestrictToOutput, ppSwapChain);\n'
    '\tg_in_dxgi_runtime = false;\n'
)
new = (
    '\tg_in_dxgi_runtime = true;\n'
    '\tHRESULT hr = trampoline(pFactory, pDevice, hWnd, &desc, fullscreen_desc.Windowed ? nullptr : &fullscreen_desc, pRestrictToOutput, ppSwapChain);\n'
    '\tg_in_dxgi_runtime = false;\n'
    '\tif (FAILED(hr) && v24hdr_format_modified)\n'
    '\t{\n'
    '\t\treshade::log::message(reshade::log::level::warning, "KAIOZEN V24 NATIVE HDR SHADER TRANSPLANT: SWAPCHAIN_CREATE_FALLBACK_R8 first_hr=0x%08X.", static_cast<unsigned>(hr));\n'
    '\t\tdesc = *pDesc;\n'
    '\t\tif (0 == desc.BufferUsage && direct3d_version == reshade::api::device_api::d3d12)\n'
    '\t\t\tdesc.BufferUsage = DXGI_USAGE_RENDER_TARGET_OUTPUT;\n'
    '\t\tg_in_dxgi_runtime = true;\n'
    '\t\thr = trampoline(pFactory, pDevice, hWnd, &desc, fullscreen_desc.Windowed ? nullptr : &fullscreen_desc, pRestrictToOutput, ppSwapChain);\n'
    '\t\tg_in_dxgi_runtime = false;\n'
    '\t\tv24hdr_format_modified = false;\n'
    '\t\tmodified = false;\n'
    '\t}\n'
)
if chunk.count(old) != 1:
    raise RuntimeError(f'hwnd native call anchor count={chunk.count(old)}')
chunk = chunk.replace(old, new, 1)

old = '\tinit_swapchain_proxy(pFactory, direct3d_version, device_proxy, pDevice, *ppSwapChain, desc.BufferUsage, sync_interval,\n'
new = (
    '\tif (v24hdr_format_modified)\n'
    '\t\tv24hdr_set_hdr10(*ppSwapChain);\n'
    '\tinit_swapchain_proxy(pFactory, direct3d_version, device_proxy, pDevice, *ppSwapChain, desc.BufferUsage, sync_interval,\n'
)
if chunk.count(old) != 1:
    raise RuntimeError(f'hwnd init anchor count={chunk.count(old)}')
chunk = chunk.replace(old, new, 1)
s = s[:pos] + chunk + s[end:]
write(p, s)


# ======================================================================================
# DXGI resize: preserve the game's original R8 descriptor, but send R10 to the native
# swap chain. If R10 resize fails, retry original R8. Reassert HDR10 after successful R10.
# ======================================================================================
p = Path('source/dxgi/dxgi_swapchain.cpp')
s = read(p)
s = once(s, '#include "runtime_manager.hpp"\n', '#include "runtime_manager.hpp"\n#include <cwchar>\n', 'swap include')
anchor = 'thread_local bool g_in_dxgi_runtime = false;\n'
helper = r'''
static bool v24hdr_resize_enabled()
{
    static const bool enabled = []() {
        wchar_t exe[MAX_PATH] = {};
        const DWORD n = GetModuleFileNameW(nullptr, exe, MAX_PATH);
        if (n == 0 || n >= MAX_PATH)
            return false;
        wchar_t *slash = wcsrchr(exe, L'\\');
        if (slash == nullptr)
            return false;
        *(slash + 1) = L'\0';
        wcscat_s(exe, L"KAIOZEN_ZZZ_NATIVE_HDR.ENABLE");
        return GetFileAttributesW(exe) != INVALID_FILE_ATTRIBUTES;
    }();
    return enabled;
}

static bool v24hdr_resize_hdr10(IDXGISwapChain *sc)
{
    if (!v24hdr_resize_enabled() || sc == nullptr)
        return false;
    IDXGISwapChain3 *sc3 = nullptr;
    if (FAILED(sc->QueryInterface(IID_PPV_ARGS(&sc3))) || sc3 == nullptr)
        return false;
    UINT support = 0;
    const HRESULT check = sc3->CheckColorSpaceSupport(
        DXGI_COLOR_SPACE_RGB_FULL_G2084_NONE_P2020,
        &support);
    if (FAILED(check) || (support & DXGI_SWAP_CHAIN_COLOR_SPACE_SUPPORT_FLAG_PRESENT) == 0)
    {
        reshade::log::message(
            reshade::log::level::warning,
            "KAIOZEN V24 NATIVE HDR SHADER TRANSPLANT: HDR10_AFTER_RESIZE_UNSUPPORTED check=0x%08X support=0x%X; SetColorSpace1 skipped.",
            static_cast<unsigned>(check),
            support);
        sc3->Release();
        return false;
    }
    const HRESULT hr = sc3->SetColorSpace1(
        DXGI_COLOR_SPACE_RGB_FULL_G2084_NONE_P2020);
    reshade::log::message(
        SUCCEEDED(hr) ? reshade::log::level::info : reshade::log::level::warning,
        "KAIOZEN V24 NATIVE HDR SHADER TRANSPLANT: HDR10_AFTER_RESIZE check=0x%08X support=0x%X set=0x%08X.",
        static_cast<unsigned>(check),
        support,
        static_cast<unsigned>(hr));
    sc3->Release();
    return SUCCEEDED(hr);
}
'''
s = once(s, anchor, anchor + helper, 'swap helper')

# Patch ResizeBuffers structurally within its function only.
start = s.find('HRESULT STDMETHODCALLTYPE DXGISwapChain::ResizeBuffers(')
end = s.find('HRESULT STDMETHODCALLTYPE DXGISwapChain::ResizeTarget(', start)
if start < 0 or end < 0:
    raise RuntimeError('ResizeBuffers boundaries missing')
chunk = s[start:end]
old = (
    '\tg_in_dxgi_runtime = true;\n'
    '\tconst HRESULT hr = _orig->ResizeBuffers(BufferCount, Width, Height, NewFormat, SwapChainFlags);\n'
    '\tg_in_dxgi_runtime = was_in_dxgi_runtime;\n'
)
new = (
    '\tconst DXGI_FORMAT v24hdr_requested_format = NewFormat;\n'
    '\tconst bool v24hdr_resize_modified = v24hdr_resize_enabled() && _direct3d_version == reshade::api::device_api::d3d12 && NewFormat == DXGI_FORMAT_R8G8B8A8_UNORM;\n'
    '\tif (v24hdr_resize_modified)\n'
    '\t{\n'
    '\t\tNewFormat = DXGI_FORMAT_R10G10B10A2_UNORM;\n'
    '#if RESHADE_ADDON\n'
    '\t\t_is_desc_modified = true; // Keep reporting the game-requested R8 descriptor.\n'
    '#endif\n'
    '\t\treshade::log::message(reshade::log::level::info, "KAIOZEN V24 NATIVE HDR SHADER TRANSPLANT: RESIZE R8_TO_R10.");\n'
    '\t}\n'
    '\tg_in_dxgi_runtime = true;\n'
    '\tHRESULT hr = _orig->ResizeBuffers(BufferCount, Width, Height, NewFormat, SwapChainFlags);\n'
    '\tg_in_dxgi_runtime = was_in_dxgi_runtime;\n'
    '\tbool v24hdr_resize_active = v24hdr_resize_modified && SUCCEEDED(hr);\n'
    '\tif (FAILED(hr) && v24hdr_resize_modified)\n'
    '\t{\n'
    '\t\treshade::log::message(reshade::log::level::warning, "KAIOZEN V24 NATIVE HDR SHADER TRANSPLANT: RESIZE_FALLBACK_R8 first_hr=0x%08X.", static_cast<unsigned>(hr));\n'
    '\t\tg_in_dxgi_runtime = true;\n'
    '\t\thr = _orig->ResizeBuffers(BufferCount, Width, Height, v24hdr_requested_format, SwapChainFlags);\n'
    '\t\tg_in_dxgi_runtime = was_in_dxgi_runtime;\n'
    '#if RESHADE_ADDON\n'
    '\t\tif (SUCCEEDED(hr)) _is_desc_modified = false;\n'
    '#endif\n'
    '\t\tv24hdr_resize_active = false;\n'
    '\t}\n'
)
if chunk.count(old) != 1:
    raise RuntimeError(f'ResizeBuffers native call anchor count={chunk.count(old)}')
chunk = chunk.replace(old, new, 1)
old = '\tif (SUCCEEDED(hr))\n\t{\n\t\ton_init(true);\n\t}\n'
new = '\tif (SUCCEEDED(hr))\n\t{\n\t\tif (v24hdr_resize_active) v24hdr_resize_hdr10(_orig);\n\t\ton_init(true);\n\t}\n'
if chunk.count(old) != 1:
    raise RuntimeError(f'ResizeBuffers success anchor count={chunk.count(old)}')
chunk = chunk.replace(old, new, 1)
s = s[:start] + chunk + s[end:]

# Patch ResizeBuffers1 independently.
start = s.find('HRESULT STDMETHODCALLTYPE DXGISwapChain::ResizeBuffers1(')
end = s.find('HRESULT STDMETHODCALLTYPE DXGISwapChain::SetHDRMetaData(', start)
if start < 0 or end < 0:
    raise RuntimeError('ResizeBuffers1 boundaries missing')
chunk = s[start:end]
old = (
    '\tg_in_dxgi_runtime = true;\n'
    '\tconst HRESULT hr = static_cast<IDXGISwapChain3 *>(_orig)->ResizeBuffers1(BufferCount, Width, Height, NewFormat, SwapChainFlags, pCreationNodeMask, present_queues.p);\n'
    '\tg_in_dxgi_runtime = was_in_dxgi_runtime;\n'
)
new = (
    '\tconst DXGI_FORMAT v24hdr_requested_format = NewFormat;\n'
    '\tconst bool v24hdr_resize_modified = v24hdr_resize_enabled() && _direct3d_version == reshade::api::device_api::d3d12 && NewFormat == DXGI_FORMAT_R8G8B8A8_UNORM;\n'
    '\tif (v24hdr_resize_modified)\n'
    '\t{\n'
    '\t\tNewFormat = DXGI_FORMAT_R10G10B10A2_UNORM;\n'
    '#if RESHADE_ADDON\n'
    '\t\t_is_desc_modified = true;\n'
    '#endif\n'
    '\t\treshade::log::message(reshade::log::level::info, "KAIOZEN V24 NATIVE HDR SHADER TRANSPLANT: RESIZE1 R8_TO_R10.");\n'
    '\t}\n'
    '\tg_in_dxgi_runtime = true;\n'
    '\tHRESULT hr = static_cast<IDXGISwapChain3 *>(_orig)->ResizeBuffers1(BufferCount, Width, Height, NewFormat, SwapChainFlags, pCreationNodeMask, present_queues.p);\n'
    '\tg_in_dxgi_runtime = was_in_dxgi_runtime;\n'
    '\tbool v24hdr_resize_active = v24hdr_resize_modified && SUCCEEDED(hr);\n'
    '\tif (FAILED(hr) && v24hdr_resize_modified)\n'
    '\t{\n'
    '\t\treshade::log::message(reshade::log::level::warning, "KAIOZEN V24 NATIVE HDR SHADER TRANSPLANT: RESIZE1_FALLBACK_R8 first_hr=0x%08X.", static_cast<unsigned>(hr));\n'
    '\t\tg_in_dxgi_runtime = true;\n'
    '\t\thr = static_cast<IDXGISwapChain3 *>(_orig)->ResizeBuffers1(BufferCount, Width, Height, v24hdr_requested_format, SwapChainFlags, pCreationNodeMask, present_queues.p);\n'
    '\t\tg_in_dxgi_runtime = was_in_dxgi_runtime;\n'
    '#if RESHADE_ADDON\n'
    '\t\tif (SUCCEEDED(hr)) _is_desc_modified = false;\n'
    '#endif\n'
    '\t\tv24hdr_resize_active = false;\n'
    '\t}\n'
)
if chunk.count(old) != 1:
    raise RuntimeError(f'ResizeBuffers1 native call anchor count={chunk.count(old)}')
chunk = chunk.replace(old, new, 1)
old = '\tif (SUCCEEDED(hr))\n\t{\n\t\ton_init(true);\n\t}\n'
new = '\tif (SUCCEEDED(hr))\n\t{\n\t\tif (v24hdr_resize_active) v24hdr_resize_hdr10(_orig);\n\t\ton_init(true);\n\t}\n'
if chunk.count(old) != 1:
    raise RuntimeError(f'ResizeBuffers1 success anchor count={chunk.count(old)}')
chunk = chunk.replace(old, new, 1)
s = s[:start] + chunk + s[end:]
write(p, s)

Path('v24hdr-patch-report.txt').write_text(
    '''KAIOZEN_V24_NATIVE_HDR_SHADER_TRANSPLANT_PATCH=PASS
GAME_VISIBLE_D3D12_OBJECTS=NATIVE
RENODX_ADDON=ABSENT
RENODX_SHADER_CONSTANT_BUFFER=BAKED
CRC_IMPLEMENTATION=PINNED_RENODX_EXACT_HEADER
NATIVE_GRAPHICS_PSO_HOOK=PIXEL_SHADER_ONLY
NATIVE_COMPUTE_PSO_HOOK=ABSENT_BY_DESIGN
PSO_REPLACEMENT_FAILURE=SAFE_ORIGINAL_FALLBACK
SWAPCHAIN_CREATE_R8_TO_R10=ENABLED
SWAPCHAIN_CREATE_FAILURE=SAFE_R8_FALLBACK
RESIZE_R8_TO_R10=ENABLED
RESIZE_FAILURE=SAFE_R8_FALLBACK
HDR10_COLORSPACE_REASSERT=SUPPORT_GATED_NO_UNSUPPORTED_CALL
SENTINEL_FAILSAFE=ENABLED
''',
    encoding='utf-8',
    newline='\n',
)
print(Path('v24hdr-patch-report.txt').read_text())
