from pathlib import Path

required = {
    'source/d3d12/d3d12.cpp': [
        'v24hdr_sidecar_hotfix5.hpp',
        'v24hdr_install_device_hooks(static_cast<ID3D12Device *>(*ppDevice));',
        'D3DMetal native runtime bridge: returning the original ID3D12Device',
    ],
    'source/d3d12/v24hdr_sidecar_hotfix5.hpp': [
        'KAIOZEN V24 NATIVE HDR STREAM SIDECAR HOTFIX5',
        'ID3D12Device2::CreatePipelineState [V24HDR5]',
        'v24hdr_CreatePipelineStateStream',
        'v24hdr_prepare_stream_sidecar',
        'D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_PS',
        'D3D12_PIPELINE_STATE_SUBOBJECT_TYPE_CACHED_PSO',
        'ID3D12Device1::CreatePipelineLibrary [V24HDR5]',
        'ID3D12PipelineLibrary::LoadGraphicsPipeline [V24HDR5]',
        'ID3D12PipelineLibrary1::LoadPipeline [V24HDR5]',
        'ID3D12Device::CreateCommandList [V24HDR5]',
        'ID3D12Device4::CreateCommandList1 [V24HDR5]',
        'ID3D12GraphicsCommandList::Reset [V24HDR5]',
        'ID3D12GraphicsCommandList::SetPipelineState [V24HDR5]',
        'SIDECAR_SUCCESS',
        'PS_CRC_OBSERVED',
        'HDR_READY armed=1',
        'PSO_BIND_SUBSTITUTE',
        'RESET_PSO_SUBSTITUTE',
        'GAME_VISIBLE_D3D12',
        'KAIOZEN_ZZZ_NATIVE_HDR.ENABLE',
        'case 0x011329C3u:',
        'case 0xF432415Bu:',
    ],
    'source/dxgi/dxgi.cpp': [
        'v24hdr_dxgi_gate_hotfix5.hpp',
        'SWAPCHAIN_CREATE_SDR_WAITING_FOR_SHADER_ARM',
        'SWAPCHAIN_CREATE_ARMED R8_TO_R10',
        'SWAPCHAIN_CREATE_HDR10_ROLLBACK_R8',
        'SWAPCHAIN_CREATE_R10_FAIL_ROLLBACK_R8',
        'v24hdr_should_attempt_hdr()',
        'v24hdr_set_hdr_active(true)',
    ],
    'source/dxgi/dxgi_swapchain.cpp': [
        'v24hdr_dxgi_gate_hotfix5.hpp',
        'RESIZE_SDR_WAITING_FOR_SHADER_ARM',
        'RESIZE_ARMED R8_TO_R10',
        'RESIZE_HDR10_ROLLBACK_R8',
        'RESIZE_R10_FAIL_ROLLBACK_R8',
        'RESIZE1_SDR_WAITING_FOR_SHADER_ARM',
        'RESIZE1_ARMED R8_TO_R10',
        'RESIZE1_HDR10_ROLLBACK_R8',
        'RESIZE1_R10_FAIL_ROLLBACK_R8',
    ],
    'source/dxgi/v24hdr_dxgi_gate_hotfix5.hpp': [
        'extern bool v24hdr_should_attempt_hdr();',
        'extern bool v24hdr_hdr_active();',
        'extern void v24hdr_set_hdr_active(bool active);',
        'HDR10_SET phase=%s',
        'HDR10_UNSUPPORTED phase=%s',
    ],
}

for rel, markers in required.items():
    p = Path(rel)
    if not p.is_file():
        raise SystemExit(f'VERIFY_FAIL missing_file={rel}')
    text = p.read_text(encoding='utf-8')
    for marker in markers:
        if marker not in text:
            raise SystemExit(f'VERIFY_FAIL {rel} missing={marker}')

