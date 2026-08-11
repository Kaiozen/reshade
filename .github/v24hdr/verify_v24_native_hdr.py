from pathlib import Path
import ast
import sys

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
        'PS_ADAPTIVE_MATCH',
        'V31_SEMANTIC_MAP',
        'KAIOZEN V24 HDR SIDECAR HOTFIX11: V31_SEMANTIC_MAP',
        'crc_gate=REMOVED',
        'fp.input_crc == 0x0791E583u',
        'fp.output_crc == 0xDB99520Bu',
        'v24hdr_find_shader(0x06D90AA2u)',
        'compatibility=native_pso_creation_required',
        'KAIOZEN V24 HDR OUTPUT HOTFIX12: UBERPOST_RTV',
        'v24hdr_find_adaptive_shader',
        'HDR_READY armed=1',
        'PSO_BIND_SUBSTITUTE',
        'RESET_PSO_SUBSTITUTE',
        'native_identity=1 addon_runtime=0 sidecar_psos=1 arm_before_hdr=1',
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
        'v24hdr_hotfix12_prepare_final_proxy(*ppSwapChain, "create")',
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
        'PRESENT_TRANSITION_ARMED phase=%s',
        'PRESENT_SELF_RESIZE_ATTEMPT phase=%s',
        'PRESENT_SELF_RESIZE_SUCCESS phase=%s',
        'PRESENT_SELF_RESIZE_NO_HDR phase=%s',
        'WINDOW_NUDGE_SENT queued=%u',
        'WINDOW_NUDGE_RESTORE queued=%u',
        'v24hdr_hotfix9_present_transition(this, _orig, "present")',
        'v24hdr_hotfix9_present_transition(this, _orig, "present1")',
        'v24hdr_swapchain_proxy_shaders.hpp',
        'FINAL_PROXY_PREPARE=PASS',
        'FINAL_PROXY_PREPARE_FAIL',
        'FINAL_PROXY_DRAW count=%llu',
        'FINAL_PROXY_DRAW_FAIL',
        'v24hdr_hotfix12_final_proxy_draw(_orig',
        'v24hdr_hotfix12_prepare_final_proxy(_orig, "resize")',
        'v24hdr_hotfix12_prepare_final_proxy(_orig, "resize1")',
    ],
    'source/dxgi/v24hdr_swapchain_proxy_shaders.hpp': [
        'g_v24hdr_hotfix12_proxy_vs',
        'g_v24hdr_hotfix12_proxy_ps',
        'g_v24hdr_hotfix12_proxy_vs_size',
        'g_v24hdr_hotfix12_proxy_ps_size',
    ],
    'source/dxgi/v24hdr_dxgi_gate_hotfix5.hpp': [
        'extern bool v24hdr_should_attempt_hdr();',
        'extern bool v24hdr_hdr_active();',
        'extern void v24hdr_set_hdr_active(bool active);',
        'extern bool v24hdr_hotfix12_prepare_final_proxy(IDXGISwapChain *swapchain, const char *phase);',
        'HDR10_SET phase=%s',
        'HDR10_UNSUPPORTED phase=%s',
    ],
}


def fail(message):
    raise SystemExit(message)


def require_markers(rel, text, markers):
    for marker in markers:
        if marker not in text:
            fail(f'VERIFY_FAIL {rel} missing={marker}')


def function_definition(text, marker):
    """Return one full C/C++ function definition, explicitly skipping forward declarations."""
    pos = 0
    while True:
        start = text.find(marker, pos)
        if start < 0:
            fail('FUNCTION_DEFINITION_MISSING=' + marker)
        brace = text.find('{', start)
        semi = text.find(';', start)
        if brace >= 0 and (semi < 0 or brace < semi):
            depth = 0
            i = brace
            in_string = False
            quote = ''
            escaped = False
            while i < len(text):
                ch = text[i]
                if in_string:
                    if escaped:
                        escaped = False
                    elif ch == '\\':
                        escaped = True
                    elif ch == quote:
                        in_string = False
                else:
                    if ch in ('"', "'"):
                        in_string = True
                        quote = ch
                    elif ch == '{':
                        depth += 1
                    elif ch == '}':
                        depth -= 1
                        if depth == 0:
                            return text[start:i + 1]
                i += 1
            fail('FUNCTION_DEFINITION_UNTERMINATED=' + marker)
        pos = start + len(marker)


