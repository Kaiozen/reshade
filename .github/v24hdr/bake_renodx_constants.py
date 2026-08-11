from pathlib import Path
import sys
import re

p = Path(sys.argv[1])
s = p.read_text(encoding='utf-8-sig')
start = s.find('#ifndef __cplusplus\n')
end = s.find('#define RENODX_RENO_DRT_TONE_MAP_METHOD', start)
if start < 0 or end < 0:
    raise SystemExit('RENODX_BAKE_SHARED_ANCHOR=FAIL')
old = s[start:end]
for x in [
    'cbuffer injected_buffer : register(b13, space50)',
    'cbuffer injected_buffer : register(b13)',
    '#define RENODX_PEAK_NITS',
    '#define RENODX_SWAP_CHAIN_ENCODING',
]:
    if x not in old:
        raise SystemExit('RENODX_BAKE_REQUIRED_MARKER_MISSING=' + x)

new = '''#ifndef __cplusplus
// KAIOZEN D3DMetal native shader transplant: values are baked so replacement
// shaders require no dynamic injection binding and no pipeline-layout mutation.
#define RENODX_TONE_MAP_TYPE                   3.0f
#define RENODX_PEAK_NITS                       1000.0f
#define RENODX_GAME_NITS                       203.0f
#define RENODX_UI_NITS                         203.0f
#define RENODX_GAMMA_CORRECTION                1.0f
#define RENODX_TONE_MAP_HUE_PROCESSOR          0.0f
#define RENODX_TONE_MAP_HUE_CORRECTION         1.0f
#define RENODX_TONE_MAP_HUE_SHIFT              0.5f
#define RENODX_TONE_MAP_EXPOSURE               1.0f
#define RENODX_TONE_MAP_HIGHLIGHTS             1.0f
#define RENODX_TONE_MAP_SHADOWS                1.0f
#define RENODX_TONE_MAP_CONTRAST               1.0f
#define RENODX_TONE_MAP_SATURATION             1.0f
#define RENODX_TONE_MAP_HIGHLIGHT_SATURATION   1.0f
#define RENODX_TONE_MAP_BLOWOUT                0.0f
#define RENODX_TONE_MAP_FLARE                  0.0f
#define RENODX_INTERMEDIATE_ENCODING           renodx::draw::ENCODING_NONE
#define RENODX_SWAP_CHAIN_GAMMA_CORRECTION     RENODX_GAMMA_CORRECTION
#define RENODX_SWAP_CHAIN_CUSTOM_COLOR_SPACE   0.0f
#define RENODX_SWAP_CHAIN_CLAMP_COLOR_SPACE    1.0f
#define RENODX_SWAP_CHAIN_ENCODING             4.0f
#define RENODX_SWAP_CHAIN_ENCODING_COLOR_SPACE 1.0f
'''

s = s[:start] + new + s[end:]
p.write_text(s, encoding='utf-8', newline='\n')

check = p.read_text(encoding='utf-8')
if 'register(b13' in check or 'injectedData.' in check:
    raise SystemExit('RENODX_BAKE_INJECTION_SURVIVED_SHARED=FAIL')

# The pinned ZZZ source also has a tiny number of shaders that access three
# ShaderInjectData members directly instead of going through shared.h macros.
# Those must be baked too, otherwise removing b13/space50 leaves unresolved HLSL.
# Fail closed on exact occurrence counts so a source-shape change cannot be hidden.
game_dir = p.parent
field_bakes = {
    'injectedData.colorGradeLUTStrength': ('1.0f', 2),   # addon default 100% -> parsed 1.0
    'injectedData.colorGradeLUTScaling': ('1.0f', 2),  # addon default 100% -> parsed 1.0
    'injectedData.fxBloomIntensity': ('0.1f', 4),      # addon default 10%  -> parsed 0.1
}

shader_files = [
    f for f in game_dir.rglob('*')
    if f.is_file() and f.suffix.lower() in {'.h', '.hlsl'}
]

observed = {token: 0 for token in field_bakes}
for f in shader_files:
    text = f.read_text(encoding='utf-8-sig', errors='replace')
    # Count code only, not comments.
    code = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
    code = re.sub(r'//[^\r\n]*', '', code)
    for token in observed:
        observed[token] += code.count(token)