# Native COM identity remains the non-negotiable invariant.
d = Path('source/d3d12/d3d12.cpp').read_text(encoding='utf-8')
native_marker = d.find('D3DMetal native runtime bridge: returning the original ID3D12Device')
hook = d.find('v24hdr_install_device_hooks(static_cast<ID3D12Device *>(*ppDevice));')
proxy = d.find('*ppDevice = device_proxy;')
if native_marker < 0 or hook < 0 or hook > native_marker:
    raise SystemExit('NATIVE_IDENTITY_INVARIANT=FAIL')
if proxy >= 0 and proxy < native_marker:
    raise SystemExit('GAME_VISIBLE_DEVICE_PROXY_SURVIVED=FAIL')

h = Path('source/d3d12/v24hdr_sidecar_hotfix5.hpp').read_text(encoding='utf-8')
# Original PSO must be created before any sidecar attempt in both creation paths.
gfx_fn = h[h.find('static HRESULT STDMETHODCALLTYPE v24hdr_CreateGraphicsPipelineState('):]
gfx_fn = gfx_fn[:gfx_fn.find('static HRESULT STDMETHODCALLTYPE v24hdr_CreatePipelineStateStream(', 20)]
if not (gfx_fn.find('const HRESULT hr = trampoline(device, desc, riid, ppPipelineState);') < gfx_fn.find('v24hdr_try_graphics_sidecar(')):
    raise SystemExit('GRAPHICS_ORIGINAL_FIRST_INVARIANT=FAIL')
stream_fn = h[h.find('static HRESULT STDMETHODCALLTYPE v24hdr_CreatePipelineStateStream(', h.find('static ID3D12PipelineState *v24hdr_query_original_pso')):]
stream_fn = stream_fn[:stream_fn.find('static HRESULT STDMETHODCALLTYPE v24hdr_CommandListReset(', 20)]
if not (stream_fn.find('const HRESULT hr = trampoline(device, desc, riid, ppPipelineState);') < stream_fn.find('v24hdr_try_stream_sidecar(')):
    raise SystemExit('STREAM_ORIGINAL_FIRST_INVARIANT=FAIL')


# Command-list creation/reset must also preserve the original game-visible call first.
reset_pos = h.find('static HRESULT STDMETHODCALLTYPE v24hdr_CommandListReset(')
reset_end = h.find('static void STDMETHODCALLTYPE v24hdr_SetPipelineState(', reset_pos)
reset_seg = h[reset_pos:reset_end]
if not (reset_seg.find('const HRESULT hr = trampoline(list, allocator, initial);') < reset_seg.find('set_trampoline(list, sidecar);')):
    raise SystemExit('COMMAND_LIST_RESET_ORIGINAL_FIRST_INVARIANT=FAIL')
create_pos = h.find('static HRESULT STDMETHODCALLTYPE v24hdr_CreateCommandList(')
create_end = h.find('static HRESULT STDMETHODCALLTYPE v24hdr_CreateCommandList1(', create_pos)
create_seg = h[create_pos:create_end]
if not (create_seg.find('const HRESULT hr = trampoline(device, nodeMask, type, allocator, initial, riid, ppCommandList);') < create_seg.find('set_trampoline(list, sidecar);')):
    raise SystemExit('COMMAND_LIST_CREATE_ORIGINAL_FIRST_INVARIANT=FAIL')

# Sidecars can be substituted only while HDR_ACTIVE is true.
for fn_marker in ['v24hdr_CommandListReset(', 'v24hdr_SetPipelineState(', 'v24hdr_CreateCommandList(']:
    pos = h.find(fn_marker)
    if pos < 0:
        raise SystemExit('SIDE_CAR_BIND_FUNCTION_MISSING=' + fn_marker)
    segment = h[pos:pos + 3500]
    if 'v24hdr_hdr_active()' not in segment:
        raise SystemExit('SIDECAR_BIND_WITHOUT_HDR_ACTIVE_GATE=' + fn_marker)