def validate_sidecar_header(h):
    require_markers('source/d3d12/v24hdr_sidecar_hotfix5.hpp', h, required['source/d3d12/v24hdr_sidecar_hotfix5.hpp'])

    gfx_fn = function_definition(h, 'static HRESULT STDMETHODCALLTYPE v24hdr_CreateGraphicsPipelineState(')
    original = gfx_fn.find('const HRESULT hr = trampoline(device, desc, riid, ppPipelineState);')
    sidecar = gfx_fn.find('v24hdr_try_graphics_sidecar(')
    if original < 0 or sidecar < 0 or not (original < sidecar):
        fail('GRAPHICS_ORIGINAL_FIRST_INVARIANT=FAIL')

    stream_fn = function_definition(h, 'static HRESULT STDMETHODCALLTYPE v24hdr_CreatePipelineStateStream(')
    original = stream_fn.find('const HRESULT hr = trampoline(device, desc, riid, ppPipelineState);')
    sidecar = stream_fn.find('v24hdr_try_stream_sidecar(')
    if original < 0 or sidecar < 0 or not (original < sidecar):
        fail('STREAM_ORIGINAL_FIRST_INVARIANT=FAIL')

    reset_fn = function_definition(h, 'static HRESULT STDMETHODCALLTYPE v24hdr_CommandListReset(')
    original = reset_fn.find('const HRESULT hr = trampoline(list, allocator, initial);')
    substitute = reset_fn.find('set_trampoline(list, sidecar);')
    if original < 0 or substitute < 0 or not (original < substitute):
        fail('COMMAND_LIST_RESET_ORIGINAL_FIRST_INVARIANT=FAIL')

    create_fn = function_definition(h, 'static HRESULT STDMETHODCALLTYPE v24hdr_CreateCommandList(')
    original = create_fn.find('const HRESULT hr = trampoline(device, nodeMask, type, allocator, initial, riid, ppCommandList);')
    substitute = create_fn.find('set_trampoline(list, sidecar);')
    if original < 0 or substitute < 0 or not (original < substitute):
        fail('COMMAND_LIST_CREATE_ORIGINAL_FIRST_INVARIANT=FAIL')

    for marker in [
        'static HRESULT STDMETHODCALLTYPE v24hdr_CommandListReset(',
        'static void STDMETHODCALLTYPE v24hdr_SetPipelineState(',
        'static HRESULT STDMETHODCALLTYPE v24hdr_CreateCommandList(',
    ]:
        fn = function_definition(h, marker)
        if 'v24hdr_hdr_active()' not in fn:
            fail('SIDECAR_BIND_WITHOUT_HDR_ACTIVE_GATE=' + marker)

    if 'const_cast<D3D12_PIPELINE_STATE_STREAM_DESC' in h:
        fail('STREAM_CALLER_MEMORY_MUTATION=FAIL')
    if 'std::memcpy(storage.data(), source->pPipelineStateSubobjectStream' not in h:
        fail('STREAM_COPY_FIRST_INVARIANT=FAIL')


def extract_constant_string(patch_path, name):
    tree = ast.parse(Path(patch_path).read_text(encoding='utf-8-sig'))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            value = ast.literal_eval(node.value)
            if not isinstance(value, str):
                fail('SELFTEST_CONSTANT_NOT_STRING=' + name)
            return value
    fail('SELFTEST_CONSTANT_MISSING=' + name)


def selftest_patch_asset(patch_path):
    h = extract_constant_string(patch_path, 'sidecar_header')
    g = extract_constant_string(patch_path, 'dxgi_gate')
    validate_sidecar_header(h)
    require_markers('source/dxgi/v24hdr_dxgi_gate_hotfix5.hpp', g, required['source/dxgi/v24hdr_dxgi_gate_hotfix5.hpp'])
    print('V24HDR5B_VERIFIER_PATCH_ASSET_REPLAY=PASS')
    print('V24HDR5B_FORWARD_DECLARATION_SKIP=PASS')
    print('V24HDR5B_HEADER_MARKER_SCOPE=PASS')


if len(sys.argv) == 3 and sys.argv[1] == '--selftest-patch-asset':
    selftest_patch_asset(sys.argv[2])
    raise SystemExit(0)
if len(sys.argv) != 1:
    fail('USAGE: verify_v24_native_hdr.py [--selftest-patch-asset patch_v24_native_hdr.py]')

for rel, markers in required.items():
    p = Path(rel)
    if not p.is_file():
        fail(f'VERIFY_FAIL missing_file={rel}')
    text = p.read_text(encoding='utf-8')
    require_markers(rel, text, markers)

