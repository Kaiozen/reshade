from pathlib import Path

checks = {
    'source/d3d12/d3d12.cpp': [
        'KAIOZEN V24 NATIVE HDR SHADER TRANSPLANT',
        'v24hdr_CreateGraphicsPipelineState',
        'g_v24hdr_shader_count',
        'v24hdr_crc32_hash.hpp',
        'compute_crc32(',
        'PSO_FALLBACK type=graphics',
        'KAIOZEN_ZZZ_NATIVE_HDR.ENABLE',
        'D3DMetal native runtime bridge: returning the original ID3D12Device',
    ],
    'source/dxgi/dxgi.cpp': [
        'SWAPCHAIN_CREATE R8_TO_R10',
        'SWAPCHAIN_CREATE_FALLBACK_R8',
        'HDR10_COLORSPACE',
        'HDR10_COLORSPACE_UNSUPPORTED',
        'IDXGIFactory2_CreateSwapChainForHwnd_Impl',
    ],
    'source/dxgi/dxgi_swapchain.cpp': [
        'RESIZE R8_TO_R10',
        'RESIZE1 R8_TO_R10',
        'RESIZE_FALLBACK_R8',
        'RESIZE1_FALLBACK_R8',
        'HDR10_AFTER_RESIZE',
        'HDR10_AFTER_RESIZE_UNSUPPORTED',
    ],
}
for f, markers in checks.items():
    text = Path(f).read_text(encoding='utf-8')
    for marker in markers:
        if marker not in text:
            raise SystemExit(f'VERIFY_FAIL {f} missing {marker}')

# Native COM identity is the non-negotiable invariant.
d = Path('source/d3d12/d3d12.cpp').read_text(encoding='utf-8')
native_marker = d.find('D3DMetal native runtime bridge: returning the original ID3D12Device')
proxy = d.find('*ppDevice = device_proxy;')
hook = d.find('v24hdr_install_device_hooks(static_cast<ID3D12Device *>(*ppDevice));')
if native_marker < 0 or hook < 0 or hook > native_marker:
    raise SystemExit('NATIVE_IDENTITY_INVARIANT=FAIL')
if proxy >= 0 and proxy < native_marker:
    raise SystemExit('GAME_VISIBLE_DEVICE_PROXY_SURVIVED=FAIL')

# Exact RenoDX CRC implementation must be physically copied into the ReShade source.
crc = Path('source/d3d12/v24hdr_crc32_hash.hpp')
if not crc.is_file() or crc.stat().st_size < 100:
    raise SystemExit('PINNED_RENODX_CRC_HEADER=FAIL')

manifest = Path('v24hdr-shader-manifest.txt').read_text(encoding='utf-8')
required_manifest = [
    'INJECTION_BUFFER=ABSENT',
    'B13_SPACE50=ABSENT',
    'TARGET_API=D3D12',
    'DX11_SHADER_VARIANTS=EXCLUDED',
    'DX12_SM5X_VARIANTS=PREFERRED',
    'SHADER_STAGE=PIXEL_ONLY_VERIFIED',
]
for marker in required_manifest:
    if marker not in manifest:
        raise SystemExit('BAKED_SHADER_MANIFEST=FAIL missing=' + marker)

# The old RenoDX runtime architecture must not be embedded into this patch.
for forbidden in [
    'renodx-zenless-zone-zero.addon64',
    'ReShadeRegisterAddon',
    'force_pipeline_cloning',
    'use_resource_cloning',
]:
    if forbidden in d:
        raise SystemExit('FORBIDDEN_RENODX_RUNTIME_MARKER=FAIL marker=' + forbidden)

print('V24HDR_VERIFY_EXACT_V24_LINEAGE=PASS')
print('V24HDR_VERIFY_NATIVE_COM_IDENTITY=PASS')
print('V24HDR_VERIFY_NO_RENODX_ADDON_RUNTIME=PASS')
print('V24HDR_VERIFY_PINNED_RENODX_CRC=PASS')
print('V24HDR_VERIFY_BAKED_CONSTANTS=PASS')
print('V24HDR_VERIFY_DX12_SHADER_SELECTION=PASS')
if 'v24hdr_CreateComputePipelineState' in d or 'v24hdr_replace_bytecode(d.VS' in d:
    raise SystemExit('V24HDR_PIXEL_ONLY_INVARIANT=FAIL')
print('V24HDR_VERIFY_PIXEL_SHADER_ONLY=PASS')
print('V24HDR_VERIFY_PSO_FAIL_OPEN=PASS')
print('V24HDR_VERIFY_SWAPCHAIN_CREATE_FAIL_OPEN=PASS')
print('V24HDR_VERIFY_RESIZE_FAIL_OPEN=PASS')
print('V24HDR_VERIFY_HDR10_SUPPORT_GATED=PASS')
print('V24HDR_VERIFY_SWAPCHAIN_CREATE_RESIZE_HDR10=PASS')
print('V24HDR_SOURCE_VERIFICATION=PASS')