for token, (_, expected) in field_bakes.items():
    if observed[token] != expected:
        raise SystemExit(
            f'RENODX_BAKE_DIRECT_FIELD_COUNT=FAIL token={token} '
            f'observed={observed[token]} expected={expected}'
        )
print('RENODX_BAKE_DIRECT_FIELD_COUNTS=PASS')

rewritten = {token: 0 for token in field_bakes}
for f in shader_files:
    text = f.read_text(encoding='utf-8-sig', errors='replace')
    original = text
    for token, (literal, _) in field_bakes.items():
        c = text.count(token)
        if c:
            rewritten[token] += c
            text = text.replace(token, literal)
    if text != original:
        f.write_text(text, encoding='utf-8', newline='\n')

for token, (_, expected) in field_bakes.items():
    if rewritten[token] != expected:
        raise SystemExit(
            f'RENODX_BAKE_DIRECT_FIELD_REWRITE=FAIL token={token} '
            f'rewritten={rewritten[token]} expected={expected}'
        )
print('RENODX_BAKE_DIRECT_FIELD_REWRITE=PASS')

# Final whole-tree code scan. At this point there must be zero runtime injection
# object references, zero b13 injection buffer registrations and zero descriptor
# space 50 registrations anywhere in the pinned ZZZ HLSL/include tree.
bad = []
for f in shader_files:
    text = f.read_text(encoding='utf-8-sig', errors='replace')
    code = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
    code = re.sub(r'//[^\r\n]*', '', code)
    if (
        'injectedData.' in code or
        'register(b13' in code or
        re.search(r'register\s*\([^)]*\bspace50\b', code)
    ):
        bad.append(str(f))
if bad:
    raise SystemExit('RENODX_BAKE_DIRECT_INJECTION_DEPENDENCY=FAIL files=' + ';'.join(bad))

print('RENODX_BAKED_CONSTANTS=PASS')
print('RENODX_B13_SPACE50_REMOVED=PASS')
print('RENODX_DIRECT_INJECTION_DEPENDENCY_ABSENT=PASS')
print('RENODX_BAKED_LUT_STRENGTH=1.0')
print('RENODX_BAKED_LUT_SCALING=1.0')
print('RENODX_BAKED_BLOOM_INTENSITY=0.1')
print('RENODX_BAKED_HDR10=PASS')


# HOTFIX12: keep the critical UberPost faithful to RenoDX. RenderIntermediatePass
# remains in the game shader, while the exact RenoDX SwapChainPass executes later
# in a separate final swapchain-boundary proxy. Fusing these stages made downstream
# game passes consume PQ/BT.2020 data as if it were intermediate color and caused
# the cyan/magenta corruption seen exactly when HDR activated in HOTFIX11.
critical = game_dir / 'd3d12' / 'UberPosts' / 'uberpost_0x06D90AA2.ps_6_0.hlsl'
if not critical.is_file():
    raise SystemExit('HOTFIX12_CRITICAL_UBERPOST_SOURCE=FAIL missing=' + str(critical))
critical_text = critical.read_text(encoding='utf-8-sig')
intermediate = 'SV_Target.xyz = renodx::draw::RenderIntermediatePass(SV_Target.xyz);'
fused = 'renodx::draw::SwapChainPass(renodx::draw::RenderIntermediatePass'
if critical_text.count(intermediate) != 1:
    raise SystemExit(
        'HOTFIX12_CRITICAL_UBERPOST_INTERMEDIATE_ANCHOR=FAIL count=' +
        str(critical_text.count(intermediate))
    )
if fused in critical_text:
    raise SystemExit('HOTFIX12_FORBIDDEN_FUSED_SWAPCHAIN_PASS=FAIL')
print('HOTFIX12_CRITICAL_UBERPOST=0x06D90AA2')
print('HOTFIX12_CRITICAL_UBERPOST_INTERMEDIATE_ONLY=PASS')
print('HOTFIX12_FINAL_SWAPCHAIN_PROXY=SEPARATE')
print('HOTFIX12_FUSED_SWAPCHAIN_PASS=ABSENT')