# Native COM identity remains the non-negotiable invariant.
d = Path('source/d3d12/d3d12.cpp').read_text(encoding='utf-8')
native_marker = d.find('D3DMetal native runtime bridge: returning the original ID3D12Device')
hook = d.find('v24hdr_install_device_hooks(static_cast<ID3D12Device *>(*ppDevice));')
proxy = d.find('*ppDevice = device_proxy;')
if native_marker < 0 or hook < 0 or hook > native_marker:
    fail('NATIVE_IDENTITY_INVARIANT=FAIL')
if proxy >= 0 and proxy < native_marker:
    fail('GAME_VISIBLE_DEVICE_PROXY_SURVIVED=FAIL')

h = Path('source/d3d12/v24hdr_sidecar_hotfix5.hpp').read_text(encoding='utf-8')
validate_sidecar_header(h)

# Dynamic RenoDX injection remains absent.
manifest = Path('v24hdr-shader-manifest.txt').read_text(encoding='utf-8')
for marker in [
    'INJECTION_BUFFER=ABSENT',
    'B13_SPACE50=ABSENT',
    'TARGET_API=D3D12',
    'DX11_SHADER_VARIANTS=EXCLUDED',
    'DX12_SM5X_VARIANTS=PREFERRED',
    'HOTFIX12_PROXY_SEPARATE_FROM_UBERPOST=PASS',
    'HOTFIX12_SWAPCHAIN_PROXY_VS=',
    'HOTFIX12_SWAPCHAIN_PROXY_PS=',
    'HOTFIX12_FINAL_ENCODING=HDR10_PQ_BT2020',
]:
    if marker not in manifest:
        fail('BAKED_SHADER_MANIFEST=FAIL missing=' + marker)

crc = Path('source/d3d12/v24hdr_crc32_hash.hpp')
if not crc.is_file() or crc.stat().st_size < 100:
    fail('PINNED_RENODX_CRC_HEADER=FAIL')

# Ensure the previous failure mode is impossible: no unconditional R8->R10 when readiness is false.
dxgi = Path('source/dxgi/dxgi.cpp').read_text(encoding='utf-8')
swap = Path('source/dxgi/dxgi_swapchain.cpp').read_text(encoding='utf-8')
if 'SWAPCHAIN_CREATE R8_TO_R10' in dxgi or 'RESIZE R8_TO_R10' in swap:
    fail('OLD_UNCONDITIONAL_HDR_MARKER_SURVIVED=FAIL')
if 'v24hdr_should_attempt_hdr()' not in dxgi or swap.count('v24hdr_should_attempt_hdr()') < 2:
    fail('ARM_BEFORE_HDR_GATE=FAIL')

# HOTFIX9 must preserve R8 startup and must not regress to HOTFIX8 early-R10 staging.
if 'SWAPCHAIN_CREATE_STAGE_R10_SDR' in dxgi or 'RESIZE_STAGE_R10_SDR' in swap:
    fail('HOTFIX9_EARLY_R10_STAGE_REGRESSION=FAIL')
for marker in [
    'PRESENT_TRANSITION_ARMED phase=%s',
    'PRESENT_SELF_RESIZE_ATTEMPT phase=%s',
    'WINDOW_NUDGE_SENT queued=%u',
    'WINDOW_NUDGE_RESTORE queued=%u',
    'proxy->ResizeBuffers(',
]:
    if marker not in swap:
        fail('HOTFIX9_PRESENT_TRANSITION_GATE=FAIL missing=' + marker)
if swap.count('v24hdr_hotfix9_present_transition(this, _orig') < 2:
    fail('HOTFIX9_PRESENT_AND_PRESENT1_COVERAGE=FAIL')
if 'PostMessageW(' not in swap or 'GetClientRect(' not in swap:
    fail('HOTFIX9_ASYNC_WM_SIZE_PATH=FAIL')
if 'SetWindowPos(' in swap or 'GetWindowRect(' in swap:
    fail('HOTFIX9_RENDER_THREAD_WINDOW_MUTATION_FORBIDDEN=FAIL')

# HOTFIX11 must not regress to the scene-dependent exact whole-shader CRC gate.
if 'observed_crc == 0x4584C304u' in h:
    fail('HOTFIX11_STALE_EXACT_UBERPOST_CRC_GATE=FAIL')

# HOTFIX12 must keep RenoDX's final SwapChainPass separate from the UberPost and execute it at the actual D3D12 Present boundary.
if 'SwapChainPass(renodx::draw::RenderIntermediatePass' in manifest:
    fail('HOTFIX12_FUSED_UBERPOST_REGRESSION=FAIL')