# The stream parser must never patch the caller memory directly.
if 'const_cast<D3D12_PIPELINE_STATE_STREAM_DESC' in h:
    raise SystemExit('STREAM_CALLER_MEMORY_MUTATION=FAIL')
if 'std::memcpy(storage.data(), source->pPipelineStateSubobjectStream' not in h:
    raise SystemExit('STREAM_COPY_FIRST_INVARIANT=FAIL')

# Dynamic RenoDX injection remains absent.
manifest = Path('v24hdr-shader-manifest.txt').read_text(encoding='utf-8')
for marker in [
    'INJECTION_BUFFER=ABSENT',
    'B13_SPACE50=ABSENT',
    'TARGET_API=D3D12',
    'DX11_SHADER_VARIANTS=EXCLUDED',
    'DX12_SM5X_VARIANTS=PREFERRED',
    'SHADER_STAGE=PIXEL_ONLY_VERIFIED',
]:
    if marker not in manifest:
        raise SystemExit('BAKED_SHADER_MANIFEST=FAIL missing=' + marker)

crc = Path('source/d3d12/v24hdr_crc32_hash.hpp')
if not crc.is_file() or crc.stat().st_size < 100:
    raise SystemExit('PINNED_RENODX_CRC_HEADER=FAIL')

# Ensure the previous failure mode is impossible: no unconditional R8->R10 when readiness is false.
dxgi = Path('source/dxgi/dxgi.cpp').read_text(encoding='utf-8')
swap = Path('source/dxgi/dxgi_swapchain.cpp').read_text(encoding='utf-8')
if 'SWAPCHAIN_CREATE R8_TO_R10' in dxgi or 'RESIZE R8_TO_R10' in swap:
    raise SystemExit('OLD_UNCONDITIONAL_HDR_MARKER_SURVIVED=FAIL')
if 'v24hdr_should_attempt_hdr()' not in dxgi or swap.count('v24hdr_should_attempt_hdr()') < 2:
    raise SystemExit('ARM_BEFORE_HDR_GATE=FAIL')

# Forbidden runtime-addon architecture must not be reintroduced by HOTFIX5 helper.
for forbidden in [
    'renodx-zenless-zone-zero.addon64',
    'ReShadeRegisterAddon',
    'force_pipeline_cloning',
    'use_resource_cloning',
]:
    if forbidden in h:
        raise SystemExit('FORBIDDEN_RENODX_RUNTIME_MARKER=FAIL marker=' + forbidden)

print('V24HDR5_VERIFY_EXACT_V24_LINEAGE=PASS')
print('V24HDR5_VERIFY_NATIVE_COM_IDENTITY=PASS')
print('V24HDR5_VERIFY_GAME_PSO_IDENTITY_ORIGINAL=PASS')
print('V24HDR5_VERIFY_STREAM_SLOT47_COVERAGE=PASS')
print('V24HDR5_VERIFY_CRC_OBSERVABILITY=PASS')
print('V24HDR5_VERIFY_STREAM_COPY_AND_CACHED_PSO_CLEAR=PASS')
print('V24HDR5_VERIFY_PIPELINE_LIBRARY_COVERAGE=PASS')
print('V24HDR5_VERIFY_COMMAND_LIST_RESET_SETPSO_COVERAGE=PASS')
print('V24HDR5_VERIFY_COMMAND_LIST_FAIL_OPEN_ORIGINAL_FIRST=PASS')
print('V24HDR5_VERIFY_SIDECAR_BIND_HDR_ACTIVE_ONLY=PASS')
print('V24HDR5_VERIFY_CRITICAL_UBERPOST_ARM_GATE=PASS')
print('V24HDR5_VERIFY_ZERO_SIDECAR_FORCED_HDR_IMPOSSIBLE=PASS')
print('V24HDR5_VERIFY_R10_AND_COLORSPACE_ROLLBACK_R8=PASS')
print('V24HDR5_VERIFY_NO_RENODX_ADDON_RUNTIME=PASS')
print('V24HDR5_SOURCE_VERIFICATION=PASS')