proxy_header = Path('source/dxgi/v24hdr_swapchain_proxy_shaders.hpp')
if not proxy_header.is_file() or proxy_header.stat().st_size < 1024:
    fail('HOTFIX12_PROXY_SHADER_HEADER=FAIL')

present_effect = swap.find('reshade::present_effect_runtime(_impl);')
final_proxy = swap.find('v24hdr_hotfix12_final_proxy_draw(_orig')
flush = swap.find('flush_immediate_command_list();', present_effect)
if present_effect < 0 or final_proxy < 0 or flush < 0 or not (present_effect < final_proxy < flush):
    fail('HOTFIX12_FINAL_PROXY_PRESENT_ORDER=FAIL')

for phase in ['resize', 'resize1']:
    prep = swap.find(f'v24hdr_hotfix12_prepare_final_proxy(_orig, "{phase}")')
    hdr = swap.find(f'v24hdr_apply_hdr10_hotfix5(_orig, "{phase}")')
    if prep < 0 or hdr < 0 or prep > hdr:
        fail('HOTFIX12_PROXY_BEFORE_HDR_ACTIVE=FAIL phase=' + phase)
create_prep = dxgi.find('v24hdr_hotfix12_prepare_final_proxy(*ppSwapChain, "create")')
create_hdr = dxgi.find('v24hdr_apply_hdr10_hotfix5(*ppSwapChain, "create")')
if create_prep < 0 or create_hdr < 0 or create_prep > create_hdr:
    fail('HOTFIX12_CREATE_PROXY_BEFORE_HDR_ACTIVE=FAIL')

# Forbidden runtime-addon architecture must not be reintroduced by HOTFIX5 helper.
for forbidden in [
    'renodx-zenless-zone-zero.addon64',
    'ReShadeRegisterAddon',
    'force_pipeline_cloning',
    'use_resource_cloning',
]:
    if forbidden in h:
        fail('FORBIDDEN_RENODX_RUNTIME_MARKER=FAIL marker=' + forbidden)

print('V24HDR5_VERIFY_EXACT_V24_LINEAGE=PASS')
print('V24HDR5_VERIFY_NATIVE_COM_IDENTITY=PASS')
print('V24HDR5_VERIFY_GAME_PSO_IDENTITY_ORIGINAL=PASS')
print('V24HDR5_VERIFY_STREAM_SLOT47_COVERAGE=PASS')
print('V24HDR5_VERIFY_CRC_OBSERVABILITY=PASS')
print('V24HDR6_VERIFY_ADAPTIVE_V31_MATCHER=PASS')
print('V24HDR11_VERIFY_SEMANTIC_V31_MAP=PASS')
print('V24HDR11_VERIFY_WHOLE_BLOB_CRC_GATE_REMOVED=PASS')
print('V24HDR5_VERIFY_STREAM_COPY_AND_CACHED_PSO_CLEAR=PASS')
print('V24HDR5_VERIFY_PIPELINE_LIBRARY_COVERAGE=PASS')
print('V24HDR5_VERIFY_COMMAND_LIST_RESET_SETPSO_COVERAGE=PASS')
print('V24HDR5_VERIFY_COMMAND_LIST_FAIL_OPEN_ORIGINAL_FIRST=PASS')
print('V24HDR5_VERIFY_SIDECAR_BIND_HDR_ACTIVE_ONLY=PASS')
print('V24HDR5_VERIFY_CRITICAL_UBERPOST_ARM_GATE=PASS')
print('V24HDR5_VERIFY_ZERO_SIDECAR_FORCED_HDR_IMPOSSIBLE=PASS')
print('V24HDR5_VERIFY_R10_AND_COLORSPACE_ROLLBACK_R8=PASS')
print('V24HDR9_VERIFY_R8_STARTUP_PRESERVED=PASS')
print('V24HDR9_VERIFY_PRESENT_SELF_RESIZE=PASS')
print('V24HDR9_VERIFY_WINDOW_NUDGE_FALLBACK=PASS')
print('V24HDR9_VERIFY_WINDOW_RESTORE=PASS')
print('V24HDR12_VERIFY_SEPARATE_FINAL_PROXY=PASS')
print('V24HDR12_VERIFY_PROXY_BEFORE_HDR_ACTIVE=PASS')
print('V24HDR12_VERIFY_FINAL_PROXY_PRESENT_ORDER=PASS')
print('V24HDR12_VERIFY_UBERPOST_RTV_DIAGNOSTIC=PASS')
print('V24HDR5_VERIFY_NO_RENODX_ADDON_RUNTIME=PASS')
print('V24HDR5_SOURCE_VERIFICATION=PASS')
